import pytest
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

    spoofed = client.post(
        f"/api/v1/copilot/proposals/{preview['id']}/confirm",
        json={"idempotency_key": "spoofed-actor", "actor": "admin"},
    )
    assert spoofed.status_code == 422
    assert db.query(CopilotActionAudit).count() == 0

    confirmed = client.post(
        f"/api/v1/copilot/proposals/{preview['id']}/confirm",
        json={"idempotency_key": "api-confirm-once"},
    )
    repeated = client.post(
        f"/api/v1/copilot/proposals/{preview['id']}/confirm",
        json={"idempotency_key": "api-confirm-once"},
    )

    assert confirmed.status_code == 200
    assert repeated.json() == confirmed.json()
    assert client.get(f"/api/v1/jobs/{job.id}").json()["status"] == "Saved"
    assert db.query(CopilotActionAudit).one().actor == "local_user"


def test_session_titles_are_trimmed_and_blank_titles_are_rejected(client: TestClient, db) -> None:
    created = client.post(
        "/api/v1/copilot/sessions", json={"title": "  Focused search  ", "locale": "en"}
    )
    assert created.status_code == 201
    assert created.json()["title"] == "Focused search"
    session_id = created.json()["id"]

    blank_create = client.post("/api/v1/copilot/sessions", json={"title": "   ", "locale": "en"})
    blank_rename = client.patch(f"/api/v1/copilot/sessions/{session_id}", json={"title": "\t  "})

    assert blank_create.status_code == 422
    assert blank_rename.status_code == 422
    db.expire_all()
    from app.database.models import CopilotSession

    assert db.get(CopilotSession, session_id).title == "Focused search"


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


def test_grounded_answer_uses_selected_context_and_persists_citations(
    client: TestClient, db
) -> None:
    from app.database.models import Job

    job = Job(
        fingerprint="copilot-grounded-answer-job",
        company="Synthetic Signal Labs",
        title="Applied AI Engineer",
        location="Hong Kong",
        description="[SYNTHETIC] Build reliable AI systems using Python and SQL.",
        source="manual",
        status="New",
    )
    db.add(job)
    db.commit()
    session = client.post(
        "/api/v1/copilot/sessions", json={"title": "Grounded answer", "locale": "en"}
    ).json()

    response = client.post(
        "/api/v1/copilot/answer",
        json={
            "session_id": session["id"],
            "message": "Summarize the selected job.",
            "job_id": job.id,
        },
    )

    assert response.status_code == 201
    assert response.json()["source_ids"] == [f"job:{job.id}"]
    assert job.description in response.json()["answer"]
    messages = client.get(f"/api/v1/copilot/sessions/{session['id']}/messages").json()
    assert messages[-1]["role"] == "assistant"
    assert messages[-1]["sources"] == [{"record_type": "job", "record_id": job.id, "version": None}]


@pytest.mark.parametrize("length", [3900, 3999, 4000, 4001, 4589, 20000])
def test_rr_f08_long_jd_answer_is_bounded_and_cited(client, length):
    created = client.post(
        "/api/v1/jobs",
        json={
            "company": "Synthetic",
            "title": "AI Engineer",
            "location": "Hong Kong",
            "description": ("Build reliable AI. " * (length // 19 + 1))[:length],
        },
    )
    assert created.status_code == 201
    job = created.json()
    session = client.post(
        "/api/v1/copilot/sessions", json={"title": "Question", "locale": "en"}
    ).json()
    response = client.post(
        "/api/v1/copilot/answer",
        json={
            "session_id": session["id"],
            "job_id": job["id"],
            "message": "Why is this score low?",
        },
    )
    assert response.status_code == 201, response.text
    assert 0 < len(response.json()["answer"]) <= 4000
    assert f"job:{job['id']}" in response.json()["source_ids"]
