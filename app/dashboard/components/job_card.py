"""Decision-first job cards shared across RoleRadar pages."""

from __future__ import annotations

from typing import Any

import streamlit as st

from app.dashboard.client import RoleRadarClient
from app.dashboard.components.states import low_confidence_label
from app.dashboard.state import select_job_context, stable_key
from app.i18n.service import translate
from app.schemas import ApplicationStatus, Locale

_STATUS_KEYS = {
    status.value: f"application_status.{status.value.casefold()}" for status in ApplicationStatus
}

_GAP_DIMENSIONS = {
    "AI_DEPTH_EVIDENCE_WEAK": "score.ai_depth",
    "OWNERSHIP_EVIDENCE_WEAK": "score.ownership",
    "BUILD_AND_SHIP_EVIDENCE_WEAK": "score.build_ship",
    "PRODUCT_EXPOSURE_EVIDENCE_WEAK": "score.product_exposure",
    "TECHNICAL_EXPOSURE_EVIDENCE_WEAK": "score.technical_exposure",
    "CAREER_OPTION_VALUE_EVIDENCE_WEAK": "score.career_option_value",
}
_ANALYSIS_SIGNAL_KEYS = {
    "NO_MATCHED_GREEN_FLAGS": "analysis.no_strength_signals",
    "NO_WEAK_DIMENSIONS": "analysis.no_gap_signals",
}
_RECOMMENDATION_KEYS = {
    "Must Apply": "score.must_apply",
    "Strong Apply": "score.strong_apply",
    "Selective": "score.selective",
    "Skip": "score.skip",
    "Apply Now": "recommendation.apply_now",
    "Consider": "recommendation.consider",
    "Build Skills First": "recommendation.build_skills_first",
}


def analysis_signal_label(locale: Locale, value: str, *, gap: bool = False) -> str:
    """Present analysis machine codes in the active locale."""
    if value in _ANALYSIS_SIGNAL_KEYS:
        return translate(locale, _ANALYSIS_SIGNAL_KEYS[value])
    if gap and value in _GAP_DIMENSIONS:
        return translate(
            locale,
            "analysis.weak_evidence",
            dimension=translate(locale, _GAP_DIMENSIONS[value]),
        )
    prefix = "score.red_flag." if gap else "score.green_flag."
    key = f"{prefix}{value.casefold()}"
    try:
        return translate(locale, key)
    except KeyError:
        # Unknown model codes remain safe presentation text, never raw machine tokens.
        return value.replace("_", " ").capitalize()


def recommendation_label(locale: Locale, recommendation: str | None) -> str:
    """Localize the persisted decision without deriving a new one from its score."""
    if recommendation is None:
        return translate(locale, "analysis.analysis_pending")
    key = _RECOMMENDATION_KEYS.get(recommendation)
    return translate(locale, key) if key else recommendation


def render_job_card(
    job: dict[str, Any],
    *,
    region: str,
    locale: Locale,
    client: RoleRadarClient,
) -> None:
    analysis = job.get("analysis") or {}
    classification = job.get("classification") or {}
    score = analysis.get("fit_score")
    decision = recommendation_label(locale, analysis.get("recommendation"))
    with st.container(border=True):
        st.markdown(f"<span class='rr-kicker'>{decision}</span>", unsafe_allow_html=True)
        st.subheader(f"{job['company']} — {job['title']}")
        st.caption(f"{job['location']} · {score if score is not None else '—'}/100")
        if analysis:
            st.write(
                translate(
                    locale,
                    "analysis.summary",
                    score=score if score is not None else "—",
                    recommendation=decision,
                )
            )
            evidence = analysis.get("evidence") or []
            if evidence:
                with st.expander(translate(locale, "analysis.evidence")):
                    for item in evidence:
                        st.write(f"• {item}")
            strengths, gaps = st.columns(2)
            with strengths:
                st.markdown(f"**{translate(locale, 'analysis.strengths')}**")
                st.write(
                    ", ".join(
                        analysis_signal_label(locale, item)
                        for item in analysis.get("strengths") or []
                    )
                    or "—"
                )
            with gaps:
                st.markdown(f"**{translate(locale, 'analysis.gaps')}**")
                st.write(
                    ", ".join(
                        analysis_signal_label(locale, item, gap=True)
                        for item in analysis.get("gaps") or []
                    )
                    or "—"
                )
        confidence = float(classification.get("confidence", 0))
        warning = low_confidence_label(locale, confidence)
        if warning:
            st.warning(translate(locale, "analysis.needs_review_bilingual"))
        controls = st.columns([2, 1])
        with controls[0]:
            status_values = [status.value for status in ApplicationStatus]
            selected = st.selectbox(
                translate(locale, "application.status"),
                status_values,
                index=status_values.index(job["status"]),
                format_func=lambda value: translate(locale, _STATUS_KEYS[value]),
                key=stable_key(region, "status", job["id"]),
            )
            if selected != job["status"]:
                client.patch(f"/api/v1/jobs/{job['id']}/status", {"status": selected})
                st.rerun()
        with controls[1]:
            if job.get("url"):
                st.link_button(
                    translate(locale, "action.view_posting"),
                    job["url"],
                    key=stable_key(region, "link", job["id"]),
                    use_container_width=True,
                )
        if st.button(
            translate(locale, "accessibility.open_copilot"),
            key=stable_key(region, "copilot", job["id"]),
        ):
            select_job_context(st.session_state, job["id"])
            st.rerun()
