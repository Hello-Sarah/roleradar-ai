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
    CandidateProfileVersionRead,
    ClassificationRead,
    DashboardRead,
    DigestRead,
    JobCreate,
    JobRead,
    TrendPoint,
)
from app.scoring.rules import PROMPT_VERSION, SCORING_VERSION
from app.scoring.v2 import JobEvidence, ProfileEvidence, score_job_v2
from app.services.profile_service import (
    get_or_create_profile,
    get_or_create_profile_version,
    to_profile_read,
)

logger = logging.getLogger(__name__)


class DuplicateJobError(ValueError):
    pass


def _job_query():
    return (
        select(Job)
        .options(
            selectinload(Job.classification),
            selectinload(Job.analyses).selectinload(JobAnalysis.profile_snapshot),
            selectinload(Job.application_events),
        )
        .execution_options(populate_existing=True)
    )


def to_analysis_read(analysis: JobAnalysis) -> AnalysisRead:
    return AnalysisRead(
        id=analysis.id,
        job_id=analysis.job_id,
        profile_id=analysis.profile_id,
        profile_version_id=analysis.profile_version_id,
        profile_snapshot=CandidateProfileVersionRead.model_validate(analysis.profile_snapshot),
        created_at=analysis.created_at,
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
        model_used=analysis.model_used,
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
        analysis = to_analysis_read(job.analysis)
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


def _build_analysis(
    db: Session, job: Job, profile: CandidateProfile, settings: Settings
) -> JobAnalysis:
    score = score_job_v2(
        JobEvidence(title=job.title, description=job.description),
        ProfileEvidence(
            target_roles=profile.target_roles,
            domain_strengths=profile.domain_strengths,
            technical_strengths=profile.technical_strengths,
            development_gaps=profile.development_gaps,
        ),
    )
    details = score.model_dump(mode="json")
    strengths = [flag.code for flag in score.matched_green_flags]
    gaps = [
        weak
        for dimension in score.dimensions.values()
        for weak in dimension.missing_or_weak_evidence
    ]
    explanation, model_used = explain_fit(
        job=JobCreate(
            company=job.company,
            title=job.title,
            location=job.location,
            url=job.url,
            posting_date=job.posting_date,
            description=job.description,
            source=job.source,
        ),
        profile=to_profile_read(profile),
        classification=ClassificationRead(
            category=job.classification.category,
            confidence=job.classification.confidence,
            evidence=job.classification.evidence,
        ),
        result=score,
        settings=settings,
    )
    profile_snapshot = get_or_create_profile_version(db, profile)
    return JobAnalysis(
        profile_id=profile.id,
        profile_snapshot=profile_snapshot,
        scoring_version=SCORING_VERSION,
        profile_version=profile_snapshot.version,
        rubric_version=SCORING_VERSION,
        model_version=model_used,
        prompt_version=PROMPT_VERSION,
        fit_score=score.total_score,
        score_breakdown={name: dimension.score for name, dimension in score.dimensions.items()},
        score_details=details,
        strengths=strengths or ["NO_MATCHED_GREEN_FLAGS"],
        gaps=gaps or ["NO_WEAK_DIMENSIONS"],
        evidence=[f"{item.id}: {item.text}" for item in score.evidence],
        recommendation=score.recommendation_band,
        summary=explanation.summary,
        model_used=model_used,
    )


def create_and_analyze_job(db: Session, payload: JobCreate, settings: Settings) -> Job:
    normalized = normalize_job(payload)
    fingerprint = job_fingerprint(normalized)
    if db.scalar(select(Job.id).where(Job.fingerprint == fingerprint)):
        raise DuplicateJobError("This job already exists")

    profile: CandidateProfile = get_or_create_profile(db)
    classification = classify_job(normalized.title, normalized.description)
    job = Job(
        fingerprint=fingerprint,
        **normalized.model_dump(mode="python", exclude={"url"}),
        url=str(normalized.url) if normalized.url else None,
        status=ApplicationStatus.NEW.value,
    )
    job.classification = JobClassification(**classification.model_dump(mode="json"))
    job.analyses.append(_build_analysis(db, job, profile, settings))
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
    query = _job_query().order_by(desc(Job.created_at)).limit(limit)
    if status:
        query = query.where(Job.status == status.value)
    if min_fit_score is not None:
        latest_score = (
            select(JobAnalysis.fit_score)
            .where(JobAnalysis.job_id == Job.id)
            .order_by(desc(JobAnalysis.id))
            .limit(1)
            .correlate(Job)
            .scalar_subquery()
        )
        query = query.where(latest_score >= min_fit_score)
    return list(db.scalars(query).all())


def list_analyses(db: Session, job_id: int) -> list[JobAnalysis]:
    get_job(db, job_id)
    return list(
        db.scalars(
            select(JobAnalysis).where(JobAnalysis.job_id == job_id).order_by(desc(JobAnalysis.id))
        ).all()
    )


def reanalyze_job(db: Session, job_id: int, settings: Settings) -> JobAnalysis:
    job = get_job(db, job_id)
    profile = get_or_create_profile(db)
    analysis = _build_analysis(db, job, profile, settings)
    job.analyses.append(analysis)
    db.commit()
    db.refresh(analysis)
    logger.info(
        "job reanalyzed",
        extra={
            "job_id": job_id,
            "analysis_id": analysis.id,
            "scoring_version": analysis.scoring_version,
        },
    )
    return analysis


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
