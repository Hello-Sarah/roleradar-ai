import re
from dataclasses import dataclass

from app.schemas import (
    CandidateProfileRead,
    ClassificationRead,
    Recommendation,
    ScoreBreakdown,
)

SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "Python": ("python",),
    "SQL": ("sql", "postgresql", "mysql"),
    "FastAPI": ("fastapi",),
    "Docker": ("docker", "container"),
    "Cloud Deployment": ("aws", "azure", "gcp", "cloud deployment", "kubernetes"),
    "Agent Evaluation": ("agent evaluation", "evals", "evaluation framework"),
    "Data Analytics": ("data analytics", "analytics"),
    "Machine Learning": ("machine learning", "ml model"),
    "LLMs": ("large language model", "llm", "generative ai", "genai"),
    "RAG": ("retrieval augmented", "rag"),
}


@dataclass(frozen=True)
class ScoringResult:
    fit_score: int
    breakdown: ScoreBreakdown
    strengths: list[str]
    gaps: list[str]
    evidence: list[str]
    recommendation: Recommendation


def _contains(text: str, phrase: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(phrase.casefold())}(?!\w)", text.casefold()))


def extract_required_skills(description: str) -> list[str]:
    return [
        skill
        for skill, aliases in SKILL_ALIASES.items()
        if any(_contains(description, alias) for alias in aliases)
    ]


def score_job(
    *,
    title: str,
    location: str,
    description: str,
    classification: ClassificationRead,
    profile: CandidateProfileRead,
) -> ScoringResult:
    target_match = any(
        target.casefold() in {title.casefold(), classification.category.value.casefold()}
        or target.casefold() in title.casefold()
        for target in profile.target_roles
    )
    role_score = 35 if target_match else 10

    preferred_match = any(
        place.casefold() in location.casefold() for place in profile.preferred_locations
    )
    future_match = any(
        place.casefold() in location.casefold() for place in profile.future_locations
    )
    location_score = 15 if preferred_match else 8 if future_match else 2

    domain_matches = [skill for skill in profile.domain_strengths if _contains(description, skill)]
    domain_score = min(20, len(domain_matches) * 7)

    required_skills = extract_required_skills(description)
    strengths = [
        skill
        for skill in profile.technical_strengths
        if skill in required_skills or _contains(description, skill)
    ]
    gaps = [skill for skill in required_skills if skill not in profile.technical_strengths]
    technical_score = (
        10 if not required_skills else round(30 * len(strengths) / len(required_skills))
    )

    breakdown = ScoreBreakdown(
        role_alignment=role_score,
        location_alignment=location_score,
        domain_alignment=domain_score,
        technical_alignment=technical_score,
    )
    fit_score = sum(breakdown.model_dump().values())
    recommendation = (
        Recommendation.APPLY_NOW
        if fit_score >= 75
        else Recommendation.CONSIDER
        if fit_score >= 55
        else Recommendation.BUILD_SKILLS_FIRST
        if fit_score >= 35
        else Recommendation.SKIP
    )
    role_evidence = (
        f"Role family: {classification.category.value} ({classification.confidence:.0%} confidence)"
    )
    location_level = "preferred" if preferred_match else "future" if future_match else "low"
    evidence = [
        role_evidence,
        f"Location alignment: {location_level}",
        f"Matched {len(strengths)} of {len(required_skills)} detected technical skills",
    ]
    strengths = [*strengths, *domain_matches]
    if target_match:
        strengths.insert(0, f"Target role alignment: {classification.category.value}")
    return ScoringResult(
        fit_score=fit_score,
        breakdown=breakdown,
        strengths=list(dict.fromkeys(strengths)) or ["No explicit profile strengths matched"],
        gaps=gaps or ["No explicit skill gaps detected"],
        evidence=evidence,
        recommendation=recommendation,
    )
