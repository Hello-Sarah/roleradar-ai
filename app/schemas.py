from datetime import date, datetime
from enum import StrEnum
from typing import ClassVar, Literal, TypeAlias

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, HttpUrl, model_validator

from app.watchlist.models import (
    ActionWindow,
    CompanyType,
    SourceKind,
    SourceState,
    StrategicPriority,
)

Locale: TypeAlias = Literal["en", "zh-Hans"]


class RoleCategory(StrEnum):
    FORWARD_DEPLOYED_ENGINEER = "Forward Deployed Engineer"
    APPLIED_AI_ENGINEER = "Applied AI Engineer"
    AI_SOLUTIONS = "AI Solutions"
    TECHNICAL_PRODUCT_MANAGER = "Technical Product Manager"
    AI_PRODUCT = "AI Product"
    GENAI_CONSULTING = "GenAI Consulting"
    TRADITIONAL_DATA_ENGINEERING = "Traditional Data Engineering"
    PROJECT_MANAGEMENT = "Project Management"
    RESEARCH = "Research"


class ApplicationStatus(StrEnum):
    NEW = "New"
    SAVED = "Saved"
    APPLIED = "Applied"
    INTERVIEW = "Interview"
    REJECTED = "Rejected"
    OFFER = "Offer"
    IGNORED = "Ignored"


class ActionItemKind(StrEnum):
    LEARNING = "learning"
    NEXT_ACTION = "next_action"


class Recommendation(StrEnum):
    APPLY_NOW = "Apply Now"
    CONSIDER = "Consider"
    BUILD_SKILLS_FIRST = "Build Skills First"
    SKIP = "Skip"


class CandidateProfileBase(BaseModel):
    name: str = "Default Candidate"
    target_roles: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    future_locations: list[str] = Field(default_factory=list)
    domain_strengths: list[str] = Field(default_factory=list)
    technical_strengths: list[str] = Field(default_factory=list)
    development_gaps: list[str] = Field(default_factory=list)


class CandidateProfileCreate(CandidateProfileBase):
    pass


class CandidateProfileRead(CandidateProfileBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CandidateProfileVersionRead(CandidateProfileBase):
    id: int
    profile_id: int
    version: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobCreate(BaseModel):
    company: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=300)
    location: str = Field(min_length=1, max_length=200)
    url: HttpUrl | None = None
    posting_date: date | None = None
    description: str = Field(min_length=40)
    source: str = Field(default="manual", min_length=1, max_length=100)

    @model_validator(mode="after")
    def strip_text(self) -> "JobCreate":
        self.company = self.company.strip()
        self.title = self.title.strip()
        self.location = self.location.strip()
        self.description = self.description.strip()
        return self


class JobPasteCreate(BaseModel):
    text: str = Field(
        min_length=40,
        max_length=100_000,
        description="Raw text copied from a job posting page",
    )


class JobUrlCreate(BaseModel):
    url: AnyHttpUrl


class ClassificationRead(BaseModel):
    category: RoleCategory
    confidence: float = Field(ge=0, le=1)
    evidence: list[str]


class ScoreBreakdown(BaseModel):
    role_alignment: int = Field(ge=0, le=35)
    location_alignment: int = Field(ge=0, le=15)
    domain_alignment: int = Field(ge=0, le=20)
    technical_alignment: int = Field(ge=0, le=30)


class AnalysisRead(BaseModel):
    id: int
    job_id: int
    profile_id: int
    profile_version_id: int
    profile_snapshot: CandidateProfileVersionRead
    created_at: datetime
    scoring_version: str
    profile_version: str
    rubric_version: str
    model_version: str
    prompt_version: str
    fit_score: int = Field(ge=0, le=100)
    score_breakdown: dict[str, int]
    score_details: dict[str, object]
    strengths: list[str]
    gaps: list[str]
    evidence: list[str]
    recommendation: str
    summary: str
    model_used: str


class ApplicationEventCreate(BaseModel):
    status: ApplicationStatus
    occurred_at: datetime
    channel: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=2_000)
    next_follow_up_date: date | None = None


class ApplicationEventRead(ApplicationEventCreate):
    id: int
    job_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobRead(BaseModel):
    id: int
    company: str
    title: str
    location: str
    url: str | None
    posting_date: date | None
    description: str
    source: str
    status: ApplicationStatus
    created_at: datetime
    updated_at: datetime
    classification: ClassificationRead | None = None
    analysis: AnalysisRead | None = None
    application_events: list[ApplicationEventRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class StatusUpdate(BaseModel):
    status: ApplicationStatus


class WatchListCompanyBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    canonical_domain: str = Field(min_length=1, max_length=253)
    company_type: CompanyType
    strategic_priority: StrategicPriority
    action_window: ActionWindow
    target_role_patterns: list[str] = Field(default_factory=list)
    target_locations: list[str] = Field(default_factory=list)
    positive_keywords: list[str] = Field(default_factory=list)
    exclusion_keywords: list[str] = Field(default_factory=list)
    location_notes: str = Field(default="", max_length=4_000)
    work_authorization_notes: str = Field(default="", max_length=4_000)
    official_source_url: AnyHttpUrl
    source_kind: SourceKind
    source_state: SourceState
    source_state_reason: str = Field(min_length=1, max_length=2_000)
    last_verified_at: datetime | None = None
    last_checked_at: datetime | None = None
    rationale: str = Field(min_length=1, max_length=4_000)

    @model_validator(mode="after")
    def normalize_identity(self) -> "WatchListCompanyBase":
        self.name = self.name.strip()
        self.canonical_domain = self.canonical_domain.strip().casefold().removeprefix("www.")
        if "/" in self.canonical_domain or ":" in self.canonical_domain:
            raise ValueError("canonical_domain must be a domain, not a URL")
        return self


class WatchListCompanyCreate(WatchListCompanyBase):
    pass


class WatchListCompanyUpdate(BaseModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "name",
            "canonical_domain",
            "company_type",
            "strategic_priority",
            "action_window",
            "target_role_patterns",
            "target_locations",
            "positive_keywords",
            "exclusion_keywords",
            "location_notes",
            "work_authorization_notes",
            "official_source_url",
            "source_kind",
            "source_state",
            "source_state_reason",
            "rationale",
        }
    )

    name: str | None = Field(default=None, min_length=1, max_length=200)
    canonical_domain: str | None = Field(default=None, min_length=1, max_length=253)
    company_type: CompanyType | None = None
    strategic_priority: StrategicPriority | None = None
    action_window: ActionWindow | None = None
    target_role_patterns: list[str] | None = None
    target_locations: list[str] | None = None
    positive_keywords: list[str] | None = None
    exclusion_keywords: list[str] | None = None
    location_notes: str | None = Field(default=None, max_length=4_000)
    work_authorization_notes: str | None = Field(default=None, max_length=4_000)
    official_source_url: AnyHttpUrl | None = None
    source_kind: SourceKind | None = None
    source_state: SourceState | None = None
    source_state_reason: str | None = Field(default=None, min_length=1, max_length=2_000)
    last_verified_at: datetime | None = None
    last_checked_at: datetime | None = None
    rationale: str | None = Field(default=None, min_length=1, max_length=4_000)

    @model_validator(mode="before")
    @classmethod
    def reject_explicit_nulls(cls, data: object) -> object:
        if isinstance(data, dict):
            null_fields = sorted(
                field for field in cls.non_nullable_fields if data.get(field, ...) is None
            )
            if null_fields:
                raise ValueError(f"Required stored fields cannot be null: {', '.join(null_fields)}")
        return data

    @model_validator(mode="after")
    def validate_source_transition_and_identity(self) -> "WatchListCompanyUpdate":
        if self.source_state is not None and self.source_state_reason is None:
            raise ValueError("source_state_reason is required when source_state changes")
        if self.name is not None:
            self.name = self.name.strip()
        if self.canonical_domain is not None:
            self.canonical_domain = self.canonical_domain.strip().casefold().removeprefix("www.")
            if "/" in self.canonical_domain or ":" in self.canonical_domain:
                raise ValueError("canonical_domain must be a domain, not a URL")
        return self


class WatchListSourceStateEventRead(BaseModel):
    id: int
    from_state: SourceState
    to_state: SourceState
    reason: str
    changed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WatchListCompanyRead(WatchListCompanyBase):
    id: int
    enabled: bool
    created_at: datetime
    updated_at: datetime
    source_history: list[WatchListSourceStateEventRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class DigestTrendRead(BaseModel):
    category: str
    new_roles: int


class DigestRead(BaseModel):
    generated_at: datetime
    high_priority_jobs: list[JobRead]
    new_companies: list[str]
    emerging_skills: list[tuple[str, int]]
    hiring_trends: list[DigestTrendRead]


class TrendPoint(BaseModel):
    week: str
    jobs: int
    average_fit_score: float


class DueFollowUpRead(BaseModel):
    job: JobRead
    next_follow_up_date: date
    notes: str | None = None


class DashboardRead(BaseModel):
    high_priority_jobs: list[JobRead]
    recently_added_jobs: list[JobRead]
    status_counts: dict[str, int]
    skill_gap_trends: list[tuple[str, int]]
    weekly_hiring_trends: list[TrendPoint]
    due_follow_ups: list[DueFollowUpRead]


class CVDocumentRead(BaseModel):
    id: int
    file_name: str
    file_type: str
    fingerprint: str
    modified_at: datetime
    active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CVLibraryScanRead(BaseModel):
    library_path: str
    discovered: int
    added: int
    updated: int
    unchanged: int
    failed: list[str]
    documents: list[CVDocumentRead]


class GeneratedCVRead(BaseModel):
    id: int
    job_id: int
    file_name: str
    file_path: str
    source_cv_ids: list[int]
    source_cv_hashes: dict[str, str]
    output_hash: str
    model_version: str
    prompt_version: str
    generated_at: datetime
