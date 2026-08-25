from datetime import date, datetime
from enum import StrEnum
from typing import Literal, TypeAlias

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, HttpUrl, model_validator

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


class DigestRead(BaseModel):
    generated_at: datetime
    high_priority_jobs: list[JobRead]
    new_companies: list[str]
    emerging_skills: list[tuple[str, int]]
    hiring_trends: list[str]


class TrendPoint(BaseModel):
    week: str
    jobs: int
    average_fit_score: float


class DashboardRead(BaseModel):
    high_priority_jobs: list[JobRead]
    recently_added_jobs: list[JobRead]
    status_counts: dict[str, int]
    skill_gap_trends: list[tuple[str, int]]
    weekly_hiring_trends: list[TrendPoint]


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
    job_id: int
    file_name: str
    file_path: str
    source_cv_ids: list[int]
    generated_at: datetime
