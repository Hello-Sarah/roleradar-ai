from pathlib import Path
from typing import Annotated
from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.copilot.actions import (
    ActionConflictError,
    ActionProposalError,
    confirm_action,
    create_action_proposal,
    to_action_proposal_read,
)
from app.copilot.context import ContextSelection, CopilotContext, build_context
from app.copilot.contracts import (
    ActionConfirmRequest,
    ActionIntentRequest,
    ActionProposalRead,
    ActionResult,
    CopilotMessageCreate,
    CopilotMessageRead,
    CopilotSessionCreate,
    CopilotSessionRead,
    CopilotSessionUpdate,
    ProposalCreateRequest,
)
from app.copilot.service import (
    add_message,
    create_session,
    delete_session,
    get_session,
    list_messages,
    list_sessions,
    propose_action,
    rename_session,
)
from app.database.models import CopilotActionItem, CopilotActionProposal, GeneratedCV
from app.database.session import get_db
from app.i18n.service import translate
from app.ingestion.text_extractor import extract_job_from_text
from app.ingestion.url_fetcher import JobPageFetchError, fetch_job_from_url
from app.schemas import (
    ActionItemRead,
    AnalysisRead,
    ApplicationEventCreate,
    ApplicationEventRead,
    ApplicationStatus,
    CandidateProfileCreate,
    CandidateProfileRead,
    CandidateProfileVersionRead,
    CVDocumentRead,
    CVLibraryScanRead,
    DashboardRead,
    DigestRead,
    GeneratedCVRead,
    JobCreate,
    JobPasteCreate,
    JobRead,
    JobUrlCreate,
    Locale,
    StatusUpdate,
    WatchListCompanyCreate,
    WatchListCompanyRead,
    WatchListCompanyUpdate,
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
from app.services.profile_service import get_or_create_profile, get_profile_version, upsert_profile
from app.watchlist.service import (
    DuplicateWatchListCompanyError,
    SourceHistoryDeleteError,
    create_company,
    delete_company,
    disable_company,
    enable_company,
    get_company,
    list_companies,
    to_company_read,
    update_company,
)

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


@router.get("/profile/versions/{version_id}", response_model=CandidateProfileVersionRead)
def read_profile_version(version_id: int, db: Db) -> CandidateProfileVersionRead:
    try:
        return CandidateProfileVersionRead.model_validate(get_profile_version(db, version_id))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


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


@router.post("/jobs/extract-url", response_model=JobCreate)
def preview_job_url_extraction(payload: JobUrlCreate) -> JobCreate:
    """Fetch editable URL fields without writing a job to the database."""
    try:
        return fetch_job_from_url(str(payload.url))
    except JobPageFetchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc


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


@router.post(
    "/watchlist/companies",
    response_model=WatchListCompanyRead,
    status_code=status.HTTP_201_CREATED,
)
def add_watchlist_company(payload: WatchListCompanyCreate, db: Db) -> WatchListCompanyRead:
    try:
        return to_company_read(create_company(db, payload))
    except DuplicateWatchListCompanyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/watchlist/companies", response_model=list[WatchListCompanyRead])
def read_watchlist_companies(db: Db, include_disabled: bool = True) -> list[WatchListCompanyRead]:
    return [
        to_company_read(company)
        for company in list_companies(db, include_disabled=include_disabled)
    ]


@router.get("/watchlist/companies/{company_id}", response_model=WatchListCompanyRead)
def read_watchlist_company(company_id: int, db: Db) -> WatchListCompanyRead:
    try:
        return to_company_read(get_company(db, company_id))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/watchlist/companies/{company_id}", response_model=WatchListCompanyRead)
def edit_watchlist_company(
    company_id: int, payload: WatchListCompanyUpdate, db: Db
) -> WatchListCompanyRead:
    try:
        return to_company_read(update_company(db, company_id, payload))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DuplicateWatchListCompanyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/watchlist/companies/{company_id}/enable", response_model=WatchListCompanyRead)
def enable_watchlist_company(company_id: int, db: Db) -> WatchListCompanyRead:
    try:
        return to_company_read(enable_company(db, company_id))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/watchlist/companies/{company_id}/disable", response_model=WatchListCompanyRead)
def disable_watchlist_company(company_id: int, db: Db) -> WatchListCompanyRead:
    try:
        return to_company_read(disable_company(db, company_id))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete(
    "/watchlist/companies/{company_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def remove_watchlist_company(
    company_id: int,
    db: Db,
    confirm: bool = False,
    locale: Locale = "en",
) -> Response:
    try:
        delete_company(db, company_id, confirmed=confirm)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except SourceHistoryDeleteError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=translate(locale, "watch_list.disable_instead"),
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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


@router.get("/action-items/{action_item_id}", response_model=ActionItemRead)
def read_action_item(action_item_id: int, db: Db) -> ActionItemRead:
    item = db.get(CopilotActionItem, action_item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action item not found")
    return ActionItemRead.model_validate(item)


@router.get("/generated-cvs/{generated_cv_id}/metadata", response_model=GeneratedCVRead)
def read_generated_cv(generated_cv_id: int, db: Db) -> GeneratedCVRead:
    generated = db.get(GeneratedCV, generated_cv_id)
    if generated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV not found")
    return GeneratedCVRead.model_validate(generated)


@router.get("/generated-cvs/{generated_cv_id}/{file_name:path}", response_class=FileResponse)
def download_generated_cv(
    generated_cv_id: int, file_name: str, db: Db, settings: AppSettings
) -> FileResponse:
    decoded_file_name = unquote(file_name)
    if (
        not decoded_file_name
        or Path(decoded_file_name).name != decoded_file_name
        or decoded_file_name in {".", ".."}
        or "\\" in decoded_file_name
        or "\x00" in decoded_file_name
        or Path(decoded_file_name).suffix.casefold() != ".docx"
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file name")
    generated = db.get(GeneratedCV, generated_cv_id)
    if generated is None or generated.file_name != decoded_file_name:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV not found")
    output_directory = Path(settings.generated_cv_path).expanduser().resolve()
    output = Path(generated.file_path).resolve()
    try:
        output.relative_to(output_directory)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV not found") from exc
    if output.name != decoded_file_name or not output.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV not found")
    return FileResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=decoded_file_name,
    )


@router.get("/generated-cvs/{file_name:path}", include_in_schema=False)
def download_generated_cv_legacy(file_name: str) -> None:
    """Avoid ambiguous filename-only artifact retrieval after immutable output storage."""
    del file_name
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV not found")


@router.get("/copilot/context", response_model=CopilotContext)
def read_copilot_context(
    db: Db,
    route: str | None = None,
    job_id: int | None = None,
    company_id: int | None = None,
    session_id: int | None = None,
    cv_document_ids: Annotated[list[int] | None, Query()] = None,
) -> CopilotContext:
    try:
        return build_context(
            ContextSelection(
                route=route,
                job_id=job_id,
                company_id=company_id,
                session_id=session_id,
                cv_document_ids=cv_document_ids or [],
            ),
            db,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/copilot/sessions",
    response_model=CopilotSessionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_copilot_session(payload: CopilotSessionCreate, db: Db) -> CopilotSessionRead:
    return CopilotSessionRead.model_validate(
        create_session(db, title=payload.title, locale=payload.locale)
    )


@router.get("/copilot/sessions", response_model=list[CopilotSessionRead])
def read_copilot_sessions(db: Db) -> list[CopilotSessionRead]:
    return [CopilotSessionRead.model_validate(session) for session in list_sessions(db)]


@router.get("/copilot/sessions/{session_id}", response_model=CopilotSessionRead)
def read_copilot_session(session_id: int, db: Db) -> CopilotSessionRead:
    try:
        return CopilotSessionRead.model_validate(get_session(db, session_id))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/copilot/sessions/{session_id}", response_model=CopilotSessionRead)
def update_copilot_session(
    session_id: int, payload: CopilotSessionUpdate, db: Db
) -> CopilotSessionRead:
    try:
        return CopilotSessionRead.model_validate(rename_session(db, session_id, payload.title))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete(
    "/copilot/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def remove_copilot_session(session_id: int, db: Db) -> Response:
    try:
        delete_session(db, session_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/copilot/sessions/{session_id}/messages",
    response_model=CopilotMessageRead,
    status_code=status.HTTP_201_CREATED,
)
def create_copilot_message(
    session_id: int, payload: CopilotMessageCreate, db: Db
) -> CopilotMessageRead:
    try:
        return CopilotMessageRead.model_validate(add_message(db, session_id, payload))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/copilot/sessions/{session_id}/messages", response_model=list[CopilotMessageRead])
def read_copilot_messages(session_id: int, db: Db) -> list[CopilotMessageRead]:
    try:
        return [
            CopilotMessageRead.model_validate(message) for message in list_messages(db, session_id)
        ]
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/copilot/propose",
    response_model=ActionProposalRead,
    status_code=status.HTTP_201_CREATED,
)
def propose_copilot_action(
    payload: ActionIntentRequest, db: Db, settings: AppSettings
) -> ActionProposalRead:
    try:
        context = build_context(
            ContextSelection(
                route=payload.route,
                job_id=payload.job_id,
                company_id=payload.company_id,
                session_id=payload.session_id,
                cv_document_ids=payload.cv_document_ids,
            ),
            db,
        )
        # The provider receives a detached Pydantic snapshot; never hold a database
        # transaction open while waiting for model-backed intent classification.
        db.rollback()
        proposal = propose_action(payload.message, context, settings)
        return to_action_proposal_read(
            create_action_proposal(
                db,
                session_id=payload.session_id,
                proposal=proposal,
            )
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ActionProposalError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc


@router.post(
    "/copilot/proposals",
    response_model=ActionProposalRead,
    status_code=status.HTTP_201_CREATED,
)
def create_copilot_proposal(payload: ProposalCreateRequest, db: Db) -> ActionProposalRead:
    try:
        return to_action_proposal_read(
            create_action_proposal(
                db,
                session_id=payload.session_id,
                proposal=payload.proposal,
            )
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ActionProposalError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc


@router.get("/copilot/proposals/{proposal_id}", response_model=ActionProposalRead)
def read_copilot_proposal(proposal_id: int, db: Db) -> ActionProposalRead:
    proposal = db.get(CopilotActionProposal, proposal_id)
    if proposal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")
    return to_action_proposal_read(proposal)


@router.post("/copilot/proposals/{proposal_id}/confirm", response_model=ActionResult)
def confirm_copilot_proposal(
    proposal_id: int,
    payload: ActionConfirmRequest,
    db: Db,
    settings: AppSettings,
) -> ActionResult:
    try:
        return confirm_action(
            proposal_id,
            payload.idempotency_key,
            db,
            settings,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ActionConflictError, ActionProposalError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except CVLibraryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
