from fastapi.testclient import TestClient

from app.database.models import CopilotActionAudit, CopilotMessage


def test_conversation_lifecycle_clears_bodies_but_preserves_action_audit(
    client: TestClient, db
) -> None:
    session_response = client.post(
        "/api/v1/copilot/sessions", json={"title": "Job decision", "locale": "en"}
    )
    assert session_response.status_code == 201
    session_id = session_response.json()["id"]

    renamed = client.patch(
        f"/api/v1/copilot/sessions/{session_id}", json={"title": "Example AI role"}
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Example AI role"

    continued = client.post(
        f"/api/v1/copilot/sessions/{session_id}/messages",
        json={"role": "user", "body": "Why is this role a fit?"},
    )
    assert continued.status_code == 201
    assert continued.json()["body"] == "Why is this role a fit?"

    audit = CopilotActionAudit(
        session_id=session_id,
        proposal_id=None,
        proposal_type="change_application_status",
        proposal_version="1",
        parameter_summary={"target_id": 99},
        actor="user",
        result_record_ids={"job": [99]},
        idempotency_key="preserved-audit",
        error_state=None,
    )
    db.add(audit)
    db.commit()

    deleted = client.delete(f"/api/v1/copilot/sessions/{session_id}")

    assert deleted.status_code == 204
    assert db.query(CopilotMessage).one().body is None
    preserved = db.query(CopilotActionAudit).one()
    assert preserved.parameter_summary == {"target_id": 99}
    assert preserved.idempotency_key == "preserved-audit"


def test_context_preview_and_proposal_confirmation_api(client: TestClient, db) -> None:
    from app.database.models import Job

    job = Job(
        fingerprint="copilot-api-job",
        company="Example AI",
        title="Applied AI Engineer",
        location="Hong Kong",
        description="Build reliable applied AI systems with customers using Python and SQL.",
        source="manual",
        status="New",
    )
    db.add(job)
    db.commit()
    session = client.post(
        "/api/v1/copilot/sessions", json={"title": "Apply decision", "locale": "zh-Hans"}
    ).json()

    context = client.get(f"/api/v1/copilot/context?job_id={job.id}")
    assert context.status_code == 200
    assert context.json()["job"]["id"] == job.id
    assert context.json()["cv_documents"] == []

    proposed = client.post(
        "/api/v1/copilot/proposals",
        json={
            "session_id": session["id"],
            "proposal": {
                "proposal_type": "change_application_status",
                "target_id": job.id,
                "expected_status": "New",
                "status": "Saved",
            },
        },
    )
    assert proposed.status_code == 201
    preview = proposed.json()
    assert preview["target"] == {"record_type": "job", "record_id": job.id}
    assert preview["current_value"] == {"status": "New"}
    assert preview["proposed_value"] == {"status": "Saved"}
    assert preview["side_effects"]
    assert preview["private_data_usage"]["included"] is False

    confirmed = client.post(
        f"/api/v1/copilot/proposals/{preview['id']}/confirm",
        json={"idempotency_key": "api-confirm-once", "actor": "user"},
    )
    repeated = client.post(
        f"/api/v1/copilot/proposals/{preview['id']}/confirm",
        json={"idempotency_key": "api-confirm-once", "actor": "user"},
    )

    assert confirmed.status_code == 200
    assert repeated.json() == confirmed.json()
    assert client.get(f"/api/v1/jobs/{job.id}").json()["status"] == "Saved"


def test_api_rejects_forbidden_or_malformed_proposal_without_writes(client: TestClient, db) -> None:
    session = client.post(
        "/api/v1/copilot/sessions", json={"title": "Safety", "locale": "en"}
    ).json()

    for proposal_type in ("bulk_edit", "overwrite_source_cv", "auto_apply", "delete"):
        response = client.post(
            "/api/v1/copilot/proposals",
            json={
                "session_id": session["id"],
                "proposal": {"proposal_type": proposal_type, "target_id": 1},
            },
        )
        assert response.status_code == 422

    assert db.query(CopilotActionAudit).count() == 0


def test_intent_provider_runs_after_context_read_transaction_closes(
    client: TestClient, db, monkeypatch
) -> None:
    from app.copilot.contracts import SaveJobProposal
    from app.database.models import Job

    job = Job(
        fingerprint="copilot-provider-boundary-job",
        company="Example AI",
        title="Applied AI Engineer",
        location="Hong Kong",
        description="Build reliable applied AI systems using Python and SQL.",
        source="manual",
        status="New",
    )
    db.add(job)
    db.commit()
    session = client.post(
        "/api/v1/copilot/sessions", json={"title": "Intent", "locale": "en"}
    ).json()

    def assert_outside_transaction(_message, context, _settings):
        assert not db.in_transaction()
        return SaveJobProposal(target_id=context.job.id, expected_status="New")

    monkeypatch.setattr("app.api.routes.propose_action", assert_outside_transaction)

    response = client.post(
        "/api/v1/copilot/propose",
        json={
            "session_id": session["id"],
            "message": "Save this job",
            "job_id": job.id,
        },
    )

    assert response.status_code == 201
    assert response.json()["proposal_type"] == "save_job"
