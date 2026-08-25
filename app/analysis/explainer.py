import logging

from openai import OpenAI
from pydantic import BaseModel, Field

from app.config import Settings
from app.schemas import CandidateProfileRead, ClassificationRead, JobCreate
from app.scoring.v2 import CareerFitV2

logger = logging.getLogger(__name__)


class LLMExplanation(BaseModel):
    strengths: list[str] = Field(min_length=1, max_length=6)
    gaps: list[str] = Field(min_length=1, max_length=6)
    evidence: list[str] = Field(min_length=1, max_length=6)
    summary: str = Field(min_length=20, max_length=500)


def _fallback_summary(job: JobCreate, result: CareerFitV2) -> LLMExplanation:
    strengths = [flag.code for flag in result.matched_green_flags]
    gaps = [
        weak
        for dimension in result.dimensions.values()
        for weak in dimension.missing_or_weak_evidence
    ]
    return LLMExplanation(
        strengths=strengths or ["NO_MATCHED_GREEN_FLAGS"],
        gaps=gaps or ["NO_WEAK_DIMENSIONS"],
        evidence=[f"{item.id}: {item.text}" for item in result.evidence],
        summary=(
            f"{job.title} at {job.company} is in the {result.recommendation_band} band "
            f"with a deterministic fit score of {result.total_score}/100. "
            "The score is derived only from the six Career Fit V2 dimensions."
        ),
    )


def explain_fit(
    *,
    job: JobCreate,
    profile: CandidateProfileRead,
    classification: ClassificationRead,
    result: CareerFitV2,
    settings: Settings,
) -> tuple[LLMExplanation, str]:
    if not settings.ai_explanations_enabled or not settings.openai_api_key:
        return _fallback_summary(job, result), "deterministic-fallback"

    client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
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
    try:
        response = client.responses.parse(
            model=settings.openai_model,
            input=[
                {"role": "system", "content": "You are a careful career intelligence analyst."},
                {"role": "user", "content": str(prompt)},
            ],
            text_format=LLMExplanation,
        )
        if response.output_parsed is None:
            raise ValueError("Model returned no structured explanation")
        return response.output_parsed, settings.openai_model
    except Exception:
        logger.exception("AI explanation failed; using deterministic fallback")
        return _fallback_summary(job, result), "deterministic-fallback"
