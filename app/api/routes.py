from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database.session import get_db
from app.ingestion.text_extractor import extract_job_from_text
from app.ingestion.url_fetcher import JobPageFetchError, fetch_job_from_url
from app.schemas import (
    AnalysisRead,
    ApplicationEventCreate,
    ApplicationEventRead,
    ApplicationStatus,
    CandidateProfileCreate,
    CandidateProfileRead,
    CVDocumentRead,
    CVLibraryScanRead,
    DashboardRead,
    DigestRead,
    GeneratedCVRead,
    JobCreate,
    JobPasteCreate,
    JobRead,
    JobUrlCreate,
    StatusUpdate,
)
from app.services.cv_service import (
    CVLibraryError,
    generate_tailored_cv,
    list_cv_documents,
    scan_cv_library,
)
from app.services.job_service import (
    DuplicateJobError,
    add_application_event,
    create_and_analyze_job,
    get_daily_digest,
    get_dashboard,
    get_job,
    list_analyses,
    list_application_events,
    list_jobs,
    reanalyze_job,
    to_analysis_read,
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


@router.post("/jobs/from-text", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_job_from_text(payload: JobPasteCreate, db: Db, settings: AppSettings) -> JobRead:
    try:
        extracted = extract_job_from_text(payload.text)
        return to_job_read(create_and_analyze_job(db, extracted, settings))
    except DuplicateJobError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/jobs/extract", response_model=JobCreate)
def preview_job_extraction(payload: JobPasteCreate) -> JobCreate:
    """Extract editable fields without writing a job to the database."""
    return extract_job_from_text(payload.text)


@router.post("/jobs/from-url", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_job_from_url(payload: JobUrlCreate, db: Db, settings: AppSettings) -> JobRead:
    """Fetch, persist, and analyze a publicly accessible job posting URL."""
    try:
        extracted = fetch_job_from_url(str(payload.url))
        return to_job_read(create_and_analyze_job(db, extracted, settings))
    except JobPageFetchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
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


@router.post(
    "/jobs/{job_id}/reanalyze",
    response_model=AnalysisRead,
    status_code=status.HTTP_201_CREATED,
)
def reanalyze(job_id: int, db: Db, settings: AppSettings) -> AnalysisRead:
    try:
        return to_analysis_read(reanalyze_job(db, job_id, settings))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/jobs/{job_id}/analyses", response_model=list[AnalysisRead])
def read_analysis_history(job_id: int, db: Db) -> list[AnalysisRead]:
    try:
        return [to_analysis_read(analysis) for analysis in list_analyses(db, job_id)]
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/jobs/{job_id}/status", response_model=JobRead)
def change_status(job_id: int, payload: StatusUpdate, db: Db) -> JobRead:
    try:
        return to_job_read(update_status(db, job_id, payload.status))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/jobs/{job_id}/application-events",
    response_model=ApplicationEventRead,
    status_code=status.HTTP_201_CREATED,
)
def create_application_event(
    job_id: int, payload: ApplicationEventCreate, db: Db
) -> ApplicationEventRead:
    try:
        return ApplicationEventRead.model_validate(add_application_event(db, job_id, payload))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/jobs/{job_id}/application-events", response_model=list[ApplicationEventRead])
def read_application_events(job_id: int, db: Db) -> list[ApplicationEventRead]:
    try:
        return [
            ApplicationEventRead.model_validate(event)
            for event in list_application_events(db, job_id)
        ]
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/dashboard", response_model=DashboardRead)
def dashboard(db: Db) -> DashboardRead:
    return get_dashboard(db)


@router.get("/digest/daily", response_model=DigestRead)
def daily_digest(db: Db) -> DigestRead:
    return get_daily_digest(db)


@router.get("/cv-library", response_model=list[CVDocumentRead])
def read_cv_library(db: Db) -> list[CVDocumentRead]:
    return [CVDocumentRead.model_validate(document) for document in list_cv_documents(db)]


@router.post("/cv-library/scan", response_model=CVLibraryScanRead)
def scan_cv_folder(db: Db, settings: AppSettings) -> CVLibraryScanRead:
    try:
        return scan_cv_library(db, settings)
    except CVLibraryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc


@router.post("/jobs/{job_id}/tailored-cv", response_model=GeneratedCVRead)
def create_tailored_cv(job_id: int, db: Db, settings: AppSettings) -> GeneratedCVRead:
    try:
        return generate_tailored_cv(db, job_id, settings)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except CVLibraryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc


@router.get("/generated-cvs/{file_name}", response_class=FileResponse)
def download_generated_cv(file_name: str, settings: AppSettings) -> FileResponse:
    if Path(file_name).name != file_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file name")
    output_directory = Path(settings.generated_cv_path).expanduser().resolve()
    output = (output_directory / file_name).resolve()
    if output.parent != output_directory or not output.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV not found")
    return FileResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=file_name,
    )
