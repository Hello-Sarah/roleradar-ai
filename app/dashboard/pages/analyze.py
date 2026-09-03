"""Analyze Job page and editable extraction-preview boundary."""

from __future__ import annotations

from collections.abc import MutableMapping
from datetime import date
from typing import Any

import streamlit as st

from app.dashboard.client import RoleRadarClient
from app.dashboard.components.job_card import render_job_card
from app.dashboard.state import select_job_context, stable_key
from app.i18n.service import translate
from app.schemas import Locale


def build_confirmed_job_payload(
    extracted: dict[str, Any],
    *,
    company: str,
    title: str,
    location: str,
    url: str,
    posting_date: date | None,
    description: str,
) -> dict[str, Any]:
    """Build persistence input exclusively from the user's reviewed field values."""
    return {
        "company": company.strip(),
        "title": title.strip(),
        "location": location.strip(),
        "url": url.strip() or None,
        "posting_date": posting_date.isoformat() if posting_date else None,
        "description": description.strip(),
        "source": extracted.get("source") or "pasted_text",
    }


def cancel_extraction(session_state: MutableMapping[str, object]) -> None:
    session_state.pop("analyze.extracted_job", None)
    session_state.pop("analyze.raw_text", None)


def _posting_date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        return date.fromisoformat(value)
    return None


def render_page(client: RoleRadarClient, locale: Locale) -> None:
    st.title(translate(locale, "page.analyze.title"))
    st.caption(translate(locale, "page.analyze.support"))
    link_tab, text_tab = st.tabs(
        [translate(locale, "job.intake.job_link"), translate(locale, "job.intake.paste_job_text")]
    )
    with link_tab:
        st.subheader(translate(locale, "job.intake.analyze_from_url"))
        st.caption(translate(locale, "job.intake.url_help"))
        with st.form("analyze-url-form", clear_on_submit=True):
            job_url = st.text_input(translate(locale, "form.job_url"))
            submitted = st.form_submit_button(
                translate(locale, "action.save_and_analyze"), type="primary"
            )
        if submitted:
            with st.spinner(translate(locale, "job.intake.reading_page")):
                st.session_state["analyze.last_job"] = client.post(
                    "/api/v1/jobs/from-url", {"url": job_url}
                )

    with text_tab:
        st.subheader(translate(locale, "job.intake.paste_complete_posting"))
        st.caption(translate(locale, "job.intake.review_before_save"))
        extracted = st.session_state.get("analyze.extracted_job")
        if extracted is None:
            with st.form("analyze-extract-form"):
                raw_text = st.text_area(
                    translate(locale, "job.intake.paste_job_text"),
                    value=str(st.session_state.get("analyze.raw_text", "")),
                    height=420,
                )
                extract = st.form_submit_button(
                    translate(locale, "action.extract_fields"), type="primary"
                )
            if extract:
                st.session_state["analyze.raw_text"] = raw_text
                st.session_state["analyze.extracted_job"] = client.post(
                    "/api/v1/jobs/extract", {"text": raw_text}
                )
                st.rerun()
        else:
            st.info(translate(locale, "job.review.nothing_saved"))
            with st.form("analyze-preview-form"):
                company = st.text_input(translate(locale, "form.company"), extracted["company"])
                title = st.text_input(translate(locale, "form.title"), extracted["title"])
                location = st.text_input(translate(locale, "form.location"), extracted["location"])
                url = st.text_input(translate(locale, "form.job_url"), extracted.get("url") or "")
                posting_date = st.date_input(
                    translate(locale, "job.review.posting_date"),
                    value=_posting_date(extracted.get("posting_date")),
                )
                description = st.text_area(
                    translate(locale, "form.description"), extracted["description"], height=360
                )
                confirm = st.form_submit_button(
                    translate(locale, "job.review.confirm_and_analyze"), type="primary"
                )
            if st.button(
                translate(locale, "action.cancel"),
                key=stable_key("analyze-preview", "cancel"),
            ):
                cancel_extraction(st.session_state)
                st.rerun()
            if confirm:
                payload = build_confirmed_job_payload(
                    extracted,
                    company=company,
                    title=title,
                    location=location,
                    url=url,
                    posting_date=posting_date,
                    description=description,
                )
                st.session_state["analyze.last_job"] = client.post("/api/v1/jobs", payload)
                cancel_extraction(st.session_state)
                st.rerun()

    completed = st.session_state.get("analyze.last_job")
    if completed:
        select_job_context(st.session_state, completed["id"])
        score = (completed.get("analysis") or {}).get("fit_score", "—")
        st.success(translate(locale, "job.success.analysis_complete", score=score))
        render_job_card(completed, region="analyze-result", locale=locale, client=client)
