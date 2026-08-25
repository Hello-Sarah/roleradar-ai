from datetime import datetime

import pytest
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP

from app.database.session import _matches_legacy_column, upgrade_database


def table_names(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_legacy_datetime_signature_accepts_postgresql_timestamp() -> None:
    assert _matches_legacy_column(
        {"type": TIMESTAMP(timezone=True), "nullable": False},
        ("DATETIME", None, False),
    )


def create_legacy_schema(
    engine, *, include_development_gaps: bool = True, include_foreign_keys: bool = True
) -> Table:
    metadata = MetaData()

    def foreign_key(target: str) -> list[ForeignKey]:
        return [ForeignKey(target)] if include_foreign_keys else []

    profile_columns = [
        Column("id", Integer, primary_key=True),
        Column("name", String(200), nullable=False),
        Column("target_roles", JSON, nullable=False),
        Column("preferred_locations", JSON, nullable=False),
        Column("future_locations", JSON, nullable=False),
        Column("domain_strengths", JSON, nullable=False),
        Column("technical_strengths", JSON, nullable=False),
    ]
    if include_development_gaps:
        profile_columns.append(Column("development_gaps", JSON, nullable=False))
    profile_columns.extend(
        [
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column("updated_at", DateTime(timezone=True), nullable=False),
        ]
    )
    profiles = Table("candidate_profiles", metadata, *profile_columns)
    Table(
        "jobs",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("fingerprint", String(64), nullable=False, unique=True),
        Column("company", String(200), nullable=False),
        Column("title", String(300), nullable=False),
        Column("location", String(200), nullable=False),
        Column("url", Text, nullable=True),
        Column("posting_date", Date, nullable=True),
        Column("description", Text, nullable=False),
        Column("source", String(100), nullable=False),
        Column("status", String(30), nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("updated_at", DateTime(timezone=True), nullable=False),
    )
    Table(
        "job_classifications",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("job_id", Integer, *foreign_key("jobs.id"), nullable=False, unique=True),
        Column("category", String(100), nullable=False),
        Column("confidence", Float, nullable=False),
        Column("evidence", JSON, nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("updated_at", DateTime(timezone=True), nullable=False),
    )
    Table(
        "job_analyses",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("job_id", Integer, *foreign_key("jobs.id"), nullable=False, unique=True),
        Column("profile_id", Integer, *foreign_key("candidate_profiles.id"), nullable=False),
        Column("fit_score", Integer, nullable=False),
        Column("score_breakdown", JSON, nullable=False),
        Column("strengths", JSON, nullable=False),
        Column("gaps", JSON, nullable=False),
        Column("evidence", JSON, nullable=False),
        Column("recommendation", String(50), nullable=False),
        Column("summary", Text, nullable=False),
        Column("model_used", String(100), nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("updated_at", DateTime(timezone=True), nullable=False),
    )
    Table(
        "application_events",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("job_id", Integer, *foreign_key("jobs.id"), nullable=False),
        Column("status", String(30), nullable=False),
        Column("occurred_at", DateTime(timezone=True), nullable=False),
        Column("channel", String(100), nullable=True),
        Column("notes", Text, nullable=True),
        Column("next_follow_up_date", Date, nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("updated_at", DateTime(timezone=True), nullable=False),
    )
    Table(
        "cv_documents",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("file_path", Text, nullable=False, unique=True),
        Column("file_name", String(500), nullable=False),
        Column("file_type", String(20), nullable=False),
        Column("fingerprint", String(64), nullable=False),
        Column("modified_at", DateTime(timezone=True), nullable=False),
        Column("extracted_text", Text, nullable=False),
        Column("active", Boolean, nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("updated_at", DateTime(timezone=True), nullable=False),
    )
    metadata.create_all(engine)
    return profiles


def test_alembic_upgrades_empty_database(tmp_path) -> None:
    url = f"sqlite:///{tmp_path / 'migration.db'}"

    upgrade_database(url)

    assert {"application_events", "cv_documents", "workflow_runs"} <= table_names(url)


def test_alembic_preserves_known_unversioned_legacy_database(tmp_path) -> None:
    url = f"sqlite:///{tmp_path / 'legacy.db'}"
    engine = create_engine(url)
    profiles = create_legacy_schema(engine)
    with engine.begin() as connection:
        connection.execute(
            profiles.insert(),
            {
                "name": "Preserved profile",
                "target_roles": [],
                "preferred_locations": [],
                "future_locations": [],
                "domain_strengths": [],
                "technical_strengths": [],
                "development_gaps": [],
                "created_at": datetime(2026, 8, 25),
                "updated_at": datetime(2026, 8, 25),
            },
        )
    engine.dispose()

    upgrade_database(url)

    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            assert (
                connection.execute(text("SELECT name FROM candidate_profiles")).scalar_one()
                == "Preserved profile"
            )
        assert "workflow_steps" in table_names(url)
    finally:
        engine.dispose()


def test_alembic_refuses_legacy_schema_with_extra_table(tmp_path) -> None:
    url = f"sqlite:///{tmp_path / 'extra-table.db'}"
    engine = create_engine(url)
    create_legacy_schema(engine)
    Table("unrelated_records", MetaData(), Column("id", Integer, primary_key=True)).create(engine)
    engine.dispose()

    with pytest.raises(RuntimeError, match="unknown unversioned schema"):
        upgrade_database(url)

    assert "workflow_runs" not in table_names(url)


def test_alembic_refuses_legacy_schema_with_missing_required_column(tmp_path) -> None:
    url = f"sqlite:///{tmp_path / 'malformed-table.db'}"
    engine = create_engine(url)
    create_legacy_schema(engine, include_development_gaps=False)
    engine.dispose()

    with pytest.raises(RuntimeError, match="unknown unversioned schema"):
        upgrade_database(url)

    assert "workflow_runs" not in table_names(url)


def test_alembic_refuses_legacy_schema_with_missing_foreign_keys(tmp_path) -> None:
    url = f"sqlite:///{tmp_path / 'missing-foreign-keys.db'}"
    engine = create_engine(url)
    create_legacy_schema(engine, include_foreign_keys=False)
    engine.dispose()

    with pytest.raises(RuntimeError, match="unknown unversioned schema"):
        upgrade_database(url)

    assert "workflow_runs" not in table_names(url)


def test_alembic_matches_non_nullable_timestamps_and_unique_indexes(tmp_path) -> None:
    url = f"sqlite:///{tmp_path / 'schema.db'}"
    upgrade_database(url)
    engine = create_engine(url)
    try:
        inspector = inspect(engine)
        for table_name in ("jobs", "application_events", "cv_documents", "workflow_runs"):
            columns = {column["name"]: column for column in inspector.get_columns(table_name)}
            assert columns["created_at"]["nullable"] is False
            assert columns["updated_at"]["nullable"] is False

        indexes = {index["name"]: index for index in inspector.get_indexes("jobs")}
        assert bool(indexes["ix_jobs_fingerprint"]["unique"]) is True
    finally:
        engine.dispose()
