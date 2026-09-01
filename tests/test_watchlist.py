from types import SimpleNamespace

import pytest


def test_watchlist_enums_use_stable_machine_values() -> None:
    from app.watchlist.models import ActionWindow, CompanyType, SourceState, StrategicPriority

    assert {item.value for item in CompanyType} == {
        "ai_native_forward_deployed",
        "fintech_product",
        "cloud_data_enterprise_ai",
        "financial_institution",
        "consulting_professional_services",
    }
    assert {item.value for item in StrategicPriority} == {
        "core_target",
        "monitor",
        "opportunistic",
        "strict_filter",
    }
    assert {item.value for item in ActionWindow} == {
        "apply_now",
        "stretch_apply",
        "apply_in_3_to_6_months",
        "apply_after_us_relocation",
        "relationship_only",
    }
    assert {item.value for item in SourceState} == {
        "unverified",
        "verified_manual",
        "structured_ready",
        "degraded",
        "disabled",
    }


def test_seed_matches_approved_company_classification_and_is_idempotent(db) -> None:
    from app.database.seed_watchlist import seed_watchlist

    first = seed_watchlist(db)
    second = seed_watchlist(db)
    seed_map = {company.name: company for company in first}

    expected_groups = {
        ("ai_native_forward_deployed", "core_target"): {
            "Palantir",
            "Sierra",
            "Cresta",
            "Manus",
            "Hebbia",
            "Decagon",
            "Glean",
            "Harvey",
            "Scale AI",
        },
        ("fintech_product", "core_target"): {"Ant International", "Airwallex"},
        ("financial_institution", "core_target"): {"Temasek"},
        ("ai_native_forward_deployed", "monitor"): {
            "Abridge",
            "Siena AI",
            "Gradial",
            "OpenAI",
            "Anthropic",
            "Perplexity",
        },
        ("fintech_product", "monitor"): {"Reap", "SleekFlow"},
        ("cloud_data_enterprise_ai", "monitor"): {"Databricks"},
        ("fintech_product", "opportunistic"): {"Grab", "Sea", "ByteDance", "Ramp", "Stripe"},
        ("cloud_data_enterprise_ai", "opportunistic"): {
            "Snowflake",
            "AWS",
            "Microsoft",
            "Google",
            "Salesforce",
        },
        ("financial_institution", "strict_filter"): {
            "HSBC",
            "Standard Chartered",
            "JPMorgan",
            "Goldman Sachs",
        },
        ("consulting_professional_services", "strict_filter"): {"Capgemini"},
    }
    actual_groups: dict[tuple[str, str], set[str]] = {}
    for company in first:
        actual_groups.setdefault((company.company_type, company.strategic_priority), set()).add(
            company.name
        )

    assert len(first) == 36
    assert len(second) == 36
    assert actual_groups == expected_groups
    assert seed_map["Palantir"].company_type == "ai_native_forward_deployed"
    assert seed_map["Palantir"].strategic_priority == "core_target"
    assert seed_map["HSBC"].company_type == "financial_institution"
    assert seed_map["Standard Chartered"].company_type == "financial_institution"
    assert seed_map["JPMorgan"].company_type == "financial_institution"
    assert seed_map["Goldman Sachs"].company_type == "financial_institution"
    assert seed_map["Capgemini"].company_type == "consulting_professional_services"
    assert seed_map["Capgemini"].strategic_priority == "strict_filter"


@pytest.mark.parametrize(
    ("location", "preferred", "future", "expected"),
    [
        ("Hong Kong", ["Hong Kong"], ["New York"], "eligible"),
        ("New York, NY", ["Hong Kong"], ["New York"], "future"),
        ("Location to be confirmed", ["Hong Kong"], ["New York"], "unclear"),
        ("Remote — USA only", ["Hong Kong"], [], "ineligible"),
        ("Remote — USA only", ["United States"], [], "eligible"),
    ],
)
def test_job_location_eligibility_uses_explicit_evidence(
    location: str, preferred: list[str], future: list[str], expected: str
) -> None:
    from app.watchlist.eligibility import evaluate_job_eligibility

    result = evaluate_job_eligibility(
        SimpleNamespace(
            title="Applied AI Engineer",
            location=location,
            description="Build AI agents and deploy prototypes to production.",
            analysis=SimpleNamespace(fit_score=78),
        ),
        SimpleNamespace(
            strategic_priority="core_target",
            action_window="apply_now",
            rationale="Important company, evaluated separately from the job.",
        ),
        SimpleNamespace(preferred_locations=preferred, future_locations=future),
    )

    assert result.location_eligibility == expected
    assert result.career_fit_score == 78
    assert result.location_evidence


def test_remote_usa_does_not_mean_global_remote() -> None:
    from app.watchlist.eligibility import evaluate_job_eligibility

    result = evaluate_job_eligibility(
        SimpleNamespace(
            title="AI Engineer",
            location="Remote — United States",
            description="This role is remote within the USA.",
            analysis=SimpleNamespace(fit_score=90),
        ),
        SimpleNamespace(
            strategic_priority="core_target",
            action_window="apply_now",
            rationale="Core target",
        ),
        SimpleNamespace(preferred_locations=["Hong Kong", "Remote"], future_locations=[]),
    )

    assert result.location_eligibility == "ineligible"
    assert result.expected_return == "skip"
    assert any(
        "United States" in evidence or "USA" in evidence for evidence in result.location_evidence
    )


def test_authorization_restriction_is_unclear_without_candidate_status() -> None:
    from app.watchlist.eligibility import evaluate_job_eligibility

    result = evaluate_job_eligibility(
        SimpleNamespace(
            title="AI Engineer",
            location="Hong Kong",
            description="Applicants must already be authorized to work in Hong Kong.",
            analysis=SimpleNamespace(fit_score=90),
        ),
        SimpleNamespace(
            strategic_priority="monitor",
            action_window="stretch_apply",
            rationale="Monitor company",
        ),
        SimpleNamespace(preferred_locations=["Hong Kong"], future_locations=[]),
    )

    assert result.location_eligibility == "eligible"
    assert result.work_authorization == "unclear"
    assert result.expected_return == "relationship_only"
    assert any("must already be authorized" in item for item in result.work_authorization_evidence)


def test_company_tier_does_not_set_job_score_or_force_apply_now() -> None:
    from app.watchlist.eligibility import evaluate_job_eligibility

    result = evaluate_job_eligibility(
        SimpleNamespace(
            title="Operations Coordinator",
            location="Hong Kong",
            description="Coordinate reporting, governance, and vendor status tracking.",
            analysis=SimpleNamespace(fit_score=32),
        ),
        SimpleNamespace(
            strategic_priority="core_target",
            action_window="apply_now",
            rationale="Core target company",
        ),
        SimpleNamespace(preferred_locations=["Hong Kong"], future_locations=[]),
    )

    assert result.career_fit_score == 32
    assert result.expected_return == "skip"


@pytest.mark.parametrize(
    ("description", "expected_pass", "expected_return"),
    [
        (
            "Own solution design, build AI agent prototypes, evaluate quality, and deploy "
            "to production.",
            True,
            "apply_now",
        ),
        (
            "Lead AI governance, PMO reporting, vendor coordination, and steering committee "
            "updates.",
            False,
            "skip",
        ),
        (
            "You will not own solution design, build prototypes, evaluate models, or deploy to "
            "production. PMO reporting and governance dominate.",
            False,
            "skip",
        ),
    ],
)
def test_strict_filter_depends_on_job_evidence(
    description: str, expected_pass: bool, expected_return: str
) -> None:
    from app.watchlist.eligibility import evaluate_job_eligibility

    result = evaluate_job_eligibility(
        SimpleNamespace(
            title="AI Transformation Lead",
            location="Hong Kong",
            description=description,
            analysis=SimpleNamespace(fit_score=88),
        ),
        SimpleNamespace(
            strategic_priority="strict_filter",
            action_window="relationship_only",
            rationale="Strict-filter company",
        ),
        SimpleNamespace(preferred_locations=["Hong Kong"], future_locations=[]),
    )

    assert result.strict_filter_passed is expected_pass
    assert result.expected_return == expected_return
    assert result.career_fit_score == 88
    assert result.job_evidence
