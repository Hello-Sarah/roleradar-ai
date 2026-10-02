import logging
from datetime import UTC, datetime

import pytest

from app.analysis.classifier import classify_job
from app.i18n import service
from app.i18n.service import (
    CatalogParityError,
    MissingTranslationError,
    TranslationInterpolationError,
    assert_catalog_parity,
    resolve_locale,
    translate,
)
from app.schemas import (
    ApplicationStatus,
    CandidateProfileRead,
    Locale,
    Recommendation,
)
from app.scoring.engine import score_job

REQUIRED_PRESENTATION_KEYS = frozenset(
    {
        "accessibility.close_dialog",
        "accessibility.open_copilot",
        "accessibility.open_navigation",
        "action.add",
        "action.analyze",
        "action.back",
        "action.cancel",
        "action.close",
        "action.confirm",
        "action.delete",
        "action.disable",
        "action.download",
        "action.edit",
        "action.enable",
        "action.extract_fields",
        "action.generate_tailored_cv",
        "action.reanalyze",
        "action.retry",
        "action.save",
        "action.save_and_analyze",
        "action.start_over",
        "action.view_posting",
        "analysis.analysis_pending",
        "analysis.confidence",
        "analysis.evidence",
        "analysis.gaps",
        "analysis.green_flags",
        "analysis.low_confidence",
        "analysis.needs_review",
        "analysis.recommended_action",
        "analysis.red_flags",
        "analysis.strengths",
        "analysis.unclassified",
        "application.channel",
        "application.follow_up_date",
        "application.history",
        "application.notes",
        "application.status",
        "application_status.applied",
        "application_status.ignored",
        "application_status.interview",
        "application_status.new",
        "application_status.offer",
        "application_status.rejected",
        "application_status.saved",
        "application_channel.company_website",
        "application_channel.email",
        "application_channel.linkedin",
        "application_channel.other",
        "application_channel.recruiter",
        "application_channel.referral",
        "common.language",
        "common.none",
        "common.not_available",
        "common.optional",
        "component.disabled.missing_prerequisite",
        "component.empty.description",
        "component.empty.title",
        "component.error.description",
        "component.error.title",
        "component.loading",
        "component.success",
        "copilot.action.add_application_event",
        "copilot.action.create_learning_item",
        "copilot.action.generate_tailored_cv",
        "copilot.action.reanalyze_job",
        "copilot.action.save_job",
        "copilot.action.update_application_status",
        "copilot.action.update_watch_list_company",
        "copilot.confirmation.cancel",
        "copilot.confirmation.confirm",
        "copilot.confirmation.current_value",
        "copilot.confirmation.private_data",
        "copilot.confirmation.proposed_value",
        "copilot.confirmation.side_effects",
        "copilot.confirmation.summary",
        "copilot.confirmation.target",
        "copilot.error.ambiguous_target",
        "copilot.error.model_unavailable",
        "copilot.error.missing_required_fields",
        "copilot.error.unavailable_action",
        "copilot.name",
        "copilot.session.create",
        "copilot.session.delete",
        "copilot.session.rename",
        "copilot.session.title",
        "cv.download_tailored",
        "cv.empty_library",
        "cv.file_type.docx",
        "cv.file_type.pdf",
        "cv.file_type.txt",
        "cv.generate_tailored",
        "cv.generated",
        "cv.generated_path",
        "cv.generation_failed",
        "cv.library",
        "cv.library_path",
        "cv.no_job_selected",
        "cv.scan.added",
        "cv.scan.discovered",
        "cv.scan.failed",
        "cv.scan.folder",
        "cv.scan.summary",
        "cv.scan.unchanged",
        "cv.scan.updated",
        "cv.scan_folder",
        "cv.scan_in_progress",
        "cv.source_path",
        "cv.source_files_read_only",
        "cv.tailored",
        "cv.target_job",
        "dashboard.follow_ups_due",
        "dashboard.high_priority",
        "dashboard.high_priority_jobs",
        "dashboard.hiring_trends",
        "dashboard.interviews",
        "dashboard.new",
        "dashboard.next_action",
        "dashboard.recently_added",
        "dashboard.skill_gap_trends",
        "digest.emerging_skills",
        "digest.generated_at",
        "digest.high_priority_new_jobs",
        "digest.hiring_trends",
        "digest.new_companies",
        "digest.no_signal",
        "error.duplicate_job",
        "error.invalid_url",
        "error.safe_url_required",
        "error.unavailable",
        "form.company",
        "form.description",
        "form.job_url",
        "form.location",
        "form.title",
        "job.intake.analyze_from_url",
        "job.error.extraction_failed",
        "job.error.url_fetch_failed",
        "job.error.validation_failed",
        "job.intake.job_link",
        "job.intake.paste_complete_posting",
        "job.intake.paste_job_text",
        "job.intake.reading_page",
        "job.intake.review_before_save",
        "job.intake.url_help",
        "job.review.confirm_and_analyze",
        "job.review.nothing_saved",
        "job.review.posting_date",
        "job.review.review_extracted_fields",
        "job.success.analysis_complete",
        "nav.analyze_job",
        "nav.applications",
        "nav.cv_library",
        "nav.dashboard",
        "nav.digest",
        "nav.jobs",
        "nav.profile",
        "nav.watch_list",
        "profile.development_gaps",
        "profile.domain_strengths",
        "profile.future_locations",
        "profile.name",
        "profile.preferred_locations",
        "profile.save",
        "profile.save_success",
        "profile.target_roles",
        "profile.technical_strengths",
        "recommendation.apply_now",
        "recommendation.build_skills_first",
        "recommendation.consider",
        "recommendation.skip",
        "score.action_window",
        "score.ai_depth",
        "score.build_ship",
        "score.career_option_value",
        "score.must_apply",
        "score.ownership",
        "score.product_exposure",
        "score.selective",
        "score.skip",
        "score.strong_apply",
        "score.technical_exposure",
        "score.total",
        "score.warning.ai_title_pmo_substance",
        "score.evidence_by_dimension",
        "score.missing_evidence",
        "score.positive_evidence",
        "score.scoring_version",
        "score.green_flag.agentic",
        "score.green_flag.ai_platform",
        "score.green_flag.api_integration",
        "score.green_flag.customer_deployment",
        "score.green_flag.end_to_end_ownership",
        "score.green_flag.evaluation",
        "score.green_flag.hands_on",
        "score.green_flag.llm",
        "score.green_flag.production",
        "score.green_flag.product_roadmap",
        "score.green_flag.proof_of_concept",
        "score.green_flag.rag",
        "score.green_flag.rapid_prototyping",
        "score.green_flag.technical_architecture",
        "score.green_flag.tool_calling",
        "score.green_flag.user_discovery",
        "score.green_flag.workflow_orchestration",
        "score.green_flag.zero_to_one",
        "score.red_flag.coordination",
        "score.red_flag.documentation",
        "score.red_flag.governance",
        "score.red_flag.pmo",
        "score.red_flag.reporting",
        "score.red_flag.requirement_gathering",
        "score.red_flag.status_tracking",
        "score.red_flag.steering_committee",
        "score.red_flag.vendor_management",
        "validation.application.invalid_channel",
        "validation.application.invalid_date",
        "validation.application.invalid_status",
        "validation.application.invalid_follow_up_date",
        "validation.application.notes_too_long",
        "validation.description_too_short",
        "validation.field_required",
        "validation.job.duplicate",
        "validation.job.invalid_posting_date",
        "validation.job.invalid_source",
        "watch_list.action_window.apply_after_us_relocation",
        "watch_list.action_window.apply_in_3_to_6_months",
        "watch_list.action_window.apply_now",
        "watch_list.action_window.relationship_only",
        "watch_list.action_window.stretch_apply",
        "watch_list.company_type.ai_native_forward_deployed",
        "watch_list.company_type.cloud_data_enterprise_ai",
        "watch_list.company_type.consulting_professional_services",
        "watch_list.company_type.financial_institution",
        "watch_list.company_type.fintech_product",
        "watch_list.confirm_delete",
        "watch_list.create_company",
        "watch_list.disable_instead",
        "watch_list.edit_company",
        "watch_list.eligibility.eligible",
        "watch_list.eligibility.future",
        "watch_list.eligibility.ineligible",
        "watch_list.eligibility.unclear",
        "watch_list.lifecycle.disabled",
        "watch_list.lifecycle.enabled",
        "watch_list.priority.core_target",
        "watch_list.priority.monitor",
        "watch_list.priority.opportunistic",
        "watch_list.priority.strict_filter",
        "watch_list.source_state.degraded",
        "watch_list.source_state.disabled",
        "watch_list.source_state.structured_ready",
        "watch_list.source_state.unverified",
        "watch_list.source_state.verified_manual",
    }
)


def _profile() -> CandidateProfileRead:
    now = datetime.now(UTC)
    return CandidateProfileRead(
        id=1,
        name="Candidate",
        target_roles=["Applied AI Engineer"],
        preferred_locations=["Hong Kong"],
        future_locations=[],
        domain_strengths=["Banking"],
        technical_strengths=["Python", "SQL"],
        development_gaps=["Docker"],
        created_at=now,
        updated_at=now,
    )


def test_explicit_locale_wins_over_browser() -> None:
    """This fails if browser negotiation takes precedence over a valid saved choice."""
    assert resolve_locale("en", "zh-CN") == "en"


@pytest.mark.parametrize(
    ("browser", "expected"),
    [("zh-CN", "zh-Hans"), ("zh", "zh-Hans"), ("en-GB", "en"), (None, "en")],
)
def test_browser_locale_uses_chinese_only_for_chinese_preferences(
    browser: str | None, expected: Locale
) -> None:
    """This fails if a Chinese browser preference does not receive simplified Chinese."""
    assert resolve_locale(None, browser) == expected


def test_catalogs_have_identical_keys() -> None:
    """This fails if either language misses user-facing product copy."""
    assert_catalog_parity()


def test_catalogs_cover_the_required_v1_presentation_surface() -> None:
    """This fails if both matching catalogs omit a V1 presentation key."""
    for locale, catalog in service._CATALOGS.items():
        assert not REQUIRED_PRESENTATION_KEYS - set(catalog), locale


def test_recommendation_translation() -> None:
    """This fails if the canonical Must Apply label is not localized."""
    assert translate("zh-Hans", "score.must_apply") == "必须申请"


def test_translation_interpolates_named_values() -> None:
    """This fails if localized messages cannot safely render named record data."""
    translated = translate(
        "en", "copilot.confirmation.summary", action="change status", target="#42"
    )
    assert translated == ("You are about to change status #42.")


@pytest.mark.parametrize(
    "template",
    ["{}", "{0}", "{record.id}", "{record[id]}", "{record!r}", "{record:>10}"],
)
def test_catalog_parity_rejects_non_named_or_unsupported_placeholders(
    monkeypatch: pytest.MonkeyPatch, template: str
) -> None:
    """This fails if unsafe format syntax can enter a catalog without a contract error."""
    for locale in ("en", "zh-Hans"):
        monkeypatch.setitem(service._CATALOGS[locale], "score.must_apply", template)

    with pytest.raises(CatalogParityError):
        assert_catalog_parity()


def test_translation_rejects_missing_or_extra_named_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """This fails if a translated record message accepts an incomplete or stray value."""
    monkeypatch.setitem(service._CATALOGS["en"], "score.must_apply", "Apply {record}")

    with pytest.raises(TranslationInterpolationError):
        translate("en", "score.must_apply")
    with pytest.raises(TranslationInterpolationError):
        translate("en", "score.must_apply", record="#42", extra="ignored")


def test_missing_translation_raises_during_tests() -> None:
    """This fails if missing translation keys become silently invisible in CI."""
    with pytest.raises(MissingTranslationError):
        translate("zh-Hans", "missing.key")


def test_production_missing_locale_entry_logs_and_falls_back_to_english(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """This fails if a production locale miss cannot still render the English message."""
    monkeypatch.setattr(logging.root.manager, "disable", logging.NOTSET)
    monkeypatch.setattr(service.logger, "disabled", False)
    caplog.set_level(logging.ERROR, logger=service.logger.name)
    monkeypatch.setattr(service, "_is_test_environment", lambda: False)
    zh_catalog = dict(service._CATALOGS["zh-Hans"])
    zh_catalog.pop("score.must_apply")
    monkeypatch.setitem(service._CATALOGS, "zh-Hans", zh_catalog)

    service.logger.addHandler(caplog.handler)
    try:
        assert translate("zh-Hans", "score.must_apply") == "Must Apply"
        assert "score.must_apply" in caplog.text
    finally:
        service.logger.removeHandler(caplog.handler)


@pytest.mark.parametrize("locale", ["en", "zh-Hans"])
def test_locale_does_not_change_stored_values_or_deterministic_score(locale: Locale) -> None:
    """This fails if presentation language leaks into stored enums or scoring inputs."""
    classification = classify_job(
        "Applied AI Engineer", "Build Python and SQL systems for Banking using Docker."
    )
    result = score_job(
        title="Applied AI Engineer",
        location="Hong Kong",
        description="Build Python and SQL systems for Banking using Docker.",
        classification=classification,
        profile=_profile(),
    )

    assert locale in ("en", "zh-Hans")
    assert ApplicationStatus.APPLIED.value == "Applied"
    assert Recommendation.APPLY_NOW.value == "Apply Now"
    assert result.fit_score == 77
    assert result.recommendation == Recommendation.APPLY_NOW
