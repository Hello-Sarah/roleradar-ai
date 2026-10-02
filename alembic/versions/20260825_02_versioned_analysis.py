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
    op.create_table(
        "candidate_profile_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "profile_id", sa.Integer(), sa.ForeignKey("candidate_profiles.id"), nullable=False
        ),
        sa.Column("version", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("target_roles", sa.JSON(), nullable=False),
        sa.Column("preferred_locations", sa.JSON(), nullable=False),
        sa.Column("future_locations", sa.JSON(), nullable=False),
        sa.Column("domain_strengths", sa.JSON(), nullable=False),
        sa.Column("technical_strengths", sa.JSON(), nullable=False),
        sa.Column("development_gaps", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "profile_id", "version", name="uq_candidate_profile_versions_profile_version"
        ),
    )
    op.create_index(
        "ix_candidate_profile_versions_profile_id",
        "candidate_profile_versions",
        ["profile_id"],
    )
    op.execute(
        """
        INSERT INTO candidate_profile_versions
            (profile_id, version, name, target_roles, preferred_locations, future_locations,
             domain_strengths, technical_strengths, development_gaps, created_at)
        SELECT id, 'legacy-profile', name, target_roles, preferred_locations, future_locations,
               domain_strengths, technical_strengths, development_gaps, created_at
        FROM candidate_profiles
        """
    )
    with op.batch_alter_table("job_analyses") as batch_op:
        batch_op.add_column(sa.Column("profile_version_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_job_analyses_profile_version_id",
            "candidate_profile_versions",
            ["profile_version_id"],
            ["id"],
        )
    op.execute(
        """
        UPDATE job_analyses
        SET profile_version_id = (
            SELECT candidate_profile_versions.id
            FROM candidate_profile_versions
            WHERE candidate_profile_versions.profile_id = job_analyses.profile_id
              AND candidate_profile_versions.version = 'legacy-profile'
        )
        """
    )
    with op.batch_alter_table("job_analyses") as batch_op:
        batch_op.alter_column("profile_version_id", existing_type=sa.Integer(), nullable=False)
    op.create_index(
        "ix_job_analyses_profile_version_id",
        "job_analyses",
        ["profile_version_id"],
    )
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
