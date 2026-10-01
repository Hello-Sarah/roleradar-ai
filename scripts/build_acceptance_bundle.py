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
    command_by_name = (
        {
            str(command.get("name")): command
            for command in commands
            if isinstance(command, dict) and command.get("name")
        }
        if isinstance(commands, list)
        else {}
    )
    for name in REQUIRED_COMMANDS:
        command = command_by_name.get(name)
        if command is None:
            errors.append(f"missing required command result: {name}")
            continue
        if command.get("exit_code") != 0:
            errors.append(f"required command failed: {name}")
        if not command.get("command"):
            errors.append(f"required command text missing: {name}")
        command_start = _parse_utc(command.get("started_at"))
        command_end = _parse_utc(command.get("ended_at"))
        if command_start is None or command_end is None or command_end < command_start:
            errors.append(f"invalid command time range: {name}")

    for group, required_names in REQUIRED_SCREENSHOTS.items():
        screenshot_names = [path.name for path in _screenshot_files(bundle_dir, group)]
        for required_name in required_names:
            if not any(
                name == f"{required_name}.png" or name.endswith(f"-{required_name}.png")
                for name in screenshot_names
            ):
                errors.append(f"missing screenshot evidence: {group}/{required_name}")

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

    acceptance = manifest.get("acceptance")
    if not isinstance(acceptance, list) or not acceptance:
        errors.append("missing acceptance records")
    else:
        for record in acceptance:
            if not isinstance(record, dict):
                errors.append("invalid acceptance record")
                continue
            if record.get("must", True) and record.get("status") != "Pass":
                errors.append(f"Must acceptance is not Pass: {record.get('id', 'unknown')}")
            if record.get("commit") != expected_commit:
                errors.append(f"acceptance commit does not match: {record.get('id', 'unknown')}")

    for defect in manifest.get("open_defects", []):
        if isinstance(defect, dict) and defect.get("severity") in {"P0", "P1"}:
            errors.append(f"open {defect['severity']} defect: {defect.get('id', 'unknown')}")

    hashes = manifest.get("hashes")
    if not isinstance(hashes, dict) or not hashes:
        errors.append("missing evidence hashes")
    else:
        for relative_name, expected_hash in hashes.items():
            path = bundle_dir / str(relative_name)
            if not path.is_file():
                errors.append(f"hashed evidence file is missing: {relative_name}")
            elif _sha256(path) != expected_hash:
                errors.append(f"evidence hash mismatch: {relative_name}")

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


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
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
