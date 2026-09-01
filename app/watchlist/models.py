"""Stable Watch List domain values and eligibility output contracts."""

from enum import StrEnum

from pydantic import BaseModel, Field


class CompanyType(StrEnum):
    AI_NATIVE_FORWARD_DEPLOYED = "ai_native_forward_deployed"
    FINTECH_PRODUCT = "fintech_product"
    CLOUD_DATA_ENTERPRISE_AI = "cloud_data_enterprise_ai"
    FINANCIAL_INSTITUTION = "financial_institution"
    CONSULTING_PROFESSIONAL_SERVICES = "consulting_professional_services"


class StrategicPriority(StrEnum):
    CORE_TARGET = "core_target"
    MONITOR = "monitor"
    OPPORTUNISTIC = "opportunistic"
    STRICT_FILTER = "strict_filter"


class ActionWindow(StrEnum):
    APPLY_NOW = "apply_now"
    STRETCH_APPLY = "stretch_apply"
    APPLY_IN_3_TO_6_MONTHS = "apply_in_3_to_6_months"
    APPLY_AFTER_US_RELOCATION = "apply_after_us_relocation"
    RELATIONSHIP_ONLY = "relationship_only"


class SourceKind(StrEnum):
    CAREER_PAGE = "career_page"
    OFFICIAL_API = "official_api"
    STRUCTURED_VENDOR_FEED = "structured_vendor_feed"


class SourceState(StrEnum):
    UNVERIFIED = "unverified"
    VERIFIED_MANUAL = "verified_manual"
    STRUCTURED_READY = "structured_ready"
    DEGRADED = "degraded"
    DISABLED = "disabled"


class EligibilityStatus(StrEnum):
    ELIGIBLE = "eligible"
    FUTURE = "future"
    UNCLEAR = "unclear"
    INELIGIBLE = "ineligible"


class ExpectedReturn(StrEnum):
    APPLY_NOW = "apply_now"
    STRETCH = "stretch_apply"
    BUILD_FIRST = "build_first"
    RELOCATE_FIRST = "relocate_first"
    RELATIONSHIP_ONLY = "relationship_only"
    SKIP = "skip"


class JobEligibility(BaseModel, frozen=True):
    location_eligibility: EligibilityStatus
    work_authorization: EligibilityStatus
    expected_return: ExpectedReturn
    career_fit_score: int | None = Field(default=None, ge=0, le=100)
    strict_filter_passed: bool | None = None
    location_evidence: list[str] = Field(min_length=1)
    work_authorization_evidence: list[str] = Field(min_length=1)
    job_evidence: list[str] = Field(default_factory=list)
    inherited_company_rationale: str
