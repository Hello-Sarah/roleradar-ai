from __future__ import annotations

from typing import Any

import pytest
from playwright.sync_api import expect

DESKTOP_ROUTES = {
    "dashboard": (
        "Dashboard",
        "Good decisions, clearly prioritized.",
        "把重要的职业决策排在前面。",
    ),
    "job-detail": ("Jobs", "Jobs", "职位"),
    "watch-list": ("Watch List", "Watch List", "关注列表"),
    "cv-library": ("CV Library", "CV Library", "CV 库"),
}


@pytest.mark.parametrize(("locale", "language_label"), [("en", "EN"), ("zh", "中文")])
def test_bilingual_visual_routes_use_identical_redacted_seed(
    seeded_roleradar_page: Any,
    screenshot_path: Any,
    locale: str,
    language_label: str,
) -> None:
    page = seeded_roleradar_page
    page.get_by_text(language_label, exact=True).click()
    for slug, (route, en_heading, zh_heading) in DESKTOP_ROUTES.items():
        localized_route = route if locale == "en" else screenshot_path.localized_route(route)
        page.get_by_text(localized_route, exact=True).first.click()
        expect(
            page.get_by_role(
                "heading", name=en_heading if locale == "en" else zh_heading, exact=True
            )
        ).to_be_visible()
        page.screenshot(path=screenshot_path(locale, f"{slug}.png"), full_page=True)


def test_narrow_visuals_have_no_horizontal_overflow(
    narrow_seeded_page: Any,
    screenshot_path: Any,
) -> None:
    page = narrow_seeded_page
    for index, (slug, route) in enumerate((("dashboard", "Dashboard"), ("job-detail", "Jobs"))):
        if index:
            page.get_by_test_id("stExpandSidebarButton").click()
            page.get_by_text(route, exact=True).first.click()
            page.get_by_test_id("stSidebarCollapseButton").click()
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        page.screenshot(path=screenshot_path("narrow", f"{slug}.png"), full_page=True)
    page.get_by_role("button", name="Open Career Copilot").first.click()
    expect(page.get_by_role("dialog")).to_be_visible()
    page.screenshot(path=screenshot_path("narrow", "copilot.png"), full_page=True)


def test_bilingual_error_state_is_captured(
    unavailable_page: Any,
    screenshot_path: Any,
) -> None:
    page = unavailable_page
    expect(page.get_by_text("temporarily unavailable", exact=False).first).to_be_visible()
    page.screenshot(path=screenshot_path("en", "error.png"), full_page=True)
    page.get_by_text("中文", exact=True).click()
    expect(page.get_by_text("暂时不可用", exact=False).first).to_be_visible()
    page.screenshot(path=screenshot_path("zh", "error.png"), full_page=True)
