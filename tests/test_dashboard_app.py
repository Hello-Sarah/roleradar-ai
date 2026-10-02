from __future__ import annotations

from typing import Any

import pytest
from streamlit.testing.v1 import AppTest

from app.dashboard.client import APIClientError
from app.i18n.service import translate


class RecordingClient:
    def __init__(self) -> None:
        self.base_url = "http://test"
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def get(self, path: str) -> Any:
        self.calls.append(("GET", path, None))
        if path == "/api/v1/jobs":
            return []
        raise AssertionError(f"Unexpected GET {path}")

    def post(self, path: str, payload: dict[str, Any]) -> Any:
        self.calls.append(("POST", path, payload))
        if path == "/api/v1/jobs/extract-url":
            return {
                "company": "AWS",
                "title": "Forward Deployed Engineer",
                "location": "Hong Kong",
                "url": payload["url"],
                "posting_date": None,
                "description": (
                    "Example Robotics builds customer AI systems using AWS, Python, SQL, "
                    "Docker, Kubernetes, and production evaluation tooling."
                ),
                "source": "job_url",
            }
        if path == "/api/v1/jobs":
            return {
                "id": 7,
                **payload,
                "status": "New",
                "classification": {
                    "category": "Forward Deployed Engineer",
                    "confidence": 0.9,
                    "evidence": [],
                },
                "analysis": {
                    "fit_score": 70,
                    "scoring_version": "career-fit-v2",
                    "recommendation": "Strong Apply",
                    "summary": "Stored English summary",
                    "evidence": [],
                    "strengths": [],
                    "gaps": [],
                },
            }
        raise AssertionError(f"Unexpected POST {path}")


def _render_analyze(client) -> None:
    from app.dashboard.pages.analyze import render_page

    render_page(client, "en")


def _render_chinese_job_card(client) -> None:
    from app.dashboard.components.job_card import render_job_card

    render_job_card(
        {
            "id": 7,
            "company": "Example Robotics",
            "title": "Forward Deployed Engineer",
            "location": "Hong Kong",
            "url": None,
            "status": "Saved",
            "classification": {
                "category": "Forward Deployed Engineer",
                "confidence": 0.9,
                "evidence": [],
            },
            "analysis": {
                "fit_score": 70,
                "scoring_version": "career-fit-v2",
                "recommendation": "Strong Apply",
                "summary": "Stored English summary",
                "evidence": ["ev-1: Build production AI systems with customers."],
                "strengths": ["CUSTOMER_DEPLOYMENT", "NO_MATCHED_GREEN_FLAGS"],
                "gaps": ["AI_DEPTH_EVIDENCE_WEAK", "NO_WEAK_DIMENSIONS"],
            },
        },
        region="test-job",
        locale="zh-Hans",
        client=client,
    )


def _render_inconsistent_recommendation_job_card(client) -> None:
    from app.dashboard.components.job_card import render_job_card

    render_job_card(
        {
            "id": 84,
            "company": "Auditable AI",
            "title": "Applied AI Lead",
            "location": "Hong Kong",
            "url": None,
            "status": "Saved",
            "classification": {"category": "Applied AI Engineer", "confidence": 0.9},
            "analysis": {
                "fit_score": 84,
                "scoring_version": "career-fit-v2",
                "recommendation": "Selective",
                "summary": "Stored summary",
                "evidence": [],
                "strengths": [],
                "gaps": [],
            },
        },
        region="persisted-decision",
        locale="en",
        client=client,
    )


class DashboardClient(RecordingClient):
    def get(self, path: str) -> Any:
        self.calls.append(("GET", path, None))
        if path == "/api/v1/dashboard":
            job = {
                "id": 9,
                "company": "Example AI",
                "title": "Applied AI Engineer",
                "location": "Hong Kong",
                "url": None,
                "status": "Applied",
                "classification": {"category": "Applied AI Engineer", "confidence": 0.9},
                "analysis": {
                    "fit_score": 82,
                    "scoring_version": "career-fit-v2",
                    "recommendation": "Strong Apply",
                    "summary": "English summary",
                    "evidence": [],
                    "strengths": [],
                    "gaps": [],
                },
            }
            return {
                "status_counts": {"New": 2, "Applied": 1, "Interview": 1},
                "high_priority_jobs": [job],
                "recently_added_jobs": [],
                "skill_gap_trends": [
                    ["AI_DEPTH_EVIDENCE_WEAK", 2],
                    ["OWNERSHIP_EVIDENCE_WEAK", 1],
                ],
                "weekly_hiring_trends": [
                    {"week": "2026-38", "jobs": 1, "average_fit_score": 75.0},
                    {"week": "2026-39", "jobs": 1, "average_fit_score": 82.0},
                ],
                "due_follow_ups": [
                    {
                        "job": job,
                        "next_follow_up_date": "2026-09-01",
                        "timing": "overdue",
                        "notes": "Send hiring manager note",
                    }
                ],
                "next_action": {
                    "kind": "follow_up",
                    "job": job,
                    "follow_up_timing": "overdue",
                    "next_follow_up_date": "2026-09-01",
                },
            }
        return super().get(path)


class HighPriorityJobsClient(RecordingClient):
    def get(self, path: str) -> Any:
        if path == "/api/v1/jobs":
            common = {
                "location": "Hong Kong",
                "url": None,
                "status": "New",
                "classification": {"category": "Applied AI Engineer", "confidence": 0.9},
            }
            return [
                {
                    "id": 70,
                    "company": "Strong AI",
                    "title": "Strong Apply at 70",
                    **common,
                    "analysis": {
                        "fit_score": 70,
                        "scoring_version": "career-fit-v2",
                        "recommendation": "Strong Apply",
                        "summary": "",
                        "evidence": [],
                        "strengths": [],
                        "gaps": [],
                    },
                },
                {
                    "id": 84,
                    "company": "Selective AI",
                    "title": "Selective at 84",
                    **common,
                    "analysis": {
                        "fit_score": 84,
                        "scoring_version": "career-fit-v2",
                        "recommendation": "Selective",
                        "summary": "",
                        "evidence": [],
                        "strengths": [],
                        "gaps": [],
                    },
                },
                {
                    "id": 71,
                    "company": "Legacy AI",
                    "title": "Legacy Strong Apply",
                    **common,
                    "analysis": {
                        "fit_score": 71,
                        "scoring_version": "career-fit-v1",
                        "recommendation": "Strong Apply",
                        "summary": "",
                        "evidence": [],
                        "strengths": [],
                        "gaps": [],
                    },
                },
            ]
        return super().get(path)


class ShellClient(DashboardClient):
    def get(self, path: str) -> Any:
        self.calls.append(("GET", path, None))
        if path == "/api/v1/health":
            return {"status": "ok"}
        if path.startswith("/api/v1/copilot/context"):
            return {"job": None, "company": None}
        if path == "/api/v1/copilot/sessions":
            return []
        if path == "/api/v1/dashboard":
            return {
                "status_counts": {},
                "high_priority_jobs": [],
                "recently_added_jobs": [],
                "skill_gap_trends": [],
                "weekly_hiring_trends": [],
                "due_follow_ups": [],
                "next_action": None,
            }
        if path == "/api/v1/jobs":
            return []
        if path == "/api/v1/watchlist/companies":
            return []
        if path == "/api/v1/cv-library":
            return []
        if path == "/api/v1/digest/daily":
            return {
                "generated_at": "2026-09-30T08:00:00Z",
                "high_priority_jobs": [],
                "new_companies": [],
                "emerging_skills": [],
                "hiring_trends": [],
            }
        if path == "/api/v1/profile":
            return {
                "name": "Example Candidate",
                "target_roles": [],
                "preferred_locations": [],
                "future_locations": [],
                "domain_strengths": [],
                "technical_strengths": [],
                "development_gaps": [],
            }
        raise AssertionError(f"Unexpected GET {path}")


class DashboardToJobsClient(ShellClient):
    def get(self, path: str) -> Any:
        if path == "/api/v1/dashboard":
            return DashboardClient.get(self, path)
        if path == "/api/v1/jobs":
            return HighPriorityJobsClient.get(self, path)
        return super().get(path)


class ResultDestinationClient(ShellClient):
    def get(self, path: str) -> Any:
        if path == "/api/v1/copilot/sessions":
            return [{"id": 3, "title": "Career plan"}]
        if path == "/api/v1/copilot/sessions/3/messages":
            return []
        if path == "/api/v1/action-items/31":
            return {
                "id": 31,
                "job_id": 17,
                "item_kind": "next_action",
                "title": "Follow up with the hiring team",
                "details": "Send the architecture portfolio before Friday.",
                "due_date": "2026-10-02",
                "completed": False,
                "created_at": "2026-10-01T09:00:00Z",
                "updated_at": "2026-10-01T09:00:00Z",
            }
        if path == "/api/v1/generated-cvs/6/metadata":
            return {
                "id": 6,
                "job_id": 17,
                "file_name": "Example AI—Applied AI Engineer-chatgpt.docx",
                "file_path": "/tmp/generated/Example AI—Applied AI Engineer-chatgpt.docx",
                "source_cv_ids": [2],
                "source_cv_hashes": {"2": "abc123"},
                "output_hash": "def456",
                "model_version": "test-model",
                "prompt_version": "tailored-cv-v1",
                "generated_at": "2026-10-01T09:00:00Z",
            }
        return super().get(path)


def _render_shell(client) -> None:
    from app.dashboard.streamlit_app import render_app

    render_app(client)


def _render_shell_with_cookie(client) -> None:
    import app.dashboard.streamlit_app as streamlit_app

    original = streamlit_app._stored_browser_locale
    streamlit_app._stored_browser_locale = lambda: "zh-Hans"
    try:
        streamlit_app.render_app(client)
    finally:
        streamlit_app._stored_browser_locale = original


def _render_cookie_persistence() -> None:
    from app.dashboard.streamlit_app import _persist_browser_locale

    _persist_browser_locale("zh-Hans")


def _render_dashboard(client) -> None:
    from app.dashboard.pages.dashboard import render_page

    render_page(client, "zh-Hans")


def _render_jobs(client) -> None:
    from app.dashboard.pages.jobs import render_page

    render_page(client, "en")


class CVClient(RecordingClient):
    def get(self, path: str) -> Any:
        if path == "/api/v1/cv-library":
            return [
                {
                    "id": 1,
                    "file_name": "profile.pdf",
                    "file_type": "pdf",
                    "modified_at": "2026-09-03T08:00:00Z",
                }
            ]
        if path == "/api/v1/jobs":
            return []
        return super().get(path)


def _render_cv_library(client) -> None:
    from app.dashboard.pages.cv_library import render_page

    render_page(client, "zh-Hans")


class FailingCopilotClient(RecordingClient):
    def get(self, path: str) -> Any:
        if path.startswith("/api/v1/copilot/context"):
            return {"job": None, "company": None}
        if path == "/api/v1/copilot/sessions":
            raise APIClientError("backend exploded in English")
        return super().get(path)


def _render_failing_copilot(client) -> None:
    from app.dashboard.components.copilot_panel import render_copilot_panel
    from app.dashboard.state import UIContext

    render_copilot_panel(UIContext(route="profile", locale="zh-Hans"), client)


class ProposalClient(RecordingClient):
    def get(self, path: str) -> Any:
        if path.startswith("/api/v1/copilot/context"):
            return {"job": None, "company": None}
        if path == "/api/v1/copilot/sessions":
            return [{"id": 3, "title": "Career plan"}]
        if path == "/api/v1/copilot/sessions/3/messages":
            return []
        return super().get(path)

    def post(self, path: str, payload: dict[str, Any]) -> Any:
        self.calls.append(("POST", path, payload))
        if path == "/api/v1/copilot/proposals/8/confirm":
            return {
                "proposal_type": "change_application_status",
                "result_record_ids": {"job": [17], "application_event": [22]},
            }
        return super().post(path, payload)


def _render_pending_copilot(client) -> None:
    from app.dashboard.components.copilot_panel import render_copilot_panel
    from app.dashboard.state import UIContext

    render_copilot_panel(UIContext(route="jobs", locale="zh-Hans"), client)


def _render_copilot_result(client) -> None:
    from app.dashboard.components.copilot_panel import render_copilot_panel
    from app.dashboard.state import UIContext

    render_copilot_panel(UIContext(route="dashboard", locale="en"), client)


def _pending_proposal() -> dict[str, Any]:
    return {
        "id": 8,
        "proposal_type": "change_application_status",
        "target": {"record_type": "job", "record_id": 17},
        "current_value": {"status": "New"},
        "proposed_value": {"status": "Saved"},
        "side_effects": ["Update the job status", "Append one application timeline event"],
        "private_data_usage": {"included": False, "record_ids": [], "purpose": None},
    }


class DigestClient(RecordingClient):
    def get(self, path: str) -> Any:
        if path == "/api/v1/digest/daily":
            return {
                "generated_at": "2026-09-30T08:00:00Z",
                "high_priority_jobs": [],
                "new_companies": [],
                "emerging_skills": [["AI_DEPTH_EVIDENCE_WEAK", 2]],
                "hiring_trends": [{"category": "Applied AI Engineer", "new_roles": 2}],
            }
        return super().get(path)


def _render_chinese_digest(client) -> None:
    from app.dashboard.pages.digest import render_page

    render_page(client, "zh-Hans")


def _render_chinese_jobs_filter(client, filter_kind) -> None:
    import streamlit as st

    from app.dashboard.pages.jobs import render_page

    if filter_kind == "status":
        st.session_state["ui.jobs.status"] = "Applied"
    else:
        st.session_state["ui.jobs.gap"] = "AI_DEPTH_EVIDENCE_WEAK"
    render_page(client, "zh-Hans")


class FailingPageClient(ShellClient):
    def get(self, path: str) -> Any:
        if path == "/api/v1/dashboard":
            raise APIClientError("raw backend failure in English")
        return super().get(path)


def _render_duplicate_job_cards(client) -> None:
    from app.dashboard.components.job_card import render_job_card

    job = {
        "id": 17,
        "company": "Example AI",
        "title": "Applied AI Engineer",
        "location": "Hong Kong",
        "url": None,
        "status": "Saved",
        "classification": {"category": "Applied AI Engineer", "confidence": 0.9},
        "analysis": {
            "fit_score": 82,
            "summary": "Stored summary",
            "evidence": [],
            "strengths": [],
            "gaps": [],
        },
    }
    render_job_card(job, region="dashboard-next", locale="en", client=client)
    render_job_card(job, region="dashboard-recent", locale="en", client=client)


def _render_route(client, route, locale) -> None:
    from app.dashboard.streamlit_app import page_renderers

    page_renderers()[route](client, locale)


def _rendered_text(app: AppTest) -> str:
    values: list[str] = []
    for kind in (
        "title",
        "subheader",
        "caption",
        "markdown",
        "info",
        "warning",
        "error",
        "success",
    ):
        values.extend(str(element.value) for element in app.get(kind))
    return "\n".join(values)


def test_url_intake_renders_editable_preview_and_cancel_has_zero_writes() -> None:
    client = RecordingClient()
    app = AppTest.from_function(_render_analyze, args=(client,)).run()

    app.text_input(key="analyze-url").set_value("https://example.com/jobs/forward-deployed")
    app.button(key="analyze-url-submit").click().run()

    assert app.text_input(key="analyze-preview-company").value == "AWS"
    assert not [call for call in client.calls if call[:2] == ("POST", "/api/v1/jobs")]

    app.button(key="analyze-preview-cancel").click().run()

    assert not [call for call in client.calls if call[:2] == ("POST", "/api/v1/jobs")]
    assert app.text_input(key="analyze-url").value == ""

    app.text_input(key="analyze-url").set_value("https://example.com/jobs/forward-deployed")
    app.button(key="analyze-url-submit").click().run()
    app.text_input(key="analyze-preview-company").set_value("Example Robotics")
    app.button(key="analyze-preview-confirm").click().run()

    writes = [call for call in client.calls if call[:2] == ("POST", "/api/v1/jobs")]
    assert len(writes) == 1
    assert writes[0][2]["company"] == "Example Robotics"


def test_chinese_job_card_localizes_system_copy_but_keeps_source_evidence() -> None:
    app = AppTest.from_function(_render_chinese_job_card, args=(RecordingClient(),)).run()
    text = _rendered_text(app)

    assert "强烈建议申请" in text
    status = app.selectbox(key="test-job-status-7")
    assert status.format_func(status.value) == "已收藏"
    assert "客户部署" in text
    assert "未发现明确的优势信号" in text
    assert "AI 深度证据不足" in text
    assert "未发现明显能力差距" in text
    assert "ev-1: Build production AI systems with customers." in text
    assert "Stored English summary" not in text
    assert "CUSTOMER_DEPLOYMENT" not in text
    assert "AI_DEPTH_EVIDENCE_WEAK" not in text
    assert "NO_MATCHED_GREEN_FLAGS" not in text
    assert "NO_WEAK_DIMENSIONS" not in text


def test_job_card_displays_persisted_recommendation_instead_of_recomputing_score_band() -> None:
    app = AppTest.from_function(
        _render_inconsistent_recommendation_job_card,
        args=(RecordingClient(),),
    ).run()
    text = _rendered_text(app)

    assert "Selective" in text
    assert "Strong Apply" not in text


def test_dashboard_renders_due_follow_ups_and_metric_drill_through() -> None:
    app = AppTest.from_function(_render_dashboard, args=(DashboardClient(),)).run()
    text = _rendered_text(app)

    assert "到期跟进" in text
    assert "2026年9月1日" in text
    assert "Send hiring manager note" in text
    assert len([button for button in app.button if "dashboard-drill-" in str(button.key)]) == 8

    app.button(key="dashboard-drill-applied").click().run()
    assert app.session_state["ui.route"] == "jobs"
    assert app.session_state["ui.jobs.status"] == "Applied"

    app = AppTest.from_function(_render_dashboard, args=(DashboardClient(),)).run()
    app.button(key="dashboard-drill-skill-gap-1").click().run()
    assert app.session_state["ui.route"] == "jobs"
    assert app.session_state["ui.jobs.gap"] == "OWNERSHIP_EVIDENCE_WEAK"

    app = AppTest.from_function(_render_dashboard, args=(DashboardClient(),)).run()
    app.button(key="dashboard-drill-hiring-trend-0").click().run()
    assert app.session_state["ui.route"] == "jobs"
    assert app.session_state["ui.jobs.created_week"] == "2026-38"

    app = AppTest.from_function(_render_dashboard, args=(DashboardClient(),)).run()
    app.button(key="dashboard-follow-up-9").click().run()
    assert app.session_state["ui.route"] == "jobs"
    assert app.session_state["ui.selected_job_id"] == 9


def test_high_priority_drill_through_uses_persisted_recommendation_band() -> None:
    dashboard = AppTest.from_function(_render_dashboard, args=(DashboardClient(),)).run()

    dashboard.button(key="dashboard-drill-high").click().run()

    assert dashboard.session_state["ui.jobs.priority_only"] is True
    assert "ui.jobs.minimum_score" not in dashboard.session_state

    jobs = AppTest.from_function(_render_jobs, args=(HighPriorityJobsClient(),))
    jobs.session_state["ui.jobs.priority_only"] = True
    jobs.run()
    text = _rendered_text(jobs)

    assert "Strong Apply at 70" in text
    assert "Selective at 84" not in text
    assert "Legacy Strong Apply" not in text


def test_full_shell_high_priority_drill_through_renders_exact_dashboard_cohort() -> None:
    app = AppTest.from_function(_render_shell, args=(DashboardToJobsClient(),))
    app.session_state["ui.locale"] = "en"
    app.run()

    app.button(key="dashboard-drill-high").click().run()
    text = _rendered_text(app)

    assert app.title[0].value == translate("en", "page.jobs.title")
    assert "Strong Apply at 70" in text
    assert "Selective at 84" not in text
    assert "Legacy Strong Apply" not in text


def test_copilot_failure_is_localized_and_renders_retry_without_escaping() -> None:
    app = AppTest.from_function(_render_failing_copilot, args=(FailingCopilotClient(),)).run()
    text = _rendered_text(app)

    assert not app.exception
    assert "已保存的数据未受影响" in text
    assert "backend exploded in English" not in text
    assert app.button(key="copilot-retry").label == "重试"


def test_pending_copilot_confirmation_is_the_only_rendered_primary_action() -> None:
    app = AppTest.from_function(_render_pending_copilot, args=(ProposalClient(),))
    app.session_state["copilot.pending_proposal"] = _pending_proposal()
    app.run()
    app.checkbox(key="copilot-manage-session-3").check().run()

    primary_labels = [button.label for button in app.button if button.proto.type == "primary"]
    assert primary_labels == ["确认操作"]


def test_chinese_copilot_confirmation_localizes_machine_values_and_side_effects() -> None:
    app = AppTest.from_function(_render_pending_copilot, args=(ProposalClient(),))
    app.session_state["copilot.pending_proposal"] = _pending_proposal()
    app.run()
    text = _rendered_text(app)

    for localized in (
        "职位 #17",
        "状态：新增",
        "状态：已收藏",
        "更新职位状态",
        "添加一条申请时间线记录",
    ):
        assert localized in text
    for machine_value in ("record_type", "status", "New", "Saved", "Update the job status"):
        assert machine_value not in text


def test_chinese_copilot_confirmation_localizes_watchlist_enums_and_private_purpose() -> None:
    proposal = {
        "id": 9,
        "proposal_type": "update_watchlist_company",
        "target": {"record_type": "watchlist_company", "record_id": 4},
        "current_value": {
            "company_type": "financial_institution",
            "strategic_priority": "core_target",
            "action_window": "apply_now",
        },
        "proposed_value": {
            "company_type": "fintech_product",
            "strategic_priority": "monitor",
            "action_window": "stretch_apply",
        },
        "side_effects": ["Update the selected Watch List company"],
        "private_data_usage": {
            "included": True,
            "record_ids": [2],
            "purpose": "Generate a tailored CV from selected private CV evidence",
        },
    }
    app = AppTest.from_function(_render_pending_copilot, args=(ProposalClient(),))
    app.session_state["copilot.pending_proposal"] = proposal
    app.run()
    text = _rendered_text(app)

    for localized in (
        "公司类型：金融机构",
        "战略优先级：核心目标",
        "行动窗口：立即申请",
        "公司类型：金融科技 / 产品",
        "战略优先级：持续观察",
        "行动窗口：尝试申请",
        "从所选私密 CV 证据生成定制 CV",
    ):
        assert localized in text
    for machine_value in (
        "financial_institution",
        "core_target",
        "apply_now",
        "Generate a tailored CV from selected private CV evidence",
    ):
        assert machine_value not in text


def test_copilot_confirmation_persists_success_and_links_to_result() -> None:
    app = AppTest.from_function(_render_pending_copilot, args=(ProposalClient(),))
    app.session_state["copilot.pending_proposal"] = _pending_proposal()
    app.run()
    app.button(key="copilot-confirm-8").click().run()

    assert "职位 #17 的申请状态已更新。" in _rendered_text(app)
    assert app.button(key="copilot-view-result").label == "查看结果"
    app.button(key="copilot-view-result").click().run()
    assert app.session_state["ui.route"] == "jobs"
    assert app.session_state["ui.selected_job_id"] == 17


@pytest.mark.parametrize(
    ("proposal_type", "result_record_ids", "message", "route"),
    [
        ("save_job", {"job": [17]}, "Saved job #17.", "jobs"),
        (
            "change_application_status",
            {"job": [17], "application_event": [22]},
            "Updated the application status for job #17.",
            "jobs",
        ),
        (
            "create_application_event",
            {"job": [17], "application_event": [23]},
            "Added application event #23 for job #17.",
            "jobs",
        ),
        (
            "set_follow_up",
            {"job": [17], "application_event": [24]},
            "Set the follow-up for job #17.",
            "jobs",
        ),
        (
            "add_watchlist_company",
            {"watchlist_company": [4]},
            "Created Watch List company #4.",
            "watchlist",
        ),
        (
            "update_watchlist_company",
            {"watchlist_company": [4]},
            "Updated Watch List company #4.",
            "watchlist",
        ),
        (
            "reanalyze_job",
            {"job": [17], "analysis": [8]},
            "Created analysis #8 for job #17.",
            "jobs",
        ),
        (
            "generate_tailored_cv",
            {"job": [17], "generated_cv": [6]},
            "Generated tailored CV #6 for job #17.",
            "cv_library",
        ),
        (
            "create_action_item",
            {"action_item": [31]},
            "Created action item #31.",
            "dashboard",
        ),
    ],
)
def test_copilot_success_identifies_each_durable_result_and_links_to_its_destination(
    proposal_type: str,
    result_record_ids: dict[str, list[int]],
    message: str,
    route: str,
) -> None:
    app = AppTest.from_function(_render_copilot_result, args=(ProposalClient(),))
    app.session_state["copilot.last_result"] = {
        "proposal_type": proposal_type,
        "result_record_ids": result_record_ids,
    }
    app.run()

    assert message in _rendered_text(app)
    app.button(key="copilot-view-result").click().run()
    assert app.session_state["ui.route"] == route


def test_copilot_action_item_result_renders_the_exact_selected_record_on_dashboard() -> None:
    client = ResultDestinationClient()
    app = AppTest.from_function(_render_shell, args=(client,))
    app.session_state["ui.locale"] = "en"
    app.session_state["copilot.last_result"] = {
        "proposal_type": "create_action_item",
        "result_record_ids": {"action_item": [31]},
    }
    app.run()

    app.button(key="desktop-copilot-view-result").click().run()
    text = _rendered_text(app)

    assert app.session_state["ui.route"] == "dashboard"
    assert app.session_state["ui.selected_action_item_id"] == 31
    assert "Action item #31" in text
    assert "Follow up with the hiring team" in text
    assert "Send the architecture portfolio before Friday." in text


def test_copilot_generated_cv_result_renders_the_exact_selected_artifact_in_library() -> None:
    client = ResultDestinationClient()
    app = AppTest.from_function(_render_shell, args=(client,))
    app.session_state["ui.locale"] = "en"
    app.session_state["copilot.last_result"] = {
        "proposal_type": "generate_tailored_cv",
        "result_record_ids": {"job": [17], "generated_cv": [6]},
    }
    app.run()

    app.button(key="desktop-copilot-view-result").click().run()
    text = _rendered_text(app)

    assert app.session_state["ui.route"] == "cv_library"
    assert app.session_state["cv.selected_generated_id"] == 6
    assert "Generated CV #6" in text
    assert "Example AI—Applied AI Engineer-chatgpt.docx" in text
    download = app.get("link_button")
    assert len(download) == 1
    assert download[0].proto.url == (
        "http://test/api/v1/generated-cvs/6/"
        "Example%20AI%E2%80%94Applied%20AI%20Engineer-chatgpt.docx"
    )


def test_cv_library_formats_visible_dates_for_chinese() -> None:
    app = AppTest.from_function(_render_cv_library, args=(CVClient(),)).run()
    text = _rendered_text(app)

    assert "2026年9月3日" in text
    assert "2026-09-03" not in text


def test_shell_renders_language_health_and_settings_in_top_utility_area() -> None:
    app = AppTest.from_function(_render_shell, args=(ShellClient(),))
    app.session_state["ui.locale"] = "zh-Hans"
    app.run()

    assert not app.exception
    assert len(app.sidebar.get("segmented_control")) == 0
    assert app.segmented_control(key="ui-language-control").value == "中文"
    assert app.button(key="top-settings").label == "设置"
    assert translate("zh-Hans", "app.health.ready") in _rendered_text(app)


def test_fresh_base_url_session_restores_cookie_locale_in_rendered_shell() -> None:
    app = AppTest.from_function(_render_shell_with_cookie, args=(ShellClient(),)).run()

    assert not app.exception
    assert app.segmented_control(key="ui-language-control").value == "中文"
    assert app.title[0].value == translate("zh-Hans", "page.dashboard.title")


def test_language_switch_renders_executable_cookie_persistence_document() -> None:
    """Catch passing cookie JavaScript to a URL-only iframe where it cannot execute."""
    app = AppTest.from_function(_render_cookie_persistence).run()

    cookie_documents = app.get("html")
    assert len(cookie_documents) == 1
    assert cookie_documents[0].proto.unsafe_allow_javascript is True
    assert (
        "document.cookie='roleradar_locale=zh-Hans; Path=/; Max-Age=31536000; SameSite=Lax'"
        in cookie_documents[0].proto.body
    )


def test_language_switch_atomically_renders_the_complete_shell_in_chinese() -> None:
    app = AppTest.from_function(_render_shell, args=(ShellClient(),)).run()

    app.segmented_control(key="ui-language-control").set_value("中文").run()
    text = _rendered_text(app)

    assert not app.exception
    assert app.title[0].value == translate("zh-Hans", "page.dashboard.title")
    assert app.button(key="top-settings").label == "设置"
    assert translate("zh-Hans", "app.health.ready") in text


def test_shell_navigation_clears_stale_job_from_rendered_copilot_context() -> None:
    client = ShellClient()
    app = AppTest.from_function(_render_shell, args=(client,))
    app.session_state["ui.locale"] = "en"
    app.session_state["ui.route"] = "jobs"
    app.session_state["ui.selected_job_id"] = 17
    app.run()

    app.sidebar.radio(key="ui-navigation").set_value("profile").run()

    assert app.session_state["ui.route"] == "profile"
    assert "ui.selected_job_id" not in app.session_state
    context_paths = [
        path for method, path, _ in client.calls if method == "GET" and "/copilot/context?" in path
    ]
    assert context_paths[-1].startswith("/api/v1/copilot/context?route=profile")
    assert "job_id=" not in context_paths[-1]


def test_settings_shortcut_clears_stale_job_from_rendered_copilot_context() -> None:
    client = ShellClient()
    app = AppTest.from_function(_render_shell, args=(client,))
    app.session_state["ui.locale"] = "en"
    app.session_state["ui.route"] = "jobs"
    app.session_state["ui-navigation"] = "jobs"
    app.session_state["ui.selected_job_id"] = 17
    app.run()

    app.button(key="top-settings").click().run()

    assert app.session_state["ui.route"] == "profile"
    assert "ui.selected_job_id" not in app.session_state
    context_paths = [
        path for method, path, _ in client.calls if method == "GET" and "/copilot/context?" in path
    ]
    assert context_paths[-1].startswith("/api/v1/copilot/context?route=profile")
    assert "job_id=" not in context_paths[-1]


def test_page_api_error_is_localized_without_raw_backend_detail() -> None:
    app = AppTest.from_function(_render_shell, args=(FailingPageClient(),))
    app.session_state["ui.locale"] = "zh-Hans"
    app.run()
    text = _rendered_text(app)

    assert not app.exception
    assert "已保存的数据未受影响" in text
    assert "raw backend failure in English" not in text
    assert app.button(key="page-retry-dashboard").label == "重试"


def test_duplicate_job_cards_render_real_widgets_without_key_collisions() -> None:
    app = AppTest.from_function(_render_duplicate_job_cards, args=(RecordingClient(),)).run()

    assert not app.exception
    assert app.selectbox(key="dashboard-next-status-17")
    assert app.selectbox(key="dashboard-recent-status-17")


def test_chinese_digest_localizes_generated_trends_and_preserves_company_names() -> None:
    app = AppTest.from_function(_render_chinese_digest, args=(DigestClient(),)).run()
    text = _rendered_text(app)

    assert not app.exception
    assert "AI 深度证据不足：2 个职位" in text
    assert "应用型 AI 工程师：2 个新职位" in text
    assert "new role(s)" not in text
    assert "AI_DEPTH_EVIDENCE_WEAK" not in text


@pytest.mark.parametrize(
    ("filter_kind", "localized", "machine_value"),
    [
        ("status", "已申请", "Applied"),
        ("gap", "AI 深度证据不足", "AI_DEPTH_EVIDENCE_WEAK"),
    ],
)
def test_jobs_drill_through_filter_label_is_localized(
    filter_kind: str, localized: str, machine_value: str
) -> None:
    app = AppTest.from_function(
        _render_chinese_jobs_filter,
        args=(RecordingClient(), filter_kind),
    ).run()
    text = _rendered_text(app)

    assert localized in text
    assert machine_value not in text


@pytest.mark.parametrize(
    ("locale", "route"),
    [
        (locale, route)
        for locale in ("en", "zh-Hans")
        for route in (
            "dashboard",
            "analyze",
            "jobs",
            "applications",
            "watchlist",
            "cv_library",
            "digest",
            "profile",
        )
    ],
)
def test_every_route_renders_its_localized_h1_and_empty_state(locale: str, route: str) -> None:
    app = AppTest.from_function(_render_route, args=(ShellClient(), route, locale)).run()

    assert not app.exception
    assert len(app.title) == 1
    assert app.title[0].value == translate(locale, f"page.{route}.title")


@pytest.mark.parametrize("locale", ["en", "zh-Hans"])
@pytest.mark.parametrize(
    "route",
    [
        "dashboard",
        "analyze",
        "jobs",
        "applications",
        "watchlist",
        "cv_library",
        "digest",
        "profile",
    ],
)
def test_copilot_route_context_uses_localized_navigation_label(locale: str, route: str) -> None:
    from app.dashboard.components.navigation import navigation_items

    app = AppTest.from_function(_render_shell, args=(ShellClient(),))
    app.session_state["ui.locale"] = locale
    app.session_state["ui.route"] = route
    app.run()
    label = next(item.label for item in navigation_items(locale) if item.route == route)
    expected = f"{translate(locale, 'copilot.context')}: {label}"
    assert not app.exception
    assert expected in _rendered_text(app)
