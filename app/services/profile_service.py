from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import CandidateProfile
from app.schemas import CandidateProfileCreate, CandidateProfileRead

DEFAULT_PROFILE = CandidateProfileCreate(
    target_roles=["Forward Deployed Engineer", "Applied AI Engineer", "AI Product Manager"],
    preferred_locations=["Singapore", "Hong Kong"],
    future_locations=["San Francisco", "New York"],
    domain_strengths=["Banking", "Capital Markets", "AML", "Data Transformation"],
    technical_strengths=["Python", "SQL", "Data Analytics"],
    development_gaps=["FastAPI", "Docker", "Cloud Deployment", "Agent Evaluation"],
)


def get_or_create_profile(db: Session) -> CandidateProfile:
    profile = db.scalar(select(CandidateProfile).order_by(CandidateProfile.id).limit(1))
    if profile is None:
        profile = CandidateProfile(**DEFAULT_PROFILE.model_dump())
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def upsert_profile(db: Session, payload: CandidateProfileCreate) -> CandidateProfile:
    profile = get_or_create_profile(db)
    for key, value in payload.model_dump().items():
        setattr(profile, key, value)
    db.commit()
    db.refresh(profile)
    return profile


def to_profile_read(profile: CandidateProfile) -> CandidateProfileRead:
    return CandidateProfileRead.model_validate(profile)
