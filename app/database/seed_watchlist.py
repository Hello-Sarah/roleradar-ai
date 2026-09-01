"""Editable initial Watch List classification from the approved V1 specification."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import WatchListCompany
from app.watchlist.models import (
    ActionWindow,
    CompanyType,
    SourceKind,
    SourceState,
    StrategicPriority,
)

_DOMAINS = {
    "Palantir": "palantir.com",
    "Sierra": "sierra.ai",
    "Cresta": "cresta.com",
    "Manus": "manus.im",
    "Hebbia": "hebbia.ai",
    "Decagon": "decagon.ai",
    "Glean": "glean.com",
    "Harvey": "harvey.ai",
    "Scale AI": "scale.com",
    "Ant International": "ant-intl.com",
    "Airwallex": "airwallex.com",
    "Temasek": "temasek.com.sg",
    "Abridge": "abridge.com",
    "Siena AI": "siena.cx",
    "Gradial": "gradial.com",
    "OpenAI": "openai.com",
    "Anthropic": "anthropic.com",
    "Perplexity": "perplexity.ai",
    "Reap": "reap.global",
    "SleekFlow": "sleekflow.io",
    "Databricks": "databricks.com",
    "Grab": "grab.com",
    "Sea": "sea.com",
    "ByteDance": "bytedance.com",
    "Ramp": "ramp.com",
    "Stripe": "stripe.com",
    "Snowflake": "snowflake.com",
    "AWS": "aws.amazon.com",
    "Microsoft": "microsoft.com",
    "Google": "google.com",
    "Salesforce": "salesforce.com",
    "HSBC": "hsbc.com",
    "Standard Chartered": "sc.com",
    "JPMorgan": "jpmorganchase.com",
    "Goldman Sachs": "goldmansachs.com",
    "Capgemini": "capgemini.com",
}

_GROUPS = (
    (
        (
            "Palantir",
            "Sierra",
            "Cresta",
            "Manus",
            "Hebbia",
            "Decagon",
            "Glean",
            "Harvey",
            "Scale AI",
        ),
        CompanyType.AI_NATIVE_FORWARD_DEPLOYED,
        StrategicPriority.CORE_TARGET,
    ),
    (
        ("Ant International", "Airwallex"),
        CompanyType.FINTECH_PRODUCT,
        StrategicPriority.CORE_TARGET,
    ),
    (("Temasek",), CompanyType.FINANCIAL_INSTITUTION, StrategicPriority.CORE_TARGET),
    (
        ("Abridge", "Siena AI", "Gradial", "OpenAI", "Anthropic", "Perplexity"),
        CompanyType.AI_NATIVE_FORWARD_DEPLOYED,
        StrategicPriority.MONITOR,
    ),
    (("Reap", "SleekFlow"), CompanyType.FINTECH_PRODUCT, StrategicPriority.MONITOR),
    (("Databricks",), CompanyType.CLOUD_DATA_ENTERPRISE_AI, StrategicPriority.MONITOR),
    (
        ("Grab", "Sea", "ByteDance", "Ramp", "Stripe"),
        CompanyType.FINTECH_PRODUCT,
        StrategicPriority.OPPORTUNISTIC,
    ),
    (
        ("Snowflake", "AWS", "Microsoft", "Google", "Salesforce"),
        CompanyType.CLOUD_DATA_ENTERPRISE_AI,
        StrategicPriority.OPPORTUNISTIC,
    ),
    (
        ("HSBC", "Standard Chartered", "JPMorgan", "Goldman Sachs"),
        CompanyType.FINANCIAL_INSTITUTION,
        StrategicPriority.STRICT_FILTER,
    ),
    (
        ("Capgemini",),
        CompanyType.CONSULTING_PROFESSIONAL_SERVICES,
        StrategicPriority.STRICT_FILTER,
    ),
)

_ACTION_BY_PRIORITY = {
    StrategicPriority.CORE_TARGET: ActionWindow.APPLY_NOW,
    StrategicPriority.MONITOR: ActionWindow.APPLY_IN_3_TO_6_MONTHS,
    StrategicPriority.OPPORTUNISTIC: ActionWindow.STRETCH_APPLY,
    StrategicPriority.STRICT_FILTER: ActionWindow.RELATIONSHIP_ONLY,
}


def _seed_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for names, company_type, priority in _GROUPS:
        for name in names:
            domain = _DOMAINS[name]
            rows.append(
                {
                    "name": name,
                    "canonical_domain": domain,
                    "company_type": company_type.value,
                    "strategic_priority": priority.value,
                    "action_window": _ACTION_BY_PRIORITY[priority].value,
                    "target_role_patterns": [
                        "Forward Deployed",
                        "Applied AI",
                        "AI Product",
                        "AI Solutions",
                    ],
                    "target_locations": ["Hong Kong", "Singapore", "United States"],
                    "positive_keywords": [
                        "agent",
                        "prototype",
                        "deploy",
                        "evaluation",
                        "architecture",
                    ],
                    "exclusion_keywords": [
                        "PMO",
                        "governance",
                        "reporting",
                        "vendor management",
                    ],
                    "location_notes": "Verify location eligibility on each job.",
                    "work_authorization_notes": "Verify work authorization on each job.",
                    "official_source_url": f"https://{domain}/careers",
                    "source_kind": SourceKind.CAREER_PAGE.value,
                    "source_state": SourceState.UNVERIFIED.value,
                    "source_state_reason": (
                        "Initial official source awaiting manual verification."
                    ),
                    "enabled": True,
                    "rationale": "Editable initial classification from spec/watch-list.md.",
                }
            )
    return rows


WATCHLIST_SEEDS = tuple(_seed_rows())


def seed_watchlist(db: Session) -> list[WatchListCompany]:
    """Insert missing approved seeds without overwriting user edits."""

    seed_names = [str(row["name"]) for row in WATCHLIST_SEEDS]
    existing_names = set(
        db.scalars(select(WatchListCompany.name).where(WatchListCompany.name.in_(seed_names)))
    )
    db.add_all(
        WatchListCompany(**row) for row in WATCHLIST_SEEDS if row["name"] not in existing_names
    )
    db.commit()
    return list(
        db.scalars(
            select(WatchListCompany)
            .where(WatchListCompany.name.in_(seed_names))
            .order_by(WatchListCompany.id)
        )
    )
