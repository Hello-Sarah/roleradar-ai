"""Localized loading, empty, error, and success presentation states."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.i18n.service import translate
from app.schemas import Locale

StateKind = Literal["loading", "empty", "error", "success"]


@dataclass(frozen=True, slots=True)
class StateCopy:
    title: str
    description: str
    action_label: str | None = None


def state_copy(locale: Locale, kind: StateKind) -> StateCopy:
    if kind == "loading":
        loading = translate(locale, "component.loading")
        return StateCopy(loading, loading)
    if kind == "success":
        success = translate(locale, "component.success")
        return StateCopy(success, success)
    if kind == "empty":
        return StateCopy(
            translate(locale, "component.empty.title"),
            translate(locale, "component.empty.description"),
        )
    return StateCopy(
        translate(locale, "component.error.title"),
        translate(locale, "component.error.description"),
        translate(locale, "action.retry"),
    )


def low_confidence_label(locale: Locale, confidence: float) -> str | None:
    return translate(locale, "analysis.needs_review") if confidence < 0.5 else None


def render_state(
    locale: Locale,
    kind: StateKind,
    description: str | None = None,
    *,
    retry_key: str | None = None,
) -> None:
    """Render a local state without blocking unrelated page regions."""
    import streamlit as st

    copy = state_copy(locale, kind)
    body = description or copy.description
    if kind == "error":
        st.error(f"**{copy.title}**\n\n{body}")
        if st.button(copy.action_label, key=retry_key or "state-retry"):
            st.rerun()
    elif kind == "success":
        st.success(body)
    elif kind == "loading":
        st.info(body)
    else:
        st.info(f"**{copy.title}**\n\n{body}")
