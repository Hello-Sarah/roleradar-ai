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
                "skill_gap_trends": [["AI_DEPTH_EVIDENCE_WEAK", 1]],
                "weekly_hiring_trends": [{"week": "2026-39", "jobs": 1, "average_fit_score": 82.0}],
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


def _render_dashboard(client) -> None:
    from app.dashboard.pages.dashboard import render_page

    render_page(client, "zh-Hans")


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


def test_dashboard_renders_due_follow_ups_and_metric_drill_through() -> None:
    app = AppTest.from_function(_render_dashboard, args=(DashboardClient(),)).run()
    text = _rendered_text(app)

    assert "到期跟进" in text
    assert "2026年9月1日" in text
    assert "Send hiring manager note" in text
    assert len([button for button in app.button if "dashboard-drill-" in str(button.key)]) == 6

    app.button(key="dashboard-drill-applied").click().run()
    assert app.session_state["ui.route"] == "jobs"
    assert app.session_state["ui.jobs.status"] == "Applied"

    app = AppTest.from_function(_render_dashboard, args=(DashboardClient(),)).run()
    app.button(key="dashboard-drill-skill-gap").click().run()
    assert app.session_state["ui.route"] == "jobs"
    assert app.session_state["ui.jobs.gap"] == "AI_DEPTH_EVIDENCE_WEAK"


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

    assert "保存成功" in _rendered_text(app)
    assert app.button(key="copilot-view-result").label == "查看结果"
    app.button(key="copilot-view-result").click().run()
    assert app.session_state["ui.route"] == "jobs"
    assert app.session_state["ui.selected_job_id"] == 17


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
