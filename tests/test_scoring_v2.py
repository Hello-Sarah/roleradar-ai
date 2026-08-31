import pytest
from pydantic import ValidationError


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


def test_negated_responsibilities_do_not_award_points_or_green_flags() -> None:
    from app.scoring.v2 import score_job_v2

    JobEvidence, ProfileEvidence = _scoring_types()
    result = score_job_v2(
        JobEvidence(
            title="AI Strategy Manager",
            description=(
                "This role does not involve AI agents, RAG, or LLM evaluation. "
                "You will not build prototypes, deploy systems, write code, or design APIs."
            ),
        ),
        ProfileEvidence(),
    )

    assert result.dimensions["ai_depth"].score == 0
    assert result.dimensions["build_and_ship"].score == 0
    assert result.dimensions["technical_exposure"].score == 0
    assert not result.matched_green_flags


def test_affirmative_responsibilities_after_contrast_are_scored() -> None:
    from app.scoring.v2 import score_job_v2

    JobEvidence, ProfileEvidence = _scoring_types()
    result = score_job_v2(
        JobEvidence(
            title="AI Solutions Engineer",
            description=(
                "This is not only coordination; instead, build agentic RAG prototypes, "
                "write code, and deploy API integrations to production."
            ),
        ),
        ProfileEvidence(),
    )

    assert result.dimensions["ai_depth"].score > 0
    assert result.dimensions["build_and_ship"].score > 0
    assert result.dimensions["technical_exposure"].score > 0


def test_negated_build_language_cannot_suppress_ai_title_pmo_warning() -> None:
    from app.scoring.v2 import score_job_v2

    JobEvidence, ProfileEvidence = _scoring_types()
    result = score_job_v2(
        JobEvidence(
            title="AI Transformation Manager",
            description=(
                "You will not build prototypes, deploy to production, write code, design "
                "architecture, experiment, evaluate, or work hands-on with AI agents, RAG, "
                "or LLMs. Responsibilities are coordination, status tracking, reporting, "
                "steering committee governance, vendor management, documentation, requirement "
                "gathering, and PMO."
            ),
        ),
        ProfileEvidence(),
    )

    warning = next(
        item for item in result.critical_warnings if item.code == "AI_TITLE_PMO_SUBSTANCE"
    )
    assert warning.evidence_ids[0] == "jd-title"
    assert set(warning.evidence_ids[1:]) == {
        item_id for flag in result.matched_red_flags for item_id in flag.evidence_ids
    }
    assert result.dimensions["ai_depth"].score == 0
    assert result.dimensions["build_and_ship"].score == 0


def test_postposed_negation_applies_to_every_item_in_responsibility_list() -> None:
    from app.scoring.v2 import score_job_v2

    JobEvidence, ProfileEvidence = _scoring_types()
    result = score_job_v2(
        JobEvidence(
            title="AI Transformation Lead",
            description=(
                "AI agent, prototype, deploy, design, experiment, and architecture are not "
                "involved. PMO coordination, status tracking, reporting, governance, vendor "
                "management, and documentation dominate the responsibilities."
            ),
        ),
        ProfileEvidence(),
    )

    for dimension in ("ai_depth", "build_and_ship", "product_exposure", "technical_exposure"):
        assert result.dimensions[dimension].score == 0
    assert not {
        "AGENTIC",
        "RAPID_PROTOTYPING",
        "CUSTOMER_DEPLOYMENT",
        "TECHNICAL_ARCHITECTURE",
    } & {flag.code for flag in result.matched_green_flags}
    assert "AI_TITLE_PMO_SUBSTANCE" in {warning.code for warning in result.critical_warnings}


def test_independent_trailing_negated_clause_preserves_exact_affirmative_ai_depth() -> None:
    from app.scoring.v2 import score_job_v2

    JobEvidence, ProfileEvidence = _scoring_types()
    result = score_job_v2(
        JobEvidence(
            title="AI Engineer",
            description=(
                "We build AI agents, deploy RAG, evaluate LLMs, and you are not involved."
            ),
        ),
        ProfileEvidence(),
    )

    assert result.dimensions["ai_depth"].score == 16
    assert result.dimensions["build_and_ship"].score == 8
    assert {"AGENTIC", "RAG", "LLM", "EVALUATION", "CUSTOMER_DEPLOYMENT"} <= {
        flag.code for flag in result.matched_green_flags
    }


@pytest.mark.parametrize(
    "description",
    [
        "Build AI agents, deploy RAG, evaluate LLMs, and you are not involved.",
        ("Build AI agents, deploy RAG, evaluate LLMs, and external advisors are not included."),
    ],
)
def test_imperative_responsibilities_are_independent_from_negated_tail_clause(
    description: str,
) -> None:
    from app.scoring.v2 import score_job_v2

    JobEvidence, ProfileEvidence = _scoring_types()
    result = score_job_v2(
        JobEvidence(title="AI Engineer", description=description),
        ProfileEvidence(),
    )

    assert result.dimensions["ai_depth"].score == 16
    assert result.dimensions["build_and_ship"].score == 8
    assert {"AGENTIC", "RAG", "LLM", "EVALUATION", "CUSTOMER_DEPLOYMENT"} <= {
        flag.code for flag in result.matched_green_flags
    }


@pytest.mark.parametrize(
    ("description", "dimension", "expected_score"),
    [
        (
            "For each launch, build AI agents, deploy RAG, evaluate LLMs, and external "
            "advisors are not included.",
            "ai_depth",
            16,
        ),
        (
            "Design API integration, build a prototype, deploy systems, and review "
            "participants are not involved.",
            "build_and_ship",
            12,
        ),
    ],
)
def test_coordinated_imperative_predicates_with_complements_remain_affirmative(
    description: str,
    dimension: str,
    expected_score: int,
) -> None:
    from app.scoring.v2 import score_job_v2

    JobEvidence, ProfileEvidence = _scoring_types()
    result = score_job_v2(
        JobEvidence(title="AI Engineer", description=description),
        ProfileEvidence(),
    )

    assert result.dimensions[dimension].score == expected_score


def test_conjunction_coordinated_imperative_predicates_remain_affirmative() -> None:
    from app.scoring.v2 import score_job_v2

    JobEvidence, ProfileEvidence = _scoring_types()
    result = score_job_v2(
        JobEvidence(
            title="AI Engineer",
            description=(
                "Build AI agents and deploy RAG and evaluate LLMs, and external advisors "
                "are not included."
            ),
        ),
        ProfileEvidence(),
    )

    assert result.dimensions["ai_depth"].score == 16
    assert result.dimensions["build_and_ship"].score == 8


@pytest.mark.parametrize(
    "description",
    [
        "AI agents, RAG systems, LLM evaluation, and external advisors are not included.",
        "AI agent, build, deploy, evaluate, and architecture are not involved.",
        ("AI agents and RAG systems and LLM evaluation, and external advisors are not included."),
    ],
)
def test_nominal_and_bare_item_lists_keep_shared_postposed_negation(
    description: str,
) -> None:
    from app.scoring.v2 import score_job_v2

    JobEvidence, ProfileEvidence = _scoring_types()
    result = score_job_v2(
        JobEvidence(title="AI Transformation Lead", description=description),
        ProfileEvidence(),
    )

    assert result.dimensions["ai_depth"].score == 0
    assert result.dimensions["build_and_ship"].score == 0
    assert result.dimensions["technical_exposure"].score == 0
    assert not {"AGENTIC", "RAG", "LLM", "EVALUATION", "CUSTOMER_DEPLOYMENT"} & {
        flag.code for flag in result.matched_green_flags
    }


@pytest.mark.parametrize(
    "description",
    [
        (
            "Platform engineers build AI agents, deploy RAG, evaluate LLMs, and delivery "
            "partners are not involved."
        ),
        (
            "In practice, platform specialists build AI agents, deploy RAG, evaluate LLMs, "
            "and external advisors are not included."
        ),
    ],
)
def test_generic_independent_trailing_subject_does_not_negate_prior_clause(
    description: str,
) -> None:
    from app.scoring.v2 import score_job_v2

    JobEvidence, ProfileEvidence = _scoring_types()
    result = score_job_v2(
        JobEvidence(title="AI Engineer", description=description),
        ProfileEvidence(),
    )

    assert result.dimensions["ai_depth"].score == 16
    assert result.dimensions["build_and_ship"].score == 8


@pytest.mark.parametrize(
    "description",
    [
        "AI agents, RAG systems, LLM evaluation, and technical architecture are not involved.",
        (
            "For this role, AI agents, RAG systems, LLM evaluation, and technical architecture "
            "are not included."
        ),
    ],
)
def test_shared_postposed_predicate_variants_negate_the_entire_list(description: str) -> None:
    from app.scoring.v2 import score_job_v2

    JobEvidence, ProfileEvidence = _scoring_types()
    result = score_job_v2(
        JobEvidence(title="AI Transformation Lead", description=description),
        ProfileEvidence(),
    )

    assert result.dimensions["ai_depth"].score == 0
    assert not {"AGENTIC", "RAG", "LLM", "EVALUATION", "TECHNICAL_ARCHITECTURE"} & {
        flag.code for flag in result.matched_green_flags
    }


def test_unrelated_prior_clause_negation_does_not_leak_into_responsibilities() -> None:
    from app.scoring.v2 import score_job_v2

    JobEvidence, ProfileEvidence = _scoring_types()
    result = score_job_v2(
        JobEvidence(
            title="AI Engineer",
            description="There is little bureaucracy, and you will build and deploy AI agents.",
        ),
        ProfileEvidence(),
    )

    assert result.dimensions["ai_depth"].score > 0
    assert result.dimensions["build_and_ship"].score > 0
    assert {"AGENTIC", "CUSTOMER_DEPLOYMENT"} <= {flag.code for flag in result.matched_green_flags}


def test_generic_engineer_subject_resets_prior_clause_negation() -> None:
    from app.scoring.v2 import score_job_v2

    JobEvidence, ProfileEvidence = _scoring_types()
    result = score_job_v2(
        JobEvidence(
            title="AI Engineer",
            description=(
                "There is little bureaucracy, and engineers will build and deploy AI agents."
            ),
        ),
        ProfileEvidence(),
    )

    assert result.dimensions["ai_depth"].score > 0
    assert result.dimensions["build_and_ship"].score > 0
    assert {"AGENTIC", "CUSTOMER_DEPLOYMENT"} <= {flag.code for flag in result.matched_green_flags}


def test_independent_conjunction_resets_negation_without_comma() -> None:
    from app.scoring.v2 import score_job_v2

    JobEvidence, ProfileEvidence = _scoring_types()
    result = score_job_v2(
        JobEvidence(
            title="AI Engineer",
            description=(
                "There is little bureaucracy and the team will build and deploy AI agents."
            ),
        ),
        ProfileEvidence(),
    )

    assert result.dimensions["ai_depth"].score > 0
    assert result.dimensions["build_and_ship"].score > 0


def test_generic_multiword_noun_subject_resets_prior_negation() -> None:
    from app.scoring.v2 import score_job_v2

    JobEvidence, ProfileEvidence = _scoring_types()
    result = score_job_v2(
        JobEvidence(
            title="AI Engineer",
            description=(
                "There is little reporting, and platform specialists will design and deploy "
                "RAG systems."
            ),
        ),
        ProfileEvidence(),
    )

    assert result.dimensions["ai_depth"].score > 0
    assert result.dimensions["build_and_ship"].score > 0


def test_relative_clause_predicate_does_not_negate_prior_responsibility() -> None:
    from app.scoring.v2 import score_job_v2

    JobEvidence, ProfileEvidence = _scoring_types()
    result = score_job_v2(
        JobEvidence(
            title="AI Engineer",
            description="You will build AI agents for clients who are not involved.",
        ),
        ProfileEvidence(),
    )

    assert result.dimensions["ai_depth"].score > 0
    assert result.dimensions["build_and_ship"].score > 0
    assert "AGENTIC" in {flag.code for flag in result.matched_green_flags}


def test_relative_clause_after_customer_does_not_negate_deployment_list() -> None:
    from app.scoring.v2 import score_job_v2

    JobEvidence, ProfileEvidence = _scoring_types()
    result = score_job_v2(
        JobEvidence(
            title="AI Engineer",
            description=(
                "You will build and deploy AI agents for customers that are not included in "
                "governance meetings."
            ),
        ),
        ProfileEvidence(),
    )

    assert result.dimensions["ai_depth"].score > 0
    assert result.dimensions["build_and_ship"].score > 0


def test_postposed_negated_list_before_contrast_does_not_negate_affirmative_clause() -> None:
    from app.scoring.v2 import score_job_v2

    JobEvidence, ProfileEvidence = _scoring_types()
    result = score_job_v2(
        JobEvidence(
            title="AI Engineer",
            description=(
                "AI agents and RAG are not involved, but you will build prototypes and deploy "
                "API integrations to production."
            ),
        ),
        ProfileEvidence(),
    )

    assert result.dimensions["ai_depth"].score == 0
    assert result.dimensions["build_and_ship"].score > 0
    assert result.dimensions["technical_exposure"].score > 0
    assert "AGENTIC" not in {flag.code for flag in result.matched_green_flags}


def test_negated_independent_clause_before_conjunction_does_not_leak() -> None:
    from app.scoring.v2 import score_job_v2

    JobEvidence, ProfileEvidence = _scoring_types()
    result = score_job_v2(
        JobEvidence(
            title="AI Engineer",
            description=(
                "We do not coordinate reporting, and we build agentic prototypes and deploy "
                "them to production."
            ),
        ),
        ProfileEvidence(),
    )

    assert not result.matched_red_flags
    assert result.dimensions["ai_depth"].score > 0
    assert result.dimensions["build_and_ship"].score > 0


def test_workflow_orchestration_green_flag_contributes_to_ai_depth() -> None:
    from app.scoring.v2 import score_job_v2

    JobEvidence, ProfileEvidence = _scoring_types()
    result = score_job_v2(
        JobEvidence(
            title="Platform Engineer",
            description="Own workflow orchestration for production customer automation systems.",
        ),
        ProfileEvidence(),
    )

    flag = next(
        flag for flag in result.matched_green_flags if flag.code == "WORKFLOW_ORCHESTRATION"
    )
    assert result.dimensions["ai_depth"].score > 0
    assert set(flag.evidence_ids) <= set(result.dimensions["ai_depth"].evidence_ids)


def test_explicit_evidence_catalog_still_materializes_title_warning_evidence() -> None:
    from app.scoring.v2 import EvidenceItem, JobEvidence, ProfileEvidence, score_job_v2

    result = score_job_v2(
        JobEvidence(
            title="AI Programme Lead",
            evidence=[
                EvidenceItem(
                    id="jd-responsibilities",
                    text="PMO coordination, reporting, governance, and vendor management.",
                )
            ],
        ),
        ProfileEvidence(),
    )

    assert result.evidence[0].id == "jd-title"
    assert result.critical_warnings[0].evidence_ids == ["jd-title", "jd-responsibilities"]


def _valid_result_payload() -> dict:
    from app.scoring.v2 import JobEvidence, ProfileEvidence, score_job_v2

    return score_job_v2(
        JobEvidence(
            title="Applied AI Engineer",
            description="Build agentic RAG prototypes and deploy API integrations to production.",
        ),
        ProfileEvidence(),
    ).model_dump(mode="json")


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload["dimensions"].pop("ownership"),
        lambda payload: payload.update(scoring_version="career-fit-v999"),
        lambda payload: payload["dimensions"]["ai_depth"].update(max_score=999),
        lambda payload: payload.update(total_score=payload["total_score"] + 1),
        lambda payload: payload.update(recommendation_band="Must Apply"),
        lambda payload: payload["evidence"].append(payload["evidence"][0].copy()),
        lambda payload: payload["matched_green_flags"][0].update(
            evidence_ids=["jd-not-in-catalog"]
        ),
        lambda payload: payload["dimensions"]["ai_depth"].update(
            evidence_ids=["jd-not-in-catalog"]
        ),
    ],
    ids=[
        "missing-dimension",
        "wrong-version",
        "wrong-maximum",
        "wrong-total",
        "wrong-band",
        "duplicate-catalog-id",
        "flag-non-catalog-id",
        "dimension-non-catalog-id",
    ],
)
def test_career_fit_contract_rejects_invalid_public_results(mutate) -> None:
    from app.scoring.v2 import CareerFitV2

    payload = _valid_result_payload()
    mutate(payload)

    with pytest.raises(ValidationError):
        CareerFitV2.model_validate(payload)


def test_career_fit_contract_rejects_duplicate_and_non_jd_reference_ids() -> None:
    from app.scoring.v2 import CareerFitV2

    duplicate = _valid_result_payload()
    duplicate["dimensions"]["ai_depth"]["evidence_ids"] = ["jd-001", "jd-001"]
    with pytest.raises(ValidationError):
        CareerFitV2.model_validate(duplicate)

    non_jd = _valid_result_payload()
    non_jd["evidence"][0]["id"] = "external-001"
    with pytest.raises(ValidationError):
        CareerFitV2.model_validate(non_jd)
