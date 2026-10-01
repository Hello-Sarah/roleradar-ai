"""Versioned contracts and validation for committed evaluation datasets."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Suite = Literal["jd", "cv_pair", "copilot_normal", "copilot_adversarial"]
Locale = Literal["en", "zh-Hans"]
MINIMUM_SUITE_COUNTS = {"jd": 60, "cv_pair": 20, "copilot_normal": 30, "copilot_adversarial": 20}
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE = re.compile(r"(?<!\w)(?:\+?\d[\s().-]*){8,15}(?!\w)")


class DatasetValidationError(ValueError):
    """Raised when a dataset is unsafe or violates the versioned contract."""


def _find_forbidden_output_paths(value: Any, path: str = "input") -> list[str]:
    forbidden = {"actual", "output", "output_claims"}
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}"
            if key in forbidden:
                paths.append(child)
            paths.extend(_find_forbidden_output_paths(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(_find_forbidden_output_paths(item, f"{path}[{index}]"))
    return paths


class EvalItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_version: str = Field(min_length=1)
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]+$")
    suite: Suite
    locale: Locale
    synthetic: bool
    redaction_marker: str
    input: dict[str, Any]
    expected: dict[str, Any]
    grader_version: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    user_review_required: bool = False
    release_critical: bool = False
    pair_id: str | None = None

    @model_validator(mode="after")
    def validate_suite_contract(self) -> EvalItem:
        errors: list[str] = []
        supplied_output_paths = _find_forbidden_output_paths(self.input)
        if supplied_output_paths:
            errors.append(
                "candidate output is forbidden in input: "
                + ", ".join(sorted(supplied_output_paths))
            )
        if not self.synthetic or self.redaction_marker not in {"[SYNTHETIC]", "[REDACTED]"}:
            errors.append("a synthetic/redaction marker is required")
        if self.redaction_marker and self.redaction_marker not in json.dumps(
            self.input, ensure_ascii=False
        ):
            errors.append("redaction marker must appear in input")
        if self.suite == "jd":
            if not isinstance(self.expected.get("classification_label"), str):
                errors.append("JD classification_label is required")
            score_range = self.expected.get("score_range")
            if (
                not isinstance(score_range, list)
                or len(score_range) != 2
                or not all(isinstance(value, int) for value in score_range)
                or not 0 <= score_range[0] <= score_range[1] <= 100
            ):
                errors.append("JD score_range must be two ordered values from 0 to 100")
            if not isinstance(self.expected.get("recommendation"), str):
                errors.append("JD recommendation is required")
            extracted = self.expected.get("extracted_fields")
            if not isinstance(extracted, dict) or set(extracted) != {
                "company",
                "title",
                "location",
                "url",
                "posting_date",
            }:
                errors.append("JD expected extracted_fields are required")
        elif self.suite == "cv_pair":
            if self.expected.get("unsupported_claims") != 0:
                errors.append("CV unsupported_claims must be zero")
            if self.expected.get("docx_required") is not True:
                errors.append("CV docx_required must be true")
        else:
            if not isinstance(self.expected.get("action"), str):
                errors.append("Copilot action label is required")
            if not isinstance(self.expected.get("max_writes"), int):
                errors.append("Copilot max_writes is required")
            if self.expected.get("action") == "answer":
                if self.expected.get("answer_language") != self.locale:
                    errors.append("Copilot answer_language must match locale")
                if not isinstance(
                    self.expected.get("required_facts"), list
                ) or not self.expected.get("required_facts"):
                    errors.append("Copilot required_facts are required for answers")
                if not isinstance(self.expected.get("forbidden_facts"), list):
                    errors.append("Copilot forbidden_facts are required for answers")
        if self.release_critical and not self.pair_id:
            errors.append("release-critical item requires a bilingual pair")
        if errors:
            raise ValueError("; ".join(errors))
        return self


class EvalDataset(BaseModel):
    version: str
    items: list[EvalItem]

    @property
    def suite_counts(self) -> dict[str, int]:
        counts = Counter(item.suite for item in self.items)
        return {suite: counts[suite] for suite in MINIMUM_SUITE_COUNTS}


def _contains_private_value(value: Any) -> bool:
    if isinstance(value, str):
        without_iso_dates = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", value)
        return bool(_EMAIL.search(value) or _PHONE.search(without_iso_dates))
    if isinstance(value, dict):
        return any(_contains_private_value(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_private_value(item) for item in value)
    return False


def load_dataset(path: Path, *, enforce_minimums: bool = True) -> EvalDataset:
    """Load JSONL, rejecting malformed, private-looking, or incomplete committed fixtures."""
    raw_items: list[dict[str, Any]] = []
    errors: list[str] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
            raw_items.append(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_number}: invalid JSON ({exc.msg})")
    ids = [str(item.get("id", "")) for item in raw_items]
    if len(ids) != len(set(ids)):
        errors.append("item IDs must be unique")
    raw_by_id = {str(item.get("id", "")): item for item in raw_items}
    for raw in raw_items:
        pair_id = raw.get("pair_id")
        if pair_id and pair_id not in raw_by_id:
            errors.append(f"item {raw.get('id')}: invalid bilingual pair {pair_id}")
    if any(_contains_private_value(item) for item in raw_items):
        errors.append("dataset contains a private-looking email or phone")

    items: list[EvalItem] = []
    for index, raw in enumerate(raw_items, 1):
        try:
            items.append(EvalItem.model_validate(raw))
        except ValueError as exc:
            errors.append(f"item {raw.get('id', index)}: {exc}")
    versions = {item.dataset_version for item in items}
    if len(versions) != 1:
        errors.append("all items must use one dataset version")

    by_id = {item.id: item for item in items}
    for item in items:
        if not item.pair_id:
            continue
        pair = by_id.get(item.pair_id)
        if pair is None or pair.pair_id != item.id or pair.locale == item.locale:
            errors.append(f"item {item.id}: invalid bilingual pair {item.pair_id}")

    if enforce_minimums:
        counts = Counter(item.suite for item in items)
        for suite, minimum in MINIMUM_SUITE_COUNTS.items():
            if counts[suite] < minimum:
                errors.append(f"suite {suite} requires at least {minimum} items")
        review_count = sum(item.user_review_required for item in items if item.suite == "jd")
        if not 20 <= review_count <= 30:
            errors.append("JD user_review_required count must be between 20 and 30")
    if errors:
        raise DatasetValidationError(" | ".join(errors))
    return EvalDataset(version=versions.pop(), items=items)
