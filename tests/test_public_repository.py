"""Regression checks for the repository surface visible to a signed-out visitor."""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LOCAL_ACCOUNT_PATH = "/Users/" + "shen"


def scan_tracked_public_risks(repo_root: Path) -> list[str]:
    """Return public-release risks present in Git-tracked files."""
    tracked_paths = subprocess.run(
        ["git", "ls-files"],
        check=True,
        cwd=repo_root,
        capture_output=True,
        text=True,
    ).stdout.splitlines()

    risks: list[str] = []
    private_path_markers = (
        ".env",
        ".db",
        ".sqlite",
        "data/cv_library/",
        "data/generated_cvs/",
        "private-evidence/",
        "release-evidence/",
        ".superpowers/",
    )
    for tracked_path in tracked_paths:
        normalized_path = tracked_path.lower()
        if tracked_path != ".env.example" and any(
            marker in normalized_path for marker in private_path_markers
        ):
            risks.append(f"private runtime artifact is tracked: {tracked_path}")

        if tracked_path.endswith(".md"):
            document = repo_root / tracked_path
            if LOCAL_ACCOUNT_PATH in document.read_text(encoding="utf-8"):
                risks.append(f"absolute user path is tracked: {tracked_path}")

    return risks


def test_tracked_files_exclude_private_runtime_artifacts() -> None:
    """Catches accidentally staging local credentials, CV data, or agent artifacts."""
    risks = scan_tracked_public_risks(REPO_ROOT)

    assert not [risk for risk in risks if "private runtime artifact" in risk]


def test_tracked_docs_exclude_absolute_user_paths() -> None:
    """Catches a local workstation path leaking into public-facing documentation."""
    risks = scan_tracked_public_risks(REPO_ROOT)

    assert not [risk for risk in risks if "absolute user path" in risk]


def test_readme_declares_demo_privacy_and_current_limits() -> None:
    """Catches a README that overpromises public-demo handling or capabilities."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert "not stored" in readme.lower()
    assert "runnable Eval Harness" in readme
    assert "Current limitations" in readme
