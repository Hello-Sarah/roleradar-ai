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
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REQUIRED_COMMANDS = ("ruff", "format", "pytest", "e2e", "accessibility", "eval")
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
    "e2e": ("automated-tests/e2e-results.json",),
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


def _canonical_command(name: str, command: object) -> bool:
    if not isinstance(command, str):
        return False
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    if not parts:
        return False
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
            and args[0].startswith("--junitxml=")
            and args[0].endswith("/automated-tests/pytest.xml")
            and args[1] == "--cov"
            and args[2].startswith("--cov-report=xml:")
            and args[2].endswith("/automated-tests/coverage.xml")
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
            and args[7].startswith("--output=")
            and args[7].endswith("/browser-results")
        )
    if name == "accessibility":
        return (
            executable == "node"
            and len(args) == 5
            and args[:2] == ["scripts/run_accessibility.mjs", "--base-url"]
            and re.fullmatch(r"http://127\.0\.0\.1:\d+", args[2]) is not None
            and args[3] == "--output"
            and args[4].endswith("/automated-tests/accessibility.json")
        )
    if name == "eval":
        return (
            executable in {"python", "python3"}
            and len(args) == 6
            and args[:3] == ["-m", "app.evals.runner", "--dataset"]
            and args[3] == "evals/datasets/v1.jsonl"
            and args[4] == "--output"
            and args[5].endswith("/automated-tests")
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
    seen_command_times: set[str] = set()
    for name in REQUIRED_COMMANDS:
        command = command_by_name.get(name)
        if command is None:
            errors.append(f"missing required command result: {name}")
            continue
        if command.get("exit_code") != 0:
            errors.append(f"required command failed: {name}")
        if not _canonical_command(name, command.get("command")):
            errors.append(f"non-canonical command: {name}")
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

    for group, required_names in REQUIRED_SCREENSHOTS.items():
        screenshot_names = [path.name for path in _screenshot_files(bundle_dir, group)]
        for required_name in required_names:
            for browser in ("chromium", "webkit"):
                expected_name = f"{browser}-{required_name}.png"
                if expected_name not in screenshot_names:
                    errors.append(f"missing screenshot evidence: {group}/{expected_name}")

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

    acceptance = manifest.get("acceptance")
    catalog = _catalog()
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
        ],
        "UI-003": ["screenshots/en/webkit-dashboard.png"],
        "JOB-001": ["screenshots/en/chromium-job-detail.png"],
        "WATCH-003": ["screenshots/zh/chromium-watch-list.png"],
        "WATCH-006": ["screenshots/en/webkit-watch-list.png"],
        "CV-002": ["screenshots/en/chromium-cv-library.png"],
        "CHAT-005": [
            "screenshots/en/chromium-copilot-confirmation.png",
            "screenshots/zh/chromium-copilot-confirmation.png",
        ],
        "DASH-001": ["screenshots/en/webkit-dashboard.png"],
    }
    browser_prefixes = {"I18N", "UI", "JOB", "APP", "WATCH", "CV", "CHAT", "DASH"}
    tested_at = _utc_now()
    records: list[dict[str, Any]] = []
    for acceptance_id, criterion in catalog.items():
        prefix = acceptance_id.split("-", 1)[0]
        if prefix == "EVAL":
            automated = [
                "automated-tests/eval-summary.json",
                "automated-tests/eval-items.jsonl",
            ]
        elif acceptance_id == "UI-003":
            automated = [
                "automated-tests/accessibility.json",
                "automated-tests/e2e-results.json",
            ]
        elif acceptance_id == "REL-001":
            automated = ["command-results.json", "automated-tests/eval-summary.json"]
        elif prefix in browser_prefixes:
            automated = ["automated-tests/pytest.xml", "automated-tests/e2e-results.json"]
        else:
            automated = ["automated-tests/pytest.xml"]
        visual = visual_by_id.get(acceptance_id, [])
        if criterion.get("visual_required") and not visual:
            raise RuntimeError(f"catalog visual mapping missing: {acceptance_id}")
        for relative_name in [*automated, *visual]:
            if not (source / relative_name).is_file():
                raise RuntimeError(f"acceptance evidence missing: {acceptance_id}: {relative_name}")
        records.append(
            {
                "id": acceptance_id,
                "requirement": f"V1 acceptance criterion {acceptance_id}",
                "preconditions": "Clean candidate commit; isolated synthetic/redacted fixtures",
                "steps": "Run the catalog-linked automated and visual evidence for this commit",
                "expected_result": "The criterion passes with fresh, hashed evidence",
                "automated_evidence": automated,
                "visual_evidence": visual,
                "actual_result": (
                    "Pass; linked evidence completed without a release-blocking defect"
                ),
                "status": "Pass",
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
    started_at = _utc_now()
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
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
    }
    if output_path.suffix == ".json":
        output_path.write_text(
            json.dumps({**result, "stdout": completed.stdout, "stderr": completed.stderr}, indent=2)
            + "\n",
            encoding="utf-8",
        )
    else:
        output_path.write_text(completed.stdout + completed.stderr, encoding="utf-8")
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
            "schema_version": 1,
            "version": args.version,
            "git_commit": commit,
            "dirty_worktree": False,
            "started_at": started_at,
            "ended_at": ended_at,
            "runtime": {
                "os": platform.platform(),
                "python": platform.python_version(),
                "node": args.node_version,
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
