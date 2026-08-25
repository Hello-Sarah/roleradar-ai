from sqlalchemy import MetaData, create_engine, inspect, text
from sqlalchemy.orm import Session

from app.database.models import CandidateProfile
from app.database.session import Base, upgrade_database


def table_names(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_alembic_upgrades_empty_database(tmp_path) -> None:
    url = f"sqlite:///{tmp_path / 'migration.db'}"

    upgrade_database(url)

    assert {"application_events", "cv_documents", "workflow_runs"} <= table_names(url)


def test_alembic_preserves_known_unversioned_legacy_database(tmp_path) -> None:
    url = f"sqlite:///{tmp_path / 'legacy.db'}"
    engine = create_engine(url)
    legacy_metadata = MetaData()
    for table_name in (
        "candidate_profiles",
        "jobs",
        "job_classifications",
        "job_analyses",
        "application_events",
        "cv_documents",
    ):
        Base.metadata.tables[table_name].to_metadata(legacy_metadata)
    legacy_metadata.create_all(engine)
    with Session(engine) as session:
        session.add(CandidateProfile(name="Preserved profile"))
        session.commit()
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
