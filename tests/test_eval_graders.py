from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from app.evals.adapters import DeterministicReleaseAdapter
from app.evals.contracts import load_dataset
from app.evals.graders import (
    grade_bilingual_parity,
    grade_cv_case,
    grade_docx_structure,
    grade_evidence_ids,
    grade_schema,
    grade_score_stability,
    grade_write_counts,
)


def test_unsupported_cv_claim_fails_even_when_composite_is_high() -> None:
    result = grade_cv_case(
        expected_claim_ids={"cv-1", "cv-2"},
        output_claim_ids={"cv-1", "cv-2", "invented"},
        other_metric_scores={"structure": 1.0, "clarity": 1.0, "relevance": 1.0},
    )

    assert result.passed is False
    assert result.metrics["unsupported_claims"] == 1
    assert result.zero_tolerance_failure is True


def test_deterministic_contract_graders() -> None:
    schema = grade_schema({"score": 70}, required_fields={"score"})
    score = grade_score_stability([70, 70, 70], expected_range=(70, 85))
    evidence = grade_evidence_ids({"jd-1", "jd-2"}, ["jd-1"])
    writes = grade_write_counts(actual=0, maximum=0)
    parity = grade_bilingual_parity(
        {"score": 70, "class": "Applied AI", "evidence_ids": ["jd-1"]},
        {"score": 70, "class": "Applied AI", "evidence_ids": ["jd-1"]},
    )

    assert all(result.passed for result in (schema, score, evidence, writes, parity))


@pytest.mark.parametrize(
    ("field", "mismatched_value"),
    [
        ("classification_label", "Project Management"),
        ("recommendation", "Skip"),
        ("scores", [45, 45]),
    ],
)
def test_jd_bilingual_parity_rejects_actual_contract_mismatches(
    field: str, mismatched_value: object
) -> None:
    english = {
        "classification_label": "Applied AI Engineer",
        "recommendation": "Strong Apply",
        "scores": [75, 75],
        "available_evidence_ids": ["jd-title", "jd-001"],
        "evidence_ids": ["jd-001"],
    }
    chinese = {**english, field: mismatched_value}

    result = grade_bilingual_parity(english, chinese)

    assert result.passed is False
    assert result.metrics["mismatches"] == 1


def test_matching_release_critical_jd_pair_passes_bilingual_parity() -> None:
    dataset = load_dataset(Path("evals/datasets/v1.jsonl"))
    english = next(
        item
        for item in dataset.items
        if item.suite == "jd" and item.locale == "en" and item.pair_id
    )
    chinese = next(item for item in dataset.items if item.id == english.pair_id)

    adapter = DeterministicReleaseAdapter()
    assert (
        grade_bilingual_parity(adapter.evaluate(english), adapter.evaluate(chinese)).passed is True
    )


def test_copilot_bilingual_parity_compares_action_and_write_count() -> None:
    left = {"action": "refuse", "write_count": 0, "answer": "English localized prose"}
    right = {"action": "refuse", "write_count": 1, "answer": "中文本地化文本"}

    result = grade_bilingual_parity(left, right)

    assert result.passed is False
    assert result.metrics["compared_fields"] == 2


def test_docx_structure_grader_requires_a_valid_document() -> None:
    stream = BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="urn:test"><w:body><w:p><w:r>'
            "<w:t>Evidence-backed experience</w:t></w:r></w:p></w:body></w:document>",
        )

    assert grade_docx_structure(stream.getvalue()).passed is True
    assert grade_docx_structure(b"not a docx").passed is False
