"""Store immutable tailored-CV provenance and output fingerprints.

Revision ID: 20260825_04
Revises: 20260825_03
Create Date: 2026-08-25
"""

import sqlalchemy as sa

from alembic import op

revision = "20260825_04"
down_revision = "20260825_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "generated_cvs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("file_name", sa.String(length=500), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("output_hash", sa.String(length=64), nullable=False),
        sa.Column("source_cv_ids", sa.JSON(), nullable=False),
        sa.Column("source_cv_hashes", sa.JSON(), nullable=False),
        sa.Column("model_version", sa.String(length=200), nullable=False),
        sa.Column("prompt_version", sa.String(length=100), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for name, columns in (
        ("ix_generated_cvs_file_name", ["file_name"]),
        ("ix_generated_cvs_generated_at", ["generated_at"]),
        ("ix_generated_cvs_job_id", ["job_id"]),
    ):
        op.create_index(name, "generated_cvs", columns)


def downgrade() -> None:
    raise NotImplementedError(
        "Generated CV provenance is append-only and cannot be safely downgraded."
    )
