"""View models and rendering for confirmed-action Career Copilot."""

from __future__ import annotations

from collections.abc import MutableMapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from uuid import uuid4

import streamlit as st

from app.dashboard.client import APIClientError, RoleRadarClient
from app.dashboard.components.states import render_state
from app.dashboard.state import PageAction, UIContext, stable_key, validate_primary_actions
from app.i18n.service import translate
from app.schemas import Locale


@dataclass(frozen=True, slots=True)
class ConfirmationField:
    key: str
    label: str
    value: object


@dataclass(frozen=True, slots=True)
class ConfirmationView:
    fields: tuple[ConfirmationField, ...]
    confirm_label: str
    cancel_label: str


_CONFIRMATION_FIELDS = (
    ("target", "copilot.confirmation.target"),
    ("current_value", "copilot.confirmation.current_value"),
    ("proposed_value", "copilot.confirmation.proposed_value"),
    ("side_effects", "copilot.confirmation.side_effects"),
    ("private_data_usage", "copilot.confirmation.private_data"),
)

_CONFIRMATION_FIELD_KEYS = {
    "status": "copilot.field.status",
    "occurred_at": "copilot.field.occurred_at",
    "channel": "copilot.field.channel",
    "notes": "copilot.field.notes",
    "next_follow_up_date": "copilot.field.next_follow_up_date",
    "analysis_id": "copilot.field.analysis_id",
    "generated_cv": "copilot.field.generated_cv",
    "source_cv_ids": "copilot.field.source_cv_ids",
    "item_kind": "copilot.field.item_kind",
    "title": "copilot.field.title",
    "details": "copilot.field.details",
    "due_date": "copilot.field.due_date",
    "company_type": "copilot.field.company_type",
    "strategic_priority": "copilot.field.strategic_priority",
    "action_window": "copilot.field.action_window",
    "name": "copilot.field.name",
    "canonical_domain": "copilot.field.canonical_domain",
}
_SIDE_EFFECT_KEYS = {
    "Update the job status": "copilot.effect.update_job_status",
    "Append one application timeline event": "copilot.effect.append_application_event",
    (
        "Append one follow-up timeline event without changing the current status"
    ): "copilot.effect.append_follow_up",
    "Create one Watch List company": "copilot.effect.create_watchlist_company",
    "Update the selected Watch List company": "copilot.effect.update_watchlist_company",
    "Run explicit analysis": "copilot.effect.run_analysis",
    "Append a new immutable analysis version": "copilot.effect.append_analysis",
    "Use model-backed exact-evidence generation": "copilot.effect.use_model_evidence",
    "Create one new DOCX artifact": "copilot.effect.create_docx",
    "Create one local career action item": "copilot.effect.create_action_item",
}
_STATUS_KEYS = {
    "New": "application_status.new",
    "Saved": "application_status.saved",
    "Applied": "application_status.applied",
    "Interview": "application_status.interview",
    "Offer": "application_status.offer",
    "Rejected": "application_status.rejected",
    "Ignored": "application_status.ignored",
}
_ENUM_VALUE_KEYS = {
    **_STATUS_KEYS,
    "Company website": "application_channel.company_website",
    "LinkedIn": "application_channel.linkedin",
    "Referral": "application_channel.referral",
    "Recruiter": "application_channel.recruiter",
    "Email": "application_channel.email",
    "Other": "application_channel.other",
    "ai_native_forward_deployed": "watch_list.company_type.ai_native_forward_deployed",
    "fintech_product": "watch_list.company_type.fintech_product",
    "cloud_data_enterprise_ai": "watch_list.company_type.cloud_data_enterprise_ai",
    "financial_institution": "watch_list.company_type.financial_institution",
    "consulting_professional_services": (
        "watch_list.company_type.consulting_professional_services"
    ),
    "core_target": "watch_list.priority.core_target",
    "monitor": "watch_list.priority.monitor",
    "opportunistic": "watch_list.priority.opportunistic",
    "strict_filter": "watch_list.priority.strict_filter",
    "apply_now": "watch_list.action_window.apply_now",
    "stretch_apply": "watch_list.action_window.stretch_apply",
    "apply_in_3_to_6_months": "watch_list.action_window.apply_in_3_to_6_months",
    "apply_after_us_relocation": "watch_list.action_window.apply_after_us_relocation",
    "relationship_only": "watch_list.action_window.relationship_only",
    "learning": "copilot.value.learning",
    "next_action": "copilot.value.next_action",
    "new_immutable_analysis": "copilot.value.new_immutable_analysis",
}
_PRIVATE_PURPOSE_KEYS = {
    "Generate a tailored CV from selected private CV evidence": (
        "copilot.private.purpose.tailored_cv"
    ),
    "Answer using explicitly attached CV evidence": "copilot.private.purpose.answer_with_cv",
}


def clear_deleted_session_state(
    session_state: MutableMapping[str, Any], deleted_session_id: int
) -> None:
    selection_keys = [
        key
        for key, value in session_state.items()
        if key.startswith("copilot.session_id") and value == deleted_session_id
    ]
    if not selection_keys:
        return
    for key in selection_keys:
        session_state.pop(key, None)
    session_state.pop("copilot.pending_proposal", None)


def chat_avatar(role: str) -> str:
    return "🤖" if role == "assistant" else "🧑"


def resolve_session_selection(
    session_ids: Sequence[int],
    *,
    durable_id: int | None,
    widget_id: int | None,
    forced_id: int | None = None,
) -> int | None:
    for candidate in (forced_id, widget_id, durable_id):
        if candidate in session_ids:
            return candidate
    return session_ids[0] if session_ids else None


def _rotate_session_selector(session_state: MutableMapping[str, Any], key_prefix: str) -> None:
    epoch_key = f"copilot.session_selector_epoch.{key_prefix}"
    session_state[epoch_key] = int(session_state.get(epoch_key, 0)) + 1


def select_new_session(
    session_state: MutableMapping[str, Any], key_prefix: str, session_id: int
) -> None:
    _rotate_session_selector(session_state, key_prefix)
    session_state[f"copilot.session_id.{key_prefix}"] = session_id
    session_state[f"copilot.force_session_id.{key_prefix}"] = session_id


def _render_session_management(
    *,
    session_id: int,
    current_title: str,
    locale: Locale,
    client: RoleRadarClient,
    key_prefix: str,
    primary_allowed: bool,
) -> None:
    manage_session = st.checkbox(
        translate(locale, "copilot.session.manage"),
        key=f"{key_prefix}-manage-session-{session_id}",
    )
    if manage_session:
        with st.form(f"{key_prefix}-rename-session-{session_id}"):
            title = st.text_input(
                translate(locale, "copilot.session.title"),
                value=current_title,
                key=f"{key_prefix}-session-title-{session_id}",
            )
            if st.form_submit_button(
                translate(locale, "copilot.session.rename"),
                type="primary" if primary_allowed else "secondary",
                use_container_width=True,
            ):
                client.patch(f"/api/v1/copilot/sessions/{session_id}", {"title": title})
                st.rerun()
        delete_confirmed = st.checkbox(
            translate(locale, "copilot.session.delete_confirm"),
            key=f"{key_prefix}-delete-session-confirm-{session_id}",
        )
        if st.button(
            translate(locale, "copilot.session.delete"),
            key=f"{key_prefix}-delete-session-{session_id}",
            disabled=not delete_confirmed,
            use_container_width=True,
        ):
            client.delete(f"/api/v1/copilot/sessions/{session_id}")
            clear_deleted_session_state(st.session_state, session_id)
            _rotate_session_selector(st.session_state, key_prefix)
            st.rerun()


def _localized_value(locale: Locale, value: object) -> object:
    if isinstance(value, str) and value in _ENUM_VALUE_KEYS:
        return translate(locale, _ENUM_VALUE_KEYS[value])
    if isinstance(value, dict):
        return "\n".join(
            f"{translate(locale, _CONFIRMATION_FIELD_KEYS.get(key, 'copilot.field.other'))}："
            f"{_localized_value(locale, item)}"
            for key, item in value.items()
        ) or translate(locale, "common.none")
    if isinstance(value, list):
        return "\n".join(f"• {_localized_value(locale, item)}" for item in value) or translate(
            locale, "common.none"
        )
    if value is None:
        return translate(locale, "common.none")
    return value


def _localized_confirmation_field(proposal: dict[str, Any], key: str, locale: Locale) -> object:
    value = proposal.get(key)
    if key == "target" and isinstance(value, dict):
        record_type = str(value.get("record_type", "record"))
        label_key = f"copilot.record.{record_type}"
        return f"{translate(locale, label_key)} #{value.get('record_id')}"
    if key == "side_effects" and isinstance(value, list):
        return "\n".join(
            f"• {translate(locale, _SIDE_EFFECT_KEYS[item])}"
            if item in _SIDE_EFFECT_KEYS
            else f"• {translate(locale, 'copilot.effect.other')}"
            for item in value
        )
    if key == "private_data_usage" and isinstance(value, dict):
        included = translate(
            locale,
            "copilot.private.included" if value.get("included") else "copilot.private.not_included",
        )
        ids = value.get("record_ids") or []
        suffix = (
            f" · {translate(locale, 'copilot.private.records')}: {', '.join(map(str, ids))}"
            if ids
            else ""
        )
        purpose = value.get("purpose")
        purpose_suffix = ""
        if purpose:
            purpose_key = _PRIVATE_PURPOSE_KEYS.get(str(purpose), "copilot.private.purpose.other")
            purpose_suffix = " · " + translate(locale, purpose_key)
        return included + suffix + purpose_suffix
    return _localized_value(locale, value)


def confirmation_view(proposal: dict[str, Any], locale: Locale) -> ConfirmationView:
    return ConfirmationView(
        fields=tuple(
            ConfirmationField(
                key,
                translate(locale, label_key),
                _localized_confirmation_field(proposal, key, locale),
            )
            for key, label_key in _CONFIRMATION_FIELDS
        ),
        confirm_label=translate(locale, "copilot.confirmation.confirm"),
        cancel_label=translate(locale, "copilot.confirmation.cancel"),
    )


def _context_path(context: UIContext) -> str:
    query: dict[str, str | int | list[int]] = {"route": context.route}
    for name, value in (
        ("job_id", context.job_id),
        ("company_id", context.company_id),
        ("session_id", context.session_id),
    ):
        if value is not None:
            query[name] = value
    if context.cv_document_ids:
        query["cv_document_ids"] = list(context.cv_document_ids)
    return f"/api/v1/copilot/context?{urlencode(query, doseq=True)}"


def _render_last_result(locale: Locale, key_prefix: str) -> None:
    result = st.session_state.get("copilot.last_result")
    if not isinstance(result, dict):
        return
    st.success(translate(locale, "component.success"))
    result_ids = result.get("result_record_ids") or {}
    route = "jobs"
    job_ids = result_ids.get("job") or []
    if result_ids.get("watchlist_company"):
        route = "watchlist"
    elif result_ids.get("generated_cv"):
        route = "cv_library"
    if st.button(
        translate(locale, "copilot.view_result"),
        key=f"{key_prefix}-view-result",
        use_container_width=True,
    ):
        st.session_state["ui.route"] = route
        st.session_state["ui-navigation"] = route
        if job_ids:
            st.session_state["ui.selected_job_id"] = job_ids[0]
        st.rerun()


def _render_copilot_panel(
    context: UIContext,
    client: RoleRadarClient,
    *,
    key_prefix: str = "copilot",
) -> None:
    locale = context.locale
    st.markdown("<div class='rr-copilot'></div>", unsafe_allow_html=True)
    st.subheader(translate(locale, "copilot.name"))
    st.caption(translate(locale, "copilot.support"))
    with st.spinner(translate(locale, "component.loading")):
        selected_context = client.get(_context_path(context))
    route_context = selected_context.get("job") or selected_context.get("company")
    if route_context:
        label = route_context.get("title") or route_context.get("name")
        st.info(f"{translate(locale, 'copilot.context')}: {label}")
    else:
        st.caption(f"{translate(locale, 'copilot.context')}: {context.route}")

    sessions = client.get("/api/v1/copilot/sessions")
    proposal = st.session_state.get("copilot.pending_proposal")
    validate_primary_actions(
        [
            PageAction("copilot", "confirm", primary=bool(proposal), active=bool(proposal)),
            PageAction("copilot", "rename", primary=not bool(proposal)),
        ]
    )
    selection_key = f"copilot.session_id.{key_prefix}"
    session_id = st.session_state.get(selection_key)
    if sessions:
        labels = {session["id"]: session["title"] for session in sessions}
        ids = list(labels)
        selector_epoch = st.session_state.get(f"copilot.session_selector_epoch.{key_prefix}", 0)
        widget_key = f"{key_prefix}-session-select-{selector_epoch}"
        forced_key = f"copilot.force_session_id.{key_prefix}"
        forced_id = st.session_state.pop(forced_key, None)
        widget_id = st.session_state.get(widget_key)
        session_id = resolve_session_selection(
            ids,
            durable_id=session_id,
            widget_id=widget_id,
            forced_id=forced_id,
        )
        session_id = st.selectbox(
            translate(locale, "copilot.session.title"),
            ids,
            index=ids.index(session_id),
            format_func=lambda value: labels[value],
            key=widget_key,
        )
        st.session_state[selection_key] = session_id
        _render_session_management(
            session_id=session_id,
            current_title=labels[session_id],
            locale=locale,
            client=client,
            key_prefix=key_prefix,
            primary_allowed=not bool(proposal),
        )
    if st.button(
        translate(locale, "copilot.session.create"),
        key=f"{key_prefix}-new-session",
        use_container_width=True,
    ):
        created = client.post(
            "/api/v1/copilot/sessions",
            {"title": translate(locale, "copilot.session.create"), "locale": locale},
        )
        select_new_session(st.session_state, key_prefix, created["id"])
        st.rerun()
    if session_id is None:
        st.info(translate(locale, "copilot.empty"))
        return

    messages = client.get(f"/api/v1/copilot/sessions/{session_id}/messages")
    for message in messages:
        with st.chat_message(message["role"], avatar=chat_avatar(message["role"])):
            st.write(message.get("body") or "—")
            for source in message.get("sources") or []:
                st.caption(str(source))
    prompt = st.chat_input(translate(locale, "copilot.prompt"), key=f"{key_prefix}-chat-input")
    if prompt:
        client.post(
            f"/api/v1/copilot/sessions/{session_id}/messages",
            {"role": "user", "body": prompt, "sources": []},
        )
        proposal = client.post(
            "/api/v1/copilot/propose",
            {
                "session_id": session_id,
                "message": prompt,
                "route": context.route,
                "job_id": context.job_id,
                "company_id": context.company_id,
                "cv_document_ids": list(context.cv_document_ids),
            },
        )
        st.session_state["copilot.pending_proposal"] = proposal
        st.rerun()

    if not proposal:
        _render_last_result(locale, key_prefix)
        return
    st.warning(translate(locale, "copilot.pending_confirmation"))
    view = confirmation_view(proposal, locale)
    for field in view.fields:
        st.markdown(f"**{field.label}**")
        st.write(field.value)
    confirm_col, cancel_col = st.columns(2)
    with confirm_col:
        if st.button(
            view.confirm_label,
            type="primary",
            key=stable_key(key_prefix, "confirm", proposal["id"]),
            use_container_width=True,
        ):
            idempotency_key = st.session_state.setdefault(
                f"copilot.idempotency.{proposal['id']}", str(uuid4())
            )
            result = client.post(
                f"/api/v1/copilot/proposals/{proposal['id']}/confirm",
                {"idempotency_key": idempotency_key},
            )
            st.session_state["copilot.last_result"] = result
            st.session_state.pop("copilot.pending_proposal", None)
            st.rerun()
    with cancel_col:
        if st.button(
            view.cancel_label,
            key=stable_key(key_prefix, "cancel", proposal["id"]),
            use_container_width=True,
        ):
            st.session_state.pop("copilot.pending_proposal", None)
            st.rerun()


def render_copilot_panel(
    context: UIContext,
    client: RoleRadarClient,
    *,
    key_prefix: str = "copilot",
) -> None:
    """Keep Copilot failures local and offer a localized recovery action."""
    try:
        _render_copilot_panel(context, client, key_prefix=key_prefix)
    except APIClientError:
        render_state(
            context.locale,
            "error",
            translate(context.locale, "copilot.error.model_unavailable"),
            retry_key=f"{key_prefix}-retry",
        )
