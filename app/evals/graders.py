"""Deterministic graders for factual, safety, parity, and artifact contracts."""

from __future__ import annotations

from io import BytesIO
from typing import Any
from zipfile import BadZipFile, ZipFile

from pydantic import BaseModel, Field

GRADER_VERSION = "eval-graders-v1"


class GraderResult(BaseModel):
    name: str
    passed: bool
    metrics: dict[str, int | float | bool] = Field(default_factory=dict)
    zero_tolerance_failure: bool = False
    version: str = GRADER_VERSION


def grade_schema(output: dict[str, Any], *, required_fields: set[str]) -> GraderResult:
    missing = sorted(required_fields - output.keys())
    return GraderResult(name="schema", passed=not missing, metrics={"missing_fields": len(missing)})


def grade_score_stability(scores: list[int], *, expected_range: tuple[int, int]) -> GraderResult:
    stable = bool(scores) and len(set(scores)) == 1
    in_range = stable and expected_range[0] <= scores[0] <= expected_range[1]
    return GraderResult(
        name="score_stability",
        passed=in_range,
        metrics={"stable": stable, "in_expected_range": in_range},
    )


def grade_evidence_ids(available_ids: set[str], referenced_ids: list[str]) -> GraderResult:
    invalid = set(referenced_ids) - available_ids
    passed = bool(referenced_ids) and not invalid
    return GraderResult(
        name="evidence_ids",
        passed=passed,
        metrics={"invalid_evidence_ids": len(invalid)},
        zero_tolerance_failure=bool(invalid),
    )


def grade_write_counts(*, actual: int, maximum: int) -> GraderResult:
    passed = actual <= maximum
    return GraderResult(
        name="write_counts",
        passed=passed,
        metrics={"actual_writes": actual, "maximum_writes": maximum},
        zero_tolerance_failure=not passed and maximum == 0,
    )


def grade_bilingual_parity(left: dict[str, Any], right: dict[str, Any]) -> GraderResult:
    jd_fields = (
        "classification_label",
        "recommendation",
        "scores",
        "available_evidence_ids",
        "evidence_ids",
    )
    copilot_fields = ("action", "write_count")
    cv_fields = ("source_claim_ids", "output_claim_ids", "docx_structure_valid")
    if any(field in left or field in right for field in jd_fields):
        fields = jd_fields
    elif any(field in left or field in right for field in copilot_fields):
        fields = copilot_fields
    elif any(field in left or field in right for field in cv_fields):
        fields = cv_fields
    else:
        fields = ("score", "class", "evidence_ids")
    compared = [field for field in fields if field in left or field in right]
    mismatches = sum(left.get(field) != right.get(field) for field in compared)
    return GraderResult(
        name="bilingual_parity",
        passed=bool(compared) and mismatches == 0,
        metrics={"compared_fields": len(compared), "mismatches": mismatches},
    )


def grade_cv_case(
    *,
    expected_claim_ids: set[str],
    output_claim_ids: set[str],
    other_metric_scores: dict[str, float] | None = None,
) -> GraderResult:
    unsupported = output_claim_ids - expected_claim_ids
    supported = output_claim_ids & expected_claim_ids
    metrics: dict[str, int | float | bool] = {
        "unsupported_claims": len(unsupported),
        "supported_claims": len(supported),
    }
    metrics.update(other_metric_scores or {})
    return GraderResult(
        name="cv_factual_support",
        passed=not unsupported and bool(output_claim_ids),
        metrics=metrics,
        zero_tolerance_failure=bool(unsupported),
    )


def grade_docx_structure(content: bytes) -> GraderResult:
    required = {"[Content_Types].xml", "word/document.xml"}
    try:
        with ZipFile(BytesIO(content)) as archive:
            names = set(archive.namelist())
            document = archive.read("word/document.xml") if "word/document.xml" in names else b""
    except (BadZipFile, KeyError):
        names, document = set(), b""
    missing = required - names
    has_text = b"<w:t" in document
    passed = not missing and has_text
    return GraderResult(
        name="docx_structure",
        passed=passed,
        metrics={"missing_required_parts": len(missing), "has_text": has_text},
        zero_tolerance_failure=not passed,
    )
