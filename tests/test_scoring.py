from datetime import UTC, datetime

from app.schemas import CandidateProfileRead, ClassificationRead, RoleCategory
from app.scoring.engine import score_job


def profile() -> CandidateProfileRead:
    now = datetime.now(UTC)
    return CandidateProfileRead(
        id=1,
        name="Candidate",
        target_roles=["Applied AI Engineer"],
        preferred_locations=["Hong Kong"],
        future_locations=[],
        domain_strengths=["Banking"],
        technical_strengths=["Python", "SQL"],
        development_gaps=["Docker"],
        created_at=now,
        updated_at=now,
    )


def test_score_is_deterministic_and_explainable() -> None:
    classification = ClassificationRead(
        category=RoleCategory.APPLIED_AI_ENGINEER,
        confidence=0.9,
        evidence=["Matched 'applied ai'"],
    )
    result = score_job(
        title="Applied AI Engineer",
        location="Hong Kong",
        description="Build Python and SQL systems for Banking using Docker and AWS.",
        classification=classification,
        profile=profile(),
    )
    assert result.fit_score == sum(result.breakdown.model_dump().values())
    assert result.fit_score >= 70
    assert "Docker" in result.gaps
    assert result.evidence
