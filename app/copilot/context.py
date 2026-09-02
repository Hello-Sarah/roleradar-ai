from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.copilot.contracts import PrivateDataUsage
from app.database.models import (
    CandidateProfile,
    CandidateProfileVersion,
    CopilotSession,
    CVDocument,
    Job,
    JobAnalysis,
    WatchListCompany,
)


class ContextSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route: str | None = Field(default=None, max_length=500)
    job_id: int | None = None
    company_id: int | None = None
    session_id: int | None = None
    cv_document_ids: list[int] = Field(default_factory=list)


class ContextSource(BaseModel):
    record_type: str
    record_id: int
    version: str | None = None


class ContextJob(BaseModel):
    id: int
    company: str
    title: str
    location: str
    description: str
    status: str
    analysis_id: int | None = None
    analysis_version: str | None = None


class ContextAnalysis(BaseModel):
    id: int
    scoring_version: str
    profile_version: str
    rubric_version: str
    model_version: str
    prompt_version: str
    fit_score: int
    score_breakdown: dict[str, int]
    score_details: dict[str, object]
    strengths: list[str]
    gaps: list[str]
    evidence: list[str]
    recommendation: str
    summary: str


class ContextCompany(BaseModel):
    id: int
    name: str
    canonical_domain: str
    strategic_priority: str
    action_window: str
    enabled: bool


class ContextProfile(BaseModel):
    id: int
    version_id: int | None
    version: str | None
    target_roles: list[str]
    preferred_locations: list[str]
    future_locations: list[str]
    domain_strengths: list[str]
    technical_strengths: list[str]
    development_gaps: list[str]


class ContextApplicationEvent(BaseModel):
    id: int
    status: str
    occurred_at: datetime
    channel: str | None
    notes: str | None
    next_follow_up_date: date | None


class ContextCVDocument(BaseModel):
    id: int
    file_name: str
    fingerprint: str
    extracted_text: str


class CopilotContext(BaseModel):
    route: str | None = None
    job: ContextJob | None = None
    analysis: ContextAnalysis | None = None
    company: ContextCompany | None = None
    profile: ContextProfile | None = None
    application_events: list[ContextApplicationEvent] = Field(default_factory=list)
    cv_documents: list[ContextCVDocument] = Field(default_factory=list)
    conversation_summary: str | None = None
    sources: list[ContextSource] = Field(default_factory=list)
    private_data_usage: PrivateDataUsage = Field(default_factory=PrivateDataUsage)
    untrusted_content: bool = True


def _selected_job(db: Session, job_id: int) -> Job:
    job = db.scalar(
        select(Job)
        .options(selectinload(Job.analyses), selectinload(Job.application_events))
        .where(Job.id == job_id)
    )
    if job is None:
        raise LookupError("Job not found")
    return job


def _active_profile(db: Session) -> tuple[CandidateProfile, CandidateProfileVersion | None] | None:
    profile = db.scalar(select(CandidateProfile).order_by(CandidateProfile.id).limit(1))
    if profile is None:
        return None
    version = db.scalar(
        select(CandidateProfileVersion)
        .where(CandidateProfileVersion.profile_id == profile.id)
        .order_by(desc(CandidateProfileVersion.id))
        .limit(1)
    )
    return profile, version


def build_context(selection: ContextSelection, db: Session) -> CopilotContext:
    """Build a minimal explicit context without invoking a provider or writing data."""
    sources: list[ContextSource] = []
    context_job = None
    context_analysis = None
    application_events: list[ContextApplicationEvent] = []
    if selection.job_id is not None:
        job = _selected_job(db, selection.job_id)
        analysis: JobAnalysis | None = job.analyses[0] if job.analyses else None
        context_job = ContextJob(
            id=job.id,
            company=job.company,
            title=job.title,
            location=job.location,
            description=job.description,
            status=job.status,
            analysis_id=analysis.id if analysis else None,
            analysis_version=analysis.scoring_version if analysis else None,
        )
        sources.append(
            ContextSource(
                record_type="job",
                record_id=job.id,
                version=analysis.scoring_version if analysis else None,
            )
        )
        if analysis is not None:
            context_analysis = ContextAnalysis(
                id=analysis.id,
                scoring_version=analysis.scoring_version,
                profile_version=analysis.profile_version,
                rubric_version=analysis.rubric_version,
                model_version=analysis.model_version,
                prompt_version=analysis.prompt_version,
                fit_score=analysis.fit_score,
                score_breakdown=analysis.score_breakdown,
                score_details=analysis.score_details,
                strengths=analysis.strengths,
                gaps=analysis.gaps,
                evidence=analysis.evidence,
                recommendation=analysis.recommendation,
                summary=analysis.summary,
            )
            sources.append(
                ContextSource(
                    record_type="job_analysis",
                    record_id=analysis.id,
                    version=analysis.scoring_version,
                )
            )
        application_events = [
            ContextApplicationEvent.model_validate(
                {
                    "id": event.id,
                    "status": event.status,
                    "occurred_at": event.occurred_at,
                    "channel": event.channel,
                    "notes": event.notes,
                    "next_follow_up_date": event.next_follow_up_date,
                }
            )
            for event in job.application_events
        ]
        sources.extend(
            ContextSource(record_type="application_event", record_id=event.id)
            for event in job.application_events
        )

    context_company = None
    if selection.company_id is not None:
        company = db.get(WatchListCompany, selection.company_id)
        if company is None:
            raise LookupError("Watch List company not found")
        context_company = ContextCompany.model_validate(
            {
                "id": company.id,
                "name": company.name,
                "canonical_domain": company.canonical_domain,
                "strategic_priority": company.strategic_priority,
                "action_window": company.action_window,
                "enabled": company.enabled,
            }
        )
        sources.append(ContextSource(record_type="watchlist_company", record_id=company.id))

    context_profile = None
    profile_pair = _active_profile(db)
    if profile_pair is not None:
        profile, version = profile_pair
        context_profile = ContextProfile(
            id=profile.id,
            version_id=version.id if version else None,
            version=version.version if version else None,
            target_roles=profile.target_roles,
            preferred_locations=profile.preferred_locations,
            future_locations=profile.future_locations,
            domain_strengths=profile.domain_strengths,
            technical_strengths=profile.technical_strengths,
            development_gaps=profile.development_gaps,
        )
        sources.append(
            ContextSource(
                record_type="candidate_profile",
                record_id=profile.id,
                version=version.version if version else None,
            )
        )

    cv_documents: list[ContextCVDocument] = []
    if selection.cv_document_ids:
        unique_ids = list(dict.fromkeys(selection.cv_document_ids))
        documents = list(
            db.scalars(
                select(CVDocument)
                .where(CVDocument.id.in_(unique_ids), CVDocument.active.is_(True))
                .order_by(CVDocument.id)
            ).all()
        )
        if {document.id for document in documents} != set(unique_ids):
            raise LookupError("An attached CV document was not found or is inactive")
        by_id = {document.id: document for document in documents}
        for document_id in unique_ids:
            document = by_id[document_id]
            cv_documents.append(
                ContextCVDocument(
                    id=document.id,
                    file_name=document.file_name,
                    fingerprint=document.fingerprint,
                    extracted_text=document.extracted_text,
                )
            )
            sources.append(
                ContextSource(
                    record_type="cv_document",
                    record_id=document.id,
                    version=document.fingerprint,
                )
            )

    summary = None
    if selection.session_id is not None:
        session = db.get(CopilotSession, selection.session_id)
        if session is None or session.deleted_at is not None:
            raise LookupError("Copilot session not found")
        summary = session.summary

    return CopilotContext(
        route=selection.route,
        job=context_job,
        analysis=context_analysis,
        company=context_company,
        profile=context_profile,
        application_events=application_events,
        cv_documents=cv_documents,
        conversation_summary=summary,
        sources=sources,
        private_data_usage=PrivateDataUsage(
            included=bool(cv_documents),
            record_ids=[document.id for document in cv_documents],
            purpose="Answer using explicitly attached CV evidence" if cv_documents else None,
        ),
    )
