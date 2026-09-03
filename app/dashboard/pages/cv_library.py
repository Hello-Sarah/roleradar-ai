"""Read-only CV Library and explicit tailored-CV generation page."""

from __future__ import annotations

import os
from urllib.parse import quote

import streamlit as st

from app.dashboard.client import RoleRadarClient
from app.dashboard.components.states import render_state
from app.i18n.service import translate
from app.schemas import Locale


def render_page(client: RoleRadarClient, locale: Locale) -> None:
    st.title(translate(locale, "page.cv_library.title"))
    st.caption(translate(locale, "page.cv_library.support"))
    source_path = os.getenv("CV_LIBRARY_PATH", "./data/cv_library")
    output_path = os.getenv("GENERATED_CV_PATH", "./data/generated_cvs")
    st.caption(f"{translate(locale, 'cv.source_path')}: {source_path}")
    st.caption(f"{translate(locale, 'cv.generated_path')}: {output_path}")
    st.write(translate(locale, "cv.source_files_read_only"))
    if st.button(translate(locale, "cv.scan_folder"), type="primary"):
        with st.spinner(translate(locale, "cv.scan_in_progress")):
            result = client.post("/api/v1/cv-library/scan", {})
        st.success(
            translate(
                locale,
                "cv.scan.summary",
                discovered=result["discovered"],
                added=result["added"],
                updated=result["updated"],
                unchanged=result["unchanged"],
            )
        )
        for failure in result["failed"]:
            st.warning(failure)
    documents = client.get("/api/v1/cv-library")
    if not documents:
        render_state(locale, "empty", translate(locale, "cv.empty_library"))
        return
    for document in documents:
        with st.container(border=True):
            st.write(f"**{document['file_name']}**")
            st.caption(f"{document['file_type'].upper()} · {document['modified_at'][:10]}")
    jobs = client.get("/api/v1/jobs")
    if not jobs:
        st.info(translate(locale, "cv.no_job_selected"))
        return
    options = {f"{job['company']} — {job['title']}": job["id"] for job in jobs}
    with st.form("cv-generate-form"):
        selected = st.selectbox(translate(locale, "cv.target_job"), list(options))
        generate = st.form_submit_button(translate(locale, "cv.generate_tailored"), type="primary")
    if generate:
        generated = client.post(f"/api/v1/jobs/{options[selected]}/tailored-cv", {})
        st.session_state["cv.generated"] = generated
    generated = st.session_state.get("cv.generated")
    if generated:
        st.success(translate(locale, "cv.generated", file_name=generated["file_name"]))
        download_url = (
            f"{client.base_url}/api/v1/generated-cvs/{generated['id']}/"
            f"{quote(generated['file_name'], safe='')}"
        )
        st.link_button(translate(locale, "cv.download_tailored"), download_url, type="primary")
