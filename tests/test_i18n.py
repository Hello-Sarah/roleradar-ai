import logging
from datetime import UTC, datetime

import pytest

from app.analysis.classifier import classify_job
from app.i18n import service
from app.i18n.service import (
    MissingTranslationError,
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


def test_recommendation_translation() -> None:
    """This fails if the canonical Must Apply label is not localized."""
    assert translate("zh-Hans", "score.must_apply") == "必须申请"


def test_translation_interpolates_named_values() -> None:
    """This fails if localized messages cannot safely render named record data."""
    translated = translate(
        "en", "copilot.confirmation.summary", action="change status", target="#42"
    )
    assert translated == (
        "You are about to change status #42."
    )


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
