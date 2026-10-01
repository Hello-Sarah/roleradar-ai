import json
import subprocess
from pathlib import Path


def _run_fixture(tmp_path: Path, payload: dict) -> tuple[subprocess.CompletedProcess[str], dict]:
    fixture = tmp_path / "fixture.json"
    output = tmp_path / "report.json"
    fixture.write_text(json.dumps(payload), encoding="utf-8")
    completed = subprocess.run(
        [
            "node",
            "scripts/run_accessibility.mjs",
            "--audit-fixture",
            str(fixture),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return completed, json.loads(output.read_text(encoding="utf-8"))


def test_wcag_aa_serious_violation_blocks_release(tmp_path: Path) -> None:
    completed, report = _run_fixture(
        tmp_path,
        {
            "streamlit_version": "1.62.0",
            "routes": [
                {
                    "route": "Dashboard",
                    "violations": [
                        {
                            "id": "color-contrast",
                            "impact": "serious",
                            "tags": ["wcag2aa"],
                            "nodes": [{"target": ["button"], "failureSummary": "4.08:1"}],
                        }
                    ],
                    "incomplete": [],
                    "keyboard": {"all_controls_reached": True, "all_controls_named": True},
                }
            ],
        },
    )

    assert completed.returncode == 1
    assert report["passed"] is False
    assert report["aa_failure_count"] == 1


def test_sidebar_suppression_requires_reviewed_streamlit_version(tmp_path: Path) -> None:
    sidebar = {
        "id": "aria-allowed-attr",
        "impact": "critical",
        "tags": ["wcag2a"],
        "nodes": [
            {
                "target": [".stSidebar"],
                "failureSummary": 'ARIA attribute is not allowed: aria-expanded="true"',
            }
        ],
    }
    completed, report = _run_fixture(
        tmp_path,
        {
            "streamlit_version": "1.63.0",
            "routes": [
                {
                    "route": "Dashboard",
                    "violations": [sidebar],
                    "incomplete": [],
                    "keyboard": {"all_controls_reached": True, "all_controls_named": True},
                }
            ],
        },
    )

    assert completed.returncode == 1
    assert report["suppressed_findings"] == []
    assert report["suppression_policy"]["reviewed_streamlit_version"] == "1.62.0"
    assert "re-review" in report["suppression_policy"]["status"]


def test_reviewed_passing_incomplete_is_reported_without_false_failure(tmp_path: Path) -> None:
    completed, report = _run_fixture(
        tmp_path,
        {
            "streamlit_version": "1.62.0",
            "routes": [
                {
                    "route": "Dashboard",
                    "violations": [],
                    "incomplete": [
                        {
                            "id": "color-contrast",
                            "impact": "serious",
                            "nodes": [{"target": [".caption"]}],
                        }
                    ],
                    "incomplete_reviews": [
                        {
                            "rule_id": "color-contrast",
                            "target": ".caption",
                            "status": "pass",
                            "contrast_ratio": 7.1,
                            "required_ratio": 4.5,
                        }
                    ],
                    "keyboard": {
                        "all_controls_reached": True,
                        "all_controls_named": True,
                        "all_focus_visible": True,
                    },
                }
            ],
        },
    )

    assert completed.returncode == 0
    assert report["passed"] is True
    assert report["incomplete_review_count"] == 1
    assert report["unresolved_incomplete_count"] == 0


def test_missing_dynamic_keyboard_activation_blocks_release(tmp_path: Path) -> None:
    completed, report = _run_fixture(
        tmp_path,
        {
            "streamlit_version": "1.62.0",
            "routes": [
                {
                    "route": "Dashboard",
                    "violations": [],
                    "incomplete": [],
                    "keyboard": {
                        "all_controls_reached": True,
                        "all_controls_named": True,
                        "all_focus_visible": True,
                    },
                }
            ],
            "dynamic_states": [
                {
                    "state": "extracted-review",
                    "keyboard": {
                        "all_controls_reached": True,
                        "all_controls_named": True,
                        "all_focus_visible": True,
                    },
                    "activation": {"control": "Confirm & analyze", "passed": False},
                }
            ],
        },
    )

    assert completed.returncode == 1
    assert report["passed"] is False
    assert report["dynamic_keyboard_failure_count"] == 1


def test_live_keyboard_runner_activates_every_dynamic_primary_action() -> None:
    source = Path("scripts/run_accessibility.mjs").read_text(encoding="utf-8")

    for state in (
        "status-change",
        "cv-scan",
        "cv-generation",
        "copilot-context",
        "copilot-proposal",
        "copilot-cancelled",
        "copilot-confirmed",
    ):
        assert f'"{state}"' in source
    for control in (
        "Application status",
        "Scan CV folder",
        "Generate tailored CV",
        "Open Career Copilot",
        "Cancel",
        "Confirm action",
    ):
        assert control in source
    assert 'control: "Persistent Career Copilot panel",\n      passed: true' not in source
