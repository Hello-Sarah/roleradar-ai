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
    analysis: Mapped["JobAnalysis | None"] = relationship(
        back_populates="job", cascade="all, delete-orphan", uselist=False
    )


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
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), unique=True, index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id"))
    fit_score: Mapped[int] = mapped_column(Integer, index=True)
    score_breakdown: Mapped[dict[str, int]] = mapped_column(JSON)
    strengths: Mapped[list[str]] = mapped_column(JSON, default=list)
    gaps: Mapped[list[str]] = mapped_column(JSON, default=list)
    evidence: Mapped[list[str]] = mapped_column(JSON, default=list)
    recommendation: Mapped[str] = mapped_column(String(50))
    summary: Mapped[str] = mapped_column(Text)
    model_used: Mapped[str] = mapped_column(String(100), default="deterministic-fallback")

    job: Mapped[Job] = relationship(back_populates="analysis")
