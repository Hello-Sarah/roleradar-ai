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

_LEGACY_TABLES = frozenset(
    {
        "candidate_profiles",
        "jobs",
        "job_classifications",
        "job_analyses",
        "application_events",
        "cv_documents",
    }
)


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


def upgrade_database(database_url: str | None = None) -> None:
    """Upgrade the configured database without discarding an unversioned legacy baseline."""
    url = database_url or settings.database_url
    table_names = _existing_table_names(url)
    config = _alembic_config(url)

    if "alembic_version" not in table_names and table_names:
        if not table_names >= _LEGACY_TABLES:
            raise RuntimeError(
                "Refusing to migrate an unknown unversioned schema; expected the RoleRadar legacy "
                "jobs/profile, application-events, and CV-document tables."
            )
        command.stamp(config, "base")

    command.upgrade(config, "head")


def create_tables() -> None:
    """Backward-compatible development bootstrap for callers not yet using ``upgrade_database``."""

    upgrade_database()
