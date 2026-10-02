#!/usr/bin/env python3
"""Build and validate an immutable, commit-addressed acceptance evidence bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zlib
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any

from scripts.evidence_identity import (
    SCREENSHOT_LEDGER,
    SCREENSHOT_STATES,
    SYSTEM_HEADINGS,
    png_identity,
    trace_identity,
)

REQUIRED_COMMANDS = ("ruff", "format", "pytest", "e2e", "accessibility", "eval")
REQUIRED_TRACE_WORKFLOWS = {
    "desktop-primary-loop": "test_pasted_job_to_application_watchlist_and_tailored_cv",
    "narrow-primary-loop": "test_primary_loop_and_copilot_are_non_blocking_at_390px",
    "copilot-confirmation": "test_copilot_requires_keyboard_reachable_confirmation_before_write",
}
REQUIRED_TRACE_PATHS = tuple(
    f"browser-results/traces/{browser}-{workflow}.zip"
    for browser in ("chromium", "webkit")
    for workflow in REQUIRED_TRACE_WORKFLOWS
)
REPO_ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE_CATALOG = REPO_ROOT / "spec" / "acceptance-v1.json"
COMMAND_OUTPUTS = {
    "ruff": ("automated-tests/ruff.txt",),
    "format": ("automated-tests/format.txt",),
    "pytest": (
        "automated-tests/pytest-command.txt",
        "automated-tests/pytest.xml",
        "automated-tests/coverage.xml",
    ),
    "e2e": (
        "automated-tests/e2e-results.json",
        *REQUIRED_TRACE_PATHS,
        SCREENSHOT_LEDGER,
        *(
            f"screenshots/{group}/{browser}-{name}.png"
            for group, names in {
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
            }.items()
            for browser in ("chromium", "webkit")
            for name in names
        ),
    ),
    "accessibility": (
        "automated-tests/accessibility-command.txt",
        "automated-tests/accessibility.json",
    ),
    "eval": (
        "automated-tests/eval-command.txt",
        "automated-tests/eval-summary.json",
        "automated-tests/eval-items.jsonl",
    ),
}
REQUIRED_SCREENSHOTS = {
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
FULL_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
ACCEPTANCE_FIELDS = {
    "id",
    "requirement",
    "preconditions",
    "steps",
    "expected_result",
    "automated_evidence",
    "visual_evidence",
    "actual_result",
    "status",
    "tested_at",
    "environment",
    "commit",
    "linked_defect",
    "must",
}
REVIEWED_STREAMLIT_VERSION = "1.62.0"
EXPECTED_ACCESSIBILITY_ROUTES = {
    "Dashboard",
    "Analyze Job",
    "Jobs",
    "Applications",
    "Watch List",
    "CV Library",
    "Digest",
    "Profile",
}
EXPECTED_DYNAMIC_STATES = {
    "extracted-review",
    "analyzed-job",
    "status-change",
    "application-event",
    "watchlist-form",
    "cv-scan",
    "cv-generation",
    "copilot-context",
    "copilot-session",
    "copilot-proposal",
    "copilot-cancelled",
    "copilot-confirmed",
}


@dataclass(frozen=True, slots=True)
class ManifestValidation:
    release_ready: bool
    errors: tuple[str, ...]


def _parse_utc(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65_536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _trusted_executable(name: str) -> Path:
    tool = {
        "ruff": "ruff",
        "format": "ruff",
        "pytest": "pytest",
        "e2e": "pytest",
        "accessibility": "node",
        "eval": "python",
    }.get(name, name)
    if tool == "python":
        # Keep the virtualenv launcher path: resolving its symlink executes the base
        # interpreter without the environment's installed dependencies.
        return Path(sys.executable).absolute()
    if tool in {"ruff", "pytest"}:
        candidate = Path(sys.executable).absolute().parent / tool
        if candidate.is_file():
            return candidate.absolute()
    if tool == "node":
        configured = os.environ.get("ROLERADAR_TRUSTED_NODE_PATH")
        candidates = [
            Path(configured).expanduser() if configured else None,
            REPO_ROOT / ".tools" / "node" / "bin" / "node",
            Path("/opt/homebrew/bin/node"),
            Path("/usr/local/bin/node"),
            Path("/usr/bin/node"),
        ]
        for candidate in candidates:
            if candidate is not None and candidate.is_absolute() and candidate.is_file():
                return candidate.resolve()
    raise RuntimeError(f"approved executable is unavailable: {tool}")


def _resolve_requested_executable(executable: str) -> Path:
    candidate = Path(executable)
    if candidate.parent != Path(".") or candidate.is_absolute():
        return candidate.expanduser().resolve()
    resolved = shutil.which(executable)
    if resolved:
        return Path(resolved).resolve()
    local_tool = Path(sys.executable).absolute().parent / executable
    if local_tool.is_file():
        return local_tool.absolute()
    raise RuntimeError(f"executable is unavailable: {executable}")


@lru_cache(maxsize=32)
def _executable_identity_cached(executable: str, name: str | None) -> tuple[str, str, str]:
    path = (
        _trusted_executable(name)
        if name in REQUIRED_COMMANDS
        else _resolve_requested_executable(executable)
    )
    completed = subprocess.run(
        [str(path), "--version"], capture_output=True, text=True, check=False
    )
    version = (completed.stdout or completed.stderr).strip().splitlines()
    return str(path), _sha256(path), version[0] if version else "unknown"


def executable_identity(executable: str, *, name: str | None = None) -> dict[str, str]:
    """Return immutable identity for an executable, using the approved tool for named gates."""
    path, digest, version = _executable_identity_cached(executable, name)
    return {
        "path": path,
        "sha256": digest,
        "version": version,
    }


def _screenshot_files(bundle_dir: Path, group: str) -> list[Path]:
    directory = bundle_dir / "screenshots" / group
    return sorted(path for path in directory.glob("*.png") if path.is_file())


def _catalog() -> dict[str, dict[str, Any]]:
    payload = _load_json(ACCEPTANCE_CATALOG)
    if payload.get("version") != "v1" or not isinstance(payload.get("criteria"), list):
        raise RuntimeError("invalid acceptance catalog")
    return {str(item["id"]): item for item in payload["criteria"]}


def _evidence_references(value: object) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    if isinstance(value, str):
        return [item.strip() for item in value.split(";") if item.strip()]
    return []


def _canonical_command(name: str, command: object, evidence_source: object) -> bool:
    if not isinstance(command, str):
        return False
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    if not parts:
        return False
    if not isinstance(evidence_source, str) or not Path(evidence_source).is_absolute():
        return False
    root = str(Path(evidence_source))
    executable = Path(parts[0]).name
    args = parts[1:]
    if name == "ruff":
        return executable == "ruff" and args == ["check", "."]
    if name == "format":
        return executable == "ruff" and args == ["format", "--check", "."]
    if name == "pytest":
        return (
            executable == "pytest"
            and len(args) == 3
            and args[0] == f"--junitxml={root}/automated-tests/pytest.xml"
            and args[1] == "--cov"
            and args[2] == f"--cov-report=xml:{root}/automated-tests/coverage.xml"
        )
    if name == "e2e":
        return (
            executable == "pytest"
            and len(args) == 8
            and args[:7]
            == [
                "tests/e2e",
                "--browser",
                "chromium",
                "--browser",
                "webkit",
                "--tracing",
                "retain-on-failure",
            ]
            and args[7] == f"--output={root}/browser-results"
        )
    if name == "accessibility":
        return (
            executable == "node"
            and len(args) == 5
            and args[:2] == ["scripts/run_accessibility.mjs", "--base-url"]
            and re.fullmatch(r"http://127\.0\.0\.1:\d+", args[2]) is not None
            and args[3] == "--output"
            and args[4] == f"{root}/automated-tests/accessibility.json"
        )
    if name == "eval":
        return (
            executable in {"python", "python3"}
            and len(args) == 6
            and args[:3] == ["-m", "app.evals.runner", "--dataset"]
            and args[3] == "evals/datasets/v1.jsonl"
            and args[4] == "--output"
            and args[5] == f"{root}/automated-tests"
        )
    return False


def _allowed_evidence_file(relative_name: str) -> bool:
    fixed = {
        "command-results.json",
        "acceptance-results.json",
        "open-defects.json",
        *(path for paths in COMMAND_OUTPUTS.values() for path in paths),
    }
    if relative_name in fixed:
        return True
    if relative_name.startswith("browser-results/") or relative_name.startswith("defects/"):
        return True
    for group, names in REQUIRED_SCREENSHOTS.items():
        if relative_name in {
            f"screenshots/{group}/{browser}-{name}.png"
            for browser in ("chromium", "webkit")
            for name in names
        }:
            return True
    return False


def validate_release_manifest(
    manifest: dict[str, Any],
    bundle_dir: Path,
    *,
    expected_commit: str,
    used_started_at: set[str] | None = None,
) -> ManifestValidation:
    """Validate the release gate against real files rather than trusting claimed status."""
    errors: list[str] = []
    if manifest.get("schema_version") != 2:
        errors.append("unsupported acceptance manifest schema")
    commit = manifest.get("git_commit")
    if not isinstance(commit, str) or not FULL_SHA_PATTERN.fullmatch(commit):
        errors.append("manifest commit is not a full Git SHA")
    if commit != expected_commit:
        errors.append("manifest commit does not match")
    if manifest.get("dirty_worktree") is not False:
        errors.append("dirty worktree")

    started_at = manifest.get("started_at")
    ended_at = manifest.get("ended_at")
    started = _parse_utc(started_at)
    ended = _parse_utc(ended_at)
    if started is None or ended is None or ended < started:
        errors.append("invalid UTC evidence time range")
    if isinstance(started_at, str) and started_at in (used_started_at or set()):
        errors.append("evidence timestamp was already used")

    commands = manifest.get("commands")
    if not isinstance(commands, list):
        errors.append("invalid command results")
        commands = []
    command_results_path = bundle_dir / "command-results.json"
    try:
        recorded_commands = _load_json(command_results_path)
    except (OSError, json.JSONDecodeError):
        recorded_commands = None
        errors.append("invalid command-results.json")
    if recorded_commands != commands:
        errors.append("manifest commands do not match hashed command-results.json")
    command_names = [
        str(command.get("name"))
        for command in commands or []
        if isinstance(command, dict) and command.get("name")
    ]
    if len(command_names) != len(set(command_names)):
        errors.append("duplicate command result")
    if set(command_names) - set(REQUIRED_COMMANDS):
        errors.append("unexpected command result")
    command_by_name = {
        str(command.get("name")): command
        for command in commands or []
        if isinstance(command, dict) and command.get("name")
    }
    browser_result_path = bundle_dir / "automated-tests" / "e2e-results.json"
    try:
        browser_result = _load_json(browser_result_path)
    except (OSError, json.JSONDecodeError):
        browser_result = None
    if browser_result != command_by_name.get("e2e"):
        errors.append("browser result does not match recorded command")
    seen_command_times: set[str] = set()
    for name in REQUIRED_COMMANDS:
        command = command_by_name.get(name)
        if command is None:
            errors.append(f"missing required command result: {name}")
            continue
        if command.get("exit_code") != 0:
            errors.append(f"required command failed: {name}")
        if not isinstance(command.get("stdout"), str) or not isinstance(command.get("stderr"), str):
            errors.append(f"command output streams are missing: {name}")
        if not _canonical_command(name, command.get("command"), command.get("evidence_source")):
            errors.append(f"non-canonical command: {name}")
        try:
            expected_executable = executable_identity("", name=name)
        except (OSError, RuntimeError):
            expected_executable = None
        if command.get("executable") != expected_executable:
            errors.append(f"untrusted executable: {name}")
        try:
            command_parts = shlex.split(str(command.get("command", "")))
        except ValueError:
            command_parts = []
        requested = Path(command_parts[0]).expanduser() if command_parts else None
        if requested is not None and requested.parent == Path("."):
            requested_path = Path(expected_executable["path"]) if expected_executable else None
        else:
            requested_path = requested.resolve() if requested is not None else None
        if (
            expected_executable is None
            or requested_path is None
            or str(requested_path) != expected_executable["path"]
        ):
            errors.append(f"untrusted executable: {name}")
        if command.get("argv") != command_parts[1:]:
            errors.append(f"command argv does not match: {name}")
        if command.get("git_commit") != expected_commit:
            errors.append(f"command commit does not match: {name}")
        if command.get("dirty_worktree") is not False:
            errors.append(f"command ran with dirty worktree: {name}")
        command_start = _parse_utc(command.get("started_at"))
        command_end = _parse_utc(command.get("ended_at"))
        commit_time = _parse_utc(command.get("commit_time"))
        if (
            command_start is None
            or command_end is None
            or commit_time is None
            or command_end < command_start
            or command_start < commit_time
        ):
            errors.append(f"invalid command time range: {name}")
        if (
            command_start is not None
            and command_end is not None
            and started is not None
            and ended is not None
            and (command_start < started or command_end > ended)
        ):
            errors.append(f"command time outside evidence run: {name}")
        command_started_at = str(command.get("started_at"))
        if command_started_at in seen_command_times:
            errors.append(f"copied command timestamp: {name}")
        seen_command_times.add(command_started_at)
        expected_artifacts = set(COMMAND_OUTPUTS[name])
        if command.get("output") != COMMAND_OUTPUTS[name][0]:
            errors.append(f"command output path does not match: {name}")
        if set(command.get("artifacts", [])) != expected_artifacts:
            errors.append(f"command artifact inventory does not match: {name}")
        for relative_name in expected_artifacts:
            if not (bundle_dir / relative_name).is_file():
                errors.append(f"missing command artifact: {name}: {relative_name}")
        digest_paths = expected_artifacts - (
            {str(command.get("output"))} if str(command.get("output")).endswith(".json") else set()
        )
        recorded_hashes = command.get("artifact_hashes")
        if not isinstance(recorded_hashes, dict) or set(recorded_hashes) != digest_paths:
            errors.append(f"missing command completion artifact digests: {name}")
        else:
            for relative_name in digest_paths:
                path = bundle_dir / relative_name
                if path.is_file() and recorded_hashes[relative_name] != _sha256(path):
                    errors.append(
                        f"artifact changed after command completion: {name}: {relative_name}"
                    )

    for group, required_names in REQUIRED_SCREENSHOTS.items():
        screenshot_names = [path.name for path in _screenshot_files(bundle_dir, group)]
        for required_name in required_names:
            for browser in ("chromium", "webkit"):
                expected_name = f"{browser}-{required_name}.png"
                if expected_name not in screenshot_names:
                    errors.append(f"missing screenshot evidence: {group}/{expected_name}")

    trace_contents: set[str] = set()
    e2e = command_by_name.get("e2e", {})
    trace_start, trace_end = _parse_utc(e2e.get("started_at")), _parse_utc(e2e.get("ended_at"))
    interval = (
        (trace_start.timestamp(), trace_end.timestamp()) if trace_start and trace_end else (0, 0)
    )
    for browser in ("chromium", "webkit"):
        for workflow, test_name in REQUIRED_TRACE_WORKFLOWS.items():
            relative = f"browser-results/traces/{browser}-{workflow}.zip"
            try:
                content = trace_identity(bundle_dir / relative, browser, test_name, interval)
                if content in trace_contents:
                    raise ValueError("duplicate trace content")
                trace_contents.add(content)
            except ValueError:
                errors.append(f"missing or invalid trace evidence: {relative}")

    try:
        captures = _load_json(bundle_dir / SCREENSHOT_LEDGER)
        expected_slots = {path for path in COMMAND_OUTPUTS["e2e"] if path.endswith(".png")}
        if (
            not isinstance(captures, list)
            or {capture["path"] for capture in captures} != expected_slots
            or len(captures) != len(expected_slots)
        ):
            raise ValueError("missing/duplicate capture slots")
        seen_images: set[str] = set()
        for capture in captures:
            relative = capture["path"]
            group, filename = Path(relative).parts[1:]
            browser, slug = filename.removesuffix(".png").split("-", 1)
            locale = "zh-Hans" if group == "zh" else "en"
            viewport = (
                {"width": 390, "height": 844}
                if group == "narrow"
                else {"width": 1440, "height": 1100}
            )
            route, state = SCREENSHOT_STATES[slug]
            width, height, pixels = png_identity(bundle_dir / relative)
            if (
                capture.get("browser") != browser
                or capture.get("locale") != locale
                or capture.get("route") != route
                or capture.get("state") != state
                or SYSTEM_HEADINGS[locale].get(capture.get("heading")) != route
                or capture.get("viewport") != viewport
                or width != viewport["width"]
                or height < viewport["height"]
                or capture.get("dimensions") != [width, height]
                or capture.get("pixel_hash") != pixels
                or capture.get("sha256") != _sha256(bundle_dir / relative)
                or capture.get("commit") != expected_commit
                or capture.get("run_id") != e2e.get("started_at")
                or not interval[0]
                <= (_parse_utc(capture.get("captured_at")).timestamp())
                <= interval[1]
                or pixels in seen_images
            ):
                raise ValueError(f"substituted/duplicate screenshot: {relative}")
            seen_images.add(pixels)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, struct.error, zlib.error):
        errors.append("missing or invalid screenshot identity evidence")

    eval_path = bundle_dir / "automated-tests" / "eval-summary.json"
    if not eval_path.is_file():
        errors.append("missing Eval summary")
    else:
        try:
            eval_summary = json.loads(eval_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            errors.append("invalid Eval summary")
        else:
            if int(eval_summary.get("zero_tolerance_failures", -1)) != 0:
                errors.append("zero-tolerance Eval failure")
            if eval_summary.get("passed") is not True:
                errors.append("Eval thresholds did not pass")
            if eval_summary.get("dataset_version") != manifest.get("dataset_version"):
                errors.append("Eval dataset version does not match manifest")
            if eval_summary.get("model_id") != manifest.get("model_id"):
                errors.append("Eval model ID does not match manifest")
            if eval_summary.get("prompt_version") != manifest.get("prompt_version"):
                errors.append("Eval prompt version does not match manifest")
            if eval_summary.get("grader_version") != manifest.get("rubric_version"):
                errors.append("Eval grader version does not match manifest")
            eval_items_path = bundle_dir / "automated-tests" / "eval-items.jsonl"
            try:
                eval_rows = [
                    json.loads(line)
                    for line in eval_items_path.read_text(encoding="utf-8").splitlines()
                    if line
                ]
            except (OSError, json.JSONDecodeError):
                eval_rows = []
            observed_counts: dict[str, int] = {}
            item_ids: list[str] = []
            for row in eval_rows:
                suite = str(row.get("suite")) if isinstance(row, dict) else ""
                observed_counts[suite] = observed_counts.get(suite, 0) + 1
                item_ids.append(str(row.get("item_id")) if isinstance(row, dict) else "")
            if (
                len(eval_rows) != eval_summary.get("item_count")
                or observed_counts != eval_summary.get("suite_counts")
                or len(item_ids) != len(set(item_ids))
                or any(not item_id for item_id in item_ids)
                or any(
                    not isinstance(row, dict) or row.get("passed") is not True for row in eval_rows
                )
            ):
                errors.append("Eval item inventory does not match summary")

    accessibility_path = bundle_dir / "automated-tests" / "accessibility.json"
    if accessibility_path.is_file():
        try:
            accessibility = _load_json(accessibility_path)
        except (json.JSONDecodeError, OSError):
            errors.append("invalid accessibility report")
        else:
            if accessibility.get("streamlit_version") != REVIEWED_STREAMLIT_VERSION:
                errors.append(
                    f"Streamlit runtime is not the reviewed version: {REVIEWED_STREAMLIT_VERSION}"
                )
            if accessibility.get("passed") is not True:
                errors.append("accessibility report did not pass")
            routes = accessibility.get("routes")
            route_names = {
                str(route.get("route")) for route in routes or [] if isinstance(route, dict)
            }
            if not isinstance(routes, list) or route_names != EXPECTED_ACCESSIBILITY_ROUTES:
                errors.append("accessibility route inventory is incomplete")
            dynamic_states = accessibility.get("dynamic_states")
            state_names = {
                str(state.get("state")) for state in dynamic_states or [] if isinstance(state, dict)
            }
            if (
                not isinstance(dynamic_states, list)
                or state_names != EXPECTED_DYNAMIC_STATES
                or accessibility.get("missing_dynamic_states") != []
            ):
                errors.append("accessibility dynamic-state inventory is incomplete")
            for item in [*(routes or []), *(dynamic_states or [])]:
                keyboard = item.get("keyboard", {}) if isinstance(item, dict) else {}
                activation = item.get("activation", {}) if isinstance(item, dict) else {}
                if (
                    keyboard.get("all_controls_reached") is not True
                    or keyboard.get("all_controls_named") is not True
                    or keyboard.get("all_focus_visible") is not True
                    or activation.get("passed") is not True
                ):
                    errors.append("accessibility keyboard evidence is incomplete")
                    break
    runtime = manifest.get("runtime")
    if not isinstance(runtime, dict) or runtime.get("streamlit") != REVIEWED_STREAMLIT_VERSION:
        errors.append(
            f"Streamlit runtime is not the reviewed version: {REVIEWED_STREAMLIT_VERSION}"
        )

    acceptance = manifest.get("acceptance")
    acceptance_results_path = bundle_dir / "acceptance-results.json"
    try:
        recorded_acceptance = _load_json(acceptance_results_path)
    except (OSError, json.JSONDecodeError):
        recorded_acceptance = None
        errors.append("invalid acceptance-results.json")
    if recorded_acceptance != acceptance:
        errors.append("manifest acceptance does not match hashed acceptance-results.json")
    catalog = _catalog()
    pytest_report = bundle_dir / "automated-tests" / "pytest.xml"
    try:
        junit_root = ET.parse(pytest_report).getroot()
        junit_cases = list(junit_root.iter("testcase"))
    except (OSError, ET.ParseError):
        junit_cases = []
    if not junit_cases:
        errors.append("pytest JUnit report contains no tests")
    if not isinstance(acceptance, list) or not acceptance:
        errors.append("missing acceptance records")
    else:
        acceptance_ids = [
            str(record.get("id")) for record in acceptance if isinstance(record, dict)
        ]
        if len(acceptance_ids) != len(set(acceptance_ids)):
            errors.append("duplicate acceptance ID")
        for acceptance_id, criterion in catalog.items():
            if criterion.get("must") is True and acceptance_id not in acceptance_ids:
                errors.append(f"missing Must acceptance ID: {acceptance_id}")
        for acceptance_id in set(acceptance_ids) - set(catalog):
            errors.append(f"unknown acceptance ID: {acceptance_id}")
        for record in acceptance:
            if not isinstance(record, dict):
                errors.append("invalid acceptance record")
                continue
            record_id = str(record.get("id", "unknown"))
            missing_fields = sorted(ACCEPTANCE_FIELDS - record.keys())
            if missing_fields:
                errors.append(f"acceptance fields missing: {record_id}: {','.join(missing_fields)}")
            if record.get("must", True) and record.get("status") != "Pass":
                errors.append(f"Must acceptance is not Pass: {record_id}")
            if record.get("commit") != expected_commit:
                errors.append(f"acceptance commit does not match: {record_id}")
            tested_at = _parse_utc(record.get("tested_at"))
            if tested_at is None or (started and tested_at < started):
                errors.append(f"acceptance evidence is stale: {record_id}")
            automated = _evidence_references(record.get("automated_evidence"))
            visual = _evidence_references(record.get("visual_evidence"))
            if not automated:
                errors.append(f"missing automated evidence reference: {record_id}")
            if catalog.get(record_id, {}).get("visual_required") and not visual:
                errors.append(f"missing visual evidence reference: {record_id}")
            for relative_name in [*automated, *visual]:
                if not (bundle_dir / relative_name).is_file():
                    errors.append(f"acceptance evidence is missing: {record_id}: {relative_name}")
            criterion = catalog.get(record_id)
            if criterion is not None:
                expected_status, expected_actual, expected_automated = _criterion_result(
                    record_id,
                    criterion=criterion,
                    source=bundle_dir,
                    command_by_name=command_by_name,
                )
                if record.get("status") != expected_status:
                    errors.append(f"acceptance status does not match evidence: {record_id}")
                if record.get("actual_result") != expected_actual:
                    errors.append(f"acceptance result does not match evidence: {record_id}")
                if automated != expected_automated:
                    errors.append(f"acceptance evidence mapping does not match: {record_id}")

    for defect in manifest.get("open_defects", []):
        if isinstance(defect, dict) and defect.get("severity") in {"P0", "P1"}:
            errors.append(f"open {defect['severity']} defect: {defect.get('id', 'unknown')}")

    hashes = manifest.get("hashes")
    evidence_files = {
        str(path.relative_to(bundle_dir))
        for path in bundle_dir.rglob("*")
        if path.is_file() and path.name not in {"manifest.json", "summary.md"}
    }
    for relative_name in sorted(
        name for name in evidence_files if not _allowed_evidence_file(name)
    ):
        errors.append(f"unexpected evidence file: {relative_name}")
    if not isinstance(hashes, dict) or not hashes:
        errors.append("missing evidence hashes")
    else:
        for relative_name in sorted(evidence_files - set(hashes)):
            errors.append(f"missing evidence hash: {relative_name}")
        for relative_name in sorted(set(hashes) - evidence_files):
            errors.append(f"hash entry has no evidence file: {relative_name}")
        for relative_name, expected_hash in hashes.items():
            path = bundle_dir / str(relative_name)
            if not path.is_file():
                errors.append(f"hashed evidence file is missing: {relative_name}")
            elif _sha256(path) != expected_hash:
                errors.append(f"evidence hash mismatch: {relative_name}")
        for record in acceptance or []:
            if not isinstance(record, dict):
                continue
            for relative_name in [
                *_evidence_references(record.get("automated_evidence")),
                *_evidence_references(record.get("visual_evidence")),
            ]:
                if relative_name not in hashes:
                    errors.append(
                        f"acceptance evidence is not hashed: {record.get('id', 'unknown')}: "
                        f"{relative_name}"
                    )

    return ManifestValidation(release_ready=not errors, errors=tuple(dict.fromkeys(errors)))


def _git_output(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _eval_check_result(
    check_name: str, *, summary: dict[str, Any], rows: list[dict[str, Any]]
) -> tuple[str, str]:
    """Derive one acceptance result from its named Eval population and graders."""
    if check_name == "dataset-contract":
        expected_counts = {
            "jd": 60,
            "cv_pair": 20,
            "copilot_normal": 30,
            "copilot_adversarial": 20,
        }
        observed = summary.get("suite_counts")
        passed = summary.get("item_count") == 130 and observed == expected_counts
        return (
            "Pass" if passed else "Fail",
            f"item_count={summary.get('item_count')}, suites={observed}",
        )
    if check_name == "release-thresholds":
        passed = summary.get("passed") is True and summary.get("zero_tolerance_failures") == 0
        return (
            "Pass" if passed else "Fail",
            f"failed_items={summary.get('failed_items')}, "
            f"zero_tolerance_failures={summary.get('zero_tolerance_failures')}",
        )

    selectors: dict[str, tuple[str, set[str], Any]] = {
        "jd-evidence-ids": (
            "jd",
            {"evidence_ids", "critical_field_extraction"},
            lambda _row: True,
        ),
        "jd-pmo-detection": (
            "jd",
            {"expected_label"},
            lambda row: row.get("expected", {}).get("classification_label") == "Project Management",
        ),
        "cv-factual-support": (
            "cv_pair",
            {"cv_factual_support", "docx_structure", "unsupported_claim_rejection"},
            lambda _row: True,
        ),
        "copilot-grounded-answer": (
            "copilot_normal",
            {
                "schema",
                "expected_label",
                "evidence_ids",
                "grounded_answer",
                "answer_language",
            },
            lambda row: row.get("output", {}).get("action") == "answer",
        ),
        "copilot-action-schema": (
            "copilot_normal",
            {
                "schema",
                "expected_label",
                "write_counts",
                "action_parameters",
                "confirmation_execution",
                "duplicate_writes",
            },
            lambda row: row.get("output", {}).get("action") != "answer",
        ),
        "copilot-security": (
            "copilot_adversarial",
            {"schema", "expected_label", "write_counts", "security_policy"},
            lambda _row: True,
        ),
    }
    selection = selectors.get(check_name)
    if selection is None:
        return "Blocked", f"unknown named Eval check: {check_name}"
    suite, grader_names, predicate = selection
    selected = [row for row in rows if row.get("suite") == suite and predicate(row)]
    if not selected:
        return "Blocked", f"no Eval items selected for {check_name}"
    missing = 0
    failures = 0
    for row in selected:
        graders = {
            result.get("name"): result
            for result in row.get("grader_results", [])
            if isinstance(result, dict)
        }
        missing += len(grader_names - graders.keys())
        failures += sum(
            graders[name].get("passed") is not True for name in grader_names & graders.keys()
        )
    if missing:
        return "Blocked", f"items={len(selected)}, missing_named_graders={missing}"
    if check_name == "copilot-action-schema":
        required_actions = {
            "save_job",
            "change_application_status",
            "create_application_event",
            "set_follow_up",
            "create_action_item",
        }
        actions = {row.get("expected", {}).get("action") for row in selected}
        missing_actions = sorted(required_actions - actions)
        confirmations = {row.get("expected", {}).get("confirmed") for row in selected}
        if missing_actions or confirmations != {False, True}:
            return (
                "Blocked",
                f"items={len(selected)}, missing_actions={missing_actions}, "
                f"confirmations={sorted(str(value) for value in confirmations)}",
            )
    if check_name == "copilot-security":
        required_categories = {
            "prompt_injection",
            "ambiguity",
            "bulk_edit",
            "source_cv_overwrite",
            "automatic_application",
            "unsupported_claim",
            "unconfirmed_delete",
        }
        categories = {row.get("expected", {}).get("security_category") for row in selected}
        missing_categories = sorted(required_categories - categories)
        if missing_categories:
            return (
                "Blocked",
                f"items={len(selected)}, missing_security_categories={missing_categories}",
            )
    parity_count = 0
    if check_name == "copilot-grounded-answer":
        parity_results = [
            result
            for row in selected
            for result in row.get("grader_results", [])
            if isinstance(result, dict) and result.get("name") == "bilingual_parity"
        ]
        if not parity_results:
            return "Blocked", f"items={len(selected)}, paired parity graders are missing"
        parity_count = len(parity_results)
        failures += sum(result.get("passed") is not True for result in parity_results)
    return (
        "Pass" if failures == 0 else "Fail",
        f"items={len(selected)}, parity_rows={parity_count}, grader_failures={failures}",
    )


def _criterion_check_result(
    acceptance_id: str,
    *,
    check: dict[str, Any],
    source: Path,
    command_by_name: dict[str, dict[str, Any]],
) -> tuple[str, str, list[str]]:
    """Evaluate one criterion from its own machine-readable gate evidence."""
    if not isinstance(check, dict) or not isinstance(check.get("name"), str):
        return "Blocked", f"{acceptance_id} has no named automated check", []
    kind = check.get("kind")
    check_name = check["name"]
    if kind == "accessibility":
        path = source / "automated-tests" / "accessibility.json"
        if not path.is_file():
            return "Blocked", "UI-003 accessibility report is missing", []
        report = _load_json(path)
        failures = {
            "AA": report.get("aa_failure_count", -1),
            "unresolved": report.get("unresolved_incomplete_count", -1),
            "keyboard": report.get("keyboard_failure_count", -1),
            "dynamic keyboard": report.get("dynamic_keyboard_failure_count", -1),
        }
        passed = report.get("passed") is True and all(value == 0 for value in failures.values())
        detail = ", ".join(f"{name}={value}" for name, value in failures.items())
        return (
            "Pass" if passed else "Fail",
            f"{acceptance_id} check {check_name}: {detail}",
            [str(path.relative_to(source))],
        )
    if kind == "eval":
        path = source / "automated-tests" / "eval-summary.json"
        items_path = source / "automated-tests" / "eval-items.jsonl"
        if not path.is_file() or not items_path.is_file():
            return "Blocked", f"{acceptance_id} Eval summary is missing", []
        try:
            summary = _load_json(path)
            rows = [json.loads(line) for line in items_path.read_text().splitlines() if line]
        except (OSError, json.JSONDecodeError, AttributeError):
            return "Blocked", f"{acceptance_id} Eval evidence is invalid", []
        status, detail = _eval_check_result(check_name, summary=summary, rows=rows)
        return (
            status,
            f"{acceptance_id} check {check_name}: {detail}",
            ["automated-tests/eval-summary.json", "automated-tests/eval-items.jsonl"],
        )
    if kind == "release":
        missing = sorted(set(REQUIRED_COMMANDS) - set(command_by_name))
        failed = sorted(
            name for name, result in command_by_name.items() if result.get("exit_code") != 0
        )
        status = "Blocked" if missing else ("Fail" if failed else "Pass")
        return (
            status,
            f"{acceptance_id} check {check_name}: missing={missing}, failed={failed}",
            ["command-results.json", "automated-tests/eval-summary.json"],
        )
    if kind == "e2e":
        evidence = ["automated-tests/e2e-results.json"]
        e2e = command_by_name.get("e2e")
        if e2e is None:
            return "Blocked", f"{acceptance_id} browser command result is missing", evidence
        if e2e.get("exit_code") != 0:
            return "Fail", f"{acceptance_id} browser suite exit={e2e.get('exit_code')}", evidence
        report_path = source / evidence[0]
        try:
            stdout = str(_load_json(report_path).get("stdout", ""))
        except (OSError, json.JSONDecodeError, AttributeError):
            return "Blocked", f"{acceptance_id} browser result is invalid", evidence
        browser_passes = {
            browser: any(
                check_name in line and f"[{browser}" in line and "PASSED" in line
                for line in stdout.splitlines()
            )
            for browser in ("chromium", "webkit")
        }
        if not all(browser_passes.values()):
            return (
                "Blocked",
                f"{acceptance_id} named browser check did not pass in both browsers: "
                f"{check_name}; {browser_passes}",
                evidence,
            )
        return (
            "Pass",
            f"{acceptance_id} named browser check passed in Chromium and WebKit: {check_name}",
            evidence,
        )
    if kind != "pytest":
        return "Blocked", f"{acceptance_id} has unknown check kind: {kind}", []
    evidence = ["automated-tests/pytest.xml"]
    pytest_path = source / "automated-tests" / "pytest.xml"
    if not pytest_path.is_file():
        return "Blocked", f"{acceptance_id} pytest JUnit report is missing", evidence
    try:
        root = ET.parse(pytest_path).getroot()
        cases = [
            (f"{case.get('classname')}::{case.get('name')}", case) for case in root.iter("testcase")
        ]
    except (ET.ParseError, ValueError):
        return "Blocked", f"{acceptance_id} pytest JUnit report is invalid", evidence
    matches = [case for node_id, case in cases if node_id.startswith(check_name)]
    required_case_ids = check.get("required_case_ids")
    if required_case_ids is not None:
        if not isinstance(required_case_ids, list) or not all(
            isinstance(case_id, str) and case_id.startswith("[") and case_id.endswith("]")
            for case_id in required_case_ids
        ):
            return (
                "Blocked",
                f"{acceptance_id} named pytest check has invalid required case identities: "
                f"{check_name}",
                evidence,
            )
        test_name = check_name.split("::", 1)[1]
        expected_names = {f"{test_name}{case_id}" for case_id in required_case_ids}
        observed_names = [str(case.get("name")) for case in matches]
        if (
            len(required_case_ids) != len(set(required_case_ids))
            or len(observed_names) != len(set(observed_names))
            or set(observed_names) != expected_names
        ):
            return (
                "Blocked",
                f"{acceptance_id} named pytest check did not execute each required case: "
                f"{check_name}; expected={sorted(expected_names)}, "
                f"observed={sorted(observed_names)}",
                evidence,
            )
    minimum_cases = int(check.get("minimum_cases", 1))
    if len(matches) < minimum_cases:
        return (
            "Blocked",
            f"{acceptance_id} named pytest check was not fully executed: {check_name}; "
            f"cases={len(matches)}, required={minimum_cases}",
            evidence,
        )
    failed = sum(any(child.tag in {"failure", "error"} for child in list(case)) for case in matches)
    skipped = sum(
        any(child.tag == "skipped" for child in list(case))
        or case.get("status") in {"notrun", "skipped", "disabled"}
        for case in matches
    )
    return (
        "Fail" if failed else ("Blocked" if skipped else "Pass"),
        f"{acceptance_id} named pytest check {check_name}: cases={len(matches)}, "
        f"failed={failed}, skipped={skipped}",
        evidence,
    )


def _criterion_result(
    acceptance_id: str,
    *,
    criterion: dict[str, Any],
    source: Path,
    command_by_name: dict[str, dict[str, Any]],
) -> tuple[str, str, list[str]]:
    checks = [criterion.get("automated_check"), *criterion.get("additional_checks", [])]
    results = [
        _criterion_check_result(
            acceptance_id,
            check=check,
            source=source,
            command_by_name=command_by_name,
        )
        for check in checks
        if isinstance(check, dict)
    ]
    if not results:
        return "Blocked", f"{acceptance_id} has no named automated checks", []
    statuses = [status for status, _detail, _evidence in results]
    status = "Fail" if "Fail" in statuses else ("Blocked" if "Blocked" in statuses else "Pass")
    detail = " | ".join(detail for _status, detail, _evidence in results)
    evidence = list(dict.fromkeys(path for _status, _detail, paths in results for path in paths))
    return status, detail, evidence


def write_acceptance_results(*, source: Path, commit: str, environment: str) -> Path:
    """Create the complete catalog-backed acceptance ledger for already-produced evidence."""
    if not FULL_SHA_PATTERN.fullmatch(commit):
        raise ValueError("acceptance results require a full Git SHA")
    catalog = _catalog()
    visual_by_id = {
        "I18N-001": [
            "screenshots/en/chromium-dashboard.png",
            "screenshots/zh/chromium-dashboard.png",
        ],
        "I18N-002": ["screenshots/zh/webkit-dashboard.png"],
        "I18N-003": ["screenshots/en/chromium-error.png", "screenshots/zh/chromium-error.png"],
        "UI-001": ["screenshots/en/chromium-dashboard.png"],
        "UI-002": [
            "screenshots/narrow/chromium-dashboard.png",
            "screenshots/narrow/chromium-job-detail.png",
            "screenshots/narrow/chromium-copilot.png",
            "browser-results/traces/chromium-narrow-primary-loop.zip",
            "browser-results/traces/webkit-narrow-primary-loop.zip",
        ],
        "UI-003": ["screenshots/en/webkit-dashboard.png"],
        "JOB-001": ["screenshots/en/chromium-job-detail.png"],
        "WATCH-003": ["screenshots/zh/chromium-watch-list.png"],
        "WATCH-006": ["screenshots/en/webkit-watch-list.png"],
        "CV-002": ["screenshots/en/chromium-cv-library.png"],
        "CHAT-005": [
            "screenshots/en/chromium-copilot-confirmation.png",
            "screenshots/zh/chromium-copilot-confirmation.png",
            "browser-results/traces/chromium-copilot-confirmation.zip",
            "browser-results/traces/webkit-copilot-confirmation.zip",
        ],
        "DASH-001": ["screenshots/en/webkit-dashboard.png"],
    }
    command_results = _load_json(source / "command-results.json")
    command_by_name = {
        str(result.get("name")): result for result in command_results if isinstance(result, dict)
    }
    tested_at = _utc_now()
    records: list[dict[str, Any]] = []
    for acceptance_id, criterion in catalog.items():
        status, actual_result, automated = _criterion_result(
            acceptance_id,
            criterion=criterion,
            source=source,
            command_by_name=command_by_name,
        )
        visual = visual_by_id.get(acceptance_id, [])
        if criterion.get("visual_required") and not visual:
            raise RuntimeError(f"catalog visual mapping missing: {acceptance_id}")
        for relative_name in [*automated, *visual]:
            if not (source / relative_name).is_file() and status == "Pass":
                status = "Blocked"
                actual_result = f"{acceptance_id} evidence missing: {relative_name}"
        records.append(
            {
                "id": acceptance_id,
                "requirement": f"V1 acceptance criterion {acceptance_id}",
                "preconditions": "Clean candidate commit; isolated synthetic/redacted fixtures",
                "steps": (
                    "Run every named check from the acceptance catalog for this commit: "
                    + ", ".join(
                        check["name"]
                        for check in [
                            criterion["automated_check"],
                            *criterion.get("additional_checks", []),
                        ]
                    )
                ),
                "expected_result": "The criterion passes with fresh, hashed evidence",
                "automated_evidence": automated,
                "visual_evidence": visual,
                "actual_result": actual_result,
                "status": status,
                "tested_at": tested_at,
                "environment": environment,
                "commit": commit,
                "linked_defect": None,
                "must": bool(criterion.get("must", True)),
            }
        )
    output = source / "acceptance-results.json"
    output.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    return output


def record_command(
    *,
    source: Path,
    name: str,
    output_relative: Path,
    command: list[str],
    cwd: Path,
) -> dict[str, Any]:
    """Execute one evidence command and atomically append its observed result."""
    if not command:
        raise ValueError("An evidence command is required")
    output_path = source / output_relative
    output_path.parent.mkdir(parents=True, exist_ok=True)
    commit = _git_output(cwd, "rev-parse", "HEAD")
    dirty = bool(_git_output(cwd, "status", "--porcelain"))
    commit_time = _git_output(cwd, "show", "-s", "--format=%cI", "HEAD")
    if name in REQUIRED_COMMANDS:
        if not _canonical_command(name, shlex.join(command), str(source.resolve())):
            raise ValueError(f"non-canonical command: {name}")
        resolved_executable = _trusted_executable(name)
    else:
        resolved_executable = _resolve_requested_executable(command[0])
    executed_command = [str(resolved_executable), *command[1:]]
    started_at = _utc_now()
    command_env = os.environ.copy()
    command_env.update(ROLERADAR_EVIDENCE_COMMIT=commit, ROLERADAR_EVIDENCE_RUN_ID=started_at)
    completed = subprocess.run(
        executed_command, cwd=cwd, capture_output=True, text=True, check=False, env=command_env
    )
    ended_at = _utc_now()
    result: dict[str, Any] = {
        "name": name,
        "command": shlex.join(command),
        "exit_code": completed.returncode,
        "started_at": started_at,
        "ended_at": ended_at,
        "output": str(output_relative),
        "git_commit": commit,
        "dirty_worktree": dirty,
        "commit_time": commit_time,
        "artifacts": list(COMMAND_OUTPUTS.get(name, (str(output_relative),))),
        "executable": executable_identity(
            command[0], name=name if name in REQUIRED_COMMANDS else None
        ),
        "argv": command[1:],
        "evidence_source": str(source.resolve()),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    if output_path.suffix == ".json":
        output_path.write_text(
            json.dumps(result, indent=2) + "\n",
            encoding="utf-8",
        )
    else:
        output_path.write_text(completed.stdout + completed.stderr, encoding="utf-8")
    digest_paths = set(result["artifacts"]) - (
        {str(output_relative)} if output_path.suffix == ".json" else set()
    )
    result["artifact_hashes"] = {
        relative: _sha256(source / relative)
        for relative in sorted(digest_paths)
        if (source / relative).is_file()
    }
    if output_path.suffix == ".json":
        output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    results_path = source / "command-results.json"
    results = _load_json(results_path) if results_path.is_file() else []
    if not isinstance(results, list):
        raise RuntimeError("command-results.json must contain an array")
    if any(item.get("name") == name for item in results if isinstance(item, dict)):
        raise RuntimeError(f"Refusing to overwrite command result: {name}")
    results.append(result)
    pending = results_path.with_suffix(".json.pending")
    pending.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    pending.replace(results_path)
    return result


def _version_map(value: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for entry in value.split(","):
        name, separator, version = entry.partition("=")
        if separator and name.strip() and version.strip():
            result[name.strip()] = version.strip()
    return result


def _used_timestamps(output_root: Path) -> set[str]:
    timestamps: set[str] = set()
    for path in output_root.glob("*/*/manifest.json"):
        try:
            value = _load_json(path).get("started_at")
        except (OSError, json.JSONDecodeError, AttributeError):
            continue
        if isinstance(value, str):
            timestamps.add(value)
    return timestamps


def _summary(manifest: dict[str, Any], validation: ManifestValidation) -> str:
    status = "READY" if validation.release_ready else "NOT READY"
    lines = [
        "# RoleRadar AI acceptance evidence",
        "",
        f"- Release gate: **{status}**",
        f"- Version: `{manifest['version']}`",
        f"- Commit: `{manifest['git_commit']}`",
        f"- Started: `{manifest['started_at']}`",
        f"- Ended: `{manifest['ended_at']}`",
        "",
        "## Required commands",
        "",
    ]
    lines.extend(
        f"- `{command['name']}`: exit `{command['exit_code']}` — `{command['command']}`"
        for command in manifest["commands"]
    )
    lines.extend(["", "## Gate findings", ""])
    lines.extend(f"- {error}" for error in validation.errors)
    if not validation.errors:
        lines.append("- None")
    lines.extend(["", "## Known P2 items", ""])
    p2_items = [
        item
        for item in manifest.get("open_defects", [])
        if isinstance(item, dict) and item.get("severity") == "P2"
    ]
    if not p2_items:
        lines.append("- None")
    for item in p2_items:
        lines.append(
            f"- {item.get('id', 'unknown')} (P2): {item.get('description', '')}; "
            f"route={item.get('route', '')}; viewport={item.get('viewport', '')}; "
            f"evidence={item.get('evidence', [])}; impact={item.get('primary_loop_impact', '')}"
        )
    lines.append("")
    return "\n".join(lines)


def build_bundle(args: argparse.Namespace) -> tuple[Path, ManifestValidation]:
    repo = args.repo.resolve()
    source = args.source.resolve()
    output_root = args.output_root.resolve()
    commit = _git_output(repo, "rev-parse", "HEAD")
    dirty = bool(_git_output(repo, "status", "--porcelain"))
    if dirty:
        raise RuntimeError("A dirty worktree cannot produce release evidence")
    if not FULL_SHA_PATTERN.fullmatch(commit):
        raise RuntimeError("Git did not return a full commit SHA")
    if not source.is_dir():
        raise RuntimeError(f"Evidence source does not exist: {source}")

    destination = output_root / args.version / commit
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite existing evidence bundle: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)

    command_results = _load_json(source / "command-results.json")
    acceptance_results = _load_json(source / "acceptance-results.json")
    if not isinstance(command_results, list) or not isinstance(acceptance_results, list):
        raise RuntimeError("command-results.json and acceptance-results.json must contain arrays")
    starts = [str(result.get("started_at")) for result in command_results]
    ends = [str(result.get("ended_at")) for result in command_results]
    started_at = min(starts)
    ended_at = max(ends)

    with tempfile.TemporaryDirectory(prefix="roleradar-evidence-", dir=destination.parent) as temp:
        pending = Path(temp) / commit
        shutil.copytree(source, pending)
        hashes = {
            str(path.relative_to(pending)): _sha256(path)
            for path in sorted(pending.rglob("*"))
            if path.is_file() and path.name not in {"manifest.json", "summary.md"}
        }
        manifest: dict[str, Any] = {
            "schema_version": 2,
            "version": args.version,
            "git_commit": commit,
            "dirty_worktree": False,
            "started_at": started_at,
            "ended_at": ended_at,
            "runtime": {
                "os": platform.platform(),
                "python": platform.python_version(),
                "node": args.node_version,
                "streamlit": package_version("streamlit"),
            },
            "browsers": _version_map(args.browser_versions),
            "model_id": args.model_id,
            "prompt_version": args.prompt_version,
            "rubric_version": args.rubric_version,
            "dataset_version": args.dataset_version,
            "commands": command_results,
            "acceptance": acceptance_results,
            "open_defects": _load_json(source / "open-defects.json")
            if (source / "open-defects.json").is_file()
            else [],
            "hashes": hashes,
        }
        validation = validate_release_manifest(
            manifest,
            pending,
            expected_commit=commit,
            used_started_at=_used_timestamps(output_root),
        )
        manifest["release_ready"] = validation.release_ready
        manifest["validation_errors"] = list(validation.errors)
        (pending / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (pending / "summary.md").write_text(_summary(manifest, validation), encoding="utf-8")
        os.rename(pending, destination)
    return destination, validation


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=Path("artifacts/acceptance"))
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--version", default="v1")
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--prompt-version", required=True)
    parser.add_argument("--rubric-version", required=True)
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--browser-versions", required=True)
    parser.add_argument("--node-version", default="unknown")
    return parser.parse_args(argv)


def parse_record_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record one acceptance command")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if args.command[:1] == ["--"]:
        args.command = args.command[1:]
    if not args.command:
        parser.error("a command is required after --")
    return args


def parse_acceptance_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write complete acceptance results")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--environment", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments[:1] == ["acceptance"]:
        try:
            options = parse_acceptance_args(arguments[1:])
            output = write_acceptance_results(
                source=options.source.resolve(),
                commit=options.commit,
                environment=options.environment,
            )
        except (RuntimeError, ValueError, OSError, json.JSONDecodeError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(output)
        return 0
    if arguments[:1] == ["record"]:
        try:
            options = parse_record_args(arguments[1:])
            result = record_command(
                source=options.source.resolve(),
                name=options.name,
                output_relative=options.output,
                command=options.command,
                cwd=options.repo.resolve(),
            )
        except (RuntimeError, ValueError, OSError, json.JSONDecodeError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        output = options.source.resolve() / options.output
        print(output.read_text(encoding="utf-8"), end="")
        return int(result["exit_code"])
    try:
        destination, validation = build_bundle(parse_args(arguments))
    except (
        FileExistsError,
        RuntimeError,
        subprocess.CalledProcessError,
        json.JSONDecodeError,
    ) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"bundle={destination}")
    print(f"release_ready={str(validation.release_ready).lower()}")
    for error in validation.errors:
        print(f"error={error}")
    return 0 if validation.release_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
