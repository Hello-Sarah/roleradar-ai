"""Serializable UI state and invariants for the Streamlit presentation layer."""

from __future__ import annotations

from collections.abc import MutableMapping
from dataclasses import dataclass, field
from datetime import date
from typing import cast

from app.i18n.service import resolve_locale
from app.schemas import Locale


def parse_optional_iso_date(value: str) -> date | None:
    """Parse an optional accessible date text field using the documented ISO format."""
    normalized = value.strip()
    if not normalized:
        return None
    try:
        return date.fromisoformat(normalized)
    except ValueError as error:
        raise ValueError("Date must use YYYY-MM-DD format") from error


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
    persisted_browser: str | None = None,
) -> Locale:
    """Resolve explicit/session, URL, durable browser choice, then browser preference."""
    return resolve_locale(explicit or persisted_query or persisted_browser, browser_locale)


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


def apply_route_selection(
    previous_route: str,
    selected_route: str,
    session_state: MutableMapping[str, object],
) -> None:
    """Update page context and discard record context when the visible page changes."""
    session_state["ui.route"] = selected_route
    if selected_route == previous_route:
        return
    session_state.pop("ui.selected_job_id", None)
    session_state.pop("ui.selected_company_id", None)
    session_state.pop("ui.selected_action_item_id", None)


def queue_route_selection(session_state: MutableMapping[str, object], selected_route: str) -> None:
    """Queue navigation so the keyed widget is updated before its next render."""
    apply_route_selection(
        str(session_state.get("ui.route", "dashboard")), selected_route, session_state
    )
    session_state["ui.pending_route"] = selected_route


def apply_job_filter(
    session_state: MutableMapping[str, object],
    *,
    status: str | None = None,
    minimum_score: int | None = None,
    priority_only: bool = False,
    gap: str | None = None,
    created_week: str | None = None,
) -> None:
    """Navigate a Dashboard metric to the matching saved-job records."""
    queue_route_selection(session_state, "jobs")
    if status is None:
        session_state.pop("ui.jobs.status", None)
    else:
        session_state["ui.jobs.status"] = status
    if minimum_score is None:
        session_state.pop("ui.jobs.minimum_score", None)
    else:
        session_state["ui.jobs.minimum_score"] = minimum_score
    if priority_only:
        session_state["ui.jobs.priority_only"] = True
    else:
        session_state.pop("ui.jobs.priority_only", None)
    if gap is None:
        session_state.pop("ui.jobs.gap", None)
    else:
        session_state["ui.jobs.gap"] = gap
    if created_week is None:
        session_state.pop("ui.jobs.created_week", None)
    else:
        session_state["ui.jobs.created_week"] = created_week
    session_state.pop("ui.selected_job_id", None)
    session_state.pop("ui.selected_company_id", None)
