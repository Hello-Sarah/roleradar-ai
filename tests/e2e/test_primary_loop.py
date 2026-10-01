from __future__ import annotations

import time
from typing import Any

from playwright.sync_api import expect


def _open_route(page: Any, name: str) -> None:
    if page.viewport_size and page.viewport_size["width"] <= 390:
        expand = page.get_by_test_id("stExpandSidebarButton")
        if expand.count():
            expand.click()
    page.get_by_text(name, exact=True).first.click()
    expect(page.get_by_role("heading", name=name, exact=True)).to_be_visible()
    if page.viewport_size and page.viewport_size["width"] <= 390:
        collapse = page.get_by_test_id("stSidebarCollapseButton")
        if collapse.count():
            collapse.click()


def _choose_streamlit_option(page: Any, label: str, option: str) -> None:
    combobox = page.get_by_role("combobox", name=label).last
    combobox.click()
    page.keyboard.type(option)
    page.keyboard.press("Enter")
    expect(combobox).to_have_value(option)


def _wait_for_status(api_client: Any, expected_status: str, timeout: float = 15) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        jobs = api_client.get("/api/v1/jobs").json()
        if jobs and jobs[0]["status"] == expected_status:
            return
        time.sleep(0.05)
    raise AssertionError(f"Timed out waiting for job status {expected_status}")


def test_pasted_job_to_application_watchlist_and_tailored_cv(
    roleradar_page: Any,
    synthetic_jd: str,
    provider_call_log: Any,
    api_client: Any,
) -> None:
    page = roleradar_page
    _open_route(page, "Analyze Job")
    page.get_by_role("tab", name="Paste job text").click()
    page.get_by_role("textbox", name="Paste job text").fill(synthetic_jd)
    page.get_by_role("button", name="Extract fields").click()

    expect(page.get_by_text("Nothing has been saved yet.", exact=False)).to_be_visible()
    expect(page.get_by_label("Company")).to_have_value("Synthetic Signal Labs")
    expect(page.get_by_label("Job title")).to_have_value("Forward Deployed AI Engineer")
    page.get_by_label("Company").fill("Synthetic Edited Labs")
    page.get_by_label("Job title").fill("Edited Forward Deployed AI Engineer")
    page.get_by_label("Location").fill("Kowloon, Hong Kong")
    page.get_by_role("button", name="Confirm & analyze").click()
    expect(page.get_by_text("Analysis complete", exact=False)).to_be_visible()

    _choose_streamlit_option(page, "Application status", "Saved")
    _wait_for_status(api_client, "Saved")
    _choose_streamlit_option(page, "Application status", "Applied")
    _wait_for_status(api_client, "Applied")

    _open_route(page, "Applications")
    page.get_by_label("Notes").fill("Synthetic application event for acceptance testing")
    page.get_by_role("button", name="Add").click()
    expect(page.get_by_text("Synthetic application event for acceptance testing")).to_be_visible()

    _open_route(page, "Watch List")
    page.get_by_text("Add Watch List company", exact=True).first.click()
    add_form = page.get_by_test_id("stForm").first
    add_form.get_by_label("Company name").fill("Synthetic Watch Labs")
    add_form.get_by_label("Canonical domain").fill("synthetic-watch.invalid")
    add_form.get_by_label("Target role patterns (comma-separated)").fill(
        "Forward Deployed AI Engineer"
    )
    add_form.get_by_label("Target locations (comma-separated)").fill("Hong Kong")
    add_form.get_by_label("Official career source URL").fill("https://example.invalid/careers")
    add_form.get_by_label("Why this company matters").fill("Synthetic acceptance target")
    add_form.get_by_role("button", name="Add Watch List company").click()
    expect(page.get_by_role("heading", name="Synthetic Watch Labs")).to_be_visible()

    _open_route(page, "CV Library")
    page.get_by_role("button", name="Scan CV folder").click()
    expect(page.get_by_text("synthetic-redacted-cv.txt", exact=True)).to_be_visible()
    page.get_by_role("button", name="Generate tailored CV").click()
    expect(page.get_by_text("Generated CV #", exact=False)).to_be_visible()
    assert provider_call_log.read_text(encoding="utf-8").splitlines() == ["tailored_cv"]
    jobs = api_client.get("/api/v1/jobs").json()
    assert len(jobs) == 1
    assert jobs[0]["company"] == "Synthetic Edited Labs"
    assert jobs[0]["title"] == "Edited Forward Deployed AI Engineer"
    assert jobs[0]["location"] == "Kowloon, Hong Kong"
    assert jobs[0]["status"] == "Applied"
    assert any(
        event["notes"] == "Synthetic application event for acceptance testing"
        for event in jobs[0]["application_events"]
    )
    companies = api_client.get("/api/v1/watchlist/companies").json()
    assert any(company["name"] == "Synthetic Watch Labs" for company in companies)


def test_primary_loop_and_copilot_are_non_blocking_at_390px(
    narrow_roleradar_page: Any,
    synthetic_jd: str,
    api_client: Any,
) -> None:
    page = narrow_roleradar_page
    _open_route(page, "Analyze Job")
    page.get_by_role("tab", name="Paste job text").click()
    page.get_by_role("textbox", name="Paste job text").fill(synthetic_jd)
    page.get_by_role("button", name="Extract fields").click()
    page.get_by_role("button", name="Confirm & analyze").click()
    expect(page.get_by_text("Analysis complete", exact=False)).to_be_visible()
    _choose_streamlit_option(page, "Application status", "Saved")
    _wait_for_status(api_client, "Saved")
    _choose_streamlit_option(page, "Application status", "Applied")
    _wait_for_status(api_client, "Applied")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.get_by_role("button", name="Open Career Copilot").first.click()
    expect(page.get_by_role("dialog")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    bounds = page.get_by_role("dialog").bounding_box()
    assert bounds is not None
    assert bounds["x"] <= 1 and bounds["width"] >= 388
