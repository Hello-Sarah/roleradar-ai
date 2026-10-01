from __future__ import annotations

from datetime import date

import httpx
import pytest

from app.i18n.service import translate


def test_duplicate_job_cards_use_region_scoped_stable_keys() -> None:
    """Catch widget collisions when one job appears in two dashboard regions."""
    from app.dashboard.state import stable_key

    assert stable_key("dashboard-priority", "status", 17) == "dashboard-priority-status-17"
    assert stable_key("dashboard-recent", "status", 17) == "dashboard-recent-status-17"
    assert stable_key("dashboard-priority", "status", 17) != stable_key(
        "dashboard-recent", "status", 17
    )


def test_each_page_region_rejects_multiple_active_primary_actions() -> None:
    """Catch two visually dominant actions competing in one page region."""
    from app.dashboard.state import PageAction, validate_primary_actions

    validate_primary_actions(
        [
            PageAction(region="job-intake", key="extract", primary=True, active=True),
            PageAction(region="job-intake", key="cancel", primary=False, active=True),
        ]
    )

    with pytest.raises(ValueError, match="job-intake"):
        validate_primary_actions(
            [
                PageAction(region="job-intake", key="extract", primary=True, active=True),
                PageAction(region="job-intake", key="save", primary=True, active=True),
            ]
        )


@pytest.mark.parametrize(
    ("locale", "empty_title", "error_title", "retry"),
    [
        ("en", "No results yet", "Something went wrong", "Retry"),
        ("zh-Hans", "暂无结果", "出现问题", "重试"),
    ],
)
def test_component_states_are_fully_localized(
    locale: str, empty_title: str, error_title: str, retry: str
) -> None:
    """Catch English-only empty/error/recovery copy in the Chinese UI."""
    from app.dashboard.components.states import state_copy

    empty = state_copy(locale, "empty")
    error = state_copy(locale, "error")

    assert empty.title == empty_title
    assert empty.description == translate(locale, "component.empty.description")
    assert error.title == error_title
    assert error.description == translate(locale, "component.error.description")
    assert error.action_label == retry


def test_explicit_locale_persists_without_changing_route_state() -> None:
    """Catch language switches that reset navigation or fail to survive refresh."""
    from app.dashboard.state import persist_locale, resolve_ui_locale

    session = {"ui.route": "watchlist", "ui.selected_job_id": 42}
    query = {}

    persist_locale("zh-Hans", session, query)

    assert session == {
        "ui.route": "watchlist",
        "ui.selected_job_id": 42,
        "ui.locale": "zh-Hans",
    }
    assert query == {"lang": "zh-Hans"}
    assert resolve_ui_locale(None, query["lang"], "en-US") == "zh-Hans"
    assert resolve_ui_locale(None, None, "zh-HK") == "zh-Hans"
    assert resolve_ui_locale(None, None, "fr-FR") == "en"


def test_fresh_session_restores_explicit_locale_from_browser_cookie() -> None:
    """Catch a canonical base-URL reopen falling back to browser language."""
    from app.dashboard.state import resolve_ui_locale

    assert resolve_ui_locale(None, None, "en-US", "zh-Hans") == "zh-Hans"


@pytest.mark.parametrize(
    ("locale", "expected"),
    [("en", "Sep 3, 2026"), ("zh-Hans", "2026年9月3日")],
)
def test_api_dates_are_formatted_for_active_locale(locale: str, expected: str) -> None:
    """Catch neutral ISO storage values leaking into localized presentation."""
    from app.dashboard.state import format_local_date

    assert format_local_date(locale, "2026-09-03T13:16:41") == expected


def test_navigation_has_exact_bilingual_information_architecture() -> None:
    """Catch a missing/reordered V1 route or untranslated navigation label."""
    from app.dashboard.components.navigation import navigation_items

    en = navigation_items("en")
    zh = navigation_items("zh-Hans")

    assert [item.route for item in en] == [
        "dashboard",
        "analyze",
        "jobs",
        "applications",
        "watchlist",
        "cv_library",
        "digest",
        "profile",
    ]
    assert [item.label for item in en] == [
        "Dashboard",
        "Analyze Job",
        "Jobs",
        "Applications",
        "Watch List",
        "CV Library",
        "Digest",
        "Profile",
    ]
    assert [item.label for item in zh] == [
        "仪表盘",
        "分析职位",
        "职位",
        "申请记录",
        "关注列表",
        "CV 库",
        "每日报告",
        "个人档案",
    ]


def test_edited_preview_wins_over_rich_jd_aws_false_positive() -> None:
    """Catch persistence of an AWS technology mention as the employer after user correction."""
    from app.dashboard.pages.analyze import build_confirmed_job_payload

    extracted = {
        "company": "AWS",
        "title": "Forward Deployed Engineer",
        "location": "Hong Kong",
        "url": None,
        "posting_date": None,
        "description": (
            "Example Robotics\nForward Deployed Engineer\nHong Kong\n"
            "Deploy customer solutions on AWS and build production AI systems."
        ),
        "source": "pasted_text",
    }

    payload = build_confirmed_job_payload(
        extracted,
        company="Example Robotics",
        title="Forward Deployed Engineer",
        location="Hong Kong",
        url="",
        posting_date=None,
        description=extracted["description"],
    )

    assert payload["company"] == "Example Robotics"
    assert payload["description"] == extracted["description"]
    assert payload["source"] == "pasted_text"


def test_accessible_date_text_fields_reject_invalid_iso_dates() -> None:
    """Keep text-based date controls keyboard-accessible without accepting invalid dates."""
    from app.dashboard.state import parse_optional_iso_date

    assert parse_optional_iso_date("") is None
    assert parse_optional_iso_date("2026-10-02") == date(2026, 10, 2)
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        parse_optional_iso_date("02/10/2026")


def test_copilot_confirmation_exposes_every_mandatory_field_in_both_languages() -> None:
    """Catch a confirmation card that hides a write, side effect, or private-data use."""
    from app.dashboard.components.copilot_panel import confirmation_view

    proposal = {
        "id": 8,
        "proposal_type": "change_application_status",
        "target": {"record_type": "job", "record_id": 17},
        "current_value": {"status": "New"},
        "proposed_value": {"status": "Saved"},
        "side_effects": ["Append application status history"],
        "private_data_usage": {"included": False, "record_ids": [], "purpose": None},
    }

    en = confirmation_view(proposal, "en")
    zh = confirmation_view(proposal, "zh-Hans")

    assert [field.key for field in en.fields] == [
        "target",
        "current_value",
        "proposed_value",
        "side_effects",
        "private_data_usage",
    ]
    assert [field.label for field in en.fields] == [
        "Target record",
        "Current value",
        "Proposed value",
        "Side effects",
        "Private data usage",
    ]
    assert [field.label for field in zh.fields] == [
        "目标记录",
        "当前值",
        "拟议值",
        "副作用",
        "私密数据使用情况",
    ]
    assert en.confirm_label == "Confirm action"
    assert zh.cancel_label == "取消"


def test_theme_emits_exact_tokens_focus_and_narrow_screen_guards() -> None:
    """Catch token drift, invisible keyboard focus, and 390px horizontal overflow."""
    from app.dashboard.theme import calm_intelligence_css

    css = calm_intelligence_css()

    for token in (
        "#F5F5F7",
        "#FFFFFF",
        "#1D1D1F",
        "#6E6E73",
        "#0071E3",
        "#248A3D",
        "#B35C00",
        "#D70015",
        "#D2D2D7",
    ):
        assert token in css
    assert "-apple-system" in css
    assert "font-size: 16px" in css
    assert ":focus-visible" in css
    assert "@media (max-width: 390px)" in css
    assert "overflow-x: hidden" in css
    assert "prefers-reduced-motion: reduce" in css


def test_theme_switches_persistent_copilot_to_full_screen_mobile_drawer() -> None:
    """Catch the right panel squeezing content instead of becoming a 390px drawer."""
    from app.dashboard.theme import calm_intelligence_css

    css = calm_intelligence_css()

    assert ".st-key-mobile_copilot_launcher" in css
    assert ".st-key-desktop_copilot_panel" in css
    assert "height: 100dvh" in css
    assert "width: 100vw" in css


def test_theme_keeps_primary_copy_contrasting_and_sidebar_control_legible() -> None:
    """Catch gray primary-button copy and leaked Material icon names on narrow screens."""
    from app.dashboard.theme import calm_intelligence_css

    css = calm_intelligence_css()

    assert '.stButton > button[kind="primary"] p' in css
    assert "color: #FFFFFF !important" in css
    assert '[data-testid="stSidebarCollapsedControl"] button' in css
    assert '[data-testid="stSidebarCollapseButton"] button' in css
    assert '[data-testid="stIconMaterial"]' in css
    assert 'content: "☰"' in css
    assert "background: var(--rr-surface) !important" in css
    assert "overflow-y: auto" in css


def test_page_registry_exposes_all_focused_v1_modules() -> None:
    """Catch a route silently falling back to the old monolith."""
    from app.dashboard.streamlit_app import page_renderers

    assert set(page_renderers()) == {
        "dashboard",
        "analyze",
        "jobs",
        "applications",
        "watchlist",
        "cv_library",
        "digest",
        "profile",
    }
    assert all(callable(renderer) for renderer in page_renderers().values())


def test_cancel_extraction_discards_only_unsaved_preview() -> None:
    """Catch cancel persisting a job or resetting unrelated current-page state."""
    from app.dashboard.pages.analyze import cancel_extraction

    session = {
        "ui.route": "analyze",
        "ui.locale": "zh-Hans",
        "analyze.extracted_job": {"company": "AWS"},
        "analyze.raw_text": "Example Robotics uses AWS in production.",
    }

    cancel_extraction(session)

    assert session == {"ui.route": "analyze", "ui.locale": "zh-Hans"}


@pytest.mark.parametrize(
    ("locale", "confidence", "expected"),
    [("en", 0.49, "Needs Review"), ("zh-Hans", 0.49, "需要复核"), ("en", 0.75, None)],
)
def test_low_confidence_label_never_implies_certainty(
    locale: str, confidence: float, expected: str | None
) -> None:
    """Catch low-confidence classifications rendered without a review warning."""
    from app.dashboard.components.states import low_confidence_label

    assert low_confidence_label(locale, confidence) == expected


@pytest.mark.parametrize("locale", ["en", "zh-Hans"])
def test_low_confidence_notice_uses_required_bilingual_copy(locale: str) -> None:
    """Catch duplicated or differently capitalized review warnings."""
    assert translate(locale, "analysis.needs_review_bilingual") == "Needs review / 需要复核"


def test_watchlist_edit_preserves_machine_values_and_independent_dimensions() -> None:
    """Catch localized labels leaking into storage or one dimension overwriting another."""
    from app.dashboard.pages.watchlist import build_watchlist_patch

    company = {
        "company_type": "financial_institution",
        "strategic_priority": "core_target",
        "action_window": "apply_now",
        "target_role_patterns": ["Forward Deployed Engineer"],
        "target_locations": ["Hong Kong"],
        "rationale": "Source-language rationale",
    }

    patch = build_watchlist_patch(
        company,
        company_type="financial_institution",
        strategic_priority="monitor",
        action_window="apply_now",
        target_role_patterns="Forward Deployed Engineer",
        target_locations="Hong Kong",
        rationale="Source-language rationale",
    )

    assert patch == {
        "company_type": "financial_institution",
        "strategic_priority": "monitor",
        "action_window": "apply_now",
        "target_role_patterns": ["Forward Deployed Engineer"],
        "target_locations": ["Hong Kong"],
        "rationale": "Source-language rationale",
    }
    assert company["company_type"] == "financial_institution"
    assert company["action_window"] == "apply_now"


def test_theme_forces_readable_text_when_host_prefers_dark_mode() -> None:
    """Catch white host-theme text leaking onto the approved light canvas."""
    from app.dashboard.theme import calm_intelligence_css

    css = calm_intelligence_css()

    assert "background: var(--rr-canvas) !important" in css
    assert "color: var(--rr-text) !important" in css


def test_legacy_streamlit_page_navigation_is_disabled() -> None:
    """Catch the focused page modules appearing as a duplicate legacy navigation tree."""
    import tomllib
    from pathlib import Path

    config = tomllib.loads(Path(".streamlit/config.toml").read_text(encoding="utf-8"))

    assert config["client"]["showSidebarNavigation"] is False


def test_locale_selection_reports_when_shell_must_rerender() -> None:
    """Catch mixed-language navigation and page copy during the switch rerun."""
    from app.dashboard.state import apply_locale_selection

    session = {"ui.route": "dashboard", "ui.locale": "en"}
    query = {"lang": "en"}

    changed = apply_locale_selection("en", "zh-Hans", session, query)

    assert changed is True
    assert session == {"ui.route": "dashboard", "ui.locale": "zh-Hans"}
    assert query == {"lang": "zh-Hans"}
    assert apply_locale_selection("zh-Hans", "zh-Hans", session, query) is False


def test_job_selection_updates_copilot_context_without_touching_durable_state() -> None:
    """Catch Copilot staying on stale company/page context after opening a job."""
    from app.dashboard.state import select_job_context

    session = {
        "ui.route": "jobs",
        "ui.selected_company_id": 9,
        "ui.selected_job_id": 3,
    }

    select_job_context(session, 17)

    assert session == {"ui.route": "jobs", "ui.selected_job_id": 17}


def test_route_change_clears_stale_record_context_but_same_route_keeps_it() -> None:
    from app.dashboard.state import apply_route_selection

    session = {
        "ui.route": "jobs",
        "ui.selected_job_id": 17,
        "ui.selected_company_id": 9,
    }

    apply_route_selection("jobs", "jobs", session)
    assert session["ui.selected_job_id"] == 17

    apply_route_selection("jobs", "profile", session)
    assert session == {"ui.route": "profile"}


def test_api_client_accepts_empty_no_content_response(monkeypatch) -> None:
    """Catch successful DELETE responses being reported as invalid JSON."""
    from app.dashboard.client import RoleRadarClient

    monkeypatch.setattr(
        httpx,
        "request",
        lambda *args, **kwargs: httpx.Response(
            204, request=httpx.Request("DELETE", "http://test/api/v1/copilot/sessions/1")
        ),
    )

    assert RoleRadarClient("http://test").delete("/api/v1/copilot/sessions/1") is None


def test_deleted_copilot_session_clears_only_its_transient_selection() -> None:
    """Catch a deleted conversation remaining selected or unrelated UI state being lost."""
    from app.dashboard.components.copilot_panel import clear_deleted_session_state

    session = {
        "ui.route": "jobs",
        "ui.selected_job_id": 17,
        "copilot.session_id": 4,
        "copilot.session_id.mobile-copilot": 4,
        "copilot.session_id.desktop-copilot": 7,
        "copilot.pending_proposal": {"id": 8},
    }

    clear_deleted_session_state(session, 4)

    assert session == {
        "ui.route": "jobs",
        "ui.selected_job_id": 17,
        "copilot.session_id.desktop-copilot": 7,
    }


@pytest.mark.parametrize(
    ("locale", "manage", "delete_confirm"),
    [
        ("en", "Manage conversation", "I understand this conversation will be deleted"),
        ("zh-Hans", "管理对话", "我明白此对话将被删除"),
    ],
)
def test_copilot_session_management_is_localized(
    locale: str, manage: str, delete_confirm: str
) -> None:
    """Catch destructive session controls falling back to raw or English-only copy."""
    assert translate(locale, "copilot.session.manage") == manage
    assert translate(locale, "copilot.session.delete_confirm") == delete_confirm


def test_copilot_chat_avatars_do_not_depend_on_remote_icon_fonts() -> None:
    """Catch Material icon names leaking into the local-only conversation UI."""
    from app.dashboard.components.copilot_panel import chat_avatar

    assert chat_avatar("user") == "🧑"
    assert chat_avatar("assistant") == "🤖"


def test_new_copilot_session_overrides_stale_selectbox_value() -> None:
    """Catch a newly created conversation opening the previously selected transcript."""
    from app.dashboard.components.copilot_panel import resolve_session_selection

    assert resolve_session_selection([1, 2], durable_id=2, widget_id=1, forced_id=2) == 2
    assert resolve_session_selection([1, 2], durable_id=2, widget_id=1) == 1
    assert resolve_session_selection([1, 2], durable_id=99, widget_id=98) == 1


def test_new_copilot_session_rotates_widget_identity() -> None:
    """Catch restored browser widget state overwriting a just-created conversation."""
    from app.dashboard.components.copilot_panel import select_new_session

    session = {"copilot.session_selector_epoch.mobile-copilot": 2}

    select_new_session(session, "mobile-copilot", 11)

    assert session == {
        "copilot.session_selector_epoch.mobile-copilot": 3,
        "copilot.session_id.mobile-copilot": 11,
        "copilot.force_session_id.mobile-copilot": 11,
    }
