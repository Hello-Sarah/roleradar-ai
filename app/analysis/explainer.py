import logging
from collections.abc import Callable, Iterable

from openai import OpenAI
from pydantic import BaseModel, Field

from app.config import Settings
from app.schemas import CandidateProfileRead, ClassificationRead, JobCreate
from app.scoring.v2 import CareerFitV2

logger = logging.getLogger(__name__)

ExplanationProvider = Callable[[dict[str, object], float | None], "LLMExplanation"]


class LLMExplanation(BaseModel):
    strengths: list[str] = Field(min_length=1, max_length=6)
    gaps: list[str] = Field(min_length=1, max_length=6)
    evidence: list[str] = Field(min_length=1, max_length=6)
    summary: str = Field(min_length=20, max_length=500)


def _bounded_items(items: Iterable[str], fallback: str) -> list[str]:
    return list(dict.fromkeys(items))[:6] or [fallback]


def _fallback_summary(job: JobCreate, result: CareerFitV2) -> LLMExplanation:
    strengths = [flag.code for flag in result.matched_green_flags]
    gaps = [
        weak
        for dimension in result.dimensions.values()
        for weak in dimension.missing_or_weak_evidence
    ]
    return LLMExplanation(
        strengths=_bounded_items(strengths, "NO_MATCHED_GREEN_FLAGS"),
        gaps=_bounded_items(gaps, "NO_WEAK_DIMENSIONS"),
        evidence=_bounded_items(
            (f"{item.id}: {item.text}" for item in result.evidence),
            "NO_JD_EVIDENCE",
        ),
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
    provider_call: ExplanationProvider | None = None,
    timeout_seconds: float | None = None,
) -> tuple[LLMExplanation, str]:
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
    try:
        if provider_call is not None:
            return provider_call(prompt, timeout_seconds), settings.openai_model
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
            text_format=LLMExplanation,
        )
        if response.output_parsed is None:
            raise ValueError("Model returned no structured explanation")
        return response.output_parsed, settings.openai_model
    except Exception:
        logger.exception("AI explanation failed; using deterministic fallback")
        return _fallback_summary(job, result), "deterministic-fallback"
