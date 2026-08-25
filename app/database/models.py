from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CandidateProfile(TimestampMixin, Base):
    __tablename__ = "candidate_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), default="Default Candidate")
    target_roles: Mapped[list[str]] = mapped_column(JSON, default=list)
    preferred_locations: Mapped[list[str]] = mapped_column(JSON, default=list)
    future_locations: Mapped[list[str]] = mapped_column(JSON, default=list)
    domain_strengths: Mapped[list[str]] = mapped_column(JSON, default=list)
    technical_strengths: Mapped[list[str]] = mapped_column(JSON, default=list)
    development_gaps: Mapped[list[str]] = mapped_column(JSON, default=list)


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    company: Mapped[str] = mapped_column(String(200), index=True)
    title: Mapped[str] = mapped_column(String(300), index=True)
    location: Mapped[str] = mapped_column(String(200))
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    posting_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(100), default="manual")
    status: Mapped[str] = mapped_column(String(30), default="New", index=True)

    classification: Mapped["JobClassification | None"] = relationship(
        back_populates="job", cascade="all, delete-orphan", uselist=False
    )
    analyses: Mapped[list["JobAnalysis"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="JobAnalysis.id.desc()",
    )
    application_events: Mapped[list["ApplicationEvent"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="ApplicationEvent.occurred_at.desc()",
    )

    @property
    def analysis(self) -> "JobAnalysis | None":
        """Return the newest immutable analysis for backward-compatible job reads."""
        return self.analyses[0] if self.analyses else None


class JobClassification(TimestampMixin, Base):
    __tablename__ = "job_classifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(100))
    confidence: Mapped[float] = mapped_column(Float)
    evidence: Mapped[list[str]] = mapped_column(JSON, default=list)

    job: Mapped[Job] = relationship(back_populates="classification")


class JobAnalysis(TimestampMixin, Base):
    __tablename__ = "job_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id"))
    scoring_version: Mapped[str] = mapped_column(String(50), default="legacy-v1")
    profile_version: Mapped[str] = mapped_column(String(100), default="legacy-profile")
    rubric_version: Mapped[str] = mapped_column(String(50), default="legacy-v1")
    model_version: Mapped[str] = mapped_column(String(200), default="deterministic-fallback")
    prompt_version: Mapped[str] = mapped_column(String(100), default="legacy-prompt")
    fit_score: Mapped[int] = mapped_column(Integer, index=True)
    score_breakdown: Mapped[dict[str, int]] = mapped_column(JSON)
    score_details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    strengths: Mapped[list[str]] = mapped_column(JSON, default=list)
    gaps: Mapped[list[str]] = mapped_column(JSON, default=list)
    evidence: Mapped[list[str]] = mapped_column(JSON, default=list)
    recommendation: Mapped[str] = mapped_column(String(50))
    summary: Mapped[str] = mapped_column(Text)
    model_used: Mapped[str] = mapped_column(String(100), default="deterministic-fallback")

    job: Mapped[Job] = relationship(back_populates="analyses")


class ApplicationEvent(TimestampMixin, Base):
    __tablename__ = "application_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    channel: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_follow_up_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)

    job: Mapped[Job] = relationship(back_populates="application_events")


class CVDocument(TimestampMixin, Base):
    __tablename__ = "cv_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_path: Mapped[str] = mapped_column(Text, unique=True)
    file_name: Mapped[str] = mapped_column(String(500), index=True)
    file_type: Mapped[str] = mapped_column(String(20))
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    extracted_text: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(default=True, index=True)


class WorkflowRun(TimestampMixin, Base):
    __tablename__ = "workflow_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_type: Mapped[str] = mapped_column(String(100), index=True)
    contract_version: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30), index=True)
    input_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    result_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(200), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)

    steps: Mapped[list["WorkflowStep"]] = relationship(
        back_populates="workflow_run", cascade="all, delete-orphan"
    )


class WorkflowStep(TimestampMixin, Base):
    __tablename__ = "workflow_steps"

    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_run_id: Mapped[int] = mapped_column(ForeignKey("workflow_runs.id"), index=True)
    step_name: Mapped[str] = mapped_column(String(100), index=True)
    version: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30), index=True)
    input_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    result_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    workflow_run: Mapped[WorkflowRun] = relationship(back_populates="steps")
