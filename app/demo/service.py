"""Stateless orchestration for one public job-analysis request."""

from app.analysis.classifier import classify_job
from app.analysis.explainer import explain_fit
from app.config import Settings
from app.demo.contracts import DemoAnalysisResponse, DemoAnalyzeRequest
from app.demo.profile import PUBLIC_DEMO_PROFILE_VERSION, public_demo_profile
from app.ingestion.text_extractor import extract_job_from_text
from app.scoring.v2 import JobEvidence, ProfileEvidence, score_job_v2


def analyze_demo_job(payload: DemoAnalyzeRequest, settings: Settings) -> DemoAnalysisResponse:
    """Analyze an untrusted JD without persistence or access to private candidate data."""

    job = extract_job_from_text(payload.text)
    classification = classify_job(job.title, job.description)
    profile = public_demo_profile()
    score = score_job_v2(
        JobEvidence(title=job.title, description=job.description),
        ProfileEvidence(
            target_roles=profile.target_roles,
            domain_strengths=profile.domain_strengths,
            technical_strengths=profile.technical_strengths,
            development_gaps=profile.development_gaps,
        ),
    )
    explanation, explanation_source = explain_fit(
        job=job,
        profile=profile,
        classification=classification,
        result=score,
        settings=settings,
    )
    return DemoAnalysisResponse.from_explanation(
        job=job,
        classification=classification,
        scoring_version=score.scoring_version,
        score=score.total_score,
        dimensions=score.dimensions,
        evidence=score.evidence,
        red_flags=score.matched_red_flags,
        green_flags=score.matched_green_flags,
        recommendation=score.recommendation_band,
        next_action=score.recommended_next_action,
        explanation=explanation,
        explanation_source=explanation_source,
        profile_version=PUBLIC_DEMO_PROFILE_VERSION,
        locale=payload.locale,
    )
