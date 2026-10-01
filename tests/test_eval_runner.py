import json
from pathlib import Path

import pytest

from app.evals.contracts import DatasetValidationError, load_dataset
from app.evals.runner import run_dataset


def _item(item_id: str, suite: str = "jd", **overrides):
    item = {
        "dataset_version": "v1",
        "id": item_id,
        "suite": suite,
        "locale": "en",
        "synthetic": True,
        "redaction_marker": "[SYNTHETIC]",
        "input": {"text": "[SYNTHETIC] Build applied AI systems."},
        "expected": {
            "classification_label": "Applied AI Engineer",
            "score_range": [70, 85],
            "recommendation": "Strong Apply",
        },
        "grader_version": "v1",
        "model_id": "deterministic",
        "prompt_version": "none",
        "user_review_required": False,
        "release_critical": False,
    }
    item.update(overrides)
    return item


def _write(path: Path, items: list[dict]) -> None:
    path.write_text("".join(json.dumps(item) + "\n" for item in items), encoding="utf-8")


def test_dataset_rejects_duplicate_ids_and_private_looking_values(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.jsonl"
    _write(duplicate, [_item("same"), _item("same")])
    with pytest.raises(DatasetValidationError, match="unique"):
        load_dataset(duplicate, enforce_minimums=False)

    private = tmp_path / "private.jsonl"
    _write(private, [_item("private", input={"text": "person@example.com +852 9123 4567"})])
    with pytest.raises(DatasetValidationError, match="private-looking"):
        load_dataset(private, enforce_minimums=False)


def test_dataset_rejects_committed_actual_output(tmp_path: Path) -> None:
    supplied_output = tmp_path / "supplied-output.jsonl"
    _write(supplied_output, [_item("supplied", actual={"recommendation": "Must Apply"})])

    with pytest.raises(DatasetValidationError, match="actual"):
        load_dataset(supplied_output, enforce_minimums=False)


@pytest.mark.parametrize("forbidden_key", ["actual", "output_claims"])
def test_dataset_rejects_candidate_output_hidden_inside_input(
    tmp_path: Path, forbidden_key: str
) -> None:
    supplied_output = tmp_path / "supplied-output.jsonl"
    _write(
        supplied_output,
        [
            _item(
                "cv-supplied",
                suite="cv_pair",
                input={
                    "source_claims": ["[SYNTHETIC] Built reliable AI systems."],
                    forbidden_key: ["[SYNTHETIC] Claimed candidate output."],
                },
                expected={"unsupported_claims": 0, "docx_required": True},
            )
        ],
    )

    with pytest.raises(DatasetValidationError, match="candidate output"):
        load_dataset(supplied_output, enforce_minimums=False)


def test_dataset_requires_labels_ranges_redaction_and_valid_bilingual_pairs(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.jsonl"
    _write(
        invalid,
        [
            _item(
                "zh",
                locale="zh-Hans",
                release_critical=True,
                pair_id="missing-en",
                redaction_marker="",
                expected={"score_range": [90, 70]},
            )
        ],
    )

    with pytest.raises(DatasetValidationError) as error:
        load_dataset(invalid, enforce_minimums=False)

    message = str(error.value)
    assert "redaction" in message
    assert "score_range" in message
    assert "bilingual pair" in message


def test_committed_dataset_meets_minimum_counts_and_review_range() -> None:
    dataset = load_dataset(Path("evals/datasets/v1.jsonl"))
    counts = dataset.suite_counts

    assert counts == {"jd": 60, "cv_pair": 20, "copilot_normal": 30, "copilot_adversarial": 20}
    review_count = sum(item.user_review_required for item in dataset.items if item.suite == "jd")
    assert 20 <= review_count <= 30


def test_runner_writes_privacy_safe_versioned_reports(tmp_path: Path) -> None:
    result = run_dataset(Path("evals/datasets/v1.jsonl"), tmp_path)
    summary = json.loads((tmp_path / "eval-summary.json").read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in (tmp_path / "eval-items.jsonl").read_text().splitlines()]

    assert result.passed is True
    assert summary["dataset_version"] == "v1"
    assert summary["dataset_hash"].startswith("sha256:")
    assert len(rows) == 130
    assert all(row["dataset_hash"] == summary["dataset_hash"] for row in rows)
    assert all(row["item_hash"].startswith("sha256:") for row in rows)
    assert all(row["input_hash"].startswith("sha256:") for row in rows)
    assert all("input" not in row and "private_text" not in row for row in rows)
    assert all(
        {"output_hash", "grader_version", "model_id", "prompt_version", "latency_ms"} <= row.keys()
        for row in rows
    )


def test_release_runner_uses_observed_adapter_output_not_dataset_actual(tmp_path: Path) -> None:
    class BrokenRuntimeAdapter:
        model_id = "broken-runtime"
        prompt_version = "none"

        def evaluate(self, item):
            if item.suite == "jd":
                return {
                    "classification_label": "Project Management",
                    "scores": [0, 0],
                    "recommendation": "Skip",
                    "available_evidence_ids": ["jd-title"],
                    "evidence_ids": ["jd-title"],
                }
            if item.suite == "cv_pair":
                return {
                    "source_claim_ids": ["source"],
                    "output_claim_ids": ["invented"],
                    "docx_structure_valid": False,
                }
            return {"action": "refuse", "write_count": 99}

    result = run_dataset(Path("evals/datasets/v1.jsonl"), tmp_path, adapter=BrokenRuntimeAdapter())
    rows = [json.loads(line) for line in (tmp_path / "eval-items.jsonl").read_text().splitlines()]

    assert result.passed is False
    assert result.failed_items > 0
    assert result.zero_tolerance_failures > 0
    assert rows[0]["output"]["classification_label"] == "Project Management"
    assert rows[0]["model_id"] == "broken-runtime"
