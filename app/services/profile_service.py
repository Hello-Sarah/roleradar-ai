import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import CandidateProfile, CandidateProfileVersion
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


def profile_content_version(profile: CandidateProfile) -> str:
    snapshot = {
        "name": profile.name,
        "target_roles": profile.target_roles,
        "preferred_locations": profile.preferred_locations,
        "future_locations": profile.future_locations,
        "domain_strengths": profile.domain_strengths,
        "technical_strengths": profile.technical_strengths,
        "development_gaps": profile.development_gaps,
    }
    digest = hashlib.sha256(
        json.dumps(snapshot, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return f"profile-sha256:{digest}"


def get_or_create_profile_version(
    db: Session, profile: CandidateProfile
) -> CandidateProfileVersion:
    version = profile_content_version(profile)
    snapshot = db.scalar(
        select(CandidateProfileVersion).where(
            CandidateProfileVersion.profile_id == profile.id,
            CandidateProfileVersion.version == version,
        )
    )
    if snapshot is None:
        snapshot = CandidateProfileVersion(
            profile_id=profile.id,
            version=version,
            name=profile.name,
            target_roles=list(profile.target_roles),
            preferred_locations=list(profile.preferred_locations),
            future_locations=list(profile.future_locations),
            domain_strengths=list(profile.domain_strengths),
            technical_strengths=list(profile.technical_strengths),
            development_gaps=list(profile.development_gaps),
        )
        db.add(snapshot)
        db.flush()
    return snapshot


def get_profile_version(db: Session, version_id: int) -> CandidateProfileVersion:
    snapshot = db.get(CandidateProfileVersion, version_id)
    if snapshot is None:
        raise LookupError("Profile version not found")
    return snapshot
