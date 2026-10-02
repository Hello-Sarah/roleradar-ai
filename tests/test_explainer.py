def test_fallback_explanation_bounds_all_contract_lists() -> None:
    from app.analysis.explainer import _fallback_summary
    from app.schemas import JobCreate
    from app.scoring.v2 import JobEvidence, ProfileEvidence, score_job_v2

    description = (
        "Build AI agents. Deploy RAG prototypes. Evaluate LLM quality. "
        "Design technical architecture. Own end-to-end delivery. "
        "Lead user discovery and product roadmap. Ship API integrations to production."
    )
    job = JobCreate(
        company="DemoAI",
        title="Applied AI Engineer",
        location="Hong Kong",
        description=description,
    )
    result = score_job_v2(
        JobEvidence(title=job.title, description=description),
        ProfileEvidence(),
    )

    explanation = _fallback_summary(job, result)

    assert 1 <= len(explanation.strengths) <= 6
    assert 1 <= len(explanation.gaps) <= 6
    assert 1 <= len(explanation.evidence) <= 6


def test_rr_f03_private_analysis_rejects_schema_valid_fabricated_summary(db, monkeypatch):
    from types import SimpleNamespace

    from app.analysis.explainer import LLMExplanation
    from app.config import Settings
    from app.schemas import JobCreate
    from app.services.job_service import create_and_analyze_job

    fabricated = "The candidate holds a Stanford PhD and this employer guarantees visa sponsorship."
    result = LLMExplanation(
        strengths=["Stanford PhD"], gaps=["None"], evidence=["invented"], summary=fabricated
    )
    monkeypatch.setattr(
        "app.analysis.explainer.OpenAI",
        lambda **_: SimpleNamespace(
            responses=SimpleNamespace(parse=lambda **_: SimpleNamespace(output_parsed=result))
        ),
    )
    job = create_and_analyze_job(
        db,
        JobCreate(
            company="Synthetic",
            title="AI Engineer",
            location="Hong Kong",
            description="Build reliable Python AI systems for customers.",
        ),
        Settings(ai_explanations_enabled=True, openai_api_key="synthetic"),
    )
    assert "Stanford" not in job.analysis.summary
    assert "guarantees" not in job.analysis.summary
    assert job.analysis.model_version == "deterministic-fallback"
