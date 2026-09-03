"""View models and rendering for confirmed-action Career Copilot."""

from __future__ import annotations

from collections.abc import MutableMapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from uuid import uuid4

import streamlit as st

from app.dashboard.client import APIClientError, RoleRadarClient
from app.dashboard.state import UIContext, stable_key
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
                type="primary",
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


def confirmation_view(proposal: dict[str, Any], locale: Locale) -> ConfirmationView:
    return ConfirmationView(
        fields=tuple(
            ConfirmationField(key, translate(locale, label_key), proposal.get(key))
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


def render_copilot_panel(
    context: UIContext,
    client: RoleRadarClient,
    *,
    key_prefix: str = "copilot",
) -> None:
    locale = context.locale
    st.markdown("<div class='rr-copilot'></div>", unsafe_allow_html=True)
    st.subheader(translate(locale, "copilot.name"))
    st.caption(translate(locale, "copilot.support"))
    try:
        selected_context = client.get(_context_path(context))
    except APIClientError as exc:
        st.error(f"{translate(locale, 'copilot.error.model_unavailable')}\n\n{exc}")
        return
    route_context = selected_context.get("job") or selected_context.get("company")
    if route_context:
        label = route_context.get("title") or route_context.get("name")
        st.info(f"{translate(locale, 'copilot.context')}: {label}")
    else:
        st.caption(f"{translate(locale, 'copilot.context')}: {context.route}")

    sessions = client.get("/api/v1/copilot/sessions")
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

    proposal = st.session_state.get("copilot.pending_proposal")
    if not proposal:
        return
    st.warning(translate(locale, "copilot.pending_confirmation"))
    view = confirmation_view(proposal, locale)
    for field in view.fields:
        st.markdown(f"**{field.label}**")
        st.json(field.value, expanded=True)
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
            client.post(
                f"/api/v1/copilot/proposals/{proposal['id']}/confirm",
                {"idempotency_key": idempotency_key},
            )
            st.session_state.pop("copilot.pending_proposal", None)
            st.success(translate(locale, "component.success"))
            st.rerun()
    with cancel_col:
        if st.button(
            view.cancel_label,
            key=stable_key(key_prefix, "cancel", proposal["id"]),
            use_container_width=True,
        ):
            st.session_state.pop("copilot.pending_proposal", None)
            st.rerun()
