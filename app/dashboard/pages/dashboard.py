"""Decision-first Dashboard page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.dashboard.client import RoleRadarClient
from app.dashboard.components.job_card import analysis_signal_label, render_job_card
from app.dashboard.components.states import render_state
from app.dashboard.state import apply_job_filter, format_local_date
from app.i18n.service import translate
from app.schemas import Locale


def render_page(client: RoleRadarClient, locale: Locale) -> None:
    st.title(translate(locale, "page.dashboard.title"))
    st.caption(translate(locale, "page.dashboard.support"))
    data = client.get("/api/v1/dashboard")
    counts = data["status_counts"]
    metrics = st.columns(4)
    metric_specs = (
        ("high", "dashboard.high_priority", len(data["high_priority_jobs"]), None, True),
        ("new", "dashboard.new", counts.get("New", 0), "New", False),
        ("applied", "application_status.applied", counts.get("Applied", 0), "Applied", False),
        ("interview", "dashboard.interviews", counts.get("Interview", 0), "Interview", False),
    )
    for column, (slug, label_key, value, status, priority_only) in zip(
        metrics, metric_specs, strict=True
    ):
        with column:
            st.metric(translate(locale, label_key), value)
            if st.button(
                translate(locale, "dashboard.view_records"),
                key=f"dashboard-drill-{slug}",
                use_container_width=True,
            ):
                apply_job_filter(st.session_state, status=status, priority_only=priority_only)
                st.rerun()
    st.subheader(translate(locale, "dashboard.next_action"))
    next_action = data.get("next_action")
    if next_action and next_action["kind"] == "follow_up":
        job = next_action["job"]
        with st.container(border=True):
            st.write(f"**{job['company']} — {job['title']}**")
            st.caption(
                translate(locale, f"dashboard.follow_up_{next_action['follow_up_timing']}")
                + " · "
                + format_local_date(locale, next_action["next_follow_up_date"])
            )
            if st.button(
                translate(locale, "dashboard.view_records"),
                key=f"dashboard-next-follow-up-{job['id']}",
            ):
                apply_job_filter(st.session_state, status=job["status"])
                st.session_state["ui.selected_job_id"] = job["id"]
                st.rerun()
    elif next_action:
        render_job_card(next_action["job"], region="dashboard-next", locale=locale, client=client)
    else:
        render_state(locale, "empty", translate(locale, "dashboard.empty"))
    st.subheader(translate(locale, "dashboard.follow_ups_due"))
    if not data["due_follow_ups"]:
        render_state(locale, "empty")
    for follow_up in data["due_follow_ups"]:
        job = follow_up["job"]
        with st.container(border=True):
            st.write(f"**{job['company']} — {job['title']}**")
            st.caption(
                translate(locale, f"dashboard.follow_up_{follow_up['timing']}")
                + " · "
                + format_local_date(locale, follow_up["next_follow_up_date"])
            )
            if follow_up.get("notes"):
                st.write(follow_up["notes"])
            if st.button(
                translate(locale, "dashboard.view_records"),
                key=f"dashboard-follow-up-{job['id']}",
            ):
                apply_job_filter(st.session_state, status=job["status"])
                st.session_state["ui.selected_job_id"] = job["id"]
                st.rerun()
    st.subheader(translate(locale, "dashboard.high_priority_jobs"))
    next_job_id = (
        next_action["job"]["id"] if next_action and next_action["kind"] == "review_job" else None
    )
    for job in data["high_priority_jobs"]:
        if job["id"] == next_job_id:
            continue
        render_job_card(job, region="dashboard-priority", locale=locale, client=client)
    charts = st.columns(2)
    with charts[0]:
        st.subheader(translate(locale, "dashboard.skill_gap_trends"))
        if data["skill_gap_trends"]:
            localized_gaps = [
                (analysis_signal_label(locale, gap, gap=True), count)
                for gap, count in data["skill_gap_trends"]
            ]
            jobs_label = translate(locale, "dashboard.jobs_count")
            frame = pd.DataFrame(localized_gaps, columns=["signal", jobs_label])
            st.bar_chart(frame.set_index("signal").rename_axis(None))
            for index, ((gap, _count), (localized_gap, _)) in enumerate(
                zip(data["skill_gap_trends"], localized_gaps, strict=True)
            ):
                if st.button(
                    f"{translate(locale, 'dashboard.view_records')} · {localized_gap}",
                    key=f"dashboard-drill-skill-gap-{index}",
                    use_container_width=True,
                ):
                    apply_job_filter(st.session_state, gap=gap)
                    st.rerun()
        else:
            render_state(locale, "empty")
    with charts[1]:
        st.subheader(translate(locale, "dashboard.hiring_trends"))
        if data["weekly_hiring_trends"]:
            frame = pd.DataFrame(data["weekly_hiring_trends"]).rename(
                columns={"jobs": translate(locale, "dashboard.jobs_count")}
            )
            st.line_chart(frame.set_index("week")[[translate(locale, "dashboard.jobs_count")]])
            for index, trend in enumerate(data["weekly_hiring_trends"]):
                if st.button(
                    f"{translate(locale, 'dashboard.view_records')} · {trend['week']}",
                    key=f"dashboard-drill-hiring-trend-{index}",
                    use_container_width=True,
                ):
                    apply_job_filter(st.session_state, created_week=trend["week"])
                    st.rerun()
        else:
            render_state(locale, "empty")
    st.subheader(translate(locale, "dashboard.recently_added"))
    for job in data["recently_added_jobs"]:
        render_job_card(job, region="dashboard-recent", locale=locale, client=client)
