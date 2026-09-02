import logging
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.copilot.contracts import (
    ActionProposal,
    ActionProposalRead,
    ActionResult,
    AddWatchListCompanyProposal,
    ChangeApplicationStatusProposal,
    CreateActionItemProposal,
    CreateApplicationEventProposal,
    GenerateTailoredCVProposal,
    PrivateDataUsage,
    ReanalyzeJobProposal,
    SaveJobProposal,
    SetFollowUpProposal,
    UpdateWatchListCompanyProposal,
)
from app.database.models import (
    CandidateProfile,
    CopilotActionAudit,
    CopilotActionItem,
    CopilotActionProposal,
    CopilotSession,
    CVDocument,
    Job,
)
from app.schemas import ApplicationEventCreate, ApplicationStatus
from app.services.cv_service import (
    PreparedTailoredCV,
    discard_prepared_tailored_cv,
    persist_prepared_tailored_cv,
    prepare_tailored_cv,
)
from app.services.job_service import (
    PreparedJobAnalysis,
    add_application_event,
    persist_prepared_reanalysis,
    prepare_reanalysis,
    update_status,
)
from app.watchlist.service import (
    DuplicateWatchListCompanyError,
    create_company,
    get_company,
    update_company,
)
from app.workflows.models import WorkflowRunCreate, WorkflowStepCreate
from app.workflows.service import (
    add_workflow_step,
    complete_workflow_run,
    complete_workflow_step,
    create_workflow_run,
    start_workflow_run,
    start_workflow_step,
)

logger = logging.getLogger(__name__)
_PROPOSAL_ADAPTER = TypeAdapter(ActionProposal)


class ActionProposalError(ValueError):
    pass


class ActionConflictError(ValueError):
    pass


def _job(db: Session, target_id: int) -> Job:
    job = db.get(Job, target_id)
    if job is None:
        raise ActionProposalError("The target job does not exist")
    return job


def _serialize(payload: ActionProposal) -> dict[str, object]:
    serialized = payload.model_dump(mode="json")
    if isinstance(payload, UpdateWatchListCompanyProposal):
        serialized["changes"] = payload.changes.model_dump(mode="json", exclude_unset=True)
    return serialized


def _json_value(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return value


def _proposal_preview(
    db: Session, proposal: ActionProposal
) -> tuple[str, dict[str, object], dict[str, object], list[str], PrivateDataUsage]:
    private = PrivateDataUsage()
    if isinstance(proposal, (SaveJobProposal, ChangeApplicationStatusProposal)):
        job = _job(db, proposal.target_id)
        if job.status != proposal.expected_status.value:
            raise ActionProposalError("The proposal's current status does not match the target job")
        proposed_status = (
            ApplicationStatus.SAVED.value
            if isinstance(proposal, SaveJobProposal)
            else proposal.status.value
        )
        if proposed_status == job.status:
            raise ActionProposalError("The target job already has the proposed status")
        return (
            "job",
            {"status": job.status},
            {"status": proposed_status},
            ["Update the job status", "Append one application timeline event"],
            private,
        )
    if isinstance(proposal, CreateApplicationEventProposal):
        job = _job(db, proposal.target_id)
        if job.status != proposal.expected_status.value:
            raise ActionProposalError("The proposal's current status does not match the target job")
        return (
            "job",
            {"status": job.status},
            {
                "status": proposal.status.value,
                "occurred_at": proposal.occurred_at.isoformat(),
                "channel": proposal.channel,
                "notes": proposal.notes,
                "next_follow_up_date": (
                    proposal.next_follow_up_date.isoformat()
                    if proposal.next_follow_up_date
                    else None
                ),
            },
            ["Append one application timeline event", "Update the job status"],
            private,
        )
    if isinstance(proposal, SetFollowUpProposal):
        job = _job(db, proposal.target_id)
        if job.status != proposal.expected_status.value:
            raise ActionProposalError("The proposal's current status does not match the target job")
        current_follow_up = next(
            (
                event.next_follow_up_date
                for event in job.application_events
                if event.next_follow_up_date is not None
            ),
            None,
        )
        return (
            "job",
            {
                "status": job.status,
                "next_follow_up_date": (
                    current_follow_up.isoformat() if current_follow_up else None
                ),
            },
            {"next_follow_up_date": proposal.follow_up_date.isoformat()},
            ["Append one follow-up timeline event without changing the current status"],
            private,
        )
    if isinstance(proposal, AddWatchListCompanyProposal):
        return (
            "watchlist_company",
            {},
            proposal.company.model_dump(mode="json"),
            ["Create one Watch List company"],
            private,
        )
    if isinstance(proposal, UpdateWatchListCompanyProposal):
        company = get_company(db, proposal.target_id)
        changes = proposal.changes.model_dump(mode="json", exclude_unset=True)
        if not changes:
            raise ActionProposalError("A Watch List update requires at least one changed field")
        current = {field: _json_value(getattr(company, field)) for field in changes}
        if current == changes:
            raise ActionProposalError("The Watch List company already has the proposed values")
        return (
            "watchlist_company",
            current,
            changes,
            ["Update the selected Watch List company"],
            private,
        )
    if isinstance(proposal, ReanalyzeJobProposal):
        job = _job(db, proposal.target_id)
        if db.scalar(select(CandidateProfile.id).limit(1)) is None:
            raise ActionProposalError("A candidate profile is required before reanalysis")
        current_id = job.analysis.id if job.analysis else None
        if proposal.analysis_id is not None and proposal.analysis_id != current_id:
            raise ActionProposalError("The selected analysis is not the current job analysis")
        return (
            "job",
            {"analysis_id": current_id},
            {"analysis_id": "new_immutable_analysis"},
            ["Run explicit analysis", "Append a new immutable analysis version"],
            private,
        )
    if isinstance(proposal, GenerateTailoredCVProposal):
        _job(db, proposal.target_id)
        source_ids = list(dict.fromkeys(proposal.source_cv_ids))
        if not source_ids:
            source_ids = list(
                db.scalars(
                    select(CVDocument.id).where(CVDocument.active.is_(True)).order_by(CVDocument.id)
                ).all()
            )
            if not source_ids:
                raise ActionProposalError(
                    "Select at least one active source CV before proposing generation"
                )
        else:
            found = set(
                db.scalars(
                    select(CVDocument.id).where(
                        CVDocument.id.in_(source_ids), CVDocument.active.is_(True)
                    )
                ).all()
            )
            if found != set(source_ids):
                raise ActionProposalError("A selected source CV is missing or inactive")
        return (
            "job",
            {"generated_cv": None},
            {"source_cv_ids": source_ids},
            ["Use model-backed exact-evidence generation", "Create one new DOCX artifact"],
            PrivateDataUsage(
                included=bool(source_ids),
                record_ids=source_ids,
                purpose="Generate a tailored CV from selected private CV evidence",
            ),
        )
    if isinstance(proposal, CreateActionItemProposal):
        if proposal.target_id is not None:
            _job(db, proposal.target_id)
        return (
            "job" if proposal.target_id is not None else "action_item",
            {},
            {
                "item_kind": proposal.item_kind,
                "title": proposal.title,
                "details": proposal.details,
                "due_date": proposal.due_date.isoformat() if proposal.due_date else None,
            },
            ["Create one local career action item"],
            private,
        )
    raise ActionProposalError("Unsupported Copilot action")


def to_action_proposal_read(record: CopilotActionProposal) -> ActionProposalRead:
    return ActionProposalRead(
        id=record.id,
        session_id=record.session_id,
        proposal_type=record.proposal_type,
        proposal_version=record.proposal_version,
        target={"record_type": record.target_type, "record_id": record.target_id},
        current_value=record.current_value,
        proposed_value=record.proposed_value,
        side_effects=record.side_effects,
        private_data_usage=record.private_data_usage,
        status=record.status,
        created_at=record.created_at,
    )


def create_action_proposal(
    db: Session, *, session_id: int, proposal: ActionProposal
) -> CopilotActionProposal:
    session = db.get(CopilotSession, session_id)
    if session is None or session.deleted_at is not None:
        raise ActionProposalError("Copilot session not found")
    target_type, current, proposed, side_effects, private = _proposal_preview(db, proposal)
    if isinstance(proposal, GenerateTailoredCVProposal):
        proposal = proposal.model_copy(update={"source_cv_ids": private.record_ids})
    record = CopilotActionProposal(
        session_id=session.id,
        proposal_type=proposal.proposal_type,
        proposal_version=proposal.proposal_version,
        target_type=target_type,
        target_id=proposal.target_id,
        parameters=_serialize(proposal),
        current_value=current,
        proposed_value=proposed,
        side_effects=side_effects,
        private_data_usage=private.model_dump(mode="json"),
        status="pending",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    logger.info(
        "copilot action proposed",
        extra={"proposal_id": record.id, "proposal_type": record.proposal_type},
    )
    return record


def _assert_snapshot(record: CopilotActionProposal, current: dict[str, object]) -> None:
    if current != record.current_value:
        raise ActionConflictError(
            "The target changed after this proposal was created; create a new proposal"
        )


def _result_from_audit(audit: CopilotActionAudit) -> ActionResult:
    return ActionResult(
        audit_id=audit.id,
        proposal_id=audit.proposal_id or 0,
        proposal_type=audit.proposal_type,
        result_record_ids=audit.result_record_ids,
        idempotency_key=audit.idempotency_key,
        error_state=audit.error_state,
    )


def _execute(
    db: Session,
    record: CopilotActionProposal,
    proposal: ActionProposal,
    settings: Settings,
    *,
    prepared_analysis: PreparedJobAnalysis | None = None,
    prepared_cv: PreparedTailoredCV | None = None,
) -> tuple[dict[str, list[int]], Path | None]:
    artifact_path: Path | None = None
    if isinstance(proposal, SaveJobProposal):
        job = _job(db, proposal.target_id)
        _assert_snapshot(record, {"status": job.status})
        updated = update_status(db, job.id, ApplicationStatus.SAVED, commit=False)
        return {"job": [updated.id]}, None
    if isinstance(proposal, ChangeApplicationStatusProposal):
        job = _job(db, proposal.target_id)
        _assert_snapshot(record, {"status": job.status})
        updated = update_status(db, job.id, proposal.status, commit=False)
        return {"job": [updated.id]}, None
    if isinstance(proposal, CreateApplicationEventProposal):
        job = _job(db, proposal.target_id)
        _assert_snapshot(record, {"status": job.status})
        event = add_application_event(
            db,
            job.id,
            ApplicationEventCreate(
                status=proposal.status,
                occurred_at=proposal.occurred_at,
                channel=proposal.channel,
                notes=proposal.notes,
                next_follow_up_date=proposal.next_follow_up_date,
            ),
            commit=False,
        )
        return {"job": [job.id], "application_event": [event.id]}, None
    if isinstance(proposal, SetFollowUpProposal):
        job = _job(db, proposal.target_id)
        current_follow_up = next(
            (
                event.next_follow_up_date
                for event in job.application_events
                if event.next_follow_up_date is not None
            ),
            None,
        )
        _assert_snapshot(
            record,
            {
                "status": job.status,
                "next_follow_up_date": (
                    current_follow_up.isoformat() if current_follow_up else None
                ),
            },
        )
        event = add_application_event(
            db,
            job.id,
            ApplicationEventCreate(
                status=ApplicationStatus(job.status),
                occurred_at=datetime.now(UTC),
                notes=proposal.notes or "Follow-up scheduled",
                next_follow_up_date=proposal.follow_up_date,
            ),
            commit=False,
        )
        return {"job": [job.id], "application_event": [event.id]}, None
    if isinstance(proposal, AddWatchListCompanyProposal):
        _assert_snapshot(record, {})
        try:
            company = create_company(db, proposal.company, commit=False)
        except DuplicateWatchListCompanyError as exc:
            raise ActionConflictError(str(exc)) from exc
        return {"watchlist_company": [company.id]}, None
    if isinstance(proposal, UpdateWatchListCompanyProposal):
        company = get_company(db, proposal.target_id)
        changes = proposal.changes.model_dump(mode="json", exclude_unset=True)
        current = {field: _json_value(getattr(company, field)) for field in changes}
        _assert_snapshot(record, current)
        try:
            company = update_company(db, company.id, proposal.changes, commit=False)
        except DuplicateWatchListCompanyError as exc:
            raise ActionConflictError(str(exc)) from exc
        return {"watchlist_company": [company.id]}, None
    if isinstance(proposal, ReanalyzeJobProposal):
        job = _job(db, proposal.target_id)
        current_id = job.analysis.id if job.analysis else None
        _assert_snapshot(record, {"analysis_id": current_id})
        if prepared_analysis is None:
            raise RuntimeError("Reanalysis was not prepared outside the transaction")
        try:
            analysis = persist_prepared_reanalysis(db, prepared_analysis)
        except ValueError as exc:
            raise ActionConflictError(str(exc)) from exc
        return {"job": [job.id], "analysis": [analysis.id]}, None
    if isinstance(proposal, GenerateTailoredCVProposal):
        job = _job(db, proposal.target_id)
        _assert_snapshot(record, {"generated_cv": None})
        if prepared_cv is None:
            raise RuntimeError("Tailored CV was not prepared outside the transaction")
        generated = persist_prepared_tailored_cv(db, prepared_cv)
        artifact_path = Path(generated.file_path)
        return {"job": [job.id], "generated_cv": [generated.id]}, artifact_path
    if isinstance(proposal, CreateActionItemProposal):
        _assert_snapshot(record, {})
        item = CopilotActionItem(
            job_id=proposal.target_id,
            item_kind=proposal.item_kind,
            title=proposal.title,
            details=proposal.details,
            due_date=proposal.due_date,
        )
        db.add(item)
        db.flush()
        return {"action_item": [item.id]}, None
    raise ActionProposalError("Unsupported Copilot action")


def confirm_action(
    proposal_id: int,
    idempotency_key: str,
    db: Session,
    settings: Settings,
    *,
    actor: str = "user",
) -> ActionResult:
    existing = db.scalar(
        select(CopilotActionAudit).where(CopilotActionAudit.idempotency_key == idempotency_key)
    )
    if existing is not None:
        if existing.proposal_id != proposal_id:
            raise ActionConflictError("The idempotency key belongs to another proposal")
        return _result_from_audit(existing)

    record = db.scalar(
        select(CopilotActionProposal)
        .where(CopilotActionProposal.id == proposal_id)
        .with_for_update()
    )
    if record is None:
        raise LookupError("Action proposal not found")
    if record.status == "confirmed":
        audit = db.scalar(
            select(CopilotActionAudit).where(CopilotActionAudit.proposal_id == record.id)
        )
        if audit is None:
            raise ActionConflictError("Confirmed proposal is missing its audit")
        return _result_from_audit(audit)
    if record.status != "pending":
        raise ActionConflictError("Action proposal is no longer pending")

    proposal = _PROPOSAL_ADAPTER.validate_python(record.parameters)
    prepared_analysis = None
    prepared_cv = None
    if isinstance(proposal, ReanalyzeJobProposal):
        prepared_analysis = prepare_reanalysis(db, proposal.target_id, settings)
    elif isinstance(proposal, GenerateTailoredCVProposal):
        prepared_cv = prepare_tailored_cv(
            db,
            proposal.target_id,
            settings,
            source_cv_ids=proposal.source_cv_ids,
        )
    if prepared_analysis is not None or prepared_cv is not None:
        record = db.scalar(
            select(CopilotActionProposal)
            .where(CopilotActionProposal.id == proposal_id)
            .with_for_update()
        )
        if record is not None and record.status == "confirmed":
            if prepared_cv is not None:
                discard_prepared_tailored_cv(prepared_cv)
            audit = db.scalar(
                select(CopilotActionAudit).where(CopilotActionAudit.proposal_id == proposal_id)
            )
            if audit is not None:
                return _result_from_audit(audit)
        if record is None or record.status != "pending":
            if prepared_cv is not None:
                discard_prepared_tailored_cv(prepared_cv)
            raise ActionConflictError("Action proposal is no longer pending")
    artifact_path: Path | None = None
    if prepared_cv is not None:
        artifact_path = Path(prepared_cv.file_path)
    try:
        audit = CopilotActionAudit(
            session_id=record.session_id,
            proposal_id=record.id,
            proposal_type=record.proposal_type,
            proposal_version=record.proposal_version,
            parameter_summary={
                "target_type": record.target_type,
                "target_id": record.target_id,
                "proposed_fields": sorted(record.proposed_value),
                "private_record_ids": record.private_data_usage.get("record_ids", []),
            },
            confirmed_at=datetime.now(UTC),
            actor=actor,
            result_record_ids={},
            idempotency_key=idempotency_key,
            error_state=None,
        )
        db.add(audit)
        # The two unique constraints are the concurrency claim. A competing confirmation
        # blocks here and then rolls back without reaching a business write.
        db.flush()
        run = create_workflow_run(
            db,
            WorkflowRunCreate(
                workflow_type="copilot_confirmed_action",
                contract_version=record.proposal_version,
                input_reference=f"copilot_proposal:{record.id}",
            ),
            commit=False,
        )
        start_workflow_run(db, run, commit=False)
        step = add_workflow_step(
            db,
            run,
            WorkflowStepCreate(
                step_name=record.proposal_type,
                version=record.proposal_version,
                input_reference=f"copilot_proposal:{record.id}",
            ),
            commit=False,
        )
        start_workflow_step(db, step, commit=False)
        result_ids, artifact_path = _execute(
            db,
            record,
            proposal,
            settings,
            prepared_analysis=prepared_analysis,
            prepared_cv=prepared_cv,
        )
        audit.result_record_ids = result_ids
        record.status = "confirmed"
        record.confirmed_at = audit.confirmed_at
        complete_workflow_step(
            db,
            step,
            result_reference=f"copilot_audit:{audit.id}",
            commit=False,
        )
        complete_workflow_run(
            db,
            run,
            result_reference=f"copilot_audit:{audit.id}",
            commit=False,
        )
        db.commit()
        db.refresh(audit)
        logger.info(
            "copilot action confirmed",
            extra={"proposal_id": record.id, "audit_id": audit.id},
        )
        return _result_from_audit(audit)
    except IntegrityError:
        db.rollback()
        if prepared_cv is not None:
            discard_prepared_tailored_cv(prepared_cv)
        elif artifact_path is not None:
            artifact_path.unlink(missing_ok=True)
        winner = db.scalar(
            select(CopilotActionAudit).where(
                (CopilotActionAudit.idempotency_key == idempotency_key)
                | (CopilotActionAudit.proposal_id == proposal_id)
            )
        )
        if winner is not None:
            if winner.idempotency_key == idempotency_key and winner.proposal_id != proposal_id:
                raise ActionConflictError(
                    "The idempotency key belongs to another proposal"
                ) from None
            return _result_from_audit(winner)
        raise
    except Exception:
        db.rollback()
        if prepared_cv is not None:
            discard_prepared_tailored_cv(prepared_cv)
        elif artifact_path is not None:
            artifact_path.unlink(missing_ok=True)
        raise
