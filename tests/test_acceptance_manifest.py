import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts.build_acceptance_bundle import record_command, validate_release_manifest

FULL_COMMIT = "1" * 40
STARTED_AT = "2026-10-01T10:00:00Z"
ENDED_AT = "2026-10-01T10:05:00Z"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _valid_bundle(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    bundle = tmp_path / "v1" / FULL_COMMIT
    automated = bundle / "automated-tests"
    screenshots = bundle / "screenshots"
    screenshot_names = {
        "en": (
            "dashboard",
            "job-detail",
            "watch-list",
            "cv-library",
            "copilot-confirmation",
            "error",
        ),
        "zh": (
            "dashboard",
            "job-detail",
            "watch-list",
            "cv-library",
            "copilot-confirmation",
            "error",
        ),
        "narrow": ("dashboard", "job-detail", "copilot"),
    }
    for locale, names in screenshot_names.items():
        (screenshots / locale).mkdir(parents=True, exist_ok=True)
        for name in names:
            (screenshots / locale / f"chromium-{name}.png").write_bytes(b"synthetic-redacted-image")
    automated.mkdir(parents=True)
    (automated / "eval-summary.json").write_text(
        json.dumps({"passed": True, "zero_tolerance_failures": 0}), encoding="utf-8"
    )
    (automated / "pytest.xml").write_text("<testsuite failures='0'/>", encoding="utf-8")

    evidence_files = [
        path
        for path in bundle.rglob("*")
        if path.is_file() and path.name not in {"manifest.json", "summary.md"}
    ]
    commands = [
        {
            "name": name,
            "command": command,
            "exit_code": 0,
            "started_at": STARTED_AT,
            "ended_at": ENDED_AT,
        }
        for name, command in (
            ("ruff", "ruff check ."),
            ("format", "ruff format --check ."),
            ("pytest", "pytest --junitxml=... --cov --cov-report=xml:..."),
            ("e2e", "pytest tests/e2e --browser chromium --browser webkit"),
            ("accessibility", "node scripts/run_accessibility.mjs"),
            ("eval", "python -m app.evals.runner"),
        )
    ]
    manifest: dict[str, object] = {
        "schema_version": 1,
        "version": "v1",
        "git_commit": FULL_COMMIT,
        "dirty_worktree": False,
        "started_at": STARTED_AT,
        "ended_at": ENDED_AT,
        "runtime": {"os": "test-os", "python": "3.12.0"},
        "browsers": {"chromium": "test", "webkit": "test"},
        "model_id": "mocked-provider",
        "prompt_version": "career-fit-prompt-v2",
        "rubric_version": "career-fit-v2",
        "dataset_version": "v1",
        "commands": commands,
        "acceptance": [
            {
                "id": "REL-001",
                "requirement": "Fresh complete evidence",
                "preconditions": "Synthetic redacted seed",
                "steps": "Run required commands",
                "expected_result": "All gates pass",
                "automated_evidence": "automated-tests/pytest.xml",
                "visual_evidence": "screenshots/en/chromium-dashboard.png",
                "actual_result": "Passed",
                "status": "Pass",
                "tested_at": ENDED_AT,
                "environment": "test-os",
                "commit": FULL_COMMIT,
                "linked_defect": None,
                "must": True,
            }
        ],
        "open_defects": [],
        "hashes": {str(path.relative_to(bundle)): _sha256(path) for path in sorted(evidence_files)},
    }
    return bundle, manifest


@pytest.mark.parametrize(
    ("mutation", "expected_error"),
    [
        (
            lambda manifest, _bundle: manifest["commands"].pop(),
            "missing required command result: eval",
        ),
        (
            lambda manifest, _bundle: manifest.update(git_commit="2" * 40),
            "manifest commit does not match",
        ),
        (
            lambda manifest, _bundle: manifest.update(dirty_worktree=True),
            "dirty worktree",
        ),
        (
            lambda manifest, _bundle: manifest.update(started_at="2026-09-30T10:00:00Z"),
            "evidence timestamp was already used",
        ),
        (
            lambda _manifest, bundle: (
                bundle / "screenshots" / "en" / "chromium-watch-list.png"
            ).unlink(),
            "missing screenshot evidence: en/watch-list",
        ),
        (
            lambda _manifest, bundle: (bundle / "automated-tests" / "eval-summary.json").write_text(
                json.dumps({"passed": False, "zero_tolerance_failures": 1}), encoding="utf-8"
            ),
            "zero-tolerance Eval failure",
        ),
    ],
)
def test_release_gate_rejects_incomplete_or_stale_evidence(
    tmp_path: Path, mutation, expected_error: str
) -> None:
    bundle, manifest = _valid_bundle(tmp_path)
    mutated = copy.deepcopy(manifest)
    mutation(mutated, bundle)

    result = validate_release_manifest(
        mutated,
        bundle,
        expected_commit=FULL_COMMIT,
        used_started_at={"2026-09-30T10:00:00Z"},
    )

    assert result.release_ready is False
    assert expected_error in result.errors


def test_release_gate_accepts_complete_current_hashed_evidence(tmp_path: Path) -> None:
    bundle, manifest = _valid_bundle(tmp_path)

    result = validate_release_manifest(
        manifest,
        bundle,
        expected_commit=FULL_COMMIT,
        used_started_at=set(),
    )

    assert result.release_ready is True
    assert result.errors == ()


def test_command_recorder_persists_actual_exit_code_times_and_output(tmp_path: Path) -> None:
    result = record_command(
        source=tmp_path,
        name="focused",
        output_relative=Path("automated-tests/focused.txt"),
        command=["/bin/sh", "-c", "printf recorded-output; exit 3"],
        cwd=tmp_path,
    )

    assert result["exit_code"] == 3
    assert result["command"] == "/bin/sh -c 'printf recorded-output; exit 3'"
    assert result["started_at"].endswith("Z")
    assert result["ended_at"].endswith("Z")
    assert (tmp_path / "automated-tests" / "focused.txt").read_text() == "recorded-output"
    persisted = json.loads((tmp_path / "command-results.json").read_text())
    assert persisted == [result]


def test_command_recorder_writes_structured_json_when_requested(tmp_path: Path) -> None:
    result = record_command(
        source=tmp_path,
        name="e2e",
        output_relative=Path("automated-tests/e2e-results.json"),
        command=["/bin/sh", "-c", "printf browser-pass"],
        cwd=tmp_path,
    )

    report = json.loads((tmp_path / "automated-tests" / "e2e-results.json").read_text())
    assert report == {**result, "stdout": "browser-pass", "stderr": ""}
