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
