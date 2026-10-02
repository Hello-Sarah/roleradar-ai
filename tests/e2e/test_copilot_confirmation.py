from __future__ import annotations

from typing import Any

from playwright.sync_api import expect


def test_copilot_requires_keyboard_reachable_confirmation_before_write(
    roleradar_page: Any,
    synthetic_jd: str,
    api_client: Any,
    screenshot_path: Any,
) -> None:
    page = roleradar_page
    page.get_by_text("Analyze Job", exact=True).first.click()
    page.get_by_role("tab", name="Paste job text").click()
    page.get_by_role("textbox", name="Paste job text").fill(synthetic_jd)
    page.get_by_role("button", name="Extract fields").click()
    page.get_by_role("button", name="Confirm & analyze").click()
    expect(page.get_by_text("Analysis complete", exact=False)).to_be_visible()
    page.get_by_role("button", name="New conversation").last.click()
    expect(page.get_by_text("Current context: Forward Deployed AI Engineer").last).to_be_visible()
    page.get_by_placeholder("Ask about this context or propose an action").last.fill(
        "Change status to Applied"
    )
    page.keyboard.press("Enter")

    expect(page.get_by_text("Review this proposed action", exact=False).last).to_be_visible()
    for label in (
        "Target record",
        "Current value",
        "Proposed value",
        "Side effects",
        "Private data usage",
    ):
        expect(page.get_by_text(label, exact=True).last).to_be_visible()
    assert api_client.get("/api/v1/jobs").json()[0]["status"] == "New"
    screenshot_path.capture(page, "en", "copilot-confirmation.png")

    page.get_by_text("中文", exact=True).click()
    expect(page.get_by_text("目标记录", exact=True).last).to_be_visible()
    screenshot_path.capture(page, "zh", "copilot-confirmation.png")
    page.get_by_text("EN", exact=True).click()

    page.get_by_role("button", name="Confirm action").last.focus()
    expect(page.get_by_role("button", name="Confirm action").last).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.get_by_text("Updated the application status", exact=False).last).to_be_visible()
    assert api_client.get("/api/v1/jobs").json()[0]["status"] == "Applied"
