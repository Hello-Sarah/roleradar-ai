"""Persist Career Copilot conversations, proposals, actions, and audits.

Revision ID: 20260825_05
Revises: 20260825_04
Create Date: 2026-08-25
"""

import sqlalchemy as sa

from alembic import op

revision = "20260825_05"
down_revision = "20260825_04"
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


def upgrade() -> None:
    op.create_table(
        "copilot_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("locale", sa.String(length=20), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
    )
    op.create_table(
        "copilot_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("copilot_sessions.id"), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_copilot_messages_created_at", "copilot_messages", ["created_at"])
    op.create_index("ix_copilot_messages_session_id", "copilot_messages", ["session_id"])

    op.create_table(
        "copilot_action_proposals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("copilot_sessions.id"), nullable=False),
        sa.Column("proposal_type", sa.String(length=80), nullable=False),
        sa.Column("proposal_version", sa.String(length=20), nullable=False),
        sa.Column("target_type", sa.String(length=40), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("current_value", sa.JSON(), nullable=False),
        sa.Column("proposed_value", sa.JSON(), nullable=False),
        sa.Column("side_effects", sa.JSON(), nullable=False),
        sa.Column("private_data_usage", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
    )
    for name, columns in (
        ("ix_copilot_action_proposals_proposal_type", ["proposal_type"]),
        ("ix_copilot_action_proposals_session_id", ["session_id"]),
        ("ix_copilot_action_proposals_status", ["status"]),
        ("ix_copilot_action_proposals_target_id", ["target_id"]),
    ):
        op.create_index(name, "copilot_action_proposals", columns)

    op.create_table(
        "copilot_action_audits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("copilot_sessions.id"), nullable=False),
        sa.Column(
            "proposal_id",
            sa.Integer(),
            sa.ForeignKey("copilot_action_proposals.id"),
            nullable=True,
            unique=True,
        ),
        sa.Column("proposal_type", sa.String(length=80), nullable=False),
        sa.Column("proposal_version", sa.String(length=20), nullable=False),
        sa.Column("parameter_summary", sa.JSON(), nullable=False),
        sa.Column(
            "confirmed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("actor", sa.String(length=100), nullable=False),
        sa.Column("result_record_ids", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("error_state", sa.String(length=200), nullable=True),
    )
    for name, columns, unique in (
        ("ix_copilot_action_audits_confirmed_at", ["confirmed_at"], False),
        ("ix_copilot_action_audits_idempotency_key", ["idempotency_key"], True),
        ("ix_copilot_action_audits_proposal_type", ["proposal_type"], False),
        ("ix_copilot_action_audits_session_id", ["session_id"], False),
    ):
        op.create_index(name, "copilot_action_audits", columns, unique=unique)

    op.create_table(
        "copilot_action_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("item_kind", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("completed", sa.Boolean(), nullable=False),
        *_timestamps(),
    )
    for name, columns in (
        ("ix_copilot_action_items_completed", ["completed"]),
        ("ix_copilot_action_items_due_date", ["due_date"]),
        ("ix_copilot_action_items_item_kind", ["item_kind"]),
        ("ix_copilot_action_items_job_id", ["job_id"]),
    ):
        op.create_index(name, "copilot_action_items", columns)


def downgrade() -> None:
    raise NotImplementedError("Career Copilot audit migrations are append-only.")
