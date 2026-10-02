from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
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

    versions: Mapped[list["CandidateProfileVersion"]] = relationship(
        back_populates="profile", order_by="CandidateProfileVersion.id.desc()"
    )


class CandidateProfileVersion(Base):
    __tablename__ = "candidate_profile_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id"), index=True)
    version: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(200))
    target_roles: Mapped[list[str]] = mapped_column(JSON, default=list)
    preferred_locations: Mapped[list[str]] = mapped_column(JSON, default=list)
    future_locations: Mapped[list[str]] = mapped_column(JSON, default=list)
    domain_strengths: Mapped[list[str]] = mapped_column(JSON, default=list)
    technical_strengths: Mapped[list[str]] = mapped_column(JSON, default=list)
    development_gaps: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profile: Mapped[CandidateProfile] = relationship(back_populates="versions")

    __table_args__ = (
        UniqueConstraint(
            "profile_id", "version", name="uq_candidate_profile_versions_profile_version"
        ),
    )


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
    watchlist_company_id: Mapped[int | None] = mapped_column(
        ForeignKey("watchlist_companies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    watchlist_company: Mapped["WatchListCompany | None"] = relationship()

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
    generated_cvs: Mapped[list["GeneratedCV"]] = relationship(
        back_populates="job", order_by="GeneratedCV.generated_at.desc()"
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
    profile_version_id: Mapped[int] = mapped_column(
        ForeignKey("candidate_profile_versions.id"), index=True
    )
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
    profile_snapshot: Mapped[CandidateProfileVersion] = relationship()


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


class GeneratedCV(Base):
    __tablename__ = "generated_cvs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    file_name: Mapped[str] = mapped_column(String(500), index=True)
    file_path: Mapped[str] = mapped_column(Text)
    output_hash: Mapped[str] = mapped_column(String(64))
    source_cv_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    source_cv_hashes: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    source_evidence: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    model_version: Mapped[str] = mapped_column(String(200))
    prompt_version: Mapped[str] = mapped_column(String(100))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    job: Mapped[Job] = relationship(back_populates="generated_cvs")


class WatchListCompany(TimestampMixin, Base):
    __tablename__ = "watchlist_companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    canonical_domain: Mapped[str] = mapped_column(String(253), unique=True, index=True)
    company_type: Mapped[str] = mapped_column(String(50), index=True)
    strategic_priority: Mapped[str] = mapped_column(String(30), index=True)
    action_window: Mapped[str] = mapped_column(String(40), index=True)
    target_role_patterns: Mapped[list[str]] = mapped_column(JSON, default=list)
    target_locations: Mapped[list[str]] = mapped_column(JSON, default=list)
    positive_keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    exclusion_keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    location_notes: Mapped[str] = mapped_column(Text, default="")
    work_authorization_notes: Mapped[str] = mapped_column(Text, default="")
    official_source_url: Mapped[str] = mapped_column(Text)
    source_kind: Mapped[str] = mapped_column(String(40))
    source_state: Mapped[str] = mapped_column(String(30), index=True)
    source_state_reason: Mapped[str] = mapped_column(Text)
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    rationale: Mapped[str] = mapped_column(Text)

    source_history: Mapped[list["WatchListSourceStateEvent"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        order_by="WatchListSourceStateEvent.id",
    )


class WatchListSourceStateEvent(Base):
    __tablename__ = "watchlist_source_state_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("watchlist_companies.id"), index=True)
    from_state: Mapped[str] = mapped_column(String(30))
    to_state: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    company: Mapped[WatchListCompany] = relationship(back_populates="source_history")


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


class CopilotSession(TimestampMixin, Base):
    __tablename__ = "copilot_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    locale: Mapped[str] = mapped_column(String(20), default="en")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    messages: Mapped[list["CopilotMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="CopilotMessage.id"
    )
    proposals: Mapped[list["CopilotActionProposal"]] = relationship(back_populates="session")
    audits: Mapped[list["CopilotActionAudit"]] = relationship(back_populates="session")


class CopilotMessage(Base):
    __tablename__ = "copilot_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("copilot_sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    sources: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    session: Mapped[CopilotSession] = relationship(back_populates="messages")


class CopilotActionProposal(TimestampMixin, Base):
    __tablename__ = "copilot_action_proposals"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("copilot_sessions.id"), index=True)
    proposal_type: Mapped[str] = mapped_column(String(80), index=True)
    proposal_version: Mapped[str] = mapped_column(String(20))
    target_type: Mapped[str] = mapped_column(String(40))
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    parameters: Mapped[dict[str, object]] = mapped_column(JSON)
    current_value: Mapped[dict[str, object]] = mapped_column(JSON)
    proposed_value: Mapped[dict[str, object]] = mapped_column(JSON)
    side_effects: Mapped[list[str]] = mapped_column(JSON)
    private_data_usage: Mapped[dict[str, object]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped[CopilotSession] = relationship(back_populates="proposals")
    audit: Mapped["CopilotActionAudit | None"] = relationship(
        back_populates="proposal", uselist=False
    )


class CopilotActionAudit(Base):
    __tablename__ = "copilot_action_audits"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("copilot_sessions.id"), index=True)
    proposal_id: Mapped[int | None] = mapped_column(
        ForeignKey("copilot_action_proposals.id"), nullable=True, unique=True
    )
    proposal_type: Mapped[str] = mapped_column(String(80), index=True)
    proposal_version: Mapped[str] = mapped_column(String(20))
    parameter_summary: Mapped[dict[str, object]] = mapped_column(JSON)
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    actor: Mapped[str] = mapped_column(String(100))
    result_record_ids: Mapped[dict[str, list[int]]] = mapped_column(JSON)
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    error_state: Mapped[str | None] = mapped_column(String(200), nullable=True)

    session: Mapped[CopilotSession] = relationship(back_populates="audits")
    proposal: Mapped[CopilotActionProposal | None] = relationship(back_populates="audit")


class CopilotActionItem(TimestampMixin, Base):
    __tablename__ = "copilot_action_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"), nullable=True, index=True)
    item_kind: Mapped[str] = mapped_column(String(30), index=True)
    title: Mapped[str] = mapped_column(String(300))
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
