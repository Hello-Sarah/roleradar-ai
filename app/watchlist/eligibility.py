"""Evidence-based job eligibility, independent from company classification."""

import re
from collections.abc import Iterable
from typing import Protocol

from app.scoring.v2 import positive_evidence_phrases
from app.watchlist.models import (
    EligibilityStatus,
    ExpectedReturn,
    JobEligibility,
    StrategicPriority,
)


class JobLike(Protocol):
    title: str
    location: str
    description: str
    analysis: object | None


class CompanyLike(Protocol):
    strategic_priority: str
    action_window: str
    rationale: str


class ProfileLike(Protocol):
    preferred_locations: list[str]
    future_locations: list[str]


_UNKNOWN_LOCATION = re.compile(r"\b(?:unknown|tbd|to be confirmed|not specified)\b", re.I)
_US_LOCATION = re.compile(r"\b(?:u\.?s\.?a?|united states)\b", re.I)
_SPONSORSHIP_AVAILABLE = re.compile(
    r"\b(?:visa sponsorship (?:is )?(?:available|provided)|"
    r"(?:provide|offer) visa sponsorship|sponsor (?:work )?visas?)\b",
    re.I,
)
_NEGATED_AUTHORIZATION = re.compile(
    r"\b(?:no|not|never|without|cannot|can't|won't|unable|unavailable|must|require[sd]?)\b", re.I
)
_STRICT_POSITIVE_GROUPS: tuple[tuple[str, ...], ...] = (
    ("own", "ownership", "accountable", "decision"),
    ("solution design", "system design", "architecture"),
    ("build", "prototype", "proof of concept"),
    ("evaluate", "evaluation", "experiment"),
    ("deploy", "production", "adoption"),
)
_STRICT_NEGATIVE_PHRASES = (
    "pmo",
    "governance",
    "reporting",
    "vendor coordination",
    "vendor management",
    "steering committee",
    "status tracking",
)


def _matches_location(location: str, configured: Iterable[str]) -> str | None:
    folded_location = _US_LOCATION.sub("united states", location.casefold())
    for candidate in configured:
        folded_candidate = _US_LOCATION.sub("united states", candidate.strip().casefold())
        if folded_candidate and (
            folded_candidate in folded_location or folded_location in folded_candidate
        ):
            return candidate
    return None


def _location_status(job: JobLike, profile: ProfileLike) -> tuple[EligibilityStatus, list[str]]:
    location = (job.location or "").strip()
    if not location or _UNKNOWN_LOCATION.search(location):
        return EligibilityStatus.UNCLEAR, [f"Job location is not explicit: {location or 'missing'}"]
    us_remote = "remote" in location.casefold() and _US_LOCATION.search(location)
    if us_remote:
        explicit_preferred = [
            item for item in profile.preferred_locations if item.strip().casefold() != "remote"
        ]
        if preferred_match := _matches_location(location, explicit_preferred):
            return EligibilityStatus.ELIGIBLE, [
                f"US-remote job '{location}' matches current location '{preferred_match}'."
            ]
        explicit_future = [
            item for item in profile.future_locations if item.strip().casefold() != "remote"
        ]
        if future_match := _matches_location(location, explicit_future):
            return EligibilityStatus.FUTURE, [
                f"US-remote job '{location}' matches future location '{future_match}'."
            ]
        return EligibilityStatus.INELIGIBLE, [
            f"Remote geography is explicitly limited to the United States: {location}"
        ]
    preferred_match = _matches_location(location, profile.preferred_locations)
    if preferred_match:
        return EligibilityStatus.ELIGIBLE, [
            f"Job location '{location}' matches current location '{preferred_match}'."
        ]
    future_match = _matches_location(location, profile.future_locations)
    if future_match:
        return EligibilityStatus.FUTURE, [
            f"Job location '{location}' matches future location '{future_match}'."
        ]
    if "remote" in location.casefold() and not _US_LOCATION.search(location):
        return EligibilityStatus.UNCLEAR, [
            f"Remote geography is not explicit enough to verify eligibility: {location}"
        ]
    return EligibilityStatus.INELIGIBLE, [
        f"Job location '{location}' matches neither a current nor future configured location."
    ]


def _authorization_status(job: JobLike) -> tuple[EligibilityStatus, list[str], bool]:
    # Keep full statements, including negation. Training/event sponsorship is not
    # visa evidence; uncertainty or conflicting clauses never becomes approval.
    statements = [
        part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", job.description) if part.strip()
    ]
    evidence = [
        part
        for part in statements
        if re.search(r"\b(?:visas?|sponsor\w*|authoriz\w*)\b", part, re.I)
    ]
    positive = [
        part
        for part in evidence
        if _SPONSORSHIP_AVAILABLE.search(part) and not _NEGATED_AUTHORIZATION.search(part)
    ]
    if positive and len(positive) == len(evidence):
        return EligibilityStatus.ELIGIBLE, evidence, False
    return (
        EligibilityStatus.UNCLEAR,
        evidence or ["The job provides no explicit work-authorization evidence."],
        True,
    )


def _strict_filter(description: str) -> tuple[bool, list[str]]:
    positives = [
        phrase
        for group in _STRICT_POSITIVE_GROUPS
        if (matches := positive_evidence_phrases(description, group))
        for phrase in matches[:1]
    ]
    negatives = positive_evidence_phrases(description, _STRICT_NEGATIVE_PHRASES)
    passed = len(positives) >= 2 and len(negatives) < len(positives)
    evidence = [*(f"positive: {phrase}" for phrase in positives)]
    evidence.extend(f"review: {phrase}" for phrase in negatives)
    return passed, evidence or ["No strict-filter build or PMO evidence found in the job."]


def _fit_score(job: JobLike) -> int | None:
    analysis = getattr(job, "analysis", None)
    score = getattr(analysis, "fit_score", None)
    return score if isinstance(score, int) and 0 <= score <= 100 else None


def _expected_return(
    location: EligibilityStatus,
    score: int | None,
    strict_passed: bool | None,
    authorization_required_unresolved: bool,
) -> ExpectedReturn:
    if (
        location == EligibilityStatus.INELIGIBLE
        or strict_passed is False
        or (score is not None and score < 55)
    ):
        return ExpectedReturn.SKIP
    if authorization_required_unresolved:
        return ExpectedReturn.RELATIONSHIP_ONLY
    if location == EligibilityStatus.FUTURE:
        return ExpectedReturn.RELOCATE_FIRST
    if location == EligibilityStatus.UNCLEAR or score is None:
        return ExpectedReturn.RELATIONSHIP_ONLY
    if score >= 85:
        return ExpectedReturn.APPLY_NOW
    if score >= 70:
        return ExpectedReturn.STRETCH
    if score >= 55:
        return ExpectedReturn.BUILD_FIRST
    return ExpectedReturn.SKIP


def evaluate_job_eligibility(
    job: JobLike, company: CompanyLike, profile: ProfileLike
) -> JobEligibility:
    """Classify explicit job/profile evidence without changing the job's score."""

    location, location_evidence = _location_status(job, profile)
    authorization, authorization_evidence, authorization_required_unresolved = (
        _authorization_status(job)
    )
    score = _fit_score(job)
    strict_passed: bool | None = None
    job_evidence: list[str] = []
    if company.strategic_priority == StrategicPriority.STRICT_FILTER.value:
        strict_passed, job_evidence = _strict_filter(job.description)
    return JobEligibility(
        location_eligibility=location,
        work_authorization=authorization,
        expected_return=_expected_return(
            location, score, strict_passed, authorization_required_unresolved
        ),
        career_fit_score=score,
        strict_filter_passed=strict_passed,
        location_evidence=location_evidence,
        work_authorization_evidence=authorization_evidence,
        job_evidence=job_evidence,
        inherited_company_rationale=company.rationale,
    )
