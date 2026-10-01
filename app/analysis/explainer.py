import logging
from collections.abc import Callable, Iterable
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel, Field

from app.config import Settings
from app.schemas import CandidateProfileRead, ClassificationRead, JobCreate
from app.scoring.v2 import CareerFitV2, EvidenceItem

logger = logging.getLogger(__name__)


class LLMExplanation(BaseModel):
    strengths: list[str] = Field(min_length=1, max_length=6)
    gaps: list[str] = Field(min_length=1, max_length=6)
    evidence: list[str] = Field(min_length=1, max_length=6)
    summary: str = Field(min_length=20, max_length=500)
    strength_claims: list["EvidenceGroundedClaim"] = Field(default_factory=list, max_length=6)
    gap_claims: list["EvidenceGroundedClaim"] = Field(default_factory=list, max_length=6)
    summary_claim: "EvidenceGroundedClaim | None" = None
    selections: list["EvidenceSelection"] = Field(default_factory=list, max_length=6)


class EvidenceGroundedClaim(BaseModel):
    """Provider prose with the deterministic JD evidence that supports it."""

    text: str = Field(min_length=1, max_length=500)
    evidence_ids: list[str] = Field(min_length=1, max_length=6)


class EvidenceSelection(BaseModel):
    """A bounded public-demo model choice over the deterministic evidence catalog."""

    evidence_id: str = Field(min_length=1)
    label: Literal["strength", "gap", "summary"]


class PublicEvidenceSelections(BaseModel):
    """The only model-controlled public-demo output: catalog IDs plus bounded labels."""

    selections: list[EvidenceSelection] = Field(min_length=1, max_length=6)


LLMExplanation.model_rebuild()

ExplanationResult = LLMExplanation | PublicEvidenceSelections
ExplanationProvider = Callable[[dict[str, object], float | None], ExplanationResult]


def _bounded_items(items: Iterable[str], fallback: str) -> list[str]:
    return list(dict.fromkeys(items))[:6] or [fallback]


def _fallback_summary(job: JobCreate, result: CareerFitV2) -> LLMExplanation:
    strengths = [flag.code for flag in result.matched_green_flags]
    gaps = [
        weak
        for dimension in result.dimensions.values()
        for weak in dimension.missing_or_weak_evidence
    ]
    evidence_ids = [item.id for item in result.evidence]
    fallback_evidence_ids = evidence_ids[:6] or ["jd-title"]
    bounded_strengths = _bounded_items(strengths, "NO_MATCHED_GREEN_FLAGS")
    bounded_gaps = _bounded_items(gaps, "NO_WEAK_DIMENSIONS")
    summary = (
        f"{job.title} at {job.company} is in the {result.recommendation_band} band "
        f"with a deterministic fit score of {result.total_score}/100. "
        "The score is derived only from the six Career Fit V2 dimensions."
    )
    return LLMExplanation(
        strengths=bounded_strengths,
        gaps=bounded_gaps,
        evidence=_bounded_items(
            (f"{item.id}: {item.text}" for item in result.evidence), "NO_JD_EVIDENCE"
        ),
        summary=summary,
        strength_claims=[
            EvidenceGroundedClaim(
                text=flag.code,
                evidence_ids=flag.evidence_ids,
            )
            for flag in result.matched_green_flags[:6]
        ]
        or [EvidenceGroundedClaim(text=bounded_strengths[0], evidence_ids=fallback_evidence_ids)],
        gap_claims=[
            EvidenceGroundedClaim(text=gap, evidence_ids=fallback_evidence_ids)
            for gap in bounded_gaps
        ],
        summary_claim=EvidenceGroundedClaim(text=summary, evidence_ids=fallback_evidence_ids),
    )


def _validate_public_selections(
    explanation: ExplanationResult, allowed_evidence: list[EvidenceItem]
) -> None:
    allowed_ids = {item.id for item in allowed_evidence}
    if not explanation.selections or any(
        selection.evidence_id not in allowed_ids for selection in explanation.selections
    ):
        raise ValueError("Model explanation selected unsupported JD evidence")


def explain_fit(
    *,
    job: JobCreate,
    profile: CandidateProfileRead,
    classification: ClassificationRead,
    result: CareerFitV2,
    settings: Settings,
    provider_call: ExplanationProvider | None = None,
    timeout_seconds: float | None = None,
    allowed_evidence: list[EvidenceItem] | None = None,
    locale: str | None = None,
) -> tuple[ExplanationResult, str]:
    if not settings.ai_explanations_enabled or not settings.openai_api_key:
        return _fallback_summary(job, result), "deterministic-fallback"

    prompt = {
        "instruction": (
            "Explain the already-computed score. Do not change or invent a score. "
            "Ground every claim in the supplied job and profile. Be concise."
        ),
        "job": job.model_dump(mode="json"),
        "profile": profile.model_dump(mode="json"),
        "classification": classification.model_dump(mode="json"),
        "deterministic_result": {
            "fit_score": result.total_score,
            "dimensions": {
                name: dimension.model_dump(mode="json")
                for name, dimension in result.dimensions.items()
            },
            "green_flags": [flag.model_dump(mode="json") for flag in result.matched_green_flags],
            "red_flags": [flag.model_dump(mode="json") for flag in result.matched_red_flags],
            "critical_warnings": [
                warning.model_dump(mode="json") for warning in result.critical_warnings
            ],
            "recommendation": result.recommendation_band,
        },
    }
    if allowed_evidence is not None:
        prompt["evidence_catalog"] = [item.model_dump(mode="json") for item in allowed_evidence]
        prompt["public_claim_contract"] = (
            "Return one to six selections only: each must contain an evidence_id from "
            "evidence_catalog and one bounded label: strength, gap, or summary. The public "
            "service ignores free-form provider prose and renders the selected canonical evidence."
        )
        prompt["presentation_locale"] = locale or "en"
    try:
        if provider_call is not None:
            explanation = provider_call(prompt, timeout_seconds)
        else:
            client_options: dict[str, object] = {
                "api_key": settings.openai_api_key,
                "base_url": settings.openai_base_url,
            }
            if timeout_seconds is not None:
                client_options["timeout"] = timeout_seconds
            client = OpenAI(**client_options)
            response = client.responses.parse(
                model=settings.openai_model,
                input=[
                    {"role": "system", "content": "You are a careful career intelligence analyst."},
                    {"role": "user", "content": str(prompt)},
                ],
                text_format=(
                    PublicEvidenceSelections if allowed_evidence is not None else LLMExplanation
                ),
            )
            if response.output_parsed is None:
                raise ValueError("Model returned no structured explanation")
            explanation = response.output_parsed
        if allowed_evidence is not None:
            _validate_public_selections(explanation, allowed_evidence)
        return explanation, settings.openai_model
    except Exception:
        logger.error("AI explanation provider failed; using deterministic fallback")
        return _fallback_summary(job, result), "deterministic-fallback"
