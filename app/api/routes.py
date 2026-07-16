from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database.session import get_db
from app.schemas import (
    ApplicationStatus,
    CandidateProfileCreate,
    CandidateProfileRead,
    DashboardRead,
    DigestRead,
    JobCreate,
    JobRead,
    StatusUpdate,
)
from app.services.job_service import (
    DuplicateJobError,
    create_and_analyze_job,
    get_daily_digest,
    get_dashboard,
    get_job,
    list_jobs,
    to_job_read,
    update_status,
)
from app.services.profile_service import get_or_create_profile, upsert_profile

router = APIRouter(prefix="/api/v1")
Db = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/profile", response_model=CandidateProfileRead)
def read_profile(db: Db) -> CandidateProfileRead:
    return CandidateProfileRead.model_validate(get_or_create_profile(db))


@router.put("/profile", response_model=CandidateProfileRead)
def write_profile(payload: CandidateProfileCreate, db: Db) -> CandidateProfileRead:
    return CandidateProfileRead.model_validate(upsert_profile(db, payload))


@router.post("/jobs", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_job(payload: JobCreate, db: Db, settings: AppSettings) -> JobRead:
    try:
        return to_job_read(create_and_analyze_job(db, payload, settings))
    except DuplicateJobError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/jobs", response_model=list[JobRead])
def read_jobs(
    db: Db,
    application_status: ApplicationStatus | None = None,
    min_fit_score: Annotated[int | None, Query(ge=0, le=100)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[JobRead]:
    return [
        to_job_read(job)
        for job in list_jobs(
            db, status=application_status, min_fit_score=min_fit_score, limit=limit
        )
    ]


@router.get("/jobs/{job_id}", response_model=JobRead)
def read_job(job_id: int, db: Db) -> JobRead:
    try:
        return to_job_read(get_job(db, job_id))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/jobs/{job_id}/status", response_model=JobRead)
def change_status(job_id: int, payload: StatusUpdate, db: Db) -> JobRead:
    try:
        return to_job_read(update_status(db, job_id, payload.status))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/dashboard", response_model=DashboardRead)
def dashboard(db: Db) -> DashboardRead:
    return get_dashboard(db)


@router.get("/digest/daily", response_model=DigestRead)
def daily_digest(db: Db) -> DigestRead:
    return get_daily_digest(db)
