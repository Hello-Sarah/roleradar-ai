"""Make job analyses append-only and add scoring provenance.

Revision ID: 20260825_02
Revises: 20260825_01
Create Date: 2026-08-25
"""

import sqlalchemy as sa

from alembic import op

revision = "20260825_02"
down_revision = "20260825_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "job_analyses",
        sa.Column(
            "scoring_version", sa.String(length=50), nullable=False, server_default="legacy-v1"
        ),
    )
    op.add_column(
        "job_analyses",
        sa.Column(
            "profile_version",
            sa.String(length=100),
            nullable=False,
            server_default="legacy-profile",
        ),
    )
    op.add_column(
        "job_analyses",
        sa.Column(
            "rubric_version", sa.String(length=50), nullable=False, server_default="legacy-v1"
        ),
    )
    op.add_column(
        "job_analyses",
        sa.Column(
            "model_version",
            sa.String(length=200),
            nullable=False,
            server_default="deterministic-fallback",
        ),
    )
    op.add_column(
        "job_analyses",
        sa.Column(
            "prompt_version", sa.String(length=100), nullable=False, server_default="legacy-prompt"
        ),
    )
    op.add_column(
        "job_analyses",
        sa.Column("score_details", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.execute("UPDATE job_analyses SET model_version = model_used WHERE model_used IS NOT NULL")
    op.drop_index("ix_job_analyses_job_id", table_name="job_analyses")
    op.create_index("ix_job_analyses_job_id", "job_analyses", ["job_id"], unique=False)


def downgrade() -> None:
    raise NotImplementedError("Versioned analyses are append-only and cannot be safely downgraded.")
