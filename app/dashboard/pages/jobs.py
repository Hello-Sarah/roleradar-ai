"""Saved Jobs page."""

from __future__ import annotations

import streamlit as st

from app.dashboard.client import RoleRadarClient
from app.dashboard.components.job_card import render_job_card
from app.dashboard.components.states import render_state
from app.i18n.service import translate
from app.schemas import Locale


def render_page(client: RoleRadarClient, locale: Locale) -> None:
    st.title(translate(locale, "page.jobs.title"))
    st.caption(translate(locale, "page.jobs.support"))
    jobs = client.get("/api/v1/jobs")
    if not jobs:
        render_state(locale, "empty", translate(locale, "page.jobs.empty"))
        return
    for job in jobs:
        render_job_card(job, region="jobs-library", locale=locale, client=client)
