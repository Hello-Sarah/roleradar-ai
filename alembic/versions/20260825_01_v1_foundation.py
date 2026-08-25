"""Create the RoleRadar V1 persistence foundation.

Revision ID: 20260825_01
Revises:
Create Date: 2026-08-25
"""

from collections.abc import Iterable

import sqlalchemy as sa

from alembic import op

revision = "20260825_01"
down_revision = None
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column[object]]:
    return [
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
    ]


def _create_table(name: str, columns: Iterable[sa.Column[object] | sa.Constraint]) -> None:
    if not sa.inspect(op.get_bind()).has_table(name):
        op.create_table(name, *columns)


def _create_index(name: str, table_name: str, columns: list[str], *, unique: bool = False) -> None:
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}
    if name not in indexes:
        op.create_index(name, table_name, columns, unique=unique)


def upgrade() -> None:
    _create_table(
        "candidate_profiles",
        [
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("target_roles", sa.JSON(), nullable=False),
            sa.Column("preferred_locations", sa.JSON(), nullable=False),
            sa.Column("future_locations", sa.JSON(), nullable=False),
            sa.Column("domain_strengths", sa.JSON(), nullable=False),
            sa.Column("technical_strengths", sa.JSON(), nullable=False),
            sa.Column("development_gaps", sa.JSON(), nullable=False),
            *_timestamps(),
        ],
    )
    _create_table(
        "jobs",
        [
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("fingerprint", sa.String(length=64), nullable=False),
            sa.Column("company", sa.String(length=200), nullable=False),
            sa.Column("title", sa.String(length=300), nullable=False),
            sa.Column("location", sa.String(length=200), nullable=False),
            sa.Column("url", sa.Text(), nullable=True),
            sa.Column("posting_date", sa.Date(), nullable=True),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("source", sa.String(length=100), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False),
            *_timestamps(),
        ],
    )
    _create_index("ix_jobs_company", "jobs", ["company"])
    _create_index("ix_jobs_fingerprint", "jobs", ["fingerprint"], unique=True)
    _create_index("ix_jobs_status", "jobs", ["status"])
    _create_index("ix_jobs_title", "jobs", ["title"])

    _create_table(
        "job_classifications",
        [
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
            sa.Column("category", sa.String(length=100), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False),
            sa.Column("evidence", sa.JSON(), nullable=False),
            *_timestamps(),
        ],
    )
    _create_index("ix_job_classifications_job_id", "job_classifications", ["job_id"], unique=True)

    _create_table(
        "job_analyses",
        [
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
            sa.Column(
                "profile_id", sa.Integer(), sa.ForeignKey("candidate_profiles.id"), nullable=False
            ),
            sa.Column("fit_score", sa.Integer(), nullable=False),
            sa.Column("score_breakdown", sa.JSON(), nullable=False),
            sa.Column("strengths", sa.JSON(), nullable=False),
            sa.Column("gaps", sa.JSON(), nullable=False),
            sa.Column("evidence", sa.JSON(), nullable=False),
            sa.Column("recommendation", sa.String(length=50), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("model_used", sa.String(length=100), nullable=False),
            *_timestamps(),
        ],
    )
    _create_index("ix_job_analyses_fit_score", "job_analyses", ["fit_score"])
    _create_index("ix_job_analyses_job_id", "job_analyses", ["job_id"], unique=True)

    _create_table(
        "application_events",
        [
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("channel", sa.String(length=100), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("next_follow_up_date", sa.Date(), nullable=True),
            *_timestamps(),
        ],
    )
    for name, columns in (
        ("ix_application_events_job_id", ["job_id"]),
        ("ix_application_events_next_follow_up_date", ["next_follow_up_date"]),
        ("ix_application_events_occurred_at", ["occurred_at"]),
        ("ix_application_events_status", ["status"]),
    ):
        _create_index(name, "application_events", columns)

    _create_table(
        "cv_documents",
        [
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("file_path", sa.Text(), nullable=False),
            sa.Column("file_name", sa.String(length=500), nullable=False),
            sa.Column("file_type", sa.String(length=20), nullable=False),
            sa.Column("fingerprint", sa.String(length=64), nullable=False),
            sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("extracted_text", sa.Text(), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False),
            *_timestamps(),
            sa.UniqueConstraint("file_path"),
        ],
    )
    for name, columns in (
        ("ix_cv_documents_active", ["active"]),
        ("ix_cv_documents_file_name", ["file_name"]),
        ("ix_cv_documents_fingerprint", ["fingerprint"]),
    ):
        _create_index(name, "cv_documents", columns)

    _create_table(
        "workflow_runs",
        [
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("workflow_type", sa.String(length=100), nullable=False),
            sa.Column("contract_version", sa.String(length=50), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("input_reference", sa.String(length=500), nullable=True),
            sa.Column("result_reference", sa.String(length=500), nullable=True),
            sa.Column("model_version", sa.String(length=200), nullable=True),
            sa.Column("prompt_version", sa.String(length=100), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_code", sa.String(length=100), nullable=True),
            *_timestamps(),
        ],
    )
    _create_index("ix_workflow_runs_status", "workflow_runs", ["status"])
    _create_index("ix_workflow_runs_workflow_type", "workflow_runs", ["workflow_type"])

    _create_table(
        "workflow_steps",
        [
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "workflow_run_id", sa.Integer(), sa.ForeignKey("workflow_runs.id"), nullable=False
            ),
            sa.Column("step_name", sa.String(length=100), nullable=False),
            sa.Column("version", sa.String(length=50), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("input_reference", sa.String(length=500), nullable=True),
            sa.Column("result_reference", sa.String(length=500), nullable=True),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_code", sa.String(length=100), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            *_timestamps(),
        ],
    )
    _create_index("ix_workflow_steps_status", "workflow_steps", ["status"])
    _create_index("ix_workflow_steps_step_name", "workflow_steps", ["step_name"])
    _create_index("ix_workflow_steps_workflow_run_id", "workflow_steps", ["workflow_run_id"])


def downgrade() -> None:
    raise NotImplementedError("Foundation migrations are append-only to preserve existing data.")
