"""Versioned synthetic profile used only by the public demo."""

from datetime import UTC, datetime

from app.schemas import CandidateProfileRead

PUBLIC_DEMO_PROFILE_VERSION = "public-demo-v1"
_SYNTHETIC_PROFILE_TIMESTAMP = datetime(2026, 9, 30, tzinfo=UTC)


def public_demo_profile() -> CandidateProfileRead:
    """Return the fixed, non-private profile that anchors public-demo output."""

    return CandidateProfileRead(
        id=0,
        name="Public Demo Candidate",
        target_roles=["Applied AI Engineer", "AI Product", "AI Solutions"],
        preferred_locations=["Singapore", "Hong Kong"],
        domain_strengths=["Financial Services", "Enterprise SaaS"],
        technical_strengths=["Python", "SQL", "API Integration"],
        development_gaps=["Cloud Deployment", "Agent Evaluation"],
        created_at=_SYNTHETIC_PROFILE_TIMESTAMP,
        updated_at=_SYNTHETIC_PROFILE_TIMESTAMP,
    )
