"""Actual decision and discussion journeys required by the final-review gate."""

from playwright.sync_api import expect


def _create_company(api_client):
    response = api_client.post(
        "/api/v1/watchlist/companies",
        json={
            "name": "Synthetic Review Bank",
            "canonical_domain": "review-bank.invalid",
            "company_type": "financial_institution",
            "strategic_priority": "strict_filter",
            "action_window": "apply_now",
            "official_source_url": "https://review-bank.invalid/careers",
            "source_kind": "career_page",
            "source_state": "unverified",
            "source_state_reason": "Synthetic fixture",
            "rationale": "Company rationale only: strategic relationship",
        },
    )
    response.raise_for_status()
    return response.json()


def _associate(page):
    page.get_by_role("button", name="Associate company", exact=True).click()
    selector = page.get_by_role("combobox", name="Watch List company", exact=True)
    selector.click()
    page.keyboard.type("Synthetic Review Bank")
    page.keyboard.press("Enter")
    expect(selector).to_have_value("Synthetic Review Bank")
    page.get_by_role("button", name="Save association", exact=True).click()
    expect(page.get_by_text("Job-specific eligibility", exact=True)).to_be_visible()


def test_rr_f04_f05_f06_pmo_decision_and_grounded_question_in_both_locales(
    roleradar_page, api_client
):
    page = roleradar_page
    _create_company(api_client)
    description = (
        "Manage PMO governance, reporting, vendor management and steering committee documentation."
    )
    response = api_client.post(
        "/api/v1/jobs",
        json={
            "company": "Synthetic Review Bank",
            "title": "AI Programme Manager",
            "location": "Hong Kong",
            "description": description,
        },
    )
    response.raise_for_status()
    job = response.json()
    page.get_by_text("Jobs", exact=True).first.click()
    expect(page.get_by_text("AI_TITLE_PMO_SUBSTANCE", exact=False).first).to_be_visible()
    expect(page.get_by_text(f"jd-001: {description}", exact=True).first).to_be_visible()
    for label, maximum in [
        ("AI Depth", 20),
        ("Ownership", 20),
        ("Build & Ship", 20),
        ("Product Exposure", 15),
        ("Technical Exposure", 15),
        ("Career Option Value", 10),
    ]:
        expect(page.get_by_text(f"{label}: 0/{maximum}", exact=True)).to_be_visible()
    expect(page.get_by_text("Red Flags", exact=True)).to_be_visible()
    expect(page.get_by_text("Green Flags", exact=True)).to_be_visible()
    _associate(page)
    expect(page.get_by_text("Strict Filter: not passed", exact=False)).to_be_visible()
    expect(page.get_by_text("Company rationale (not JD evidence)", exact=True)).to_be_visible()
    page.get_by_role("button", name="Open Career Copilot", exact=True).first.click()
    page.get_by_role("button", name="New conversation", exact=True).last.click()
    expect(
        page.get_by_placeholder("Ask about this context or propose an action").last
    ).to_be_visible()
    for language, prompt, expected in [
        ("EN", "Why is this score low?", "Deterministic fit score: 0/100"),
        ("中文", "为什么这个分数很低？", "确定性匹配分数：0/100"),
    ]:
        if language != "EN":
            page.get_by_text(language, exact=True).click()
        chat = page.get_by_placeholder(
            "Ask about this context or propose an action"
            if language == "EN"
            else "询问当前上下文，或提出一项操作"
        ).last
        chat.fill(prompt)
        chat.press("Enter")
        expect(page.get_by_text(expected, exact=False).last).to_be_visible()
        expect(page.get_by_text("job_analysis", exact=False).last).to_be_visible()
    sessions = api_client.get("/api/v1/copilot/sessions").json()
    messages = api_client.get(f"/api/v1/copilot/sessions/{sessions[0]['id']}/messages").json()
    assert [item["role"] for item in messages] == ["user", "assistant", "user", "assistant"]
    assert all(item["sources"] for item in messages if item["role"] == "assistant")
    persisted = api_client.get(f"/api/v1/jobs/{job['id']}").json()
    assert persisted["status"] == "New"
    assert persisted["application_events"] == []
    assert persisted["eligibility"]["strict_filter_passed"] is False


def test_rr_f06_us_remote_unknown_authorization_is_visible_end_to_end(roleradar_page, api_client):
    page = roleradar_page
    _create_company(api_client)
    response = api_client.post(
        "/api/v1/jobs",
        json={
            "company": "Synthetic Review Bank",
            "title": "Applied AI Engineer",
            "location": "Remote USA",
            "description": "Own solution design, build AI agent prototypes, evaluate models "
            "and deploy production systems with customers.",
        },
    )
    response.raise_for_status()
    job = response.json()
    page.get_by_text("Jobs", exact=True).first.click()
    _associate(page)
    expect(page.get_by_text("Location: Ineligible", exact=True)).to_be_visible()
    expect(page.get_by_text("Work authorization: Eligibility unclear", exact=True)).to_be_visible()
    expect(page.get_by_text("Current expected return: Skip", exact=True)).to_be_visible()
    expect(page.get_by_text("Strict Filter: passed on JD evidence", exact=True)).to_be_visible()
    page.get_by_text("中文", exact=True).click()
    expect(page.get_by_text("岗位独立资格判断", exact=True)).to_be_visible()
    expect(page.get_by_text("公司关注理由（不作为岗位证据）", exact=True)).to_be_visible()
    result = api_client.get(f"/api/v1/jobs/{job['id']}").json()["eligibility"]
    assert result["location_eligibility"] == "ineligible"
    assert result["work_authorization"] == "unclear"
    assert result["strict_filter_passed"] is True
    assert result["expected_return"] == "skip"
