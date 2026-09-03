"""Watch List maintenance page; V1 makes no scheduled-monitoring claim."""

from __future__ import annotations

import streamlit as st

from app.dashboard.client import RoleRadarClient
from app.dashboard.components.states import render_state
from app.dashboard.state import stable_key
from app.i18n.service import translate
from app.schemas import Locale
from app.watchlist.models import (
    ActionWindow,
    CompanyType,
    SourceKind,
    SourceState,
    StrategicPriority,
)


def _label(locale: Locale, prefix: str, value: str) -> str:
    return translate(locale, f"{prefix}.{value}")


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def build_watchlist_patch(
    company: dict[str, object],
    *,
    company_type: str,
    strategic_priority: str,
    action_window: str,
    target_role_patterns: str,
    target_locations: str,
    rationale: str,
) -> dict[str, object]:
    """Return stable machine values and source-language user content for PATCH."""
    del company
    return {
        "company_type": company_type,
        "strategic_priority": strategic_priority,
        "action_window": action_window,
        "target_role_patterns": _csv(target_role_patterns),
        "target_locations": _csv(target_locations),
        "rationale": rationale,
    }


def _company_payload(locale: Locale) -> dict[str, object] | None:
    with st.form("watchlist-add-form"):
        name = st.text_input(translate(locale, "watch_list.name"))
        domain = st.text_input(translate(locale, "watch_list.domain"))
        company_types = [item.value for item in CompanyType]
        company_type = st.selectbox(
            translate(locale, "watch_list.company_type"),
            company_types,
            format_func=lambda value: _label(locale, "watch_list.company_type", value),
        )
        priorities = [item.value for item in StrategicPriority]
        priority = st.selectbox(
            translate(locale, "watch_list.strategic_priority"),
            priorities,
            format_func=lambda value: _label(locale, "watch_list.priority", value),
        )
        windows = [item.value for item in ActionWindow]
        window = st.selectbox(
            translate(locale, "score.action_window"),
            windows,
            format_func=lambda value: _label(locale, "watch_list.action_window", value),
        )
        role_patterns = st.text_input(translate(locale, "watch_list.target_roles"))
        locations = st.text_input(translate(locale, "watch_list.target_locations"))
        source_url = st.text_input(translate(locale, "watch_list.source_url"))
        rationale = st.text_area(translate(locale, "watch_list.rationale"))
        add = st.form_submit_button(translate(locale, "watch_list.create_company"), type="primary")
    if not add:
        return None
    return {
        "name": name,
        "canonical_domain": domain,
        "company_type": company_type,
        "strategic_priority": priority,
        "action_window": window,
        "target_role_patterns": _csv(role_patterns),
        "target_locations": _csv(locations),
        "positive_keywords": [],
        "exclusion_keywords": [],
        "location_notes": "",
        "work_authorization_notes": "",
        "official_source_url": source_url,
        "source_kind": SourceKind.CAREER_PAGE.value,
        "source_state": SourceState.UNVERIFIED.value,
        "source_state_reason": "Manual V1 source awaiting verification",
        "rationale": rationale,
    }


def render_page(client: RoleRadarClient, locale: Locale) -> None:
    st.title(translate(locale, "page.watchlist.title"))
    st.caption(translate(locale, "page.watchlist.support"))
    with st.expander(translate(locale, "watch_list.create_company")):
        payload = _company_payload(locale)
        if payload is not None:
            client.post("/api/v1/watchlist/companies", payload)
            st.rerun()
    companies = client.get("/api/v1/watchlist/companies")
    if not companies:
        render_state(locale, "empty", translate(locale, "page.watchlist.empty"))
        return
    for company in companies:
        with st.container(border=True):
            state_key = f"watch_list.source_state.{company['source_state']}"
            st.subheader(company["name"])
            st.caption(
                f"{_label(locale, 'watch_list.company_type', company['company_type'])} · "
                f"{_label(locale, 'watch_list.priority', company['strategic_priority'])} · "
                f"{_label(locale, 'watch_list.action_window', company['action_window'])}"
            )
            st.write(company["rationale"])
            source_label = translate(locale, "watch_list.source_status")
            st.caption(f"{source_label}: {translate(locale, state_key)}")
            with st.expander(translate(locale, "watch_list.edit_company")):
                company_types = [item.value for item in CompanyType]
                priorities = [item.value for item in StrategicPriority]
                windows = [item.value for item in ActionWindow]
                with st.form(stable_key("watchlist", "edit-form", company["id"])):
                    company_type = st.selectbox(
                        translate(locale, "watch_list.company_type"),
                        company_types,
                        index=company_types.index(company["company_type"]),
                        format_func=lambda value: _label(locale, "watch_list.company_type", value),
                    )
                    priority = st.selectbox(
                        translate(locale, "watch_list.strategic_priority"),
                        priorities,
                        index=priorities.index(company["strategic_priority"]),
                        format_func=lambda value: _label(locale, "watch_list.priority", value),
                    )
                    window = st.selectbox(
                        translate(locale, "score.action_window"),
                        windows,
                        index=windows.index(company["action_window"]),
                        format_func=lambda value: _label(locale, "watch_list.action_window", value),
                    )
                    roles = st.text_input(
                        translate(locale, "watch_list.target_roles"),
                        ", ".join(company["target_role_patterns"]),
                    )
                    locations = st.text_input(
                        translate(locale, "watch_list.target_locations"),
                        ", ".join(company["target_locations"]),
                    )
                    rationale = st.text_area(
                        translate(locale, "watch_list.rationale"), company["rationale"]
                    )
                    save_edit = st.form_submit_button(
                        translate(locale, "action.save"), type="primary"
                    )
                if save_edit:
                    client.patch(
                        f"/api/v1/watchlist/companies/{company['id']}",
                        build_watchlist_patch(
                            company,
                            company_type=company_type,
                            strategic_priority=priority,
                            action_window=window,
                            target_role_patterns=roles,
                            target_locations=locations,
                            rationale=rationale,
                        ),
                    )
                    st.rerun()
            lifecycle, deletion = st.columns(2)
            with lifecycle:
                endpoint = "disable" if company["enabled"] else "enable"
                action_key = "action.disable" if company["enabled"] else "action.enable"
                if st.button(
                    translate(locale, action_key),
                    key=stable_key("watchlist", endpoint, company["id"]),
                    use_container_width=True,
                ):
                    client.post(f"/api/v1/watchlist/companies/{company['id']}/{endpoint}", {})
                    st.rerun()
            with deletion:
                confirm_key = stable_key("watchlist", "delete-confirm", company["id"])
                confirmed = st.checkbox(
                    translate(locale, "watch_list.confirm_delete"), key=confirm_key
                )
                delete_clicked = st.button(
                    translate(locale, "action.delete"),
                    key=stable_key("watchlist", "delete", company["id"]),
                    use_container_width=True,
                    disabled=not confirmed,
                )
                if confirmed and delete_clicked:
                    client.delete(
                        f"/api/v1/watchlist/companies/{company['id']}?confirm=true&locale={locale}"
                    )
                    st.rerun()
