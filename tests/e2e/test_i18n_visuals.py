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


def _assert_material_icons_render(page: Any) -> None:
    broken = page.locator('[data-testid="stIconMaterial"]:visible').evaluate_all(
        """items => items.filter(item => {
          const text = (item.textContent || '').trim();
          const family = getComputedStyle(item).fontFamily.toLowerCase();
          return /(?:keyboard_)?double_arrow_(?:left|right)/.test(text) &&
            !family.includes('material symbols');
        }).map(item => item.textContent.trim())"""
    )
    assert broken == []


def _assert_top_utility_clear_of_toolbar(page: Any) -> None:
    utility = page.get_by_test_id("stMainBlockContainer").get_by_test_id("stCaptionContainer").first
    header = page.get_by_test_id("stHeader")
    expect(utility).to_be_visible()
    utility_bounds = utility.bounding_box()
    header_bounds = header.bounding_box()
    assert utility_bounds is not None and header_bounds is not None
    assert utility_bounds["y"] >= header_bounds["y"] + header_bounds["height"]


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
        _assert_material_icons_render(page)
        _assert_top_utility_clear_of_toolbar(page)
        context_prefix = "Current context" if locale == "en" else "当前上下文"
        expect(page.get_by_text(f"{context_prefix}: {localized_route}", exact=True)).to_be_visible()
        page.screenshot(path=screenshot_path(locale, f"{slug}.png"), full_page=True)


def test_narrow_visuals_have_no_horizontal_overflow(
    narrow_seeded_page: Any,
    screenshot_path: Any,
) -> None:
    page = narrow_seeded_page
    for index, (slug, route) in enumerate((("dashboard", "Dashboard"), ("job-detail", "Jobs"))):
        if index:
            page.get_by_test_id("stExpandSidebarButton").click()
            sidebar = page.locator('[data-testid="stSidebar"][aria-expanded="true"]')
            expect(sidebar).to_be_visible()
            page.wait_for_function(
                "element => element.getBoundingClientRect().width >= 388",
                arg=sidebar.element_handle(),
            )
            sidebar_bounds = sidebar.bounding_box()
            assert sidebar_bounds is not None and sidebar_bounds["width"] >= 388
            page.get_by_text(route, exact=True).first.click()
            page.get_by_test_id("stSidebarCollapseButton").click()
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        _assert_top_utility_clear_of_toolbar(page)
        page.screenshot(path=screenshot_path("narrow", f"{slug}.png"), full_page=True)
    page.get_by_role("button", name="Open Career Copilot").first.click()
    expect(page.get_by_role("dialog")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    dialog_bounds = page.get_by_role("dialog").bounding_box()
    assert dialog_bounds is not None and dialog_bounds["width"] >= 388
    _assert_material_icons_render(page)
    page.screenshot(path=screenshot_path("narrow", "copilot.png"), full_page=True)


@pytest.mark.parametrize(
    ("browser_locale", "heading"),
    [("zh-CN", "把重要的职业决策排在前面。"), ("fr-FR", "Good decisions, clearly prioritized.")],
)
def test_first_visit_uses_browser_language(
    browser: Any, app_runtime: Any, browser_locale: str, heading: str
) -> None:
    context = browser.new_context(locale=browser_locale)
    page = context.new_page()
    try:
        page.goto(app_runtime.app_url)
        expect(page.get_by_role("heading", name=heading, exact=True)).to_be_visible(timeout=20_000)
    finally:
        context.close()


def test_language_choice_survives_refresh_and_reopen_without_database_changes(
    browser: Any, app_runtime: Any, api_client: Any
) -> None:
    context = browser.new_context(locale="en-US")
    before = {
        "jobs": api_client.get("/api/v1/jobs").json(),
        "companies": api_client.get("/api/v1/watchlist/companies").json(),
    }
    page = context.new_page()
    try:
        page.goto(app_runtime.app_url)
        expect(
            page.get_by_role("heading", name="Good decisions, clearly prioritized.")
        ).to_be_visible(timeout=20_000)
        page.get_by_text("中文", exact=True).click()
        expect(page.get_by_role("heading", name="把重要的职业决策排在前面。")).to_be_visible()
        page.wait_for_function(
            "document.cookie.includes('roleradar_locale=zh-Hans')",
            timeout=10_000,
        )
        page.reload()
        expect(page.get_by_role("heading", name="把重要的职业决策排在前面。")).to_be_visible()
        page.close()
        reopened = context.new_page()
        reopened.goto(app_runtime.app_url)
        expect(reopened.get_by_role("heading", name="把重要的职业决策排在前面。")).to_be_visible()
        after = {
            "jobs": api_client.get("/api/v1/jobs").json(),
            "companies": api_client.get("/api/v1/watchlist/companies").json(),
        }
        assert after == before
    finally:
        context.close()


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
