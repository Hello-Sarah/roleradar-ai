"""Signal-only daily Digest page."""

from __future__ import annotations

import streamlit as st

from app.dashboard.client import RoleRadarClient
from app.dashboard.components.job_card import render_job_card
from app.dashboard.components.states import render_state
from app.dashboard.state import format_local_date
from app.i18n.service import translate
from app.schemas import Locale


def render_page(client: RoleRadarClient, locale: Locale) -> None:
    st.title(translate(locale, "page.digest.title"))
    st.caption(translate(locale, "page.digest.support"))
    digest = client.get("/api/v1/digest/daily")
    generated_at = format_local_date(locale, digest["generated_at"])
    st.caption(translate(locale, "digest.generated_at", generated_at=generated_at))
    sections = [
        ("digest.high_priority_new_jobs", digest["high_priority_jobs"]),
        ("digest.new_companies", digest["new_companies"]),
        ("digest.emerging_skills", digest["emerging_skills"]),
        ("digest.hiring_trends", digest["hiring_trends"]),
    ]
    for key, values in sections:
        st.subheader(translate(locale, key))
        if not values:
            render_state(locale, "empty", translate(locale, "digest.no_signal"))
        elif key == "digest.high_priority_new_jobs":
            for job in values:
                render_job_card(job, region="digest", locale=locale, client=client)
        else:
            for value in values:
                st.write(f"• {value}")
