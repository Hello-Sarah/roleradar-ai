from collections.abc import Generator
from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from alembic import command
from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _connect_args(url: str) -> dict[str, bool]:
    return {"check_same_thread": False} if url.startswith("sqlite") else {}


settings = get_settings()
engine = create_engine(
    settings.database_url,
    connect_args=_connect_args(settings.database_url),
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)

_LEGACY_SCHEMA = {
    "candidate_profiles": {
        "id": ("INTEGER", None, False),
        "name": ("VARCHAR", 200, False),
        "target_roles": ("JSON", None, False),
        "preferred_locations": ("JSON", None, False),
        "future_locations": ("JSON", None, False),
        "domain_strengths": ("JSON", None, False),
        "technical_strengths": ("JSON", None, False),
        "development_gaps": ("JSON", None, False),
        "created_at": ("DATETIME", None, False),
        "updated_at": ("DATETIME", None, False),
    },
    "jobs": {
        "id": ("INTEGER", None, False),
        "fingerprint": ("VARCHAR", 64, False),
        "company": ("VARCHAR", 200, False),
        "title": ("VARCHAR", 300, False),
        "location": ("VARCHAR", 200, False),
        "url": ("TEXT", None, True),
        "posting_date": ("DATE", None, True),
        "description": ("TEXT", None, False),
        "source": ("VARCHAR", 100, False),
        "status": ("VARCHAR", 30, False),
        "created_at": ("DATETIME", None, False),
        "updated_at": ("DATETIME", None, False),
    },
    "job_classifications": {
        "id": ("INTEGER", None, False),
        "job_id": ("INTEGER", None, False),
        "category": ("VARCHAR", 100, False),
        "confidence": ("FLOAT", None, False),
        "evidence": ("JSON", None, False),
        "created_at": ("DATETIME", None, False),
        "updated_at": ("DATETIME", None, False),
    },
    "job_analyses": {
        "id": ("INTEGER", None, False),
        "job_id": ("INTEGER", None, False),
        "profile_id": ("INTEGER", None, False),
        "fit_score": ("INTEGER", None, False),
        "score_breakdown": ("JSON", None, False),
        "strengths": ("JSON", None, False),
        "gaps": ("JSON", None, False),
        "evidence": ("JSON", None, False),
        "recommendation": ("VARCHAR", 50, False),
        "summary": ("TEXT", None, False),
        "model_used": ("VARCHAR", 100, False),
        "created_at": ("DATETIME", None, False),
        "updated_at": ("DATETIME", None, False),
    },
    "application_events": {
        "id": ("INTEGER", None, False),
        "job_id": ("INTEGER", None, False),
        "status": ("VARCHAR", 30, False),
        "occurred_at": ("DATETIME", None, False),
        "channel": ("VARCHAR", 100, True),
        "notes": ("TEXT", None, True),
        "next_follow_up_date": ("DATE", None, True),
        "created_at": ("DATETIME", None, False),
        "updated_at": ("DATETIME", None, False),
    },
    "cv_documents": {
        "id": ("INTEGER", None, False),
        "file_path": ("TEXT", None, False),
        "file_name": ("VARCHAR", 500, False),
        "file_type": ("VARCHAR", 20, False),
        "fingerprint": ("VARCHAR", 64, False),
        "modified_at": ("DATETIME", None, False),
        "extracted_text": ("TEXT", None, False),
        "active": ("BOOLEAN", None, False),
        "created_at": ("DATETIME", None, False),
        "updated_at": ("DATETIME", None, False),
    },
}

_LEGACY_FOREIGN_KEYS = {
    "candidate_profiles": set(),
    "jobs": set(),
    "job_classifications": {(("job_id",), "jobs", ("id",))},
    "job_analyses": {
        (("job_id",), "jobs", ("id",)),
        (("profile_id",), "candidate_profiles", ("id",)),
    },
    "application_events": {(("job_id",), "jobs", ("id",))},
    "cv_documents": set(),
}

_LEGACY_PRIMARY_KEYS = {table_name: ("id",) for table_name in _LEGACY_SCHEMA}

_LEGACY_UNIQUE_CONSTRAINTS = {
    "candidate_profiles": set(),
    "jobs": set(),
    "job_classifications": set(),
    "job_analyses": set(),
    "application_events": set(),
    "cv_documents": {("file_path",)},
}

_LEGACY_INDEXES = {
    "candidate_profiles": set(),
    "jobs": {
        ("ix_jobs_company", ("company",), False),
        ("ix_jobs_fingerprint", ("fingerprint",), True),
        ("ix_jobs_status", ("status",), False),
        ("ix_jobs_title", ("title",), False),
    },
    "job_classifications": {("ix_job_classifications_job_id", ("job_id",), True)},
    "job_analyses": {
        ("ix_job_analyses_fit_score", ("fit_score",), False),
        ("ix_job_analyses_job_id", ("job_id",), True),
    },
    "application_events": {
        ("ix_application_events_job_id", ("job_id",), False),
        ("ix_application_events_next_follow_up_date", ("next_follow_up_date",), False),
        ("ix_application_events_occurred_at", ("occurred_at",), False),
        ("ix_application_events_status", ("status",), False),
    },
    "cv_documents": {
        ("ix_cv_documents_active", ("active",), False),
        ("ix_cv_documents_file_name", ("file_name",), False),
        ("ix_cv_documents_fingerprint", ("fingerprint",), False),
    },
}


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _alembic_config(database_url: str) -> Config:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _existing_table_names(database_url: str) -> set[str]:
    database_engine = create_engine(database_url, connect_args=_connect_args(database_url))
    try:
        return set(inspect(database_engine).get_table_names())
    finally:
        database_engine.dispose()


def _matches_legacy_column(
    column: dict[str, object], expected: tuple[str, int | None, bool]
) -> bool:
    expected_type_name, expected_length, expected_nullable = expected
    column_type = column["type"]
    actual_type_name = column_type.__visit_name__.upper()
    expected_type_names = (
        {"DATETIME", "TIMESTAMP"} if expected_type_name == "DATETIME" else {expected_type_name}
    )
    return (
        actual_type_name in expected_type_names
        and getattr(column_type, "length", None) == expected_length
        and column["nullable"] == expected_nullable
    )


def _is_known_legacy_schema(database_url: str, table_names: set[str]) -> bool:
    if table_names != set(_LEGACY_SCHEMA):
        return False

    database_engine = create_engine(database_url, connect_args=_connect_args(database_url))
    try:
        inspector = inspect(database_engine)
        for table_name, expected_columns in _LEGACY_SCHEMA.items():
            columns = {column["name"]: column for column in inspector.get_columns(table_name)}
            if set(columns) != set(expected_columns):
                return False
            for column_name, expected_column in expected_columns.items():
                if not _matches_legacy_column(columns[column_name], expected_column):
                    return False
            foreign_keys = {
                (
                    tuple(foreign_key["constrained_columns"]),
                    foreign_key["referred_table"],
                    tuple(foreign_key["referred_columns"]),
                )
                for foreign_key in inspector.get_foreign_keys(table_name)
            }
            if foreign_keys != _LEGACY_FOREIGN_KEYS[table_name]:
                return False
            primary_key = tuple(
                inspector.get_pk_constraint(table_name)["constrained_columns"] or []
            )
            if primary_key != _LEGACY_PRIMARY_KEYS[table_name]:
                return False
            unique_constraints = {
                tuple(constraint["column_names"])
                for constraint in inspector.get_unique_constraints(table_name)
            }
            if unique_constraints != _LEGACY_UNIQUE_CONSTRAINTS[table_name]:
                return False
            indexes = {
                (index["name"], tuple(index["column_names"]), bool(index["unique"]))
                for index in inspector.get_indexes(table_name)
            }
            if indexes != _LEGACY_INDEXES[table_name]:
                return False
    finally:
        database_engine.dispose()
    return True


def upgrade_database(database_url: str | None = None) -> None:
    """Upgrade the configured database without discarding an unversioned legacy baseline."""
    url = database_url or settings.database_url
    table_names = _existing_table_names(url)
    config = _alembic_config(url)

    if "alembic_version" not in table_names and table_names:
        if not _is_known_legacy_schema(url, table_names):
            raise RuntimeError(
                "Refusing to migrate an unknown unversioned schema; expected the RoleRadar legacy "
                "jobs/profile, application-events, and CV-document tables."
            )
        command.stamp(config, "base")

    command.upgrade(config, "head")


def create_tables() -> None:
    """Backward-compatible development bootstrap for callers not yet using ``upgrade_database``."""

    upgrade_database()
