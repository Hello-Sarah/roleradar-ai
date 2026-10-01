import copy
import hashlib
import json
import os
import subprocess
import sys
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import scripts.build_acceptance_bundle as acceptance_bundle
from scripts.build_acceptance_bundle import (
    executable_identity,
    record_command,
    validate_release_manifest,
    write_acceptance_results,
)

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
                "item_count": 130,
                "suite_counts": {
                    "jd": 60,
                    "cv_pair": 20,
                    "copilot_normal": 30,
                    "copilot_adversarial": 20,
                },
                "suite_failures": {
                    "jd": 0,
                    "cv_pair": 0,
                    "copilot_normal": 0,
                    "copilot_adversarial": 0,
                },
            }
        ),
        encoding="utf-8",
    )
    eval_rows = [
        {
            "item_id": "jd-ai",
            "suite": "jd",
            "expected": {"classification_label": "Applied AI Engineer"},
            "output": {"action": None},
            "passed": True,
            "grader_results": [
                {"name": name, "passed": True}
                for name in (
                    "schema",
                    "score_stability",
                    "evidence_ids",
                    "critical_field_extraction",
                    "expected_label",
                )
            ],
        },
        {
            "item_id": "jd-pmo",
            "suite": "jd",
            "expected": {"classification_label": "Project Management"},
            "output": {"action": None},
            "passed": True,
            "grader_results": [
                {"name": "expected_label", "passed": True},
                {"name": "evidence_ids", "passed": True},
                {"name": "critical_field_extraction", "passed": True},
            ],
        },
        {
            "item_id": "cv",
            "suite": "cv_pair",
            "expected": {},
            "output": {"action": None},
            "passed": True,
            "grader_results": [
                {"name": "cv_factual_support", "passed": True},
                {"name": "docx_structure", "passed": True},
                {"name": "unsupported_claim_rejection", "passed": True},
            ],
        },
        {
            "item_id": "copilot-answer",
            "suite": "copilot_normal",
            "expected": {"action": "answer"},
            "output": {"action": "answer"},
            "passed": True,
            "grader_results": [
                {"name": "schema", "passed": True},
                {"name": "expected_label", "passed": True},
                {"name": "evidence_ids", "passed": True},
                {"name": "grounded_answer", "passed": True},
                {"name": "answer_language", "passed": True},
                {"name": "bilingual_parity", "passed": True},
            ],
        },
        {
            "item_id": "copilot-action",
            "suite": "copilot_normal",
            "expected": {"action": "save_job"},
            "output": {"action": "save_job"},
            "passed": True,
            "grader_results": [
                {"name": "schema", "passed": True},
                {"name": "expected_label", "passed": True},
                {"name": "write_counts", "passed": True},
            ],
        },
        {
            "item_id": "copilot-security",
            "suite": "copilot_adversarial",
            "expected": {"action": "refuse"},
            "output": {"action": "refuse"},
            "passed": True,
            "grader_results": [
                {"name": "schema", "passed": True},
                {"name": "expected_label", "passed": True},
                {"name": "write_counts", "passed": True},
            ],
        },
    ]
    expected_suite_counts = {
        "jd": 60,
        "cv_pair": 20,
        "copilot_normal": 30,
        "copilot_adversarial": 20,
    }
    templates = {
        suite: [row for row in eval_rows if row["suite"] == suite]
        for suite in expected_suite_counts
    }
    expanded_rows = list(eval_rows)
    for suite, expected_count in expected_suite_counts.items():
        current = [row for row in expanded_rows if row["suite"] == suite]
        for index in range(len(current), expected_count):
            row = copy.deepcopy(templates[suite][index % len(templates[suite])])
            row["item_id"] = f"{suite}-{index}"
            expanded_rows.append(row)
    eval_rows = expanded_rows
    (automated / "eval-items.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in eval_rows), encoding="utf-8"
    )
    (automated / "coverage.xml").write_text(
        '<coverage line-rate="0.87" lines-valid="100" lines-covered="87" />',
        encoding="utf-8",
    )
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
        command_parts = command.split()
        identity = executable_identity(command_parts[0], name=name)
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
                "executable": identity,
                "argv": command_parts[1:],
                "evidence_source": "/tmp/bundle",
                "stdout": "synthetic command output",
                "stderr": "",
            }
        )
    keyboard = {
        "all_controls_reached": True,
        "all_controls_named": True,
        "all_focus_visible": True,
    }
    (automated / "accessibility.json").write_text(
        json.dumps(
            {
                "passed": True,
                "streamlit_version": "1.62.0",
                "aa_failure_count": 0,
                "unresolved_incomplete_count": 0,
                "keyboard_failure_count": 0,
                "dynamic_keyboard_failure_count": 0,
                "missing_dynamic_states": [],
                "routes": [
                    {
                        "route": route,
                        "keyboard": keyboard,
                        "activation": {"passed": True},
                    }
                    for route in acceptance_bundle.EXPECTED_ACCESSIBILITY_ROUTES
                ],
                "dynamic_states": [
                    {
                        "state": state,
                        "keyboard": keyboard,
                        "activation": {"passed": True},
                    }
                    for state in acceptance_bundle.EXPECTED_DYNAMIC_STATES
                ],
            }
        ),
        encoding="utf-8",
    )
    (bundle / "command-results.json").write_text(json.dumps(commands), encoding="utf-8")
    catalog = json.loads(Path("spec/acceptance-v1.json").read_text())["criteria"]
    suite = ET.Element("testsuite", failures="0", errors="0")
    e2e_checks: list[str] = []
    for criterion in catalog:
        for check in [criterion["automated_check"], *criterion.get("additional_checks", [])]:
            if check["kind"] == "pytest":
                classname, name = check["name"].split("::", 1)
                ET.SubElement(suite, "testcase", classname=classname, name=name)
            if check["kind"] == "e2e":
                e2e_checks.append(check["name"])
    ET.ElementTree(suite).write(automated / "pytest.xml", encoding="unicode")
    browser_result = next(command for command in commands if command["name"] == "e2e")
    browser_result["stdout"] = "\n".join(
        f"{check}[{browser}] PASSED" for check in e2e_checks for browser in ("chromium", "webkit")
    )
    (automated / "e2e-results.json").write_text(json.dumps(browser_result), encoding="utf-8")
    (bundle / "command-results.json").write_text(json.dumps(commands), encoding="utf-8")
    acceptance_path = write_acceptance_results(
        source=bundle, commit=FULL_COMMIT, environment="test-os"
    )
    acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
    evidence_files = [
        path
        for path in bundle.rglob("*")
        if path.is_file() and path.name not in {"manifest.json", "summary.md"}
    ]
    manifest: dict[str, object] = {
        "schema_version": 2,
        "version": "v1",
        "git_commit": FULL_COMMIT,
        "dirty_worktree": False,
        "started_at": STARTED_AT,
        "ended_at": ENDED_AT,
        "runtime": {"os": "test-os", "python": "3.12.0", "streamlit": "1.62.0"},
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
    assert Path(result["executable"]["path"]).is_absolute()
    assert result["executable"]["sha256"]
    assert result["executable"]["version"]
    assert result["argv"] == ["-c", "printf recorded-output; exit 3"]
    assert result["evidence_source"] == str(tmp_path.resolve())
    assert (tmp_path / "automated-tests" / "focused.txt").read_text() == "recorded-output"
    persisted = json.loads((tmp_path / "command-results.json").read_text())
    assert persisted == [result]


def test_command_recorder_writes_structured_json_when_requested(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    result = record_command(
        source=tmp_path,
        name="focused-json",
        output_relative=Path("automated-tests/e2e-results.json"),
        command=["/bin/sh", "-c", "printf browser-pass"],
        cwd=tmp_path,
    )

    report = json.loads((tmp_path / "automated-tests" / "e2e-results.json").read_text())
    assert report == result


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


def test_release_gate_blocks_unreviewed_streamlit_runtime(tmp_path: Path) -> None:
    bundle, manifest = _valid_bundle(tmp_path)
    manifest["runtime"]["streamlit"] = "1.63.0"

    result = validate_release_manifest(manifest, bundle, expected_commit=FULL_COMMIT)

    assert result.release_ready is False
    assert "Streamlit runtime is not the reviewed version: 1.62.0" in result.errors


def test_project_reproduces_reviewed_streamlit_runtime_exactly() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert "streamlit==1.62.0" in project["project"]["dependencies"]


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


@pytest.mark.parametrize(
    ("command_name", "attacker_path"),
    [
        ("ruff", "/tmp/attacker/ruff"),
        ("pytest", "/tmp/attacker/pytest"),
        ("e2e", "/tmp/attacker/pytest"),
        ("accessibility", "/tmp/attacker/node"),
        ("eval", "/tmp/attacker/python"),
    ],
)
def test_release_gate_rejects_trusted_basename_from_untrusted_path(
    tmp_path: Path, command_name: str, attacker_path: str
) -> None:
    bundle, manifest = _valid_bundle(tmp_path)
    command = next(item for item in manifest["commands"] if item["name"] == command_name)
    parts = command["command"].split()
    parts[0] = attacker_path
    command["command"] = " ".join(parts)

    result = validate_release_manifest(manifest, bundle, expected_commit=FULL_COMMIT)

    assert result.release_ready is False
    assert f"untrusted executable: {command_name}" in result.errors


def test_release_gate_normalizes_the_approved_virtualenv_python_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle, manifest = _valid_bundle(tmp_path)
    eval_command = next(item for item in manifest["commands"] if item["name"] == "eval")
    virtualenv_bin = Path(sys.executable).parent
    monkeypatch.setenv("PATH", f"{virtualenv_bin}:{os.environ['PATH']}")
    eval_command["executable"] = executable_identity("python", name="eval")

    assert eval_command["executable"]["path"] == str(Path(sys.executable).absolute())
    result = validate_release_manifest(manifest, bundle, expected_commit=FULL_COMMIT)

    assert result.release_ready is True


def test_trusted_gate_executables_ignore_attacker_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    attacker = tmp_path / "attacker"
    attacker.mkdir()
    for name in ("ruff", "pytest", "node", "python", "python3"):
        path = attacker / name
        path.write_text("#!/bin/sh\necho attacker\n", encoding="utf-8")
        path.chmod(0o755)
    monkeypatch.setenv("PATH", f"{attacker}:{os.environ['PATH']}")
    acceptance_bundle._executable_identity_cached.cache_clear()

    for gate in ("ruff", "format", "pytest", "e2e", "accessibility", "eval"):
        identity = executable_identity("ignored", name=gate)
        assert not identity["path"].startswith(str(attacker))


def test_command_recorder_executes_trusted_binary_not_attacker_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_git_repo(tmp_path)
    attacker = tmp_path / "attacker"
    attacker.mkdir()
    fake_ruff = attacker / "ruff"
    fake_ruff.write_text("#!/bin/sh\necho ATTACKER-RUFF\n", encoding="utf-8")
    fake_ruff.chmod(0o755)
    monkeypatch.setenv("PATH", f"{attacker}:{os.environ['PATH']}")
    acceptance_bundle._executable_identity_cached.cache_clear()

    result = record_command(
        source=tmp_path,
        name="ruff",
        output_relative=Path("automated-tests/ruff.txt"),
        command=["ruff", "check", "."],
        cwd=tmp_path,
    )

    assert result["exit_code"] == 0
    assert "ATTACKER-RUFF" not in result["stdout"]
    assert not result["executable"]["path"].startswith(str(attacker))


def test_release_gate_cross_checks_embedded_commands_and_acceptance(tmp_path: Path) -> None:
    bundle, manifest = _valid_bundle(tmp_path)
    manifest["commands"][0]["stdout"] = "substituted"
    manifest["acceptance"][0]["actual_result"] = "substituted"

    result = validate_release_manifest(manifest, bundle, expected_commit=FULL_COMMIT)

    assert result.release_ready is False
    assert "manifest commands do not match hashed command-results.json" in result.errors
    assert "manifest acceptance does not match hashed acceptance-results.json" in result.errors


def test_release_gate_rejects_empty_rehashed_junit(tmp_path: Path) -> None:
    bundle, manifest = _valid_bundle(tmp_path)
    junit = bundle / "automated-tests" / "pytest.xml"
    junit.write_text('<testsuite tests="0" failures="0" errors="0" />', encoding="utf-8")
    manifest["hashes"]["automated-tests/pytest.xml"] = _sha256(junit)

    result = validate_release_manifest(manifest, bundle, expected_commit=FULL_COMMIT)

    assert result.release_ready is False
    assert "pytest JUnit report contains no tests" in result.errors


def test_release_gate_rejects_truncated_rehashed_eval_items(tmp_path: Path) -> None:
    bundle, manifest = _valid_bundle(tmp_path)
    items = bundle / "automated-tests" / "eval-items.jsonl"
    first = items.read_text(encoding="utf-8").splitlines()[0]
    items.write_text(first + "\n", encoding="utf-8")
    manifest["hashes"]["automated-tests/eval-items.jsonl"] = _sha256(items)

    result = validate_release_manifest(manifest, bundle, expected_commit=FULL_COMMIT)

    assert result.release_ready is False
    assert "Eval item inventory does not match summary" in result.errors


def test_release_gate_rejects_rehashed_empty_accessibility_inventory(tmp_path: Path) -> None:
    bundle, manifest = _valid_bundle(tmp_path)
    report_path = bundle / "automated-tests" / "accessibility.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report.update(routes=[], dynamic_states=[], missing_dynamic_states=[])
    report_path.write_text(json.dumps(report), encoding="utf-8")
    manifest["hashes"]["automated-tests/accessibility.json"] = _sha256(report_path)

    result = validate_release_manifest(manifest, bundle, expected_commit=FULL_COMMIT)

    assert result.release_ready is False
    assert "accessibility route inventory is incomplete" in result.errors
    assert "accessibility dynamic-state inventory is incomplete" in result.errors


def test_release_gate_rejects_rehashed_browser_result_not_bound_to_command(
    tmp_path: Path,
) -> None:
    bundle, manifest = _valid_bundle(tmp_path)
    report_path = bundle / "automated-tests" / "e2e-results.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["stdout"] += "\nforged-browser-result[chromium] PASSED"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    manifest["hashes"]["automated-tests/e2e-results.json"] = _sha256(report_path)

    result = validate_release_manifest(manifest, bundle, expected_commit=FULL_COMMIT)

    assert result.release_ready is False
    assert "browser result does not match recorded command" in result.errors


def test_acceptance_results_derive_status_from_criterion_specific_evidence(
    tmp_path: Path,
) -> None:
    source, _manifest = _valid_bundle(tmp_path)
    accessibility = source / "automated-tests" / "accessibility.json"
    payload = json.loads(accessibility.read_text(encoding="utf-8"))
    payload.update(passed=False, dynamic_keyboard_failure_count=1)
    accessibility.write_text(json.dumps(payload), encoding="utf-8")

    output = write_acceptance_results(
        source=source,
        commit=FULL_COMMIT,
        environment="isolated-test",
    )
    records = {record["id"]: record for record in json.loads(output.read_text())}

    assert records["UI-003"]["status"] == "Fail"
    assert "dynamic keyboard" in records["UI-003"]["actual_result"].lower()
    assert records["JOB-002"]["status"] == "Pass"
    assert records["UI-003"]["actual_result"] != records["JOB-002"]["actual_result"]


def test_acceptance_results_fail_only_the_named_eval_criterion(tmp_path: Path) -> None:
    source, _manifest = _valid_bundle(tmp_path)
    items_path = source / "automated-tests" / "eval-items.jsonl"
    rows = [json.loads(line) for line in items_path.read_text().splitlines()]
    cv_row = next(row for row in rows if row["suite"] == "cv_pair")
    cv_row["passed"] = False
    cv_row["grader_results"][0]["passed"] = False
    items_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    output = write_acceptance_results(
        source=source,
        commit=FULL_COMMIT,
        environment="isolated-test",
    )
    records = {record["id"]: record for record in json.loads(output.read_text())}

    assert records["CV-003"]["status"] == "Fail"
    assert "cv" in records["CV-003"]["actual_result"].lower()
    assert records["SCORE-003"]["status"] == "Pass"
    assert records["CHAT-003"]["status"] == "Pass"


def test_grounded_answer_acceptance_requires_parity_only_for_paired_rows() -> None:
    required = [
        {"name": name, "passed": True}
        for name in (
            "schema",
            "expected_label",
            "evidence_ids",
            "grounded_answer",
            "answer_language",
        )
    ]
    rows = [
        {
            "suite": "copilot_normal",
            "output": {"action": "answer"},
            "grader_results": [*required, {"name": "bilingual_parity", "passed": True}],
        },
        {
            "suite": "copilot_normal",
            "output": {"action": "answer"},
            "grader_results": required,
        },
    ]

    status, detail = acceptance_bundle._eval_check_result(
        "copilot-grounded-answer", summary={}, rows=rows
    )

    assert status == "Pass"
    assert "parity_rows=1" in detail


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
