import logging

from openai import OpenAI
from pydantic import BaseModel, Field

from app.config import Settings
from app.schemas import CandidateProfileRead, ClassificationRead, JobCreate
from app.scoring.engine import ScoringResult

logger = logging.getLogger(__name__)


class LLMExplanation(BaseModel):
    strengths: list[str] = Field(min_length=1, max_length=6)
    gaps: list[str] = Field(min_length=1, max_length=6)
    evidence: list[str] = Field(min_length=1, max_length=6)
    summary: str = Field(min_length=20, max_length=500)


def _fallback_summary(job: JobCreate, result: ScoringResult) -> LLMExplanation:
    return LLMExplanation(
        strengths=result.strengths,
        gaps=result.gaps,
        evidence=result.evidence,
        summary=(
            f"{job.title} at {job.company} is a {result.recommendation.value.lower()} opportunity "
            f"with a deterministic fit score of {result.fit_score}/100. "
            "The largest decision factors are role, location, domain, "
            "and required-skill alignment."
        ),
    )


def explain_fit(
    *,
    job: JobCreate,
    profile: CandidateProfileRead,
    classification: ClassificationRead,
    result: ScoringResult,
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
            "fit_score": result.fit_score,
            "breakdown": result.breakdown.model_dump(),
            "strengths": result.strengths,
            "gaps": result.gaps,
            "evidence": result.evidence,
            "recommendation": result.recommendation,
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
