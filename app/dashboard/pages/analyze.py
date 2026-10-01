"""Analyze Job page and editable extraction-preview boundary."""

from __future__ import annotations

from collections.abc import MutableMapping
from datetime import date
from typing import Any

import streamlit as st

from app.dashboard.client import RoleRadarClient
from app.dashboard.components.job_card import render_job_card
from app.dashboard.state import parse_optional_iso_date, select_job_context
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
    session_state.pop("analyze.source_url", None)


def _posting_date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        return date.fromisoformat(value)
    return None


def _render_preview(client: RoleRadarClient, locale: Locale, extracted: dict[str, Any]) -> None:
    st.info(translate(locale, "job.review.nothing_saved"))
    with st.form("analyze-preview-form"):
        company = st.text_input(
            translate(locale, "form.company"),
            extracted["company"],
            key="analyze-preview-company",
        )
        title = st.text_input(
            translate(locale, "form.title"),
            extracted["title"],
            key="analyze-preview-title",
        )
        location = st.text_input(
            translate(locale, "form.location"),
            extracted["location"],
            key="analyze-preview-location",
        )
        url = st.text_input(
            translate(locale, "form.job_url"),
            extracted.get("url") or "",
            key="analyze-preview-url",
        )
        posting_date_value = _posting_date(extracted.get("posting_date"))
        posting_date_text = st.text_input(
            translate(locale, "job.review.posting_date"),
            value=posting_date_value.isoformat() if posting_date_value else "",
            placeholder="YYYY-MM-DD",
            key="analyze-preview-date",
        )
        description = st.text_area(
            translate(locale, "form.description"),
            extracted["description"],
            height=360,
            key="analyze-preview-description",
        )
        confirm = st.form_submit_button(
            translate(locale, "job.review.confirm_and_analyze"),
            type="primary",
            key="analyze-preview-confirm",
        )
    if st.button(
        translate(locale, "action.cancel"),
        key="analyze-preview-cancel",
    ):
        cancel_extraction(st.session_state)
        st.rerun()
    if confirm:
        try:
            reviewed_posting_date = parse_optional_iso_date(posting_date_text)
        except ValueError:
            st.error(translate(locale, "validation.job.invalid_posting_date"))
            return
        payload = build_confirmed_job_payload(
            extracted,
            company=company,
            title=title,
            location=location,
            url=url,
            posting_date=reviewed_posting_date,
            description=description,
        )
        st.session_state["analyze.last_job"] = client.post("/api/v1/jobs", payload)
        cancel_extraction(st.session_state)
        st.rerun()


def render_page(client: RoleRadarClient, locale: Locale) -> None:
    st.title(translate(locale, "page.analyze.title"))
    st.caption(translate(locale, "page.analyze.support"))
    extracted = st.session_state.get("analyze.extracted_job")
    if extracted is not None:
        _render_preview(client, locale, extracted)
    else:
        link_tab, text_tab = st.tabs(
            [
                translate(locale, "job.intake.job_link"),
                translate(locale, "job.intake.paste_job_text"),
            ]
        )
        with link_tab:
            st.subheader(translate(locale, "job.intake.analyze_from_url"))
            st.caption(translate(locale, "job.intake.url_help"))
            with st.form("analyze-url-form", clear_on_submit=True):
                job_url = st.text_input(translate(locale, "form.job_url"), key="analyze-url")
                submitted = st.form_submit_button(
                    translate(locale, "action.extract_fields"),
                    type="primary",
                    key="analyze-url-submit",
                )
            if submitted:
                with st.spinner(translate(locale, "job.intake.reading_page")):
                    st.session_state["analyze.source_url"] = job_url
                    st.session_state["analyze.extracted_job"] = client.post(
                        "/api/v1/jobs/extract-url", {"url": job_url}
                    )
                st.rerun()

        with text_tab:
            st.subheader(translate(locale, "job.intake.paste_complete_posting"))
            st.caption(translate(locale, "job.intake.review_before_save"))
            with st.form("analyze-extract-form"):
                raw_text = st.text_area(
                    translate(locale, "job.intake.paste_job_text"),
                    value=str(st.session_state.get("analyze.raw_text", "")),
                    height=420,
                    key="analyze-text",
                )
                extract = st.form_submit_button(
                    translate(locale, "action.extract_fields"),
                    type="primary",
                    key="analyze-text-submit",
                )
            if extract:
                st.session_state["analyze.raw_text"] = raw_text
                with st.spinner(translate(locale, "component.loading")):
                    st.session_state["analyze.extracted_job"] = client.post(
                        "/api/v1/jobs/extract", {"text": raw_text}
                    )
                st.rerun()

    completed = st.session_state.get("analyze.last_job")
    if completed:
        select_job_context(st.session_state, completed["id"])
        score = (completed.get("analysis") or {}).get("fit_score", "—")
        st.success(translate(locale, "job.success.analysis_complete", score=score))
        render_job_card(completed, region="analyze-result", locale=locale, client=client)
