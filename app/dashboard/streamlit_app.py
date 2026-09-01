import os
from datetime import date, datetime
from urllib.parse import quote

import pandas as pd
import streamlit as st

from app.dashboard.client import APIClientError, RoleRadarClient
from app.schemas import ApplicationStatus

st.set_page_config(page_title="RoleRadar AI", page_icon="📡", layout="wide")
client = RoleRadarClient(os.getenv("API_BASE_URL", "http://localhost:8000"))


def render_job(job: dict, key_prefix: str) -> None:
    analysis = job.get("analysis") or {}
    classification = job.get("classification") or {}
    score = analysis.get("fit_score", "—")
    with st.expander(f"{score} · {job['company']} — {job['title']} ({job['location']})"):
        left, right = st.columns([2, 1])
        with left:
            st.write(analysis.get("summary", "Analysis pending"))
            st.caption(
                f"{classification.get('category', 'Unclassified')} · "
                f"{classification.get('confidence', 0):.0%} confidence"
            )
            st.markdown("**Strengths:** " + ", ".join(analysis.get("strengths", [])))
            st.markdown("**Gaps:** " + ", ".join(analysis.get("gaps", [])))
            if job.get("url"):
                st.link_button("View posting", job["url"], key=f"{key_prefix}-link-{job['id']}")
        with right:
            st.metric("Fit score", score)
            st.write(analysis.get("recommendation", "Pending"))
            selected = st.selectbox(
                "Application status",
                [status.value for status in ApplicationStatus],
                index=[status.value for status in ApplicationStatus].index(job["status"]),
                key=f"{key_prefix}-status-{job['id']}",
            )
            if selected != job["status"]:
                client.patch(f"/api/v1/jobs/{job['id']}/status", {"status": selected})
                st.rerun()


def render_application_history(job: dict) -> None:
    events = job.get("application_events") or []
    with st.expander(f"Application records · {job['company']} — {job['title']}"):
        with st.form(f"application-event-{job['id']}", clear_on_submit=True):
            status_value = st.selectbox(
                "Status",
                [status.value for status in ApplicationStatus],
                index=[status.value for status in ApplicationStatus].index(job["status"]),
                key=f"event-status-{job['id']}",
            )
            occurred_on = st.date_input("Date", value=date.today(), key=f"event-date-{job['id']}")
            channel = st.selectbox(
                "Channel",
                ["Company website", "LinkedIn", "Referral", "Recruiter", "Email", "Other"],
                key=f"event-channel-{job['id']}",
            )
            notes = st.text_area(
                "Notes", placeholder="Contact, outcome, interview stage, or next action..."
            )
            follow_up = st.date_input(
                "Next follow-up date (optional)",
                value=None,
                key=f"event-follow-up-{job['id']}",
            )
            add_record = st.form_submit_button("Add application record", type="primary")
        if add_record:
            client.post(
                f"/api/v1/jobs/{job['id']}/application-events",
                {
                    "status": status_value,
                    "occurred_at": datetime.combine(occurred_on, datetime.min.time()).isoformat(),
                    "channel": channel,
                    "notes": notes or None,
                    "next_follow_up_date": follow_up.isoformat() if follow_up else None,
                },
            )
            st.rerun()

        if events:
            st.markdown("#### Timeline")
            for event in events:
                details = [event["status"]]
                if event.get("channel"):
                    details.append(event["channel"])
                st.markdown(f"**{event['occurred_at'][:10]}** · " + " · ".join(details))
                if event.get("notes"):
                    st.write(event["notes"])
                if event.get("next_follow_up_date"):
                    st.caption(f"Follow up: {event['next_follow_up_date']}")
        else:
            st.caption("No application records yet.")


st.title("📡 RoleRadar AI")
st.caption("Your explainable career intelligence agent for Applied AI roles")

dashboard_tab, add_tab, tracker_tab, cv_tab, profile_tab, digest_tab = st.tabs(
    [
        "Dashboard",
        "Analyze a job",
        "Application tracker",
        "CV Library",
        "Profile",
        "Daily digest",
    ]
)

try:
    with dashboard_tab:
        data = client.get("/api/v1/dashboard")
        status_counts = data["status_counts"]
        cols = st.columns(4)
        cols[0].metric("High priority", len(data["high_priority_jobs"]))
        cols[1].metric("New", status_counts.get("New", 0))
        cols[2].metric("Applied", status_counts.get("Applied", 0))
        cols[3].metric("Interviews", status_counts.get("Interview", 0))
        st.subheader("High priority jobs")
        if not data["high_priority_jobs"]:
            st.info("No high-priority jobs yet. Analyze a job to get started.")
        for job in data["high_priority_jobs"]:
            render_job(job, "dashboard-priority")
        chart_left, chart_right = st.columns(2)
        with chart_left:
            st.subheader("Skill gap trends")
            if data["skill_gap_trends"]:
                gaps = pd.DataFrame(data["skill_gap_trends"], columns=["Skill", "Jobs"])
                st.bar_chart(gaps.set_index("Skill"))
        with chart_right:
            st.subheader("Weekly hiring trends")
            if data["weekly_hiring_trends"]:
                trends = pd.DataFrame(data["weekly_hiring_trends"])
                st.line_chart(trends.set_index("week")[["jobs"]])
        st.subheader("Recently added")
        for job in data["recently_added_jobs"]:
            render_job(job, "dashboard-recent")

    with add_tab:
        link_tab, text_tab = st.tabs(["Job link", "Paste job text"])
        with link_tab:
            st.subheader("Analyze from a job link")
            st.caption(
                "Paste a public job posting URL. RoleRadar will retrieve, record, and "
                "analyze it automatically."
            )
            with st.form("job-url-form", clear_on_submit=True):
                job_url = st.text_input(
                    "Job link", placeholder="https://company.com/careers/jobs/..."
                )
                url_submitted = st.form_submit_button("Record & analyze", type="primary")
            if url_submitted:
                with st.spinner("Reading and analyzing the job page..."):
                    st.session_state["last_analyzed_job"] = client.post(
                        "/api/v1/jobs/from-url", {"url": job_url}
                    )

        with text_tab:
            st.subheader("Paste the complete job posting")
            st.caption(
                "Paste everything from the job page, then review and correct the "
                "extracted fields before RoleRadar saves or analyzes anything."
            )
            extracted = st.session_state.get("extracted_job")
            if extracted is None:
                with st.form("job-extraction-form", clear_on_submit=True):
                    pasted_text = st.text_area(
                        "Job posting text",
                        height=480,
                        placeholder=(
                            "Paste the full job page here — header, company, location, "
                            "URL, responsibilities, and requirements..."
                        ),
                    )
                    extract_submitted = st.form_submit_button("Extract fields", type="primary")
                if extract_submitted:
                    st.session_state["extracted_job"] = client.post(
                        "/api/v1/jobs/extract", {"text": pasted_text}
                    )
                    st.session_state.pop("last_analyzed_job", None)
                    st.rerun()
            else:
                st.info("Review the extracted fields. Nothing has been saved yet.")
                with st.form("job-confirmation-form"):
                    company = st.text_input("Company", value=extracted["company"])
                    title = st.text_input("Job title", value=extracted["title"])
                    location = st.text_input("Location", value=extracted["location"])
                    url = st.text_input("Job URL (optional)", value=extracted.get("url") or "")
                    posting_date = st.date_input(
                        "Posting date (optional)", value=extracted.get("posting_date")
                    )
                    description = st.text_area(
                        "Job description", value=extracted["description"], height=400
                    )
                    confirm_submitted = st.form_submit_button("Confirm & analyze", type="primary")
                reset_col, _ = st.columns([1, 4])
                if reset_col.button("Start over", use_container_width=True):
                    st.session_state.pop("extracted_job", None)
                    st.rerun()
                if confirm_submitted:
                    payload = {
                        "company": company,
                        "title": title,
                        "location": location,
                        "url": url or None,
                        "posting_date": posting_date.isoformat() if posting_date else None,
                        "description": description,
                        "source": "pasted_text",
                    }
                    st.session_state["last_analyzed_job"] = client.post("/api/v1/jobs", payload)
                    st.session_state.pop("extracted_job", None)
                    st.rerun()

        completed_job = st.session_state.get("last_analyzed_job")
        if completed_job:
            st.success(f"Analysis complete: {completed_job['analysis']['fit_score']}/100")
            render_job(completed_job, "analysis-result")

    with tracker_tab:
        jobs = client.get("/api/v1/jobs")
        if jobs:
            st.dataframe(
                [
                    {
                        "Company": job["company"],
                        "Role": job["title"],
                        "Location": job["location"],
                        "Fit": (job.get("analysis") or {}).get("fit_score"),
                        "Status": job["status"],
                        "Added": job["created_at"][:10],
                    }
                    for job in jobs
                ],
                use_container_width=True,
                hide_index=True,
            )
            for job in jobs:
                render_job(job, "tracker")
                render_application_history(job)
        else:
            st.info("No tracked jobs yet.")

    with cv_tab:
        st.subheader("CV Library")
        cv_library_path = os.getenv("CV_LIBRARY_PATH", "./data/cv_library")
        generated_cv_path = os.getenv("GENERATED_CV_PATH", "./data/generated_cvs")
        st.caption(f"Source folder: {cv_library_path} · Generated CV folder: {generated_cv_path}")
        st.write(
            "Place your `.docx`, `.pdf`, or `.txt` CVs in the source folder. "
            "Original files remain read-only and are excluded from Git."
        )
        if st.button("Scan CV folder", type="primary"):
            with st.spinner("Scanning CV files..."):
                scan_result = client.post("/api/v1/cv-library/scan", {})
            st.success(
                f"Found {scan_result['discovered']} CVs · added {scan_result['added']} · "
                f"updated {scan_result['updated']} · unchanged {scan_result['unchanged']}"
            )
            for failure in scan_result["failed"]:
                st.warning(failure)

        cv_documents = client.get("/api/v1/cv-library")
        if cv_documents:
            st.dataframe(
                [
                    {
                        "File": document["file_name"],
                        "Type": document["file_type"].upper(),
                        "Updated": document["modified_at"][:10],
                    }
                    for document in cv_documents
                ],
                use_container_width=True,
                hide_index=True,
            )
            available_jobs = client.get("/api/v1/jobs")
            if available_jobs:
                job_options = {
                    f"{job['company']} — {job['title']} ({job['location']})": job["id"]
                    for job in available_jobs
                }
                with st.form("tailored-cv-form"):
                    selected_job_label = st.selectbox("Target job", list(job_options))
                    generate_cv = st.form_submit_button("Generate tailored CV", type="primary")
                if generate_cv:
                    with st.spinner("Building an evidence-grounded tailored CV..."):
                        generated = client.post(
                            f"/api/v1/jobs/{job_options[selected_job_label]}/tailored-cv", {}
                        )
                    st.session_state["generated_cv"] = generated

                generated = st.session_state.get("generated_cv")
                if generated:
                    st.success(f"Generated: {generated['file_name']}")
                    download_url = (
                        f"{client.base_url}/api/v1/generated-cvs/{generated['id']}/"
                        f"{quote(generated['file_name'], safe='')}"
                    )
                    st.link_button("Download tailored CV", download_url, type="primary")
            else:
                st.info("Add and analyze a job before generating a tailored CV.")
        else:
            st.info("No CVs indexed yet. Add files to the source folder and scan it.")

    with profile_tab:
        profile = client.get("/api/v1/profile")
        with st.form("profile-form"):
            name = st.text_input("Name", profile["name"])
            fields = {}
            for key, label in [
                ("target_roles", "Target roles"),
                ("preferred_locations", "Preferred locations"),
                ("future_locations", "Future locations"),
                ("domain_strengths", "Domain strengths"),
                ("technical_strengths", "Technical strengths"),
                ("development_gaps", "Development gaps"),
            ]:
                fields[key] = st.text_input(label, ", ".join(profile[key]))
            save_profile = st.form_submit_button("Save profile", type="primary")
        if save_profile:
            payload = {"name": name}
            payload.update(
                {
                    key: [item.strip() for item in value.split(",") if item.strip()]
                    for key, value in fields.items()
                }
            )
            client.put("/api/v1/profile", payload)
            st.success(
                "Profile saved. Existing analyses remain auditable; "
                "re-add or reanalyze jobs explicitly."
            )

    with digest_tab:
        digest = client.get("/api/v1/digest/daily")
        st.caption(f"Generated {digest['generated_at']}")
        st.subheader("High-priority new jobs")
        for job in digest["high_priority_jobs"]:
            render_job(job, "digest")
        st.subheader("New companies")
        st.write(", ".join(digest["new_companies"]) or "None")
        st.subheader("Emerging skills")
        st.write(digest["emerging_skills"] or "No trend yet")
        st.subheader("Hiring trends")
        for trend in digest["hiring_trends"]:
            st.write(f"• {trend}")
except APIClientError as exc:
    st.error(str(exc))
    st.info("Start the API with: uvicorn app.main:app --reload")
