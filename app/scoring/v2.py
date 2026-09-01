"""Deterministic, evidence-linked Career Fit Score V2."""

import re
from collections.abc import Iterable

from pydantic import BaseModel, Field, model_validator

from app.scoring.rules import (
    AI_TITLE_PHRASES,
    COUNTER_EVIDENCE_PHRASES,
    DIMENSION_MAXIMA,
    DIMENSION_RULES,
    GREEN_FLAG_PHRASES,
    RED_FLAG_PHRASES,
    SCORING_VERSION,
)


class EvidenceItem(BaseModel, frozen=True):
    id: str = Field(pattern=r"^jd-[A-Za-z0-9][A-Za-z0-9._:-]*$")
    text: str = Field(min_length=1)


class JobEvidence(BaseModel):
    title: str
    description: str = ""
    evidence: list[EvidenceItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def populate_evidence(self) -> "JobEvidence":
        if self.evidence:
            if len({item.id for item in self.evidence}) != len(self.evidence):
                raise ValueError("JD evidence IDs must be unique")
            title_evidence = next((item for item in self.evidence if item.id == "jd-title"), None)
            if title_evidence is None:
                self.evidence.insert(0, EvidenceItem(id="jd-title", text=self.title.strip()))
            elif title_evidence.text != self.title.strip():
                raise ValueError("jd-title evidence must exactly match the job title")
            return self
        snippets = [part.strip() for part in re.split(r"(?<=[.!?])\s+|[\r\n]+", self.description)]
        self.evidence = [
            EvidenceItem(id=f"jd-{index:03d}", text=text)
            for index, text in enumerate(snippets, 1)
            if text
        ]
        if self.title:
            self.evidence.insert(0, EvidenceItem(id="jd-title", text=self.title.strip()))
        return self


class ProfileEvidence(BaseModel):
    target_roles: list[str] = Field(default_factory=list)
    domain_strengths: list[str] = Field(default_factory=list)
    technical_strengths: list[str] = Field(default_factory=list)
    development_gaps: list[str] = Field(default_factory=list)


class Deduction(BaseModel, frozen=True):
    code: str
    points: int = Field(gt=0)
    evidence_ids: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_evidence(self) -> "Deduction":
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("deduction evidence IDs must be unique")
        return self


class DimensionScore(BaseModel, frozen=True):
    score: int = Field(ge=0)
    max_score: int = Field(gt=0)
    evidence_ids: list[str] = Field(default_factory=list)
    missing_or_weak_evidence: list[str] = Field(default_factory=list)
    deductions: list[Deduction] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_bound_and_support(self) -> "DimensionScore":
        if self.score > self.max_score:
            raise ValueError("dimension score exceeds its maximum")
        if self.score and not self.evidence_ids:
            raise ValueError("a non-zero dimension must reference JD evidence")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("dimension evidence IDs must be unique")
        return self


class EvidenceFlag(BaseModel, frozen=True):
    code: str
    evidence_ids: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_evidence(self) -> "EvidenceFlag":
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("flag evidence IDs must be unique")
        return self


class CriticalWarning(EvidenceFlag):
    message: str


class CareerFitV2(BaseModel, frozen=True):
    scoring_version: str = SCORING_VERSION
    dimensions: dict[str, DimensionScore]
    evidence: list[EvidenceItem]
    matched_green_flags: list[EvidenceFlag]
    matched_red_flags: list[EvidenceFlag]
    critical_warnings: list[CriticalWarning]
    total_score: int = Field(ge=0, le=100)
    recommendation_band: str
    concise_explanation: str
    recommended_next_action: str

    @model_validator(mode="after")
    def validate_total_and_dimensions(self) -> "CareerFitV2":
        if self.scoring_version != SCORING_VERSION:
            raise ValueError(f"scoring version must be {SCORING_VERSION}")
        if set(self.dimensions) != set(DIMENSION_MAXIMA):
            raise ValueError("Career Fit V2 requires exactly six dimensions")
        for name, expected_maximum in DIMENSION_MAXIMA.items():
            if self.dimensions[name].max_score != expected_maximum:
                raise ValueError(f"{name} maximum must be {expected_maximum}")
        derived_total = sum(dimension.score for dimension in self.dimensions.values())
        if self.total_score != derived_total:
            raise ValueError("total score must be derived only from dimensions")
        if self.recommendation_band != recommendation_band(self.total_score):
            raise ValueError("recommendation band must be derived from total score")
        catalog_ids = [item.id for item in self.evidence]
        if len(set(catalog_ids)) != len(catalog_ids):
            raise ValueError("JD evidence catalog IDs must be unique")
        known_ids = set(catalog_ids)
        referenced_ids = {
            item_id for dimension in self.dimensions.values() for item_id in dimension.evidence_ids
        }
        referenced_ids.update(
            item_id
            for dimension in self.dimensions.values()
            for deduction in dimension.deductions
            for item_id in deduction.evidence_ids
        )
        referenced_ids.update(
            item_id
            for flag in [
                *self.matched_green_flags,
                *self.matched_red_flags,
                *self.critical_warnings,
            ]
            for item_id in flag.evidence_ids
        )
        if not referenced_ids <= known_ids:
            raise ValueError("all references must belong to the JD evidence catalog")
        return self

    @property
    def version(self) -> str:
        return self.scoring_version

    @property
    def total(self) -> int:
        return self.total_score

    @property
    def band(self) -> str:
        return self.recommendation_band


def recommendation_band(score: int) -> str:
    if not 0 <= score <= 100:
        raise ValueError("score must be between 0 and 100")
    if score >= 85:
        return "Must Apply"
    if score >= 70:
        return "Strong Apply"
    if score >= 55:
        return "Selective"
    return "Skip"


def _contains(text: str, phrase: str) -> bool:
    normalized = text.casefold().replace("→", " to ")
    candidate = phrase.casefold().replace("→", " to ")
    return bool(re.search(rf"(?<!\w){re.escape(candidate)}(?!\w)", normalized))


_NEGATION_PATTERN = re.compile(
    r"\b(?:no|not|never|without|cannot|can't|won't|isn't|aren't|doesn't|don't|"
    r"does\s+not|do\s+not|will\s+not|is\s+not|are\s+not|little|lack|lacks|lacking)\b"
)
_NON_NEGATING_PATTERN = re.compile(r"\bnot\s+(?:only|just)\b")
_HARD_SCOPE_BOUNDARY_PATTERN = re.compile(r"[;]|\b(?:but|however|instead|rather|whereas|while)\b")
_SUBORDINATE_BOUNDARY_PATTERN = re.compile(
    r"\b(?:who|whom|whose|which|that|where|when|because|although|unless)\b"
)
_COORDINATOR_PATTERN = re.compile(r",?\s+(?:and|or)\s+")
_COMMA_PATTERN = re.compile(r",\s+")
_FINITE_VERB = (
    r"will|shall|can|could|must|may|might|should|would|do|does|did|is|are|was|were|"
    r"has|have|had|builds?|deploys?|designs?|owns?|coordinates?|leads?|writes?|"
    r"develops?|creates?|manages?|delivers?|evaluates?|experiments?|works?|"
    r"includes?|involves?|requires?|uses?"
)
_SUBJECT_PREDICATE_PATTERN = re.compile(
    rf"^(?P<subject>(?:(?!(?:and|or|but|who|whom|whose|which|that)\b)"
    rf"[a-z][a-z0-9'-]*\s+){{1,5}}?)(?P<verb>{_FINITE_VERB})\b"
)
_IMPERATIVE_VERB = (
    r"build|deploy|design|own|coordinate|lead|write|develop|create|manage|deliver|evaluate|"
    r"experiment|work|include|involve|require|use"
)
_IMPERATIVE_PREDICATE_PATTERN = re.compile(rf"^(?:{_IMPERATIVE_VERB})\b\s+(?!(?:and|or)\b)\S+")
_SHARED_POST_NEGATION_PATTERN = re.compile(
    r"\b(?:is|are|was|were|will\s+be)\s+(?:not|never)\s+"
    r"(?:involved|required|included|expected|used|part\s+of\s+(?:the\s+)?scope|in\s+scope)\b|"
    r"\b(?:is|are|was|were)\s+(?:excluded|out\s+of\s+scope)\b|"
    r"\b(?:isn't|aren't|wasn't|weren't)\s+"
    r"(?:involved|required|included|expected|used)\b"
)
_SCORING_EVIDENCE_PHRASES = tuple(
    dict.fromkeys(
        phrase
        for phrases in (
            *(rule.phrases for rules in DIMENSION_RULES.values() for rule in rules),
            *GREEN_FLAG_PHRASES.values(),
            *RED_FLAG_PHRASES.values(),
            COUNTER_EVIDENCE_PHRASES,
        )
        for phrase in phrases
    )
)


def _is_coordinated_negated_list(
    text: str, boundary: re.Match[str], predicate: re.Match[str]
) -> bool:
    post_predicate = text[boundary.end() + predicate.start("verb") :]
    if not _SHARED_POST_NEGATION_PATTERN.match(post_predicate):
        return False
    negative_subject = predicate.group("subject").strip()
    if not any(_contains(negative_subject, phrase) for phrase in _SCORING_EVIDENCE_PHRASES):
        return False
    prior_hard_boundaries = list(_HARD_SCOPE_BOUNDARY_PATTERN.finditer(text[: boundary.start()]))
    segment_start = prior_hard_boundaries[-1].end() if prior_hard_boundaries else 0
    prefix = text[segment_start : boundary.start()]
    prior_segments = tuple(
        segment.strip()
        for comma_segment in _COMMA_PATTERN.split(prefix)
        for segment in _COORDINATOR_PATTERN.split(comma_segment)
    )
    has_explicit_subject = any(
        _SUBJECT_PREDICATE_PATTERN.match(segment) for segment in prior_segments
    )
    imperative_predicate_count = sum(
        _IMPERATIVE_PREDICATE_PATTERN.match(segment) is not None for segment in prior_segments
    )
    return not (has_explicit_subject or imperative_predicate_count >= 2)


def _scope_boundaries(text: str) -> list[tuple[int, int]]:
    boundaries = [
        (match.start(), match.end())
        for pattern in (_HARD_SCOPE_BOUNDARY_PATTERN, _SUBORDINATE_BOUNDARY_PATTERN)
        for match in pattern.finditer(text)
    ]
    for pattern in (_COORDINATOR_PATTERN, _COMMA_PATTERN):
        for boundary in pattern.finditer(text):
            predicate = _SUBJECT_PREDICATE_PATTERN.match(text[boundary.end() :])
            if predicate is None:
                continue
            if _is_coordinated_negated_list(text, boundary, predicate):
                continue
            boundaries.append((boundary.start(), boundary.end()))
    return sorted(set(boundaries))


def _positive_occurrences(text: str, phrase: str) -> list[re.Match[str]]:
    normalized = text.casefold().replace("→", " to ").replace("’", "'")
    candidate = phrase.casefold().replace("→", " to ")
    matches = list(re.finditer(rf"(?<!\w){re.escape(candidate)}(?!\w)", normalized))
    boundaries = _scope_boundaries(normalized)
    positive: list[re.Match[str]] = []
    for match in matches:
        prior_boundaries = [boundary for boundary in boundaries if boundary[1] <= match.start()]
        scope_start = prior_boundaries[-1][1] if prior_boundaries else 0
        scope_prefix = normalized[scope_start : match.start()]
        scope_prefix = _NON_NEGATING_PATTERN.sub("", scope_prefix)
        next_boundaries = [boundary for boundary in boundaries if boundary[0] >= match.end()]
        scope_end = next_boundaries[0][0] if next_boundaries else len(normalized)
        scope_suffix = normalized[match.end() : scope_end]
        if _NEGATION_PATTERN.search(scope_prefix) or _SHARED_POST_NEGATION_PATTERN.search(
            scope_suffix
        ):
            continue
        positive.append(match)
    return positive


def positive_evidence_phrases(text: str, phrases: Iterable[str]) -> list[str]:
    """Return phrases supported by affirmative evidence under V2 negation scope rules."""

    return [phrase for phrase in phrases if _positive_occurrences(text, phrase)]


def _matching_ids(evidence: Iterable[EvidenceItem], phrases: Iterable[str]) -> list[str]:
    phrase_list = tuple(phrases)
    return list(
        dict.fromkeys(
            item.id
            for item in evidence
            if any(_positive_occurrences(item.text, phrase) for phrase in phrase_list)
        )
    )


def _match_count(evidence: Iterable[EvidenceItem], phrases: Iterable[str]) -> int:
    phrase_list = tuple(phrases)
    return sum(
        len(_positive_occurrences(item.text, phrase)) for item in evidence for phrase in phrase_list
    )


def _flags(
    evidence: list[EvidenceItem], phrase_groups: dict[str, tuple[str, ...]]
) -> list[EvidenceFlag]:
    return [
        EvidenceFlag(code=code, evidence_ids=ids)
        for code, phrases in phrase_groups.items()
        if (ids := _matching_ids(evidence, phrases))
    ]


def score_job_v2(job: JobEvidence, profile: ProfileEvidence) -> CareerFitV2:
    """Score JD evidence with bounded V2 rules; no model output enters this calculation."""
    del profile  # Profile provenance is linked at persistence; V2 scores the role's career value.
    evidence = job.evidence
    red_flags = _flags(evidence, RED_FLAG_PHRASES)
    green_flags = _flags(evidence, GREEN_FLAG_PHRASES)
    red_count = _match_count(
        evidence, (phrase for phrases in RED_FLAG_PHRASES.values() for phrase in phrases)
    )
    counter_count = _match_count(evidence, COUNTER_EVIDENCE_PHRASES)
    red_dominant = red_count >= 2 and red_count > counter_count
    ai_title = any(_contains(job.title, phrase) for phrase in AI_TITLE_PHRASES)
    pmo_warning = ai_title and red_dominant

    dimensions: dict[str, DimensionScore] = {}
    for name, rules in DIMENSION_RULES.items():
        score = 0
        support: list[str] = []
        for rule in rules:
            ids = _matching_ids(evidence, rule.phrases)
            if ids:
                score += rule.points
                support.extend(ids)
        score = min(score, DIMENSION_MAXIMA[name])
        deductions: list[Deduction] = []
        if red_dominant and name in {
            "ownership",
            "build_and_ship",
            "product_exposure",
            "technical_exposure",
        }:
            red_ids = list(
                dict.fromkeys(item_id for flag in red_flags for item_id in flag.evidence_ids)
            )
            requested = 4 if pmo_warning and name in {"ownership", "build_and_ship"} else 2
            applied = min(score, requested)
            if applied:
                deductions.append(
                    Deduction(
                        code="PMO_DOMINANCE" if pmo_warning else "RED_FLAG_DOMINANCE",
                        points=applied,
                        evidence_ids=red_ids,
                    )
                )
                score -= applied
        dimensions[name] = DimensionScore(
            score=score,
            max_score=DIMENSION_MAXIMA[name],
            evidence_ids=list(dict.fromkeys(support)) if score else [],
            missing_or_weak_evidence=[]
            if score == DIMENSION_MAXIMA[name]
            else [f"{name.upper()}_EVIDENCE_WEAK"],
            deductions=deductions,
        )

    warnings = (
        [
            CriticalWarning(
                code="AI_TITLE_PMO_SUBSTANCE",
                evidence_ids=list(
                    dict.fromkeys(
                        [
                            "jd-title",
                            *(item_id for flag in red_flags for item_id in flag.evidence_ids),
                        ]
                    )
                ),
                message=(
                    "The AI title is not supported by build-heavy responsibilities; "
                    "PMO work dominates the JD."
                ),
            )
        ]
        if pmo_warning
        else []
    )
    total = sum(dimension.score for dimension in dimensions.values())
    band = recommendation_band(total)
    strongest = max(dimensions, key=lambda dimension: dimensions[dimension].score)
    next_action = (
        "Apply and validate scope with the hiring manager."
        if total >= 70
        else "Clarify hands-on ownership and production-building scope before applying."
        if total >= 55
        else "Prioritize roles with stronger hands-on AI building and ownership evidence."
    )
    return CareerFitV2(
        dimensions=dimensions,
        evidence=evidence,
        matched_green_flags=green_flags,
        matched_red_flags=red_flags,
        critical_warnings=warnings,
        total_score=total,
        recommendation_band=band,
        concise_explanation=(
            f"Deterministic {SCORING_VERSION} score; strongest dimension: {strongest}."
        ),
        recommended_next_action=next_action,
    )
