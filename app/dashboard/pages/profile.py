"""Candidate Profile page."""

from __future__ import annotations

import streamlit as st

from app.dashboard.client import RoleRadarClient
from app.i18n.service import translate
from app.schemas import Locale

_FIELDS = (
    ("target_roles", "profile.target_roles"),
    ("preferred_locations", "profile.preferred_locations"),
    ("future_locations", "profile.future_locations"),
    ("domain_strengths", "profile.domain_strengths"),
    ("technical_strengths", "profile.technical_strengths"),
    ("development_gaps", "profile.development_gaps"),
)


def render_page(client: RoleRadarClient, locale: Locale) -> None:
    st.title(translate(locale, "page.profile.title"))
    st.caption(translate(locale, "page.profile.support"))
    profile = client.get("/api/v1/profile")
    with st.form("profile-form"):
        name = st.text_input(translate(locale, "profile.name"), profile["name"])
        values = {
            field: st.text_input(translate(locale, key), ", ".join(profile[field]))
            for field, key in _FIELDS
        }
        save = st.form_submit_button(translate(locale, "profile.save"), type="primary")
    if save:
        payload = {"name": name}
        payload.update(
            {
                field: [item.strip() for item in value.split(",") if item.strip()]
                for field, value in values.items()
            }
        )
        client.put("/api/v1/profile", payload)
        st.success(translate(locale, "profile.save_success"))
