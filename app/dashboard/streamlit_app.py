"""RoleRadar bilingual Calm Intelligence Streamlit entrypoint."""

from __future__ import annotations

import os
from collections.abc import Callable

import streamlit as st

from app.dashboard.client import APIClientError, RoleRadarClient
from app.dashboard.components.copilot_panel import render_copilot_panel
from app.dashboard.components.navigation import navigation_items
from app.dashboard.components.states import render_state
from app.dashboard.pages import (
    analyze,
    applications,
    cv_library,
    dashboard,
    digest,
    jobs,
    profile,
    watchlist,
)
from app.dashboard.state import (
    UIContext,
    apply_locale_selection,
    apply_route_selection,
    resolve_ui_locale,
)
from app.dashboard.theme import apply_theme
from app.i18n.service import translate
from app.schemas import Locale

PageRenderer = Callable[[RoleRadarClient, Locale], None]
_LOCALE_COOKIE = "roleradar_locale"


def page_renderers() -> dict[str, PageRenderer]:
    return {
        "dashboard": dashboard.render_page,
        "analyze": analyze.render_page,
        "jobs": jobs.render_page,
        "applications": applications.render_page,
        "watchlist": watchlist.render_page,
        "cv_library": cv_library.render_page,
        "digest": digest.render_page,
        "profile": profile.render_page,
    }


def _browser_locale() -> str | None:
    try:
        return st.context.locale
    except (AttributeError, RuntimeError):
        return None


def _stored_browser_locale() -> str | None:
    try:
        return st.context.cookies.get(_LOCALE_COOKIE)
    except (AttributeError, RuntimeError):
        return None


def _persist_browser_locale(locale: Locale) -> None:
    st.html(
        "<script>document.cookie="
        f"'{_LOCALE_COOKIE}={locale}; Path=/; Max-Age=31536000; SameSite=Lax'"
        "</script>",
        unsafe_allow_javascript=True,
    )


def _render_shell_navigation(locale: Locale) -> str:
    items = navigation_items(locale)
    routes = [item.route for item in items]
    current = str(st.session_state.get("ui.route", "dashboard"))
    if current not in routes:
        current = "dashboard"
    with st.sidebar:
        st.markdown("## RoleRadar AI")
        st.caption(translate(locale, "app.tagline"))
        route = st.radio(
            translate(locale, "accessibility.open_navigation"),
            routes,
            index=routes.index(current),
            format_func=lambda value: next(item.label for item in items if item.route == value),
            label_visibility="collapsed",
            key="ui-navigation",
        )
        apply_route_selection(current, route, st.session_state)
    return route


def _render_top_utilities(locale: Locale, client: RoleRadarClient) -> Locale:
    private, language, health_column, settings = st.columns([4, 1.4, 1, 0.8])
    with language:
        selected_language = st.segmented_control(
            translate(locale, "common.language"),
            ["中文", "EN"],
            default="中文" if locale == "zh-Hans" else "EN",
            key="ui-language-control",
            label_visibility="collapsed",
        )
        selected_locale: Locale = "zh-Hans" if selected_language == "中文" else "en"
        if apply_locale_selection(locale, selected_locale, st.session_state, st.query_params):
            _persist_browser_locale(selected_locale)
    with private:
        st.caption(translate(selected_locale, "app.private_local"))
    with health_column:
        try:
            health = client.get("/api/v1/health")
            key = "app.health.ready" if health.get("status") == "ok" else "app.health.degraded"
            st.caption("● " + translate(selected_locale, key))
        except APIClientError:
            st.caption("○ " + translate(selected_locale, "app.health.unavailable"))
    with settings:
        if st.button(
            translate(selected_locale, "common.settings"),
            key="top-settings",
            use_container_width=True,
        ):
            apply_route_selection(
                str(st.session_state.get("ui.route", "dashboard")), "profile", st.session_state
            )
            st.session_state["ui-navigation"] = "profile"
            st.rerun()
    return selected_locale


def render_app(client: RoleRadarClient) -> None:
    apply_theme()
    query_locale = st.query_params.get("lang")
    explicit = st.session_state.get("ui.locale")
    locale = resolve_ui_locale(
        str(explicit) if explicit else None,
        str(query_locale) if query_locale else None,
        _browser_locale(),
        _stored_browser_locale(),
    )
    locale = _render_top_utilities(locale, client)
    route = _render_shell_navigation(locale)

    context = UIContext(
        route=route,
        locale=locale,
        job_id=(st.session_state.get("ui.selected_job_id") or None),
        company_id=(st.session_state.get("ui.selected_company_id") or None),
        session_id=(st.session_state.get("copilot.session_id") or None),
        cv_document_ids=tuple(st.session_state.get("ui.selected_cv_ids", ())),
    )

    @st.dialog(translate(locale, "copilot.name"), width="large")
    def render_mobile_copilot() -> None:
        render_copilot_panel(context, client, key_prefix="mobile-copilot")

    with st.container(key="mobile_copilot_launcher"):
        if st.button(
            translate(locale, "accessibility.open_copilot"),
            key="mobile-copilot-open",
            type="primary",
            use_container_width=True,
        ):
            render_mobile_copilot()

    content, copilot = st.columns([3.25, 1], gap="large")
    with content:
        try:
            page_renderers()[route](client, locale)
        except APIClientError:
            render_state(
                locale,
                "error",
                translate(locale, "error.unavailable"),
                retry_key=f"page-retry-{route}",
            )
    with copilot, st.container(border=True, key="desktop_copilot_panel"):
        render_copilot_panel(context, client, key_prefix="desktop-copilot")


def main() -> None:
    st.set_page_config(page_title="RoleRadar AI", page_icon="◉", layout="wide")
    render_app(RoleRadarClient(os.getenv("API_BASE_URL", "http://localhost:8000")))


if __name__ == "__main__":
    main()
