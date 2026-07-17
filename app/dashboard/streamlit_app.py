import os

import pandas as pd
import streamlit as st

from app.dashboard.client import APIClientError, RoleRadarClient
from app.schemas import ApplicationStatus

st.set_page_config(page_title="RoleRadar AI", page_icon="📡", layout="wide")
client = RoleRadarClient(os.getenv("API_BASE_URL", "http://localhost:8000"))


def render_job(job: dict) -> None:
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
                st.link_button("View posting", job["url"])
        with right:
            st.metric("Fit score", score)
            st.write(analysis.get("recommendation", "Pending"))
            selected = st.selectbox(
                "Application status",
                [status.value for status in ApplicationStatus],
                index=[status.value for status in ApplicationStatus].index(job["status"]),
                key=f"status-{job['id']}",
            )
            if selected != job["status"]:
                client.patch(f"/api/v1/jobs/{job['id']}/status", {"status": selected})
                st.rerun()


st.title("📡 RoleRadar AI")
st.caption("Your explainable career intelligence agent for Applied AI roles")

dashboard_tab, add_tab, tracker_tab, profile_tab, digest_tab = st.tabs(
    ["Dashboard", "Analyze a job", "Application tracker", "Profile", "Daily digest"]
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
            render_job(job)
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
            render_job(job)

    with add_tab:
        st.subheader("Paste the complete job posting")
        st.caption(
            "Step 1: paste everything from the job page. Step 2: review and correct "
            "the extracted fields before RoleRadar saves or analyzes anything."
        )
        extracted = st.session_state.get("extracted_job")
        if extracted is None:
            with st.form("job-extraction-form", clear_on_submit=True):
                pasted_text = st.text_area(
                    "Job posting text",
                    height=480,
                    placeholder=(
                        "Paste the full job page here — header, company, location, URL, "
                        "responsibilities, and requirements..."
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
            render_job(completed_job)

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
                render_job(job)
        else:
            st.info("No tracked jobs yet.")

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
            render_job(job)
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
