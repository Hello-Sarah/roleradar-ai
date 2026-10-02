"""Regression probes through real services, API and rendered decision surfaces."""

import pytest
from streamlit.testing.v1 import AppTest

from tests.test_watchlist_api import _company_payload

PMO_JD = "Manage PMO governance, reporting, vendor management and steering committee documentation."


class ApiUIClient:
    def __init__(self, api):
        self.api = api

    def get(self, path):
        response = self.api.get(path)
        response.raise_for_status()
        return response.json()

    def post(self, path, body):
        response = self.api.post(path, json=body)
        response.raise_for_status()
        return response.json()

    def patch(self, path, body):
        response = self.api.patch(path, json=body)
        response.raise_for_status()
        return response.json()


def _job(client, **overrides):
    response = client.post(
        "/api/v1/jobs",
        json={
            "company": "Synthetic Bank",
            "title": "AI Programme Manager",
            "location": "Hong Kong",
            "description": PMO_JD,
            **overrides,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _copilot(ui, job_id, locale):
    from app.dashboard.components.copilot_panel import render_copilot_panel
    from app.dashboard.state import UIContext

    render_copilot_panel(UIContext(route="jobs", locale=locale, job_id=job_id), ui)


def _card(ui, job, locale):
    from app.dashboard.components.job_card import render_job_card

    render_job_card(job, region="test-detail", locale=locale, client=ui)


def _jobs(ui, locale):
    from app.dashboard.pages.jobs import render_page

    render_page(ui, locale)


def _text(app):
    return "\n".join(
        str(element.value)
        for kind in ("markdown", "caption", "warning", "error", "info", "subheader")
        for element in app.get(kind)
    )


@pytest.mark.parametrize("locale", ["en", "zh-Hans"])
@pytest.mark.parametrize("question_form", ["question", "discussion"])
def test_rr_f04_rendered_copilot_question_persists_answer_and_citations_without_proposal(
    client, db, locale, question_form
):
    from app.database.models import CopilotActionProposal

    job = _job(client)
    session = client.post(
        "/api/v1/copilot/sessions", json={"title": "Scoring", "locale": locale}
    ).json()
    app = AppTest.from_function(_copilot, args=(ApiUIClient(client), job["id"], locale)).run()
    if question_form == "question":
        prompt = "Why is this score low?" if locale == "en" else "为什么这个分数很低？"
    else:
        prompt = "Help me understand the score" if locale == "en" else "请解释这个岗位评分"
    app.chat_input[0].set_value(prompt).run()
    messages = client.get(f"/api/v1/copilot/sessions/{session['id']}/messages").json()
    assert messages[-1]["role"] == "assistant"
    assert any(item["record_type"] == "job" for item in messages[-1]["sources"])
    assert messages[-1]["body"] in _text(app)
    assert ("AI Depth: 0/20" if locale == "en" else "AI 深度: 0/20") in messages[-1]["body"]
    assert ("Skip" if locale == "en" else "跳过") in messages[-1]["body"]
    assert "job" in _text(app)
    assert db.query(CopilotActionProposal).count() == 0
    assert not app.exception


@pytest.mark.parametrize("locale", ["en", "zh-Hans"])
def test_rr_f05_actual_job_card_shows_all_dimensions_pmo_warning_and_versions(client, locale):
    job = _job(client)
    app = AppTest.from_function(_card, args=(ApiUIClient(client), job, locale)).run()
    rendered = _text(app)
    assert "AI_TITLE_PMO_SUBSTANCE" in rendered
    assert PMO_JD in rendered
    for dimension, maximum in zip(
        job["analysis"]["score_breakdown"], [20, 20, 20, 15, 15, 10], strict=True
    ):
        assert f"{job['analysis']['score_breakdown'][dimension]}/{maximum}" in rendered
    assert "career-fit-v2" in rendered
    assert job["analysis"]["profile_version"] in rendered
    assert not app.exception


@pytest.mark.parametrize(
    "location,expected_location", [("Hong Kong", "eligible"), ("Remote USA", "ineligible")]
)
def test_rr_f06_attached_job_api_exposes_independent_eligibility(
    client, location, expected_location
):
    company = client.post(
        "/api/v1/watchlist/companies",
        json=_company_payload(
            name="Synthetic Bank",
            canonical_domain="synthetic-bank.invalid",
            strategic_priority="strict_filter",
            rationale="Company reputation is not JD evidence",
        ),
    ).json()
    job = _job(client, location=location)
    attached = client.patch(f"/api/v1/jobs/{job['id']}/company", json={"company_id": company["id"]})
    assert attached.status_code == 200
    persisted = client.get(f"/api/v1/jobs/{job['id']}").json()
    assert persisted["watchlist_company_id"] == company["id"]
    result = persisted["eligibility"]
    assert result["location_eligibility"] == expected_location
    assert result["work_authorization"] == "unclear"
    assert result["strict_filter_passed"] is False
    assert result["expected_return"] == "skip"
    assert result["inherited_company_rationale"] == company["rationale"]
    assert company["rationale"] not in result["job_evidence"]
    assert persisted["analysis"] == job["analysis"]


@pytest.mark.parametrize("locale", ["en", "zh-Hans"])
def test_rr_f06_rendered_company_selection_displays_job_evidence_separately(client, locale):
    company = client.post(
        "/api/v1/watchlist/companies",
        json=_company_payload(
            name="Synthetic Bank",
            canonical_domain="synthetic-bank.invalid",
            strategic_priority="strict_filter",
            rationale="Company reputation is not JD evidence",
        ),
    ).json()
    job = _job(client)
    app = AppTest.from_function(_jobs, args=(ApiUIClient(client), locale)).run()
    buttons = [item for item in app.button if item.label in ("Associate company", "关联公司")]
    assert buttons, "Job UI must expose explicit company association"
    buttons[0].click().run()
    selector = next(
        item for item in app.selectbox if item.label in ("Watch List company", "关注列表公司")
    )
    selector.set_value(company["id"]).run()
    next(
        item for item in app.button if item.label in ("Save association", "保存关联")
    ).click().run()
    assert company["rationale"] in _text(app)
    assert ("Job-specific eligibility" if locale == "en" else "岗位独立资格判断") in _text(app)
    assert (
        "Company rationale (not JD evidence)"
        if locale == "en"
        else "公司关注理由（不作为岗位证据）"
    ) in _text(app)
    assert (
        client.get(f"/api/v1/jobs/{job['id']}").json()["eligibility"]["strict_filter_passed"]
        is False
    )
    assert not app.exception


def test_job_company_association_rejects_missing_targets_and_can_be_cleared(client):
    company = client.post("/api/v1/watchlist/companies", json=_company_payload()).json()
    job = _job(client)
    assert (
        client.patch(f"/api/v1/jobs/{job['id']}/company", json={"company_id": 99999}).status_code
        == 404
    )
    assert (
        client.patch("/api/v1/jobs/99999/company", json={"company_id": company["id"]}).status_code
        == 404
    )
    attached = client.patch(
        f"/api/v1/jobs/{job['id']}/company", json={"company_id": company["id"]}
    ).json()
    assert attached["eligibility"] is not None
    detached = client.patch(f"/api/v1/jobs/{job['id']}/company", json={"company_id": None}).json()
    assert detached["eligibility"] is None
    assert detached["watchlist_company_id"] is None
    assert detached["analysis"] == job["analysis"]
