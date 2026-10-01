import copy
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from scripts.build_acceptance_bundle import record_command, validate_release_manifest

FULL_COMMIT = "1" * 40
STARTED_AT = "2026-10-01T10:00:00Z"
ENDED_AT = "2026-10-01T10:06:00Z"


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "acceptance@example.invalid"], cwd=path, check=True
    )
    subprocess.run(["git", "config", "user.name", "Acceptance Test"], cwd=path, check=True)
    (path / "seed.txt").write_text("tracked", encoding="utf-8")
    subprocess.run(["git", "add", "seed.txt"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=path, check=True, capture_output=True)


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
        for browser in ("chromium", "webkit"):
            for name in names:
                (screenshots / locale / f"{browser}-{name}.png").write_bytes(
                    b"synthetic-redacted-image"
                )
    automated.mkdir(parents=True)
    (automated / "eval-summary.json").write_text(
        json.dumps(
            {
                "passed": True,
                "zero_tolerance_failures": 0,
                "dataset_version": "v1",
                "model_id": "mocked-provider",
                "prompt_version": "career-fit-prompt-v2",
                "grader_version": "career-fit-v2",
            }
        ),
        encoding="utf-8",
    )
    (automated / "eval-items.jsonl").write_text("{}\n", encoding="utf-8")
    (automated / "pytest.xml").write_text("<testsuite failures='0'/>", encoding="utf-8")
    (automated / "coverage.xml").write_text("<coverage />", encoding="utf-8")
    commands_data = (
        ("ruff", "ruff check .", ("automated-tests/ruff.txt",)),
        ("format", "ruff format --check .", ("automated-tests/format.txt",)),
        (
            "pytest",
            "pytest --junitxml=/tmp/bundle/automated-tests/pytest.xml --cov "
            "--cov-report=xml:/tmp/bundle/automated-tests/coverage.xml",
            (
                "automated-tests/pytest-command.txt",
                "automated-tests/pytest.xml",
                "automated-tests/coverage.xml",
            ),
        ),
        (
            "e2e",
            "pytest tests/e2e --browser chromium --browser webkit --tracing retain-on-failure "
            "--output=/tmp/bundle/browser-results",
            ("automated-tests/e2e-results.json",),
        ),
        (
            "accessibility",
            "node scripts/run_accessibility.mjs --base-url http://127.0.0.1:8501 "
            "--output /tmp/bundle/automated-tests/accessibility.json",
            ("automated-tests/accessibility-command.txt", "automated-tests/accessibility.json"),
        ),
        (
            "eval",
            "python -m app.evals.runner --dataset evals/datasets/v1.jsonl "
            "--output /tmp/bundle/automated-tests",
            (
                "automated-tests/eval-command.txt",
                "automated-tests/eval-summary.json",
                "automated-tests/eval-items.jsonl",
            ),
        ),
    )
    commands = []
    for index, (name, command, artifacts) in enumerate(commands_data):
        for relative_name in artifacts:
            path = bundle / relative_name
            if not path.exists():
                path.write_text(f"{name} evidence", encoding="utf-8")
        commands.append(
            {
                "name": name,
                "command": command,
                "exit_code": 0,
                "started_at": f"2026-10-01T10:0{index}:00Z",
                "ended_at": f"2026-10-01T10:0{index}:30Z",
                "output": artifacts[0],
                "git_commit": FULL_COMMIT,
                "dirty_worktree": False,
                "commit_time": "2026-10-01T09:00:00Z",
                "artifacts": list(artifacts),
            }
        )
    (bundle / "command-results.json").write_text(json.dumps(commands), encoding="utf-8")
    catalog = json.loads(Path("spec/acceptance-v1.json").read_text())["criteria"]
    acceptance = [
        {
            "id": criterion["id"],
            "requirement": f"Criterion {criterion['id']}",
            "preconditions": "Synthetic data",
            "steps": "Run evidence",
            "expected_result": "Pass",
            "automated_evidence": ["automated-tests/pytest.xml"],
            "visual_evidence": ["screenshots/en/chromium-dashboard.png"]
            if criterion["visual_required"]
            else [],
            "actual_result": "Passed",
            "status": "Pass",
            "tested_at": ENDED_AT,
            "environment": "test-os",
            "commit": FULL_COMMIT,
            "linked_defect": None,
            "must": True,
        }
        for criterion in catalog
    ]
    (bundle / "acceptance-results.json").write_text(json.dumps(acceptance), encoding="utf-8")
    evidence_files = [
        path
        for path in bundle.rglob("*")
        if path.is_file() and path.name not in {"manifest.json", "summary.md"}
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
        "acceptance": acceptance,
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
            "missing screenshot evidence: en/chromium-watch-list.png",
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
    _init_git_repo(tmp_path)
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
    _init_git_repo(tmp_path)
    result = record_command(
        source=tmp_path,
        name="e2e",
        output_relative=Path("automated-tests/e2e-results.json"),
        command=["/bin/sh", "-c", "printf browser-pass"],
        cwd=tmp_path,
    )

    report = json.loads((tmp_path / "automated-tests" / "e2e-results.json").read_text())
    assert report == {**result, "stdout": "browser-pass", "stderr": ""}


def test_release_gate_rejects_command_substitution_and_missing_provenance(tmp_path: Path) -> None:
    bundle, manifest = _valid_bundle(tmp_path)
    command = manifest["commands"][0]
    command["command"] = "true"
    command["git_commit"] = FULL_COMMIT
    command["dirty_worktree"] = False
    command["commit_time"] = "2026-10-01T09:00:00Z"

    result = validate_release_manifest(manifest, bundle, expected_commit=FULL_COMMIT)

    assert result.release_ready is False
    assert "non-canonical command: ruff" in result.errors


@pytest.mark.parametrize(
    ("field", "value", "expected_error"),
    [
        ("git_commit", "2" * 40, "command commit does not match: ruff"),
        ("dirty_worktree", True, "command ran with dirty worktree: ruff"),
    ],
)
def test_release_gate_rejects_per_command_commit_or_dirty_state(
    tmp_path: Path, field: str, value: object, expected_error: str
) -> None:
    bundle, manifest = _valid_bundle(tmp_path)
    for command in manifest["commands"]:
        command.update(
            git_commit=FULL_COMMIT,
            dirty_worktree=False,
            commit_time="2026-10-01T09:00:00Z",
        )
    manifest["commands"][0][field] = value

    result = validate_release_manifest(manifest, bundle, expected_commit=FULL_COMMIT)

    assert result.release_ready is False
    assert expected_error in result.errors


def test_release_gate_rejects_missing_hash_and_unexpected_file(tmp_path: Path) -> None:
    bundle, manifest = _valid_bundle(tmp_path)
    missing_key = next(iter(manifest["hashes"]))
    manifest["hashes"].pop(missing_key)
    unexpected = bundle / "copied-unreviewed.txt"
    unexpected.write_text("not part of the evidence contract", encoding="utf-8")

    result = validate_release_manifest(manifest, bundle, expected_commit=FULL_COMMIT)

    assert result.release_ready is False
    assert f"missing evidence hash: {missing_key}" in result.errors
    assert "unexpected evidence file: copied-unreviewed.txt" in result.errors


def test_release_gate_rejects_incomplete_acceptance_inventory(tmp_path: Path) -> None:
    bundle, manifest = _valid_bundle(tmp_path)
    manifest["acceptance"].pop(0)

    result = validate_release_manifest(manifest, bundle, expected_commit=FULL_COMMIT)

    assert result.release_ready is False
    assert any(error.startswith("missing Must acceptance ID:") for error in result.errors)


def test_release_gate_rejects_dataset_version_substitution(tmp_path: Path) -> None:
    bundle, manifest = _valid_bundle(tmp_path)
    manifest["dataset_version"] = "v2"

    result = validate_release_manifest(manifest, bundle, expected_commit=FULL_COMMIT)

    assert result.release_ready is False
    assert "Eval dataset version does not match manifest" in result.errors


def test_release_gate_rejects_copied_command_timestamps(tmp_path: Path) -> None:
    bundle, manifest = _valid_bundle(tmp_path)
    manifest["commands"][1]["started_at"] = manifest["commands"][0]["started_at"]

    result = validate_release_manifest(manifest, bundle, expected_commit=FULL_COMMIT)

    assert result.release_ready is False
    assert "copied command timestamp: format" in result.errors


def test_release_gate_rejects_wrong_command_output_path(tmp_path: Path) -> None:
    bundle, manifest = _valid_bundle(tmp_path)
    manifest["commands"][0]["output"] = "automated-tests/substituted.txt"

    result = validate_release_manifest(manifest, bundle, expected_commit=FULL_COMMIT)

    assert result.release_ready is False
    assert "command output path does not match: ruff" in result.errors


def test_release_gate_rejects_noncanonical_extra_test_filter(tmp_path: Path) -> None:
    bundle, manifest = _valid_bundle(tmp_path)
    manifest["commands"][2]["command"] += " -k no_tests"

    result = validate_release_manifest(manifest, bundle, expected_commit=FULL_COMMIT)

    assert result.release_ready is False
    assert "non-canonical command: pytest" in result.errors


def test_release_gate_rejects_command_outside_manifest_time_range(tmp_path: Path) -> None:
    bundle, manifest = _valid_bundle(tmp_path)
    manifest["commands"][0]["ended_at"] = "2026-10-01T10:07:00Z"

    result = validate_release_manifest(manifest, bundle, expected_commit=FULL_COMMIT)

    assert result.release_ready is False
    assert "command time outside evidence run: ruff" in result.errors


@pytest.mark.parametrize(
    ("mutation", "expected_error"),
    [
        (
            lambda acceptance: acceptance[0].pop("expected_result"),
            "acceptance fields missing:",
        ),
        (
            lambda acceptance: acceptance.append(copy.deepcopy(acceptance[0])),
            "duplicate acceptance ID",
        ),
    ],
)
def test_release_gate_rejects_invalid_acceptance_records(
    tmp_path: Path, mutation, expected_error: str
) -> None:
    bundle, manifest = _valid_bundle(tmp_path)
    mutation(manifest["acceptance"])

    result = validate_release_manifest(manifest, bundle, expected_commit=FULL_COMMIT)

    assert result.release_ready is False
    assert any(expected_error in error for error in result.errors)
