"""Attach jobs to Watch List companies and retain document-body CV evidence."""

import sqlalchemy as sa

from alembic import op

revision = "20261002_06"
down_revision = "20260825_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        # Additive DDL preserves referenced jobs and their histories with FK checks on.
        op.execute(
            "ALTER TABLE jobs ADD COLUMN watchlist_company_id INTEGER "
            "REFERENCES watchlist_companies(id) ON DELETE SET NULL"
        )
    else:
        op.add_column(
            "jobs",
            sa.Column(
                "watchlist_company_id",
                sa.Integer(),
                sa.ForeignKey(
                    "watchlist_companies.id", name="fk_jobs_watchlist_company", ondelete="SET NULL"
                ),
                nullable=True,
            ),
        )
    op.create_index("ix_jobs_watchlist_company_id", "jobs", ["watchlist_company_id"])
    op.add_column(
        "generated_cvs",
        sa.Column("source_evidence", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("generated_cvs", "source_evidence")
    op.drop_index("ix_jobs_watchlist_company_id", table_name="jobs")
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("fk_jobs_watchlist_company", "jobs", type_="foreignkey")
    # Native DROP COLUMN also drops SQLite's inline FK without recreating the
    # referenced jobs table (which would violate existing history foreign keys).
    op.drop_column("jobs", "watchlist_company_id")
