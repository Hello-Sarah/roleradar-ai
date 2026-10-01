"""Saved Jobs page."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from app.dashboard.client import RoleRadarClient
from app.dashboard.components.job_card import analysis_signal_label, render_job_card
from app.dashboard.components.states import render_state
from app.i18n.service import translate
from app.schemas import Locale


def render_page(client: RoleRadarClient, locale: Locale) -> None:
    st.title(translate(locale, "page.jobs.title"))
    st.caption(translate(locale, "page.jobs.support"))
    jobs = client.get("/api/v1/jobs")
    status_filter = st.session_state.get("ui.jobs.status")
    minimum_score = st.session_state.get("ui.jobs.minimum_score")
    priority_only = bool(st.session_state.get("ui.jobs.priority_only"))
    gap_filter = st.session_state.get("ui.jobs.gap")
    week_filter = st.session_state.get("ui.jobs.created_week")
    if status_filter or minimum_score is not None or priority_only or gap_filter or week_filter:
        if status_filter:
            filter_value = translate(locale, f"application_status.{str(status_filter).casefold()}")
        elif priority_only:
            filter_value = translate(locale, "dashboard.high_priority")
        elif gap_filter:
            filter_value = analysis_signal_label(locale, str(gap_filter), gap=True)
        else:
            filter_value = week_filter or f"{minimum_score}+"
        st.info(
            translate(
                locale,
                "jobs.active_filter",
                filter_value=str(filter_value),
            )
        )
        if st.button(translate(locale, "jobs.clear_filter"), key="jobs-clear-filter"):
            for key in (
                "ui.jobs.status",
                "ui.jobs.minimum_score",
                "ui.jobs.priority_only",
                "ui.jobs.gap",
                "ui.jobs.created_week",
            ):
                st.session_state.pop(key, None)
            st.rerun()
        jobs = [
            job
            for job in jobs
            if (not status_filter or job["status"] == status_filter)
            and (
                minimum_score is None
                or (job.get("analysis") or {}).get("fit_score", -1) >= minimum_score
            )
            and (
                not priority_only
                or (job.get("analysis") or {}).get("recommendation")
                in {"Must Apply", "Strong Apply"}
            )
            and (not gap_filter or gap_filter in ((job.get("analysis") or {}).get("gaps") or []))
            and (
                not week_filter
                or datetime.fromisoformat(job["created_at"]).strftime("%Y-%W") == week_filter
            )
        ]
    if not jobs:
        render_state(locale, "empty", translate(locale, "page.jobs.empty"))
        return
    for job in jobs:
        render_job_card(job, region="jobs-library", locale=locale, client=client)
