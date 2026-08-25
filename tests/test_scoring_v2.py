import pytest


def _scoring_types():
    from app.scoring.v2 import JobEvidence, ProfileEvidence

    return JobEvidence, ProfileEvidence


@pytest.mark.parametrize(
    ("score", "band"),
    [(85, "Must Apply"), (70, "Strong Apply"), (55, "Selective"), (54, "Skip")],
)
def test_recommendation_band_uses_v2_boundaries(score: int, band: str) -> None:
    from app.scoring.v2 import recommendation_band

    assert recommendation_band(score) == band


def test_same_evidence_produces_same_score() -> None:
    from app.scoring.v2 import score_job_v2

    JobEvidence, ProfileEvidence = _scoring_types()
    job = JobEvidence(
        title="Forward Deployed AI Engineer",
        description=(
            "Own end-to-end delivery of agentic RAG products. "
            "Build rapid prototypes, design APIs, and deploy them to production with customers. "
            "Lead user discovery, prioritize the roadmap, measure outcomes, and iterate."
        ),
    )
    profile = ProfileEvidence(
        target_roles=["Forward Deployed Engineer", "Applied AI Engineer"],
        technical_strengths=["Python", "APIs", "RAG"],
    )

    assert score_job_v2(job, profile) == score_job_v2(job, profile)


def test_six_dimensions_are_bounded_and_total_is_derived_from_them() -> None:
    from app.scoring.v2 import score_job_v2

    JobEvidence, ProfileEvidence = _scoring_types()
    result = score_job_v2(
        JobEvidence(
            title="AI Product Engineer",
            description=(
                "Own 0-to-1 agentic RAG and LLM products end to end. Build and ship rapid "
                "prototypes through production deployment. Design APIs, data integrations, "
                "technical architecture, and evaluation systems. Lead user discovery, roadmap "
                "prioritization, product metrics, experimentation, and iteration with customers."
            ),
        ),
        ProfileEvidence(target_roles=["Applied AI Engineer", "AI Product Manager"]),
    )

    expected_maxima = {
        "ai_depth": 20,
        "ownership": 20,
        "build_and_ship": 20,
        "product_exposure": 15,
        "technical_exposure": 15,
        "career_option_value": 10,
    }
    assert set(result.dimensions) == set(expected_maxima)
    assert {
        name: dimension.max_score for name, dimension in result.dimensions.items()
    } == expected_maxima
    assert all(
        0 <= dimension.score <= dimension.max_score for dimension in result.dimensions.values()
    )
    assert result.total_score == sum(dimension.score for dimension in result.dimensions.values())
    assert result.total_score <= 100


def test_every_scored_dimension_deduction_and_flag_references_jd_evidence() -> None:
    from app.scoring.v2 import score_job_v2

    JobEvidence, ProfileEvidence = _scoring_types()
    result = score_job_v2(
        JobEvidence(
            title="AI Delivery Lead",
            description=(
                "Own an LLM workflow orchestration platform and design API integrations. "
                "Build prototypes and deploy customer solutions to production. "
                "Coordinate vendor reporting and governance."
            ),
        ),
        ProfileEvidence(target_roles=["Forward Deployed Engineer"]),
    )

    evidence_ids = {item.id for item in result.evidence}
    for dimension in result.dimensions.values():
        if dimension.score:
            assert dimension.evidence_ids
        assert set(dimension.evidence_ids) <= evidence_ids
        for deduction in dimension.deductions:
            assert deduction.points > 0
            assert deduction.evidence_ids
            assert set(deduction.evidence_ids) <= evidence_ids
    for flag in [*result.matched_green_flags, *result.matched_red_flags]:
        assert flag.evidence_ids
        assert set(flag.evidence_ids) <= evidence_ids


def test_ai_title_with_pmo_dominant_substance_emits_critical_warning_and_deduction() -> None:
    from app.scoring.v2 import score_job_v2

    JobEvidence, ProfileEvidence = _scoring_types()
    result = score_job_v2(
        JobEvidence(
            title="AI Transformation Lead",
            description=(
                "Coordinate programme status tracking and executive reporting. "
                "Run steering committee governance, vendor management, documentation, "
                "and requirement gathering for AI initiatives."
            ),
        ),
        ProfileEvidence(target_roles=["AI Product Manager"]),
    )

    warning = next(
        item for item in result.critical_warnings if item.code == "AI_TITLE_PMO_SUBSTANCE"
    )
    assert warning.evidence_ids
    assert any(dimension.deductions for dimension in result.dimensions.values())


def test_build_heavy_ai_role_with_incidental_coordination_has_no_pmo_warning() -> None:
    from app.scoring.v2 import score_job_v2

    JobEvidence, ProfileEvidence = _scoring_types()
    result = score_job_v2(
        JobEvidence(
            title="AI Solutions Engineer",
            description=(
                "Build agentic prototypes, evaluate LLM quality, design technical architecture, "
                "and deploy API integrations to production with customers. Own experiments and "
                "iterate end to end; coordinate launch status with one partner team."
            ),
        ),
        ProfileEvidence(target_roles=["Applied AI Engineer"]),
    )

    assert "AI_TITLE_PMO_SUBSTANCE" not in {warning.code for warning in result.critical_warnings}
