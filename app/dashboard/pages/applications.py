"""Application timeline page."""

from __future__ import annotations

from datetime import date, datetime

import streamlit as st

from app.dashboard.client import RoleRadarClient
from app.dashboard.components.states import render_state
from app.dashboard.state import format_local_date, parse_optional_iso_date, stable_key
from app.i18n.service import translate
from app.schemas import ApplicationStatus, Locale

_CHANNELS = {
    "Company website": "application_channel.company_website",
    "LinkedIn": "application_channel.linkedin",
    "Referral": "application_channel.referral",
    "Recruiter": "application_channel.recruiter",
    "Email": "application_channel.email",
    "Other": "application_channel.other",
}
_STATUS_KEYS = {
    status.value: f"application_status.{status.value.casefold()}" for status in ApplicationStatus
}


def render_page(client: RoleRadarClient, locale: Locale) -> None:
    st.title(translate(locale, "page.applications.title"))
    st.caption(translate(locale, "page.applications.support"))
    jobs = client.get("/api/v1/jobs")
    if not jobs:
        render_state(locale, "empty", translate(locale, "page.applications.empty"))
        return
    for job in jobs:
        with st.container(border=True):
            st.subheader(f"{job['company']} — {job['title']}")
            st.caption(job["location"])
            with st.form(stable_key("applications", "event-form", job["id"])):
                statuses = [status.value for status in ApplicationStatus]
                status = st.selectbox(
                    translate(locale, "application.status"),
                    statuses,
                    index=statuses.index(job["status"]),
                    format_func=lambda value: translate(locale, _STATUS_KEYS[value]),
                )
                occurred_on = st.text_input(
                    translate(locale, "application.date"),
                    date.today().isoformat(),
                    placeholder="YYYY-MM-DD",
                )
                channels = list(_CHANNELS)
                channel = st.selectbox(
                    translate(locale, "application.channel"),
                    channels,
                    format_func=lambda value: translate(locale, _CHANNELS[value]),
                )
                notes = st.text_area(translate(locale, "application.notes"), max_chars=2_000)
                follow_up = st.text_input(
                    translate(locale, "application.follow_up_date"),
                    value="",
                    placeholder="YYYY-MM-DD",
                )
                add = st.form_submit_button(translate(locale, "action.add"), type="primary")
            if add:
                try:
                    occurred_date = parse_optional_iso_date(occurred_on)
                except ValueError:
                    st.error(translate(locale, "validation.application.invalid_date"))
                    continue
                try:
                    follow_up_date = parse_optional_iso_date(follow_up)
                except ValueError:
                    st.error(translate(locale, "validation.application.invalid_follow_up_date"))
                    continue
                if occurred_date is None:
                    st.error(translate(locale, "validation.application.invalid_date"))
                    continue
                client.post(
                    f"/api/v1/jobs/{job['id']}/application-events",
                    {
                        "status": status,
                        "occurred_at": datetime.combine(
                            occurred_date, datetime.min.time()
                        ).isoformat(),
                        "channel": channel,
                        "notes": notes or None,
                        "next_follow_up_date": follow_up_date.isoformat()
                        if follow_up_date
                        else None,
                    },
                )
                st.rerun()
            st.markdown(f"**{translate(locale, 'application.history')}**")
            events = job.get("application_events") or []
            if not events:
                st.caption(translate(locale, "page.applications.no_history"))
            for event in events:
                event_status = translate(locale, _STATUS_KEYS[event["status"]])
                st.write(f"**{format_local_date(locale, event['occurred_at'])}** · {event_status}")
                if event.get("notes"):
                    st.write(event["notes"])
                if event.get("next_follow_up_date"):
                    st.caption(
                        f"{translate(locale, 'application.follow_up_date')}: "
                        f"{format_local_date(locale, event['next_follow_up_date'])}"
                    )
