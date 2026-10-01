from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

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
