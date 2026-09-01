from datetime import UTC, datetime

from sqlalchemy import select


def _company_payload(**overrides) -> dict:
    payload = {
        "name": "Fano Labs",
        "canonical_domain": "fano.ai",
        "company_type": "ai_native_forward_deployed",
        "strategic_priority": "monitor",
        "action_window": "apply_in_3_to_6_months",
        "target_role_patterns": ["Applied AI Engineer"],
        "target_locations": ["Hong Kong"],
        "positive_keywords": ["agent", "deploy"],
        "exclusion_keywords": ["PMO"],
        "location_notes": "Hong Kong roles preferred",
        "work_authorization_notes": "Confirm per role",
        "official_source_url": "https://fano.ai/careers",
        "source_kind": "career_page",
        "source_state": "unverified",
        "source_state_reason": "New official source awaiting manual verification",
        "rationale": "Relevant local Applied AI company",
    }
    payload.update(overrides)
    return payload


def test_company_requires_all_three_dimensions(client) -> None:
    payload = _company_payload()
    payload.pop("action_window")

    response = client.post("/api/v1/watchlist/companies", json=payload)

    assert response.status_code == 422


def test_add_list_edit_and_change_dimensions_independently(client) -> None:
    created_response = client.post("/api/v1/watchlist/companies", json=_company_payload())
    assert created_response.status_code == 201
    created = created_response.json()

    updated_response = client.patch(
        f"/api/v1/watchlist/companies/{created['id']}",
        json={"action_window": "relationship_only"},
    )
    assert updated_response.status_code == 200
    updated = updated_response.json()

    assert updated["action_window"] == "relationship_only"
    assert updated["company_type"] == "ai_native_forward_deployed"
    assert updated["strategic_priority"] == "monitor"
    assert updated["official_source_url"] == "https://fano.ai/careers"
    assert updated["last_checked_at"] is None
    assert len(client.get("/api/v1/watchlist/companies").json()) == 1


def test_company_enable_and_disable_are_reversible(client) -> None:
    company_id = client.post("/api/v1/watchlist/companies", json=_company_payload()).json()["id"]

    disabled = client.post(f"/api/v1/watchlist/companies/{company_id}/disable").json()
    enabled = client.post(f"/api/v1/watchlist/companies/{company_id}/enable").json()

    assert disabled["enabled"] is False
    assert disabled["source_state"] == "disabled"
    assert enabled["enabled"] is True
    assert enabled["source_state"] == "unverified"
    assert [event["to_state"] for event in enabled["source_history"]] == [
        "disabled",
        "unverified",
    ]


def test_delete_requires_confirmation_but_new_company_can_be_deleted(client) -> None:
    company_id = client.post("/api/v1/watchlist/companies", json=_company_payload()).json()["id"]

    unconfirmed = client.delete(f"/api/v1/watchlist/companies/{company_id}")
    confirmed = client.delete(f"/api/v1/watchlist/companies/{company_id}?confirm=true")

    assert unconfirmed.status_code == 400
    assert confirmed.status_code == 204
    assert client.get(f"/api/v1/watchlist/companies/{company_id}").status_code == 404


def test_delete_with_source_history_is_blocked_with_localized_disable_alternative(client) -> None:
    company_id = client.post("/api/v1/watchlist/companies", json=_company_payload()).json()["id"]
    checked_at = datetime(2026, 8, 31, 10, tzinfo=UTC).isoformat()
    changed = client.patch(
        f"/api/v1/watchlist/companies/{company_id}",
        json={
            "source_state": "verified_manual",
            "source_state_reason": "Official page checked manually",
            "last_verified_at": checked_at,
            "last_checked_at": checked_at,
        },
    )
    assert changed.status_code == 200

    blocked = client.delete(f"/api/v1/watchlist/companies/{company_id}?confirm=true&locale=zh-Hans")

    assert blocked.status_code == 409
    assert "停用" in blocked.json()["detail"]


def test_source_state_change_requires_reason_and_records_transition(client, db) -> None:
    from app.database.models import WatchListSourceStateEvent

    company_id = client.post("/api/v1/watchlist/companies", json=_company_payload()).json()["id"]

    rejected = client.patch(
        f"/api/v1/watchlist/companies/{company_id}",
        json={"source_state": "degraded"},
    )
    accepted = client.patch(
        f"/api/v1/watchlist/companies/{company_id}",
        json={"source_state": "degraded", "source_state_reason": "Official page returned 503"},
    )

    assert rejected.status_code == 422
    assert accepted.status_code == 200
    history = list(
        db.scalars(
            select(WatchListSourceStateEvent).where(
                WatchListSourceStateEvent.company_id == company_id
            )
        )
    )
    assert len(history) == 1
    assert history[0].from_state == "unverified"
    assert history[0].to_state == "degraded"
    assert history[0].reason == "Official page returned 503"
    assert history[0].changed_at is not None
