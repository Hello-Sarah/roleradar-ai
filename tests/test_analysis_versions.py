from datetime import datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text

from alembic import command
from app.database.session import _alembic_config
from app.scoring.v2 import JobEvidence, ProfileEvidence, score_job_v2

JOB = {
    "company": "Example AI",
    "title": "Applied AI Engineer",
    "location": "Hong Kong",
    "url": "https://example.com/jobs/versioned-analysis",
    "posting_date": "2026-08-25",
    "description": (
        "Own agentic RAG prototypes end to end, design API integrations, and deploy them to "
        "production with customers. Lead discovery, roadmap prioritization, metrics, and iteration."
    ),
    "source": "manual",
}


def test_explicit_reanalysis_appends_provenance_and_preserves_history(
    client: TestClient,
) -> None:
    created_response = client.post("/api/v1/jobs", json=JOB)
    assert created_response.status_code == 201
    first = created_response.json()["analysis"]
    assert first["scoring_version"] == "career-fit-v2"
    assert first["rubric_version"] == "career-fit-v2"
    assert first["profile_version"]
    assert first["profile_version_id"]
    assert first["profile_snapshot"]["version"] == first["profile_version"]
    assert first["model_version"]
    assert first["prompt_version"]

    profile = client.get("/api/v1/profile").json()
    profile["technical_strengths"] = [*profile["technical_strengths"], "RAG"]
    profile.pop("id")
    profile.pop("created_at")
    profile.pop("updated_at")
    assert client.put("/api/v1/profile", json=profile).status_code == 200

    reanalyzed_response = client.post(f"/api/v1/jobs/{created_response.json()['id']}/reanalyze")
    assert reanalyzed_response.status_code == 201
    second = reanalyzed_response.json()
    assert second["id"] != first["id"]
    assert second["profile_version"] != first["profile_version"]
    assert second["profile_version_id"] != first["profile_version_id"]

    history_response = client.get(f"/api/v1/jobs/{created_response.json()['id']}/analyses")
    assert history_response.status_code == 200
    history = history_response.json()
    assert [item["id"] for item in history] == [second["id"], first["id"]]
    assert history[1] == first
    assert history[0]["profile_snapshot"]["technical_strengths"][-1] == "RAG"
    assert "RAG" not in history[1]["profile_snapshot"]["technical_strengths"]
    first_snapshot = client.get(f"/api/v1/profile/versions/{first['profile_version_id']}")
    second_snapshot = client.get(f"/api/v1/profile/versions/{second['profile_version_id']}")
    assert first_snapshot.status_code == second_snapshot.status_code == 200
    assert first_snapshot.json() == history[1]["profile_snapshot"]
    assert second_snapshot.json() == history[0]["profile_snapshot"]
    assert client.get(f"/api/v1/jobs/{created_response.json()['id']}").json()["analysis"] == second


def test_reanalysis_and_history_return_not_found(client: TestClient) -> None:
    assert client.post("/api/v1/jobs/999/reanalyze").status_code == 404
    assert client.get("/api/v1/jobs/999/analyses").status_code == 404
    assert client.get("/api/v1/profile/versions/999").status_code == 404


def test_model_explanation_cannot_modify_saved_score(client: TestClient, monkeypatch) -> None:
    deterministic = score_job_v2(
        JobEvidence(title=JOB["title"], description=JOB["description"]),
        ProfileEvidence(),
    )

    def misleading_explanation(**_kwargs):
        return SimpleNamespace(summary="Model-authored explanation.", fit_score=100), "fake-model"

    monkeypatch.setattr("app.services.job_service.explain_fit", misleading_explanation)
    response = client.post(
        "/api/v1/jobs",
        json={**JOB, "url": "https://example.com/jobs/model-cannot-score"},
    )

    assert response.status_code == 201
    analysis = response.json()["analysis"]
    assert analysis["fit_score"] == deterministic.total_score
    assert analysis["score_breakdown"] == {
        name: dimension.score for name, dimension in deterministic.dimensions.items()
    }
    assert analysis["summary"] == "Model-authored explanation."
    assert analysis["model_version"] == "fake-model"


def test_v2_migration_preserves_legacy_analysis_and_removes_job_uniqueness(tmp_path) -> None:
    url = f"sqlite:///{tmp_path / 'versioned-analysis.db'}"
    config = _alembic_config(url)
    command.upgrade(config, "20260825_01")
    engine = create_engine(url)
    now = datetime(2026, 8, 25).isoformat()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO candidate_profiles "
                "(id, name, target_roles, preferred_locations, future_locations, "
                "domain_strengths, technical_strengths, development_gaps, created_at, updated_at) "
                "VALUES (1, 'Legacy', '[]', '[]', '[]', '[]', '[]', '[]', :now, :now)"
            ),
            {"now": now},
        )
        connection.execute(
            text(
                "INSERT INTO jobs "
                "(id, fingerprint, company, title, location, description, source, status, "
                "created_at, updated_at) VALUES "
                "(1, 'legacy-fingerprint', 'Legacy Co', 'AI Lead', 'Hong Kong', "
                "'Coordinate AI reporting and governance for stakeholders.', 'manual', 'New', "
                ":now, :now)"
            ),
            {"now": now},
        )
        connection.execute(
            text(
                "INSERT INTO job_analyses "
                "(id, job_id, profile_id, fit_score, score_breakdown, strengths, gaps, evidence, "
                "recommendation, summary, model_used, created_at, updated_at) VALUES "
                "(1, 1, 1, 42, '{}', '[]', '[]', '[]', 'Skip', 'Legacy result', "
                "'deterministic-fallback', :now, :now)"
            ),
            {"now": now},
        )
    engine.dispose()

    command.upgrade(config, "head")

    engine = create_engine(url)
    try:
        assert "candidate_profile_versions" in inspect(engine).get_table_names()
        indexes = {index["name"]: index for index in inspect(engine).get_indexes("job_analyses")}
        assert indexes["ix_job_analyses_job_id"]["unique"] == 0
        with engine.connect() as connection:
            legacy = connection.execute(
                text(
                    "SELECT fit_score, scoring_version, rubric_version, model_version, "
                    "profile_version_id "
                    "FROM job_analyses WHERE id = 1"
                )
            ).one()
            assert tuple(legacy) == (
                42,
                "legacy-v1",
                "legacy-v1",
                "deterministic-fallback",
                1,
            )
            snapshot = connection.execute(
                text(
                    "SELECT profile_id, version, name FROM candidate_profile_versions "
                    "WHERE id = :snapshot_id"
                ),
                {"snapshot_id": legacy.profile_version_id},
            ).one()
            assert tuple(snapshot) == (1, "legacy-profile", "Legacy")
    finally:
        engine.dispose()
