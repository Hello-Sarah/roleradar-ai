import copy
import hashlib
import json
import os
import struct
import subprocess
import sys
import tomllib
import xml.etree.ElementTree as ET
import zlib
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile

import pytest

import scripts.build_acceptance_bundle as acceptance_bundle
from scripts.build_acceptance_bundle import (
    executable_identity,
    record_command,
    validate_release_manifest,
    write_acceptance_results,
)
from scripts.evidence_identity import (
    SCREENSHOT_LEDGER,
    SCREENSHOT_STATES,
    SYSTEM_HEADINGS,
    png_identity,
)

FULL_COMMIT = "1" * 40
STARTED_AT = "2026-10-01T10:00:00Z"
ENDED_AT = "2026-10-01T10:06:00Z"


def _refresh_command_hashes(bundle: Path, manifest: dict) -> None:
    """Remove digest mismatch as a confounder when testing semantic rejection."""
    for command in manifest["commands"]:
        command["artifact_hashes"] = {
            relative: _sha256(bundle / relative)
            for relative in command["artifacts"]
            if (bundle / relative).is_file()
            and (relative != command["output"] or not relative.endswith(".json"))
        }
    browser = next(command for command in manifest["commands"] if command["name"] == "e2e")
    (bundle / "automated-tests/e2e-results.json").write_text(json.dumps(browser))
    (bundle / "command-results.json").write_text(json.dumps(manifest["commands"]))
    for path in bundle.rglob("*"):
        if path.is_file():
            manifest["hashes"][str(path.relative_to(bundle))] = _sha256(path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("browser", "chromium"),
        ("locale", "en"),
        ("route", "dashboard"),
        ("state", "confirmation"),
        ("viewport", {"width": 390, "height": 844}),
    ],
)
def test_capture_metadata_cannot_substitute_another_identity(tmp_path: Path, field, value) -> None:
    bundle, manifest = _valid_bundle(tmp_path)
    ledger = bundle / SCREENSHOT_LEDGER
    records = json.loads(ledger.read_text())
    record = next(
        record for record in records if record["path"] == "screenshots/zh/webkit-watch-list.png"
    )
    record[field] = value
    ledger.write_text(json.dumps(records))
    _refresh_command_hashes(bundle, manifest)
    result = validate_release_manifest(manifest, bundle, expected_commit=FULL_COMMIT)
    assert "missing or invalid screenshot identity evidence" in result.errors


def test_rehashing_after_capture_does_not_hide_artifact_substitution(tmp_path: Path) -> None:
    bundle, manifest = _valid_bundle(tmp_path)
    path = bundle / "screenshots/zh/webkit-watch-list.png"
    path.write_bytes((bundle / "screenshots/en/chromium-dashboard.png").read_bytes())
    manifest["hashes"][str(path.relative_to(bundle))] = _sha256(path)
    result = validate_release_manifest(manifest, bundle, expected_commit=FULL_COMMIT)
    assert any("artifact changed after command completion: e2e" in error for error in result.errors)


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong_viewport",
        "missing_snapshot",
        "missing_resource",
        "missing_checkpoint",
        "malformed_json",
    ],
)
def test_trace_semantic_checks_are_independent_of_manifest_rehash(tmp_path: Path, mutation) -> None:
    bundle, manifest = _valid_bundle(tmp_path)
    path = bundle / "browser-results/traces/chromium-desktop-primary-loop.zip"
    with ZipFile(path) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    events = [json.loads(line) for line in entries["trace.trace"].decode().splitlines()]
    if mutation == "wrong_viewport":
        events[0]["options"]["viewport"] = {"width": 390, "height": 844}
    elif mutation == "missing_snapshot":
        events = [event for event in events if event["type"] != "frame-snapshot"]
    elif mutation == "missing_resource":
        entries = {
            name: data for name, data in entries.items() if not name.startswith("resources/")
        }
    elif mutation == "missing_checkpoint":
        for event in events:
            if event.get("method") == "click" and "Generate tailored CV" in str(
                event.get("params")
            ):
                event["params"] = {"selector": "another control"}
    entries["trace.trace"] = "\n".join(json.dumps(event) for event in events).encode()
    if mutation == "malformed_json":
        entries["trace.trace"] += b"\n{broken"
    with ZipFile(path, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    _refresh_command_hashes(bundle, manifest)
    result = validate_release_manifest(manifest, bundle, expected_commit=FULL_COMMIT)
    assert any("trace evidence" in error for error in result.errors)


@pytest.mark.parametrize(
    "mutation",
    ["failed_action", "minimal", "missing_call_id", "truncated", "no_resources", "duplicate"],
)
def test_review_rejects_failed_incomplete_or_duplicate_trace(tmp_path: Path, mutation: str) -> None:
    bundle, manifest = _valid_bundle(tmp_path)
    relative = "browser-results/traces/chromium-desktop-primary-loop.zip"
    path = bundle / relative
    with ZipFile(path) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    events = [json.loads(line) for line in entries["trace.trace"].decode().splitlines()]
    if mutation == "failed_action":
        next(event for event in events if event["type"] == "after")["error"] = {"message": "failed"}
    elif mutation == "missing_call_id":
        for event in events:
            event.pop("callId", None)
    elif mutation == "truncated":
        events.append({"type": "before", "callId": "unfinished", "method": "click"})
    elif mutation == "minimal":
        events = [
            events[0],
            {"type": "before", "callId": "x", "method": "goto"},
            {"type": "after", "callId": "x"},
        ]
    elif mutation == "no_resources":
        entries = {"trace.trace": entries["trace.trace"]}
    elif mutation == "duplicate":
        events = [
            {"type": "context-options", "browserName": browser, "title": test}
            for browser in ("chromium", "webkit")
            for test in acceptance_bundle.REQUIRED_TRACE_WORKFLOWS.values()
        ] + [{"type": "before", "callId": "x", "method": "goto"}, {"type": "after", "callId": "x"}]
    entries["trace.trace"] = "\n".join(json.dumps(event) for event in events).encode()
    with ZipFile(path, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    if mutation == "duplicate":
        for other in acceptance_bundle.REQUIRED_TRACE_PATHS:
            (bundle / other).write_bytes(path.read_bytes())
            manifest["hashes"][other] = _sha256(bundle / other)
    manifest["hashes"][relative] = _sha256(path)
    _refresh_command_hashes(bundle, manifest)
    assert not validate_release_manifest(
        manifest, bundle, expected_commit=FULL_COMMIT
    ).release_ready


@pytest.mark.parametrize("message", ["not executed", "xfail"])
@pytest.mark.parametrize("parameterized", [False, True])
def test_review_required_junit_skip_blocks_generated_ledger_and_gate(
    tmp_path: Path, message: str, parameterized: bool
) -> None:
    bundle, manifest = _valid_bundle(tmp_path)
    report = bundle / "automated-tests/pytest.xml"
    tree = ET.parse(report)
    name = (
        "test_download_endpoint_rejects_encoded_and_plain_separators"
        if parameterized
        else "test_catalogs_have_identical_keys"
    )
    case = next(case for case in tree.iter("testcase") if case.get("name", "").startswith(name))
    ET.SubElement(case, "skipped", message=message)
    tree.write(report, encoding="unicode")
    manifest["hashes"]["automated-tests/pytest.xml"] = _sha256(report)
    _refresh_command_hashes(bundle, manifest)
    assert not validate_release_manifest(
        manifest, bundle, expected_commit=FULL_COMMIT
    ).release_ready
    ledger = json.loads(
        write_acceptance_results(
            source=bundle, commit=FULL_COMMIT, environment="test-os"
        ).read_text()
    )
    criterion = "CV-004" if parameterized else "I18N-003"
    assert next(item for item in ledger if item["id"] == criterion)["status"] != "Pass"


@pytest.mark.parametrize("mutation", ["invalid_png", "wrong_route", "wrong_language", "duplicate"])
def test_review_rejects_screenshot_substitution(tmp_path: Path, mutation: str) -> None:
    bundle, manifest = _valid_bundle(tmp_path)
    relative = "screenshots/zh/webkit-watch-list.png"
    path = bundle / relative
    if mutation == "invalid_png":
        path.write_bytes(b"not a PNG")
    else:
        source = {
            "wrong_route": "screenshots/zh/webkit-dashboard.png",
            "wrong_language": "screenshots/en/webkit-watch-list.png",
            "duplicate": "screenshots/en/chromium-dashboard.png",
        }[mutation]
        path.write_bytes((bundle / source).read_bytes())
    manifest["hashes"][relative] = _sha256(path)
    if mutation != "invalid_png":
        ledger = bundle / SCREENSHOT_LEDGER
        records = json.loads(ledger.read_text())
        target = next(record for record in records if record["path"] == relative)
        origin = next(record for record in records if record["path"] == source)
        if mutation == "duplicate":
            target.update(sha256=origin["sha256"], pixel_hash=origin["pixel_hash"])
        else:
            target.update(origin)
            target["path"] = relative
        ledger.write_text(json.dumps(records))
    _refresh_command_hashes(bundle, manifest)
    assert not validate_release_manifest(
        manifest, bundle, expected_commit=FULL_COMMIT
    ).release_ready


@pytest.mark.parametrize("status", ["notrun", "disabled", "skipped"])
def test_required_junit_not_run_status_blocks_acceptance(tmp_path: Path, status: str) -> None:
    bundle, manifest = _valid_bundle(tmp_path)
    report = bundle / "automated-tests/pytest.xml"
    tree = ET.parse(report)
    case = next(
        case
        for case in tree.iter("testcase")
        if case.get("name") == "test_catalogs_have_identical_keys"
    )
    case.set("status", status)
    tree.write(report, encoding="unicode")
    _refresh_command_hashes(bundle, manifest)
    result = validate_release_manifest(manifest, bundle, expected_commit=FULL_COMMIT)
    assert "acceptance status does not match evidence: I18N-003" in result.errors


def test_generated_summary_records_nonblocking_p2_reproduction_and_evidence(tmp_path: Path) -> None:
    bundle, manifest = _valid_bundle(tmp_path)
    manifest["open_defects"] = [
        {
            "id": "RR-P2-HEADER-001",
            "severity": "P2",
            "description": "Desktop utility helper line partially clipped by framework toolbar",
            "route": "Dashboard / 仪表盘",
            "viewport": "1440x1100",
            "evidence": ["screenshots/en/chromium-dashboard.png"],
            "primary_loop_impact": "None: required controls remain reachable; accessibility passes",
        }
    ]
    validation = validate_release_manifest(manifest, bundle, expected_commit=FULL_COMMIT)
    assert validation.release_ready
    summary = acceptance_bundle._summary(manifest, validation)
    for detail in (
        "RR-P2-HEADER-001",
        "P2",
        "1440x1100",
        "Dashboard / 仪表盘",
        "screenshots/en/chromium-dashboard.png",
        "required controls remain reachable",
    ):
        assert detail in summary


@pytest.mark.parametrize("mutation", ["missing", "not_zip", "wrong_browser", "wrong_workflow"])
def test_release_gate_rejects_missing_or_substituted_passing_flow_trace(
    tmp_path: Path, mutation: str
) -> None:
    bundle, manifest = _valid_bundle(tmp_path)
    relative = "browser-results/traces/webkit-narrow-primary-loop.zip"
    path = bundle / relative
    if mutation == "missing":
        path.unlink()
        manifest["hashes"].pop(relative)
    elif mutation == "not_zip":
        path.write_bytes(b"not a replayable trace")
    else:
        replacement = (
            "chromium-narrow-primary-loop.zip"
            if mutation == "wrong_browser"
            else "webkit-copilot-confirmation.zip"
        )
        path.write_bytes((path.parent / replacement).read_bytes())
    if path.exists():
        manifest["hashes"][relative] = _sha256(path)
    result = validate_release_manifest(manifest, bundle, expected_commit=FULL_COMMIT)
    assert result.release_ready is False
    assert any("trace evidence" in error for error in result.errors)


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
    captures = []
    for locale, names in screenshot_names.items():
        (screenshots / locale).mkdir(parents=True, exist_ok=True)
        for browser in ("chromium", "webkit"):
            for name in names:
                path = screenshots / locale / f"{browser}-{name}.png"
                width, height = (390, 844) if locale == "narrow" else (1440, 1100)

                def chunk(kind, payload):
                    return (
                        struct.pack("!I", len(payload))
                        + kind
                        + payload
                        + struct.pack("!I", zlib.crc32(kind + payload))
                    )

                color = bytes([len(captures) + 1, 120, 220])
                path.write_bytes(
                    b"\x89PNG\r\n\x1a\n"
                    + chunk(b"IHDR", struct.pack("!IIBBBBB", width, height, 8, 2, 0, 0, 0))
                    + chunk(b"IDAT", zlib.compress((b"\0" + color * width) * height))
                    + chunk(b"IEND", b"")
                )
                language = "zh-Hans" if locale == "zh" else "en"
                route, state = SCREENSHOT_STATES[name]
                heading = next(
                    text for text, key in SYSTEM_HEADINGS[language].items() if key == route
                )
                captures.append(
                    {
                        "path": str(path.relative_to(bundle)),
                        "browser": browser,
                        "locale": language,
                        "route": route,
                        "state": state,
                        "heading": heading,
                        "viewport": {"width": width, "height": height},
                        "dimensions": [width, height],
                        "pixel_hash": png_identity(path)[2],
                        "sha256": _sha256(path),
                        "commit": FULL_COMMIT,
                        "run_id": "2026-10-01T10:03:00Z",
                        "captured_at": "2026-10-01T10:03:10Z",
                    }
                )
    automated.mkdir(parents=True)
    traces = bundle / "browser-results" / "traces"
    traces.mkdir(parents=True)
    trace_fixtures = json.loads(Path("tests/fixtures/acceptance/trace-cases.json").read_text())
    for browser in ("chromium", "webkit"):
        for workflow, _test_name in {
            "desktop-primary-loop": "test_pasted_job_to_application_watchlist_and_tailored_cv",
            "narrow-primary-loop": "test_primary_loop_and_copilot_are_non_blocking_at_390px",
            "copilot-confirmation": (
                "test_copilot_requires_keyboard_reachable_confirmation_before_write"
            ),
        }.items():
            with ZipFile(traces / f"{browser}-{workflow}.zip", "w") as trace:
                fixture = trace_fixtures[f"{browser}-{workflow}"]
                fixture["events"][0]["wallTime"] = int(
                    datetime.fromisoformat("2026-10-01T10:03:05+00:00").timestamp() * 1000
                )
                trace.writestr(
                    "trace.trace", "\n".join(json.dumps(event) for event in fixture["events"])
                )
                trace.writestr(
                    "trace.network", "\n".join(json.dumps(event) for event in fixture["network"])
                )
                for resource, text in fixture["resources"].items():
                    trace.writestr(resource, text)
    (bundle / SCREENSHOT_LEDGER).write_text(json.dumps(captures))
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
            "expected": {"action": "save_job", "confirmed": True},
            "output": {"action": "save_job", "confirmed": True},
            "passed": True,
            "grader_results": [
                {"name": "schema", "passed": True},
                {"name": "expected_label", "passed": True},
                {"name": "write_counts", "passed": True},
                {"name": "action_parameters", "passed": True},
                {"name": "confirmation_execution", "passed": True},
                {"name": "duplicate_writes", "passed": True},
            ],
        },
        {
            "item_id": "copilot-security",
            "suite": "copilot_adversarial",
            "expected": {"action": "refuse", "security_category": "prompt_injection"},
            "output": {"action": "refuse"},
            "passed": True,
            "grader_results": [
                {"name": "schema", "passed": True},
                {"name": "expected_label", "passed": True},
                {"name": "write_counts", "passed": True},
                {"name": "security_policy", "passed": True},
            ],
        },
    ]
    action_template = next(row for row in eval_rows if row["item_id"] == "copilot-action")
    for index, action in enumerate(
        (
            "change_application_status",
            "create_application_event",
            "set_follow_up",
            "create_action_item",
        ),
        1,
    ):
        row = copy.deepcopy(action_template)
        row["item_id"] = f"copilot-action-{index}"
        row["expected"]["action"] = action
        row["output"]["action"] = action
        eval_rows.append(row)
    proposal_only = copy.deepcopy(action_template)
    proposal_only["item_id"] = "copilot-action-proposal-only"
    proposal_only["expected"]["confirmed"] = False
    proposal_only["output"]["confirmed"] = False
    eval_rows.append(proposal_only)
    security_template = next(row for row in eval_rows if row["item_id"] == "copilot-security")
    for index, category in enumerate(
        (
            "ambiguity",
            "bulk_edit",
            "source_cv_overwrite",
            "automatic_application",
            "unsupported_claim",
            "unconfirmed_delete",
        ),
        1,
    ):
        row = copy.deepcopy(security_template)
        row["item_id"] = f"copilot-security-{index}"
        row["expected"]["security_category"] = category
        eval_rows.append(row)
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
            acceptance_bundle.COMMAND_OUTPUTS["e2e"],
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
                suffixes = check.get("required_case_ids")
                if suffixes is None:
                    count = check.get("minimum_cases", 1)
                    suffixes = [f"[case-{index}]" for index in range(count)] if count > 1 else [""]
                for suffix in suffixes:
                    ET.SubElement(suite, "testcase", classname=classname, name=name + suffix)
            if check["kind"] == "e2e":
                e2e_checks.append(check["name"])
    ET.ElementTree(suite).write(automated / "pytest.xml", encoding="unicode")
    browser_result = next(command for command in commands if command["name"] == "e2e")
    browser_result["stdout"] = "\n".join(
        f"{check}[{browser}] PASSED" for check in e2e_checks for browser in ("chromium", "webkit")
    )
    for command in commands:
        command["artifact_hashes"] = {
            relative: _sha256(bundle / relative)
            for relative in command["artifacts"]
            if relative != command["output"] or not relative.endswith(".json")
        }
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


@pytest.mark.parametrize("mutation", ["remove", "rewrite"])
@pytest.mark.parametrize(
    ("acceptance_id", "check_name", "expected_cases"),
    [
        (
            "CHAT-004",
            "tests.test_copilot_actions::test_typed_union_accepts_every_allowed_action_and_rejects_forbidden_actions",
            1,
        ),
        (
            "CHAT-004",
            "tests.test_copilot_actions::test_all_deterministic_allowed_actions_execute_through_domain_boundaries",
            1,
        ),
        (
            "CHAT-008",
            "tests.test_copilot_actions::test_adversarial_jd_cannot_trigger_automatic_or_ambiguous_action",
            1,
        ),
        (
            "CV-004",
            "tests.test_cv_api::test_generate_response_and_download_preserve_the_intended_artifact",
            1,
        ),
        (
            "CV-004",
            "tests.test_cv_api::test_download_endpoint_rejects_encoded_and_plain_separators",
            6,
        ),
        (
            "CV-004",
            "tests.test_cv_api::test_download_rejects_symlink_escaping_output_directory",
            1,
        ),
        (
            "DIGEST-001",
            "tests.test_digest::test_digest_uses_persisted_v2_bands_and_excludes_low_value_jobs",
            1,
        ),
        (
            "DIGEST-001",
            "tests.test_digest::test_empty_digest_keeps_every_signal_category_explicit",
            1,
        ),
    ],
)
def test_release_gate_rejects_rehashed_junit_missing_each_clause_case(
    tmp_path: Path,
    acceptance_id: str,
    check_name: str,
    expected_cases: int,
    mutation: str,
) -> None:
    bundle, manifest = _valid_bundle(tmp_path)
    junit = bundle / "automated-tests" / "pytest.xml"
    tree = ET.parse(junit)
    classname, name = check_name.split("::", 1)
    matches = [
        case
        for case in tree.getroot().iter("testcase")
        if case.get("classname") == classname and str(case.get("name")).startswith(name)
    ]
    assert len(matches) == expected_cases
    if mutation == "remove":
        for parent in tree.getroot().iter():
            if matches[0] in list(parent):
                parent.remove(matches[0])
                break
    else:
        matches[0].set("name", "rewritten-nonmatching-case")
    tree.write(junit, encoding="unicode")
    manifest["hashes"]["automated-tests/pytest.xml"] = _sha256(junit)

    result = validate_release_manifest(manifest, bundle, expected_commit=FULL_COMMIT)

    assert result.release_ready is False
    assert f"acceptance status does not match evidence: {acceptance_id}" in result.errors
    assert f"acceptance result does not match evidence: {acceptance_id}" in result.errors


def test_release_gate_rejects_rehashed_duplicate_cv_traversal_cases(tmp_path: Path) -> None:
    bundle, manifest = _valid_bundle(tmp_path)
    junit = bundle / "automated-tests" / "pytest.xml"
    tree = ET.parse(junit)
    prefix = "test_download_endpoint_rejects_encoded_and_plain_separators"
    matches = [
        case
        for case in tree.getroot().iter("testcase")
        if case.get("classname") == "tests.test_cv_api" and str(case.get("name")).startswith(prefix)
    ]
    assert len(matches) == 6
    for case in matches[1:]:
        case.set("name", str(matches[0].get("name")))
    tree.write(junit, encoding="unicode")
    manifest["hashes"]["automated-tests/pytest.xml"] = _sha256(junit)

    result = validate_release_manifest(manifest, bundle, expected_commit=FULL_COMMIT)

    assert result.release_ready is False
    assert "acceptance status does not match evidence: CV-004" in result.errors


@pytest.mark.parametrize(
    ("check_name", "field", "value", "detail"),
    [
        (
            "copilot-action-schema",
            "action",
            "create_application_event",
            "missing_actions",
        ),
        (
            "copilot-security",
            "security_category",
            "bulk_edit",
            "missing_security_categories",
        ),
    ],
)
def test_named_copilot_eval_checks_require_every_committed_population(
    tmp_path: Path, check_name: str, field: str, value: str, detail: str
) -> None:
    bundle, _manifest = _valid_bundle(tmp_path)
    rows = [
        json.loads(line)
        for line in (bundle / "automated-tests" / "eval-items.jsonl").read_text().splitlines()
    ]
    rows = [row for row in rows if row.get("expected", {}).get(field) != value]

    status, result_detail = acceptance_bundle._eval_check_result(check_name, summary={}, rows=rows)

    assert status == "Blocked"
    assert detail in result_detail


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
