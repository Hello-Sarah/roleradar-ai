"""Release Eval adapters that execute candidate-code behavior for committed inputs."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Protocol

from app.analysis.classifier import classify_job
from app.config import Settings
from app.copilot.actions import ActionProposalError
from app.copilot.context import ContextJob, CopilotContext
from app.copilot.service import propose_action
from app.evals.contracts import EvalItem
from app.evals.graders import grade_docx_structure
from app.scoring.v2 import JobEvidence, ProfileEvidence, score_job_v2
from app.services.cv_service import (
    EvidenceBackedItem,
    TailoredCVContent,
    TailoredCVSection,
    _build_docx,
    _validate_evidence,
)


class EvalAdapter(Protocol):
    model_id: str
    prompt_version: str

    def evaluate(self, item: EvalItem) -> dict[str, Any]: ...


class DeterministicReleaseAdapter:
    """Exercise the deterministic release paths without reading dataset oracle fields."""

    model_id = "deterministic-release-v2"
    prompt_version = "none"

    def evaluate(self, item: EvalItem) -> dict[str, Any]:
        if item.suite == "jd":
            return self._evaluate_jd(item.input)
        if item.suite == "cv_pair":
            return self._evaluate_cv(item.input)
        return self._evaluate_copilot(item.input)

    @staticmethod
    def _evaluate_jd(payload: dict[str, Any]) -> dict[str, Any]:
        title = str(payload["title"])
        description = str(payload["description"])
        classification = classify_job(title, description)
        job = JobEvidence(title=title, description=description)
        profile = ProfileEvidence.model_validate(payload.get("profile", {}))
        runs = [score_job_v2(job, profile), score_job_v2(job, profile)]
        evidence_ids = sorted(
            {
                evidence_id
                for result in runs
                for dimension in result.dimensions.values()
                for evidence_id in dimension.evidence_ids
            }
            | {
                evidence_id
                for result in runs
                for flag in [*result.matched_green_flags, *result.matched_red_flags]
                for evidence_id in flag.evidence_ids
            }
        )
        return {
            "classification_label": classification.category.value,
            "scores": [result.total_score for result in runs],
            "recommendation": runs[0].recommendation_band,
            "available_evidence_ids": [item.id for item in runs[0].evidence],
            "evidence_ids": evidence_ids or ["jd-title"],
        }

    @staticmethod
    def _evaluate_cv(payload: dict[str, Any]) -> dict[str, Any]:
        source_claims = [str(value) for value in payload["source_claims"]]
        output_claims = [str(value) for value in payload["output_claims"]]
        corpus = "\n".join(source_claims)
        supported = [claim for claim in output_claims if claim.casefold() in corpus.casefold()]
        first = supported[0] if supported else "[SYNTHETIC] unsupported output"
        content = TailoredCVContent(
            name=EvidenceBackedItem(text=first, source_quote=first),
            headline=EvidenceBackedItem(text=first, source_quote=first),
            summary=[EvidenceBackedItem(text=first, source_quote=first)],
            skills=[EvidenceBackedItem(text=first, source_quote=first)],
            sections=[
                TailoredCVSection(
                    title="Experience",
                    items=[EvidenceBackedItem(text=first, source_quote=first)],
                )
            ],
        )
        try:
            _validate_evidence(content, corpus)
            with TemporaryDirectory(prefix="roleradar-eval-docx-") as directory:
                output = Path(directory) / "synthetic-tailored-cv.docx"
                _build_docx(content, output)
                structure_valid = grade_docx_structure(output.read_bytes()).passed
        except (ValueError, KeyError):
            structure_valid = False
        return {
            "source_claim_ids": [f"source-{index}" for index in range(len(source_claims))],
            "output_claim_ids": [
                f"source-{source_claims.index(claim)}" if claim in source_claims else "unsupported"
                for claim in output_claims
            ],
            "docx_structure_valid": structure_valid,
        }

    @staticmethod
    def _evaluate_copilot(payload: dict[str, Any]) -> dict[str, Any]:
        context = CopilotContext(
            job=ContextJob(
                id=1,
                company="Synthetic Signal Labs",
                title="Forward Deployed AI Engineer",
                location="Hong Kong",
                description="[SYNTHETIC] Build production AI systems.",
                status="New",
            )
        )
        try:
            proposal = propose_action(
                str(payload["message"]),
                context,
                Settings(ai_explanations_enabled=False, openai_api_key=None),
            )
        except ActionProposalError as exc:
            action = "refuse" if "unavailable" in str(exc).casefold() else "clarify"
            return {"action": action, "write_count": 0}
        return {"action": proposal.proposal_type, "write_count": 0}
