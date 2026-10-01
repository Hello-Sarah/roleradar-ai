"""Public, persistence-free contracts for the stateless demo."""

from pydantic import BaseModel, ConfigDict, Field

from app.analysis.explainer import EvidenceGroundedClaim, LLMExplanation
from app.schemas import ClassificationRead, JobCreate, Locale
from app.scoring.v2 import DimensionScore, EvidenceFlag, EvidenceItem

ABSOLUTE_DEMO_MAX_CHARACTERS = 100_000


class DemoInputLimitError(ValueError):
    """Raised when a valid payload exceeds the deployment's public-demo limit."""


class DemoAnalyzeRequest(BaseModel):
    """A bounded, untrusted job-description payload for one demo request."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=40, max_length=ABSOLUTE_DEMO_MAX_CHARACTERS)
    locale: Locale


class DemoAnalysisResponse(BaseModel):
    """Stable explainable output; all score-bearing values are deterministic."""

    model_config = ConfigDict(extra="forbid")

    job: JobCreate
    classification: ClassificationRead
    scoring_version: str
    score: int = Field(ge=0, le=100)
    dimensions: dict[str, DimensionScore]
    evidence: list[EvidenceItem]
    strengths: list[EvidenceGroundedClaim]
    gaps: list[EvidenceGroundedClaim]
    red_flags: list[EvidenceFlag]
    green_flags: list[EvidenceFlag]
    recommendation: str
    recommendation_label: str
    next_action: str
    next_action_label: str
    explanation: EvidenceGroundedClaim
    explanation_source: str
    profile_version: str
    locale: Locale

    @classmethod
    def from_explanation(
        cls,
        *,
        job: JobCreate,
        classification: ClassificationRead,
        scoring_version: str,
        score: int,
        dimensions: dict[str, DimensionScore],
        evidence: list[EvidenceItem],
        red_flags: list[EvidenceFlag],
        green_flags: list[EvidenceFlag],
        recommendation: str,
        recommendation_label: str,
        next_action: str,
        next_action_label: str,
        explanation: LLMExplanation,
        explanation_source: str,
        profile_version: str,
        locale: Locale,
    ) -> "DemoAnalysisResponse":
        return cls(
            job=job,
            classification=classification,
            scoring_version=scoring_version,
            score=score,
            dimensions=dimensions,
            evidence=evidence,
            strengths=explanation.strength_claims,
            gaps=explanation.gap_claims,
            red_flags=red_flags,
            green_flags=green_flags,
            recommendation=recommendation,
            recommendation_label=recommendation_label,
            next_action=next_action,
            next_action_label=next_action_label,
            explanation=explanation.summary_claim,
            explanation_source=explanation_source,
            profile_version=profile_version,
            locale=locale,
        )
