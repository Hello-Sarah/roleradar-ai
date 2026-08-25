import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.analysis.classifier import classify_job
from app.analysis.explainer import explain_fit
from app.config import Settings
from app.database.models import (
    ApplicationEvent,
    CandidateProfile,
    Job,
    JobAnalysis,
    JobClassification,
)
from app.ingestion.normalizer import job_fingerprint, normalize_job
from app.schemas import (
    AnalysisRead,
    ApplicationEventCreate,
    ApplicationEventRead,
    ApplicationStatus,
    ClassificationRead,
    DashboardRead,
    DigestRead,
    JobCreate,
    JobRead,
    ScoreBreakdown,
    TrendPoint,
)
from app.scoring.engine import score_job
from app.services.profile_service import get_or_create_profile, to_profile_read

logger = logging.getLogger(__name__)


class DuplicateJobError(ValueError):
    pass


def _job_query():
    return select(Job).options(
        selectinload(Job.classification),
        selectinload(Job.analysis),
        selectinload(Job.application_events),
    )


def to_job_read(job: Job) -> JobRead:
    classification = None
    if job.classification:
        classification = ClassificationRead(
            category=job.classification.category,
            confidence=job.classification.confidence,
            evidence=job.classification.evidence,
        )
    analysis = None
    if job.analysis:
        analysis = AnalysisRead(
            fit_score=job.analysis.fit_score,
            score_breakdown=ScoreBreakdown.model_validate(job.analysis.score_breakdown),
            strengths=job.analysis.strengths,
            gaps=job.analysis.gaps,
            evidence=job.analysis.evidence,
            recommendation=job.analysis.recommendation,
            summary=job.analysis.summary,
            model_used=job.analysis.model_used,
        )
    return JobRead(
        id=job.id,
        company=job.company,
        title=job.title,
        location=job.location,
        url=job.url,
        posting_date=job.posting_date,
        description=job.description,
        source=job.source,
        status=job.status,
        created_at=job.created_at,
        updated_at=job.updated_at,
        classification=classification,
        analysis=analysis,
        application_events=[
            ApplicationEventRead.model_validate(event) for event in job.application_events
        ],
    )


def create_and_analyze_job(db: Session, payload: JobCreate, settings: Settings) -> Job:
    normalized = normalize_job(payload)
    fingerprint = job_fingerprint(normalized)
    if db.scalar(select(Job.id).where(Job.fingerprint == fingerprint)):
        raise DuplicateJobError("This job already exists")

    profile: CandidateProfile = get_or_create_profile(db)
    classification = classify_job(normalized.title, normalized.description)
    score = score_job(
        title=normalized.title,
        location=normalized.location,
        description=normalized.description,
        classification=classification,
        profile=to_profile_read(profile),
    )
    explanation, model_used = explain_fit(
        job=normalized,
        profile=to_profile_read(profile),
        classification=classification,
        result=score,
        settings=settings,
    )
    job = Job(
        fingerprint=fingerprint,
        **normalized.model_dump(mode="python", exclude={"url"}),
        url=str(normalized.url) if normalized.url else None,
        status=ApplicationStatus.NEW.value,
    )
    job.classification = JobClassification(**classification.model_dump(mode="json"))
    job.analysis = JobAnalysis(
        profile_id=profile.id,
        fit_score=score.fit_score,
        score_breakdown=score.breakdown.model_dump(),
        strengths=explanation.strengths,
        gaps=explanation.gaps,
        evidence=explanation.evidence,
        recommendation=score.recommendation.value,
        summary=explanation.summary,
        model_used=model_used,
    )
    db.add(job)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateJobError("This job already exists") from exc
    return get_job(db, job.id)


def get_job(db: Session, job_id: int) -> Job:
    job = db.scalar(_job_query().where(Job.id == job_id))
    if job is None:
        raise LookupError("Job not found")
    return job


def list_jobs(
    db: Session,
    *,
    status: ApplicationStatus | None = None,
    min_fit_score: int | None = None,
    limit: int = 100,
) -> list[Job]:
    query = (
        _job_query().join(Job.analysis, isouter=True).order_by(desc(Job.created_at)).limit(limit)
    )
    if status:
        query = query.where(Job.status == status.value)
    if min_fit_score is not None:
        query = query.where(JobAnalysis.fit_score >= min_fit_score)
    return list(db.scalars(query).all())


def update_status(db: Session, job_id: int, status: ApplicationStatus) -> Job:
    job = get_job(db, job_id)
    if job.status == status.value:
        return job
    job.status = status.value
    job.application_events.append(
        ApplicationEvent(
            status=status.value,
            occurred_at=datetime.now(UTC),
            notes=f"Status changed to {status.value}",
        )
    )
    db.commit()
    return get_job(db, job_id)


def add_application_event(
    db: Session, job_id: int, payload: ApplicationEventCreate
) -> ApplicationEvent:
    job = get_job(db, job_id)
    event = ApplicationEvent(job_id=job.id, **payload.model_dump(mode="python"))
    job.status = payload.status.value
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def list_application_events(db: Session, job_id: int) -> list[ApplicationEvent]:
    get_job(db, job_id)
    return list(
        db.scalars(
            select(ApplicationEvent)
            .where(ApplicationEvent.job_id == job_id)
            .order_by(desc(ApplicationEvent.occurred_at), desc(ApplicationEvent.id))
        ).all()
    )


def _gap_counts(jobs: list[Job]) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for job in jobs:
        if job.analysis:
            for gap in job.analysis.gaps:
                if not gap.startswith("No explicit"):
                    counts[gap] = counts.get(gap, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def get_dashboard(db: Session) -> DashboardRead:
    jobs = list_jobs(db, limit=500)
    high_priority = [job for job in jobs if job.analysis and job.analysis.fit_score >= 75]
    status_counts = {status.value: 0 for status in ApplicationStatus}
    for job in jobs:
        status_counts[job.status] = status_counts.get(job.status, 0) + 1

    grouped: dict[str, list[int]] = {}
    for job in jobs:
        if job.analysis:
            week = job.created_at.strftime("%Y-%W")
            grouped.setdefault(week, []).append(job.analysis.fit_score)
    week_rows = [
        (week, len(scores), sum(scores) / len(scores)) for week, scores in sorted(grouped.items())
    ]
    return DashboardRead(
        high_priority_jobs=[to_job_read(job) for job in high_priority[:10]],
        recently_added_jobs=[to_job_read(job) for job in jobs[:10]],
        status_counts=status_counts,
        skill_gap_trends=_gap_counts(jobs)[:10],
        weekly_hiring_trends=[
            TrendPoint(week=str(week), jobs=count, average_fit_score=round(float(avg or 0), 1))
            for week, count, avg in week_rows
        ],
    )


def get_daily_digest(db: Session) -> DigestRead:
    jobs = list_jobs(db, limit=500)
    cutoff = datetime.now(UTC) - timedelta(days=1)
    recent = [job for job in jobs if job.created_at.replace(tzinfo=UTC) >= cutoff]
    priority = [job for job in recent if job.analysis and job.analysis.fit_score >= 75]
    companies = sorted({job.company for job in recent})
    categories: dict[str, int] = {}
    for job in recent:
        if job.classification:
            key = job.classification.category
            categories[key] = categories.get(key, 0) + 1
    trends = [f"{category}: {count} new role(s)" for category, count in categories.items()]
    return DigestRead(
        generated_at=datetime.now(UTC),
        high_priority_jobs=[to_job_read(job) for job in priority],
        new_companies=companies,
        emerging_skills=_gap_counts(recent)[:5],
        hiring_trends=trends,
    )
