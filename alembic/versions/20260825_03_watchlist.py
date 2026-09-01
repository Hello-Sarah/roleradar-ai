"""Add classified Watch List companies and source-state history.

Revision ID: 20260825_03
Revises: 20260825_02
Create Date: 2026-08-25
"""

import sqlalchemy as sa

from alembic import op

revision = "20260825_03"
down_revision = "20260825_02"
branch_labels = None
depends_on = None

_SEED_DOMAINS = {
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

_SEED_GROUPS = (
    (
        "ai_native_forward_deployed",
        "core_target",
        "apply_now",
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
    ),
    ("fintech_product", "core_target", "apply_now", ("Ant International", "Airwallex")),
    ("financial_institution", "core_target", "apply_now", ("Temasek",)),
    (
        "ai_native_forward_deployed",
        "monitor",
        "apply_in_3_to_6_months",
        ("Abridge", "Siena AI", "Gradial", "OpenAI", "Anthropic", "Perplexity"),
    ),
    ("fintech_product", "monitor", "apply_in_3_to_6_months", ("Reap", "SleekFlow")),
    ("cloud_data_enterprise_ai", "monitor", "apply_in_3_to_6_months", ("Databricks",)),
    (
        "fintech_product",
        "opportunistic",
        "stretch_apply",
        ("Grab", "Sea", "ByteDance", "Ramp", "Stripe"),
    ),
    (
        "cloud_data_enterprise_ai",
        "opportunistic",
        "stretch_apply",
        ("Snowflake", "AWS", "Microsoft", "Google", "Salesforce"),
    ),
    (
        "financial_institution",
        "strict_filter",
        "relationship_only",
        ("HSBC", "Standard Chartered", "JPMorgan", "Goldman Sachs"),
    ),
    (
        "consulting_professional_services",
        "strict_filter",
        "relationship_only",
        ("Capgemini",),
    ),
)


def _seed_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for company_type, priority, action_window, names in _SEED_GROUPS:
        for name in names:
            domain = _SEED_DOMAINS[name]
            rows.append(
                {
                    "name": name,
                    "canonical_domain": domain,
                    "company_type": company_type,
                    "strategic_priority": priority,
                    "action_window": action_window,
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
                    "source_kind": "career_page",
                    "source_state": "unverified",
                    "source_state_reason": (
                        "Initial official source awaiting manual verification."
                    ),
                    "enabled": True,
                    "rationale": "Editable initial classification from spec/watch-list.md.",
                }
            )
    return rows


def upgrade() -> None:
    companies = op.create_table(
        "watchlist_companies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("canonical_domain", sa.String(length=253), nullable=False),
        sa.Column("company_type", sa.String(length=50), nullable=False),
        sa.Column("strategic_priority", sa.String(length=30), nullable=False),
        sa.Column("action_window", sa.String(length=40), nullable=False),
        sa.Column("target_role_patterns", sa.JSON(), nullable=False),
        sa.Column("target_locations", sa.JSON(), nullable=False),
        sa.Column("positive_keywords", sa.JSON(), nullable=False),
        sa.Column("exclusion_keywords", sa.JSON(), nullable=False),
        sa.Column("location_notes", sa.Text(), nullable=False),
        sa.Column("work_authorization_notes", sa.Text(), nullable=False),
        sa.Column("official_source_url", sa.Text(), nullable=False),
        sa.Column("source_kind", sa.String(length=40), nullable=False),
        sa.Column("source_state", sa.String(length=30), nullable=False),
        sa.Column("source_state_reason", sa.Text(), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("name", name="uq_watchlist_companies_name"),
        sa.UniqueConstraint("canonical_domain", name="uq_watchlist_companies_canonical_domain"),
    )
    op.create_index("ix_watchlist_companies_name", "watchlist_companies", ["name"], unique=True)
    op.create_index(
        "ix_watchlist_companies_canonical_domain",
        "watchlist_companies",
        ["canonical_domain"],
        unique=True,
    )
    for name, columns in (
        ("ix_watchlist_companies_action_window", ["action_window"]),
        ("ix_watchlist_companies_company_type", ["company_type"]),
        ("ix_watchlist_companies_enabled", ["enabled"]),
        ("ix_watchlist_companies_source_state", ["source_state"]),
        ("ix_watchlist_companies_strategic_priority", ["strategic_priority"]),
    ):
        op.create_index(name, "watchlist_companies", columns)

    op.create_table(
        "watchlist_source_state_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("watchlist_companies.id"),
            nullable=False,
        ),
        sa.Column("from_state", sa.String(length=30), nullable=False),
        sa.Column("to_state", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_watchlist_source_state_events_company_id",
        "watchlist_source_state_events",
        ["company_id"],
    )
    op.create_index(
        "ix_watchlist_source_state_events_changed_at",
        "watchlist_source_state_events",
        ["changed_at"],
    )
    op.bulk_insert(companies, _seed_rows())


def downgrade() -> None:
    raise NotImplementedError("Watch List history is append-only and cannot be safely downgraded.")
