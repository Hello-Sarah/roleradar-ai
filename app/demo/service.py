"""Stateless orchestration for one public job-analysis request."""

from app.analysis.classifier import classify_job
from app.analysis.explainer import EvidenceGroundedClaim, ExplanationProvider, explain_fit
from app.config import Settings
from app.demo.contracts import DemoAnalysisResponse, DemoAnalyzeRequest, DemoInputLimitError
from app.demo.profile import PUBLIC_DEMO_PROFILE_VERSION, public_demo_profile
from app.ingestion.text_extractor import extract_job_from_text
from app.scoring.v2 import JobEvidence, ProfileEvidence, score_job_v2

_RECOMMENDATION_LABELS = {
    "en": {
        "Must Apply": "Must Apply",
        "Strong Apply": "Strong Apply",
        "Selective": "Selective",
        "Skip": "Skip",
    },
    "zh-Hans": {
        "Must Apply": "必须申请",
        "Strong Apply": "强烈建议申请",
        "Selective": "选择性申请",
        "Skip": "跳过",
    },
}

_NEXT_ACTION_LABELS = {
    "en": {
        "Apply and validate scope with the hiring manager.": (
            "Apply and validate scope with the hiring manager."
        ),
        "Clarify hands-on ownership and production-building scope before applying.": (
            "Clarify hands-on ownership and production-building scope before applying."
        ),
        "Prioritize roles with stronger hands-on AI building and ownership evidence.": (
            "Prioritize roles with stronger hands-on AI building and ownership evidence."
        ),
    },
    "zh-Hans": {
        "Apply and validate scope with the hiring manager.": "申请，并与招聘经理确认职责范围。",
        "Clarify hands-on ownership and production-building scope before applying.": (
            "申请前先确认实际主导权和生产落地范围。"
        ),
        "Prioritize roles with stronger hands-on AI building and ownership evidence.": (
            "优先考虑有更强 AI 实操建设和主导权证据的岗位。"
        ),
    },
}


def _localized_explanation(*, locale: str, score: int, recommendation_label: str) -> str:
    if locale == "zh-Hans":
        return (
            f"确定性 Career Fit V2 得分：{score}/100。建议：{recommendation_label}。"
            "该结果仅依据六个评分维度和已引用的职位描述证据计算。"
        )
    return (
        f"Deterministic Career Fit V2 score: {score}/100. Recommendation: {recommendation_label}. "
        "This result is calculated only from the six scoring dimensions and cited JD evidence."
    )


def analyze_demo_job(
    payload: DemoAnalyzeRequest,
    settings: Settings,
    provider_call: ExplanationProvider | None = None,
) -> DemoAnalysisResponse:
    """Analyze an untrusted JD without persistence or access to private candidate data."""

    if len(payload.text) > settings.demo_max_characters:
        raise DemoInputLimitError("Input exceeds the configured demo limit")
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
        provider_call=provider_call,
        timeout_seconds=settings.demo_provider_timeout_seconds,
        allowed_evidence=score.evidence,
        locale=payload.locale,
    )
    recommendation_label = _RECOMMENDATION_LABELS[payload.locale][score.recommendation_band]
    next_action_label = _NEXT_ACTION_LABELS[payload.locale][score.recommended_next_action]
    if explanation_source == "deterministic-fallback":
        summary_claim = explanation.summary_claim
        if summary_claim is None:
            raise ValueError("Deterministic explanation must include evidence-grounded summary")
        localized_summary = _localized_explanation(
            locale=payload.locale,
            score=score.total_score,
            recommendation_label=recommendation_label,
        )
        explanation = explanation.model_copy(
            update={
                "summary": localized_summary,
                "summary_claim": EvidenceGroundedClaim(
                    text=localized_summary,
                    evidence_ids=summary_claim.evidence_ids,
                ),
            }
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
        recommendation_label=recommendation_label,
        next_action_label=next_action_label,
    )
