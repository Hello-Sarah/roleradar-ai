"""Locale resolution and catalog-backed product copy."""

import json
import logging
import os
from collections.abc import Mapping
from pathlib import Path
from string import Formatter

from app.schemas import Locale

logger = logging.getLogger(__name__)

_CATALOG_DIRECTORY = Path(__file__).parent / "catalogs"
_SUPPORTED_LOCALES: tuple[Locale, ...] = ("en", "zh-Hans")


class CatalogParityError(ValueError):
    """Raised when product catalogs cannot provide equivalent localized copy."""


class MissingTranslationError(KeyError):
    """Raised in tests when a product translation key is absent."""


class TranslationInterpolationError(ValueError):
    """Raised when a translation receives missing or unexpected named values."""


def _load_catalog(locale: Locale) -> dict[str, str]:
    with (_CATALOG_DIRECTORY / f"{locale}.json").open(encoding="utf-8") as catalog_file:
        loaded = json.load(catalog_file)
    if not isinstance(loaded, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in loaded.items()
    ):
        raise CatalogParityError(f"Catalog {locale!r} must contain string keys and values")
    return loaded


_CATALOGS: dict[Locale, dict[str, str]] = {
    locale: _load_catalog(locale) for locale in _SUPPORTED_LOCALES
}


def _placeholder_names(message: str) -> set[str]:
    """Return the only supported interpolation contract: simple named placeholders."""
    try:
        fields = Formatter().parse(message)
        names: set[str] = set()
        for _, field_name, format_spec, conversion in fields:
            if field_name is None:
                continue
            if (
                not field_name
                or not field_name.isidentifier()
                or format_spec
                or conversion is not None
            ):
                raise TranslationInterpolationError(
                    "Translations support only simple named placeholders such as {record}"
                )
            names.add(field_name)
    except ValueError as exc:
        raise TranslationInterpolationError("Translation contains invalid format syntax") from exc
    return names


def assert_catalog_parity() -> None:
    """Ensure every locale has the same keys and interpolation contract as English."""
    english = _CATALOGS["en"]
    for locale in _SUPPORTED_LOCALES:
        catalog = _CATALOGS[locale]
        missing = sorted(set(english) - set(catalog))
        unexpected = sorted(set(catalog) - set(english))
        if missing or unexpected:
            raise CatalogParityError(
                f"Catalog {locale!r} key mismatch: missing={missing}, unexpected={unexpected}"
            )
        for key, english_message in english.items():
            try:
                english_placeholders = _placeholder_names(english_message)
                locale_placeholders = _placeholder_names(catalog[key])
            except TranslationInterpolationError as exc:
                raise CatalogParityError(
                    f"Catalog {locale!r} has an invalid interpolation contract for key {key!r}"
                ) from exc
            if english_placeholders != locale_placeholders:
                raise CatalogParityError(
                    f"Catalog {locale!r} interpolation mismatch for key {key!r}"
                )


def _normalized_locale(value: str | None) -> Locale | None:
    if value is None:
        return None
    normalized = value.strip().replace("_", "-").casefold()
    if normalized == "en":
        return "en"
    if normalized == "zh" or normalized.startswith("zh-"):
        return "zh-Hans"
    return None


def resolve_locale(explicit: str | None, browser: str | None) -> Locale:
    """Choose a supported locale, preserving an explicit choice over browser preference."""
    return _normalized_locale(explicit) or _normalized_locale(browser) or "en"


def _is_test_environment() -> bool:
    return "PYTEST_CURRENT_TEST" in os.environ


def _validate_values(template: str, values: Mapping[str, object]) -> None:
    expected = _placeholder_names(template)
    received = set(values)
    missing = sorted(expected - received)
    unexpected = sorted(received - expected)
    if missing or unexpected:
        raise TranslationInterpolationError(
            f"Translation values mismatch: missing={missing}, unexpected={unexpected}"
        )


def translate(locale: Locale, key: str, **values: object) -> str:
    """Translate a stable presentation key while preserving machine values outside the catalog."""
    catalog = _CATALOGS[locale]
    message = catalog.get(key)
    if message is None:
        if _is_test_environment():
            raise MissingTranslationError(key)
        logger.error("Missing translation key=%s locale=%s; falling back to English", key, locale)
        message = _CATALOGS["en"].get(key, key)
    _validate_values(message, values)
    return message.format(**values)
