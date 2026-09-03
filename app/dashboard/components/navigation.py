"""Bilingual information architecture for the Calm Intelligence shell."""

from __future__ import annotations

from dataclasses import dataclass

from app.i18n.service import translate
from app.schemas import Locale


@dataclass(frozen=True, slots=True)
class NavigationItem:
    route: str
    label: str
    icon: str


_NAVIGATION = (
    ("dashboard", "nav.dashboard", "⌂"),
    ("analyze", "nav.analyze_job", "＋"),
    ("jobs", "nav.jobs", "◎"),
    ("applications", "nav.applications", "✓"),
    ("watchlist", "nav.watch_list", "◇"),
    ("cv_library", "nav.cv_library", "▤"),
    ("digest", "nav.digest", "☼"),
    ("profile", "nav.profile", "○"),
)


def navigation_items(locale: Locale) -> tuple[NavigationItem, ...]:
    return tuple(
        NavigationItem(route=route, label=translate(locale, key), icon=icon)
        for route, key, icon in _NAVIGATION
    )
