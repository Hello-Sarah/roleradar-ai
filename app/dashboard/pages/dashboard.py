"""Decision-first Dashboard page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.dashboard.client import RoleRadarClient
from app.dashboard.components.job_card import render_job_card
from app.dashboard.components.states import render_state
from app.i18n.service import translate
from app.schemas import Locale


def render_page(client: RoleRadarClient, locale: Locale) -> None:
    st.title(translate(locale, "page.dashboard.title"))
    st.caption(translate(locale, "page.dashboard.support"))
    data = client.get("/api/v1/dashboard")
    counts = data["status_counts"]
    metrics = st.columns(4)
    metrics[0].metric(translate(locale, "dashboard.high_priority"), len(data["high_priority_jobs"]))
    metrics[1].metric(translate(locale, "dashboard.new"), counts.get("New", 0))
    metrics[2].metric(translate(locale, "application_status.applied"), counts.get("Applied", 0))
    metrics[3].metric(translate(locale, "dashboard.interviews"), counts.get("Interview", 0))
    st.subheader(translate(locale, "dashboard.next_action"))
    if data["high_priority_jobs"]:
        render_job_card(
            data["high_priority_jobs"][0], region="dashboard-next", locale=locale, client=client
        )
    else:
        render_state(locale, "empty", translate(locale, "dashboard.empty"))
    st.subheader(translate(locale, "dashboard.high_priority_jobs"))
    for job in data["high_priority_jobs"][1:]:
        render_job_card(job, region="dashboard-priority", locale=locale, client=client)
    charts = st.columns(2)
    with charts[0]:
        st.subheader(translate(locale, "dashboard.skill_gap_trends"))
        if data["skill_gap_trends"]:
            frame = pd.DataFrame(data["skill_gap_trends"], columns=["Skill", "Jobs"])
            st.bar_chart(frame.set_index("Skill"))
        else:
            render_state(locale, "empty")
    with charts[1]:
        st.subheader(translate(locale, "dashboard.hiring_trends"))
        if data["weekly_hiring_trends"]:
            frame = pd.DataFrame(data["weekly_hiring_trends"])
            st.line_chart(frame.set_index("week")[["jobs"]])
        else:
            render_state(locale, "empty")
    st.subheader(translate(locale, "dashboard.recently_added"))
    for job in data["recently_added_jobs"]:
        render_job_card(job, region="dashboard-recent", locale=locale, client=client)
