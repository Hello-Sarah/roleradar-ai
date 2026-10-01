from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from app.evals.adapters import DeterministicReleaseAdapter
from app.evals.contracts import EvalItem, load_dataset
from app.evals.graders import (
    grade_bilingual_parity,
    grade_cv_case,
    grade_docx_structure,
    grade_evidence_ids,
    grade_schema,
    grade_score_stability,
    grade_write_counts,
)
from app.evals.runner import _grade_item


def test_unsupported_cv_claim_fails_even_when_composite_is_high() -> None:
    result = grade_cv_case(
        expected_claim_ids={"cv-1", "cv-2"},
        output_claim_ids={"cv-1", "cv-2", "invented"},
        other_metric_scores={"structure": 1.0, "clarity": 1.0, "relevance": 1.0},
    )

    assert result.passed is False
    assert result.metrics["unsupported_claims"] == 1
    assert result.zero_tolerance_failure is True


def test_deterministic_contract_graders() -> None:
    schema = grade_schema({"score": 70}, required_fields={"score"})
    score = grade_score_stability([70, 70, 70], expected_range=(70, 85))
    evidence = grade_evidence_ids({"jd-1", "jd-2"}, ["jd-1"])
    writes = grade_write_counts(actual=0, maximum=0)
    parity = grade_bilingual_parity(
        {"score": 70, "class": "Applied AI", "evidence_ids": ["jd-1"]},
        {"score": 70, "class": "Applied AI", "evidence_ids": ["jd-1"]},
    )

    assert all(result.passed for result in (schema, score, evidence, writes, parity))


@pytest.mark.parametrize(
    ("field", "mismatched_value"),
    [
        ("classification_label", "Project Management"),
        ("recommendation", "Skip"),
        ("scores", [45, 45]),
    ],
)
def test_jd_bilingual_parity_rejects_actual_contract_mismatches(
    field: str, mismatched_value: object
) -> None:
    english = {
        "classification_label": "Applied AI Engineer",
        "recommendation": "Strong Apply",
        "scores": [75, 75],
        "available_evidence_ids": ["jd-title", "jd-001"],
        "evidence_ids": ["jd-001"],
    }
    chinese = {**english, field: mismatched_value}

    result = grade_bilingual_parity(english, chinese)

    assert result.passed is False
    assert result.metrics["mismatches"] == 1


def test_matching_release_critical_jd_pair_passes_bilingual_parity() -> None:
    dataset = load_dataset(Path("evals/datasets/v1.jsonl"))
    english = next(
        item
        for item in dataset.items
        if item.suite == "jd" and item.locale == "en" and item.pair_id
    )
    chinese = next(item for item in dataset.items if item.id == english.pair_id)

    adapter = DeterministicReleaseAdapter()
    assert (
        grade_bilingual_parity(adapter.evaluate(english), adapter.evaluate(chinese)).passed is True
    )


def test_copilot_bilingual_parity_compares_action_and_write_count() -> None:
    left = {"action": "refuse", "write_count": 0, "answer": "English localized prose"}
    right = {"action": "refuse", "write_count": 1, "answer": "中文本地化文本"}

    result = grade_bilingual_parity(left, right)

    assert result.passed is False
    assert result.metrics["compared_fields"] == 2


def test_docx_structure_grader_requires_a_valid_document() -> None:
    stream = BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="urn:test"><w:body><w:p><w:r>'
            "<w:t>Evidence-backed experience</w:t></w:r></w:p></w:body></w:document>",
        )

    assert grade_docx_structure(stream.getvalue()).passed is True
    assert grade_docx_structure(b"not a docx").passed is False


def _release_item(suite: str, input_payload: dict, expected: dict) -> EvalItem:
    return EvalItem.model_validate(
        {
            "dataset_version": "v1",
            "id": f"runtime-{suite}",
            "suite": suite,
            "locale": "en",
            "synthetic": True,
            "redaction_marker": "[SYNTHETIC]",
            "input": input_payload,
            "expected": expected,
            "grader_version": "eval-graders-v2",
            "model_id": "deterministic-release-v4",
            "prompt_version": "none",
        }
    )


def test_release_jd_adapter_executes_real_text_extraction(monkeypatch) -> None:
    from app.schemas import JobCreate

    item = _release_item(
        "jd",
        {"raw_text": "[SYNTHETIC] Company: Example\nRole: Placeholder\n" + "Build AI. " * 8},
        {
            "classification_label": "Applied AI Engineer",
            "score_range": [0, 100],
            "recommendation": "Skip",
            "extracted_fields": {
                "company": "Example",
                "title": "Placeholder",
                "location": "Unknown",
                "url": None,
                "posting_date": None,
            },
        },
    )
    observed = []

    def changed_extractor(raw_text: str) -> JobCreate:
        observed.append(raw_text)
        return JobCreate(
            company="Runtime Extractor",
            title="Research Scientist",
            location="Hong Kong",
            description="[SYNTHETIC] Research models and publish papers. " * 2,
            source="pasted_text",
        )

    monkeypatch.setattr("app.evals.adapters.extract_job_from_text", changed_extractor)
    output = DeterministicReleaseAdapter().evaluate(item)

    assert observed == [item.input["raw_text"]]
    assert output["classification_label"] == "Research"
    assert output["extracted_fields"]["company"] == "Runtime Extractor"


def test_release_cv_adapter_executes_real_generation_workflow(monkeypatch) -> None:
    item = _release_item(
        "cv_pair",
        {
            "source_claims": [
                "[SYNTHETIC] Casey Candidate",
                "[SYNTHETIC] Built reliable AI systems.",
            ],
            "job": {
                "company": "Synthetic Signal Labs",
                "title": "Applied AI Engineer",
                "location": "Hong Kong",
                "description": "[SYNTHETIC] Build reliable production AI systems with customers.",
            },
        },
        {"unsupported_claims": 0, "docx_required": True},
    )
    called = []

    def broken_runtime(*args, **kwargs):
        called.append((args, kwargs))
        raise RuntimeError("changed production generation")

    monkeypatch.setattr("app.evals.adapters.prepare_tailored_cv", broken_runtime)
    output = DeterministicReleaseAdapter().evaluate(item)

    assert called
    assert output["docx_structure_valid"] is False
    assert output["output_claim_ids"] == ["unsupported"]


def test_release_copilot_answer_adapter_executes_grounded_answer_path(monkeypatch) -> None:
    item = _release_item(
        "copilot_normal",
        {
            "message": "[SYNTHETIC] Summarize the visible evidence.",
            "context": {
                "company": "Synthetic Signal Labs",
                "title": "Forward Deployed AI Engineer",
                "description": "[SYNTHETIC] Build production AI systems.",
            },
        },
        {
            "action": "answer",
            "max_writes": 0,
            "answer_language": "en",
            "required_facts": ["Synthetic Signal Labs", "Forward Deployed AI Engineer"],
            "forbidden_facts": ["salary", "credential"],
        },
    )
    called = []

    def changed_answer(message, context, settings, **kwargs):
        called.append((message, context, settings))
        return {"answer": "changed runtime answer", "source_ids": ["job:1"]}

    monkeypatch.setattr("app.evals.adapters.answer_question", changed_answer)
    output = DeterministicReleaseAdapter().evaluate(item)

    assert called
    assert output["action"] == "answer"
    assert output["answer"] == "changed runtime answer"
    assert output["source_ids"] == ["job:1"]


def test_release_adapter_output_does_not_change_when_only_oracle_expected_changes() -> None:
    dataset = load_dataset(Path("evals/datasets/v1.jsonl"))
    original = next(
        item
        for item in dataset.items
        if item.suite == "copilot_normal" and item.expected.get("action") == "answer"
    )
    poisoned = original.model_copy(
        update={
            "expected": {
                **original.expected,
                "required_facts": ["ORACLE MUST NEVER BECOME CANDIDATE OUTPUT"],
                "forbidden_facts": [],
            }
        }
    )
    adapter = DeterministicReleaseAdapter()

    assert adapter.evaluate(original) == adapter.evaluate(poisoned)


def test_jd_grading_rejects_wrong_production_extraction_fields() -> None:
    item = _release_item(
        "jd",
        {"raw_text": "[SYNTHETIC] Company: Correct Labs\nRole: Applied AI Engineer"},
        {
            "classification_label": "Applied AI Engineer",
            "score_range": [70, 90],
            "recommendation": "Strong Apply",
            "extracted_fields": {
                "company": "Correct Labs",
                "title": "Applied AI Engineer",
                "location": "Hong Kong",
                "url": "https://example.invalid/jobs/correct",
                "posting_date": "2026-10-02",
            },
        },
    )
    output = {
        "extracted_fields": {
            "company": "Invented Corp",
            "title": "Wrong title",
            "location": "Moon",
            "url": "https://attacker.invalid",
            "posting_date": "2099-01-01",
        },
        "classification_label": "Applied AI Engineer",
        "scores": [80, 80],
        "recommendation": "Strong Apply",
        "available_evidence_ids": ["jd-title"],
        "evidence_ids": ["jd-title"],
    }

    graders = {result.name: result for result in _grade_item(item, output)}

    assert graders["critical_field_extraction"].passed is False
    assert graders["critical_field_extraction"].zero_tolerance_failure is True


@pytest.mark.parametrize(
    ("answer", "expected_failed_grader"),
    [
        ("Invented private salary and credential", "grounded_answer"),
        (
            "Synthetic Signal Labs — Applied AI Engineer: Build production AI systems.",
            "answer_language",
        ),
    ],
)
def test_copilot_answer_grading_rejects_ungrounded_or_wrong_language(
    answer: str, expected_failed_grader: str
) -> None:
    item = EvalItem.model_validate(
        {
            "dataset_version": "v1",
            "id": "runtime-copilot-answer",
            "suite": "copilot_normal",
            "locale": "zh-Hans",
            "synthetic": True,
            "redaction_marker": "[SYNTHETIC]",
            "input": {"message": "[SYNTHETIC] 总结证据。"},
            "expected": {
                "action": "answer",
                "max_writes": 0,
                "answer_language": "zh-Hans",
                "required_facts": ["Synthetic Signal Labs", "Applied AI Engineer"],
                "forbidden_facts": ["salary", "credential"],
            },
            "grader_version": "eval-graders-v2",
            "model_id": "deterministic-release-v4",
            "prompt_version": "none",
        }
    )
    output = {
        "action": "answer",
        "write_count": 0,
        "answer": answer,
        "available_source_ids": ["job:1"],
        "source_ids": ["job:1"],
    }

    graders = {result.name: result for result in _grade_item(item, output)}

    assert graders[expected_failed_grader].passed is False


def test_copilot_bilingual_parity_rejects_different_answer_facts_and_sources() -> None:
    english = {
        "action": "answer",
        "write_count": 0,
        "answer_fact_ids": ["company", "title", "description"],
        "source_ids": ["job:1"],
    }
    chinese = {
        "action": "answer",
        "write_count": 0,
        "answer_fact_ids": ["company", "invented-salary"],
        "source_ids": ["profile:1"],
    }

    result = grade_bilingual_parity(english, chinese)

    assert result.passed is False
    assert result.metrics["mismatches"] == 2


def test_cv_eval_requires_production_rejection_of_an_unsupported_claim() -> None:
    item = _release_item(
        "cv_pair",
        {"source_claims": ["[SYNTHETIC] Built reliable AI systems."]},
        {"unsupported_claims": 0, "docx_required": True},
    )
    output = {
        "source_claim_ids": ["source-0"],
        "output_claim_ids": ["source-0"],
        "docx_structure_valid": True,
        "unsupported_claim_rejected": False,
    }

    graders = {result.name: result for result in _grade_item(item, output)}

    assert graders["unsupported_claim_rejection"].passed is False
    assert graders["unsupported_claim_rejection"].zero_tolerance_failure is True
