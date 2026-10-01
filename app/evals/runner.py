"""CLI runner for the versioned RoleRadar V1 Golden Dataset."""

from __future__ import annotations

import argparse
import hashlib
import time
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.evals.adapters import DeterministicReleaseAdapter, EvalAdapter
from app.evals.contracts import EvalDataset, EvalItem, load_dataset
from app.evals.graders import (
    GRADER_VERSION,
    GraderResult,
    grade_bilingual_parity,
    grade_cv_case,
    grade_evidence_ids,
    grade_schema,
    grade_score_stability,
    grade_write_counts,
)
from app.evals.report import canonical_hash, write_reports

RUNNER_VERSION = "eval-runner-v1"


class EvalRunResult(BaseModel):
    passed: bool
    item_count: int
    failed_items: int
    zero_tolerance_failures: int
    output_dir: Path


def _expected_match(item: EvalItem, output: dict[str, Any]) -> GraderResult:
    if item.suite == "jd":
        matches = (
            output.get("classification_label") == item.expected["classification_label"]
            and output.get("recommendation") == item.expected["recommendation"]
        )
    else:
        matches = output.get("action") == item.expected.get("action")
    return GraderResult(name="expected_label", passed=matches, metrics={"matches": matches})


def _grade_item(item: EvalItem, output: dict[str, Any]) -> list[GraderResult]:
    if item.suite == "jd":
        score_range = tuple(item.expected["score_range"])
        return [
            grade_schema(
                output,
                required_fields={
                    "classification_label",
                    "scores",
                    "recommendation",
                    "available_evidence_ids",
                    "evidence_ids",
                },
            ),
            grade_score_stability(output.get("scores", []), expected_range=score_range),
            grade_evidence_ids(
                set(output.get("available_evidence_ids", [])), output.get("evidence_ids", [])
            ),
            _expected_match(item, output),
        ]
    if item.suite == "cv_pair":
        factual = grade_cv_case(
            expected_claim_ids=set(output.get("source_claim_ids", [])),
            output_claim_ids=set(output.get("output_claim_ids", [])),
            other_metric_scores={"structure": float(output.get("docx_structure_valid", False))},
        )
        structure_valid = bool(output.get("docx_structure_valid"))
        structure = GraderResult(
            name="docx_structure",
            passed=structure_valid,
            metrics={"valid": structure_valid},
            zero_tolerance_failure=not structure_valid,
        )
        return [
            grade_schema(
                output,
                required_fields={"source_claim_ids", "output_claim_ids", "docx_structure_valid"},
            ),
            factual,
            structure,
        ]
    return [
        grade_schema(output, required_fields={"action", "write_count"}),
        _expected_match(item, output),
        grade_write_counts(
            actual=output.get("write_count", -1),
            maximum=item.expected["max_writes"],
        ),
        *(
            [
                grade_evidence_ids(
                    set(output.get("available_source_ids", [])),
                    output.get("source_ids", []),
                )
            ]
            if output.get("action") == "answer"
            else []
        ),
    ]


def _safe_output(output: dict[str, Any]) -> dict[str, Any]:
    safe_fields = {
        "classification_label",
        "scores",
        "recommendation",
        "available_evidence_ids",
        "evidence_ids",
        "source_claim_ids",
        "output_claim_ids",
        "docx_structure_valid",
        "action",
        "write_count",
        "answer",
        "available_source_ids",
        "source_ids",
        "extracted_fields",
    }
    return {key: output[key] for key in sorted(output.keys() & safe_fields)}


def _dataset_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def run_dataset(
    dataset_path: Path,
    output_dir: Path,
    *,
    adapter: EvalAdapter | None = None,
) -> EvalRunResult:
    dataset: EvalDataset = load_dataset(dataset_path)
    runtime = adapter or DeterministicReleaseAdapter()
    dataset_hash = _dataset_hash(dataset_path)
    pairs = {item.id: item for item in dataset.items}
    rows: list[dict[str, Any]] = []
    failed = 0
    zero_tolerance_failures = 0
    suite_failures: Counter[str] = Counter()

    outputs = {item.id: runtime.evaluate(item) for item in dataset.items}
    for item in dataset.items:
        started = time.perf_counter_ns()
        output = outputs[item.id]
        results = _grade_item(item, output)
        if item.pair_id:
            results.append(grade_bilingual_parity(output, outputs[pairs[item.pair_id].id]))
        passed = all(result.passed for result in results)
        zero_failures = sum(result.zero_tolerance_failure for result in results)
        failed += not passed
        zero_tolerance_failures += zero_failures
        suite_failures[item.suite] += not passed
        safe_output = _safe_output(output)
        rows.append(
            {
                "dataset_version": item.dataset_version,
                "dataset_hash": dataset_hash,
                "item_id": item.id,
                "item_hash": canonical_hash(item.model_dump(mode="json")),
                "suite": item.suite,
                "locale": item.locale,
                "input_hash": canonical_hash(item.input),
                "expected": item.expected,
                "output": safe_output,
                "output_hash": canonical_hash(output),
                "grader_version": item.grader_version,
                "grader_results": [result.model_dump(mode="json") for result in results],
                "model_id": runtime.model_id,
                "prompt_version": runtime.prompt_version,
                "runner_version": RUNNER_VERSION,
                "latency_ms": round((time.perf_counter_ns() - started) / 1_000_000, 3),
                "passed": passed,
                "zero_tolerance_failures": zero_failures,
                "user_review_required": item.user_review_required,
            }
        )

    summary = {
        "dataset_version": dataset.version,
        "dataset_hash": dataset_hash,
        "runner_version": RUNNER_VERSION,
        "grader_version": GRADER_VERSION,
        "model_id": runtime.model_id,
        "prompt_version": runtime.prompt_version,
        "item_count": len(dataset.items),
        "suite_counts": dataset.suite_counts,
        "suite_failures": dict(sorted(suite_failures.items())),
        "failed_items": failed,
        "zero_tolerance_failures": zero_tolerance_failures,
        "passed": failed == 0 and zero_tolerance_failures == 0,
    }
    write_reports(output_dir, summary, rows)
    return EvalRunResult(
        passed=summary["passed"],
        item_count=len(rows),
        failed_items=failed,
        zero_tolerance_failures=zero_tolerance_failures,
        output_dir=output_dir,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_dataset(args.dataset, args.output)
    print(result.model_dump_json(indent=2))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
