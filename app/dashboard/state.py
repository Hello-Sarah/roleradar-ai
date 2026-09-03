"""Serializable UI state and invariants for the Streamlit presentation layer."""

from __future__ import annotations

from collections.abc import MutableMapping
from dataclasses import dataclass, field
from datetime import date
from typing import cast

from app.i18n.service import resolve_locale
from app.schemas import Locale

_EN_MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


@dataclass(frozen=True, slots=True)
class UIContext:
    route: str
    locale: Locale
    job_id: int | None = None
    company_id: int | None = None
    session_id: int | None = None
    cv_document_ids: tuple[int, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class PageAction:
    region: str
    key: str
    primary: bool
    active: bool = True


def format_local_date(locale: Locale, value: str) -> str:
    """Format an ISO API date for presentation without changing its stored value."""
    try:
        parsed = date.fromisoformat(value[:10])
    except (TypeError, ValueError):
        return value
    if locale == "zh-Hans":
        return f"{parsed.year}年{parsed.month}月{parsed.day}日"
    return f"{_EN_MONTHS[parsed.month - 1]} {parsed.day}, {parsed.year}"


def stable_key(region: str, component: str, record_id: int | str | None = None) -> str:
    """Return a deterministic Streamlit key scoped to a page region and record."""
    parts = (region, component) if record_id is None else (region, component, str(record_id))
    return "-".join(part.strip().replace("_", "-") for part in parts)


def validate_primary_actions(actions: list[PageAction]) -> None:
    """Enforce at most one active dominant action in each visible region."""
    regions: dict[str, int] = {}
    for action in actions:
        if action.primary and action.active:
            regions[action.region] = regions.get(action.region, 0) + 1
    conflicts = sorted(region for region, count in regions.items() if count > 1)
    if conflicts:
        raise ValueError(f"Multiple active primary actions in region(s): {', '.join(conflicts)}")


def resolve_ui_locale(
    explicit: str | None,
    persisted_query: str | None,
    browser_locale: str | None,
) -> Locale:
    """Resolve explicit/session choice, persisted URL choice, then browser preference."""
    return resolve_locale(explicit or persisted_query, browser_locale)


def persist_locale(
    locale: Locale,
    session_state: MutableMapping[str, object],
    query_params: MutableMapping[str, str],
) -> None:
    """Persist locale without clearing any route or selected-record state."""
    resolved = cast(Locale, resolve_locale(locale, None))
    session_state["ui.locale"] = resolved
    query_params["lang"] = resolved


def apply_locale_selection(
    current: Locale,
    selected: Locale,
    session_state: MutableMapping[str, object],
    query_params: MutableMapping[str, str],
) -> bool:
    """Persist a selection and report whether the complete shell needs a rerender."""
    persist_locale(selected, session_state, query_params)
    return selected != current


def select_job_context(session_state: MutableMapping[str, object], job_id: int) -> None:
    """Select one job for Copilot and clear any mutually exclusive company context."""
    session_state["ui.selected_job_id"] = job_id
    session_state.pop("ui.selected_company_id", None)
