from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.database.models import WorkflowRun, WorkflowStep
from app.workflows.models import (
    WorkflowRunCreate,
    WorkflowStatus,
    WorkflowStepCreate,
)


def create_workflow_run(
    db: Session, payload: WorkflowRunCreate, *, commit: bool = True
) -> WorkflowRun:
    run = WorkflowRun(
        **payload.model_dump(mode="python"),
        status=WorkflowStatus.PENDING.value,
    )
    db.add(run)
    if commit:
        db.commit()
        db.refresh(run)
    else:
        db.flush()
    return run


def start_workflow_run(db: Session, run: WorkflowRun, *, commit: bool = True) -> WorkflowRun:
    if run.status not in {WorkflowStatus.PENDING.value, WorkflowStatus.FAILED.value}:
        raise ValueError("Only pending or failed workflow runs can start")
    if run.status == WorkflowStatus.FAILED.value:
        run.retry_count += 1
    run.status = WorkflowStatus.RUNNING.value
    run.started_at = datetime.now(UTC)
    run.completed_at = None
    run.error_code = None
    if commit:
        db.commit()
    return run


def add_workflow_step(
    db: Session,
    run: WorkflowRun,
    payload: WorkflowStepCreate,
    *,
    commit: bool = True,
) -> WorkflowStep:
    step = WorkflowStep(
        workflow_run_id=run.id,
        **payload.model_dump(mode="python"),
        status=WorkflowStatus.PENDING.value,
    )
    db.add(step)
    if commit:
        db.commit()
        db.refresh(step)
    else:
        db.flush()
    return step


def start_workflow_step(db: Session, step: WorkflowStep, *, commit: bool = True) -> WorkflowStep:
    if step.status not in {WorkflowStatus.PENDING.value, WorkflowStatus.FAILED.value}:
        raise ValueError("Only pending or failed workflow steps can start")
    if step.status == WorkflowStatus.FAILED.value:
        step.retry_count += 1
    step.status = WorkflowStatus.RUNNING.value
    step.started_at = datetime.now(UTC)
    step.completed_at = None
    step.error_code = None
    if commit:
        db.commit()
    return step


def complete_workflow_step(
    db: Session,
    step: WorkflowStep,
    *,
    result_reference: str | None = None,
    commit: bool = True,
) -> WorkflowStep:
    if step.status != WorkflowStatus.RUNNING.value:
        raise ValueError("Only running workflow steps can complete")
    step.status = WorkflowStatus.SUCCEEDED.value
    step.result_reference = result_reference
    step.completed_at = datetime.now(UTC)
    if commit:
        db.commit()
    return step


def fail_workflow_step(
    db: Session, step: WorkflowStep, error_code: str, *, commit: bool = True
) -> WorkflowStep:
    if step.status != WorkflowStatus.RUNNING.value:
        raise ValueError("Only running workflow steps can fail")
    step.status = WorkflowStatus.FAILED.value
    step.error_code = error_code
    step.completed_at = datetime.now(UTC)
    if commit:
        db.commit()
    return step


def complete_workflow_run(
    db: Session,
    run: WorkflowRun,
    *,
    result_reference: str | None = None,
    commit: bool = True,
) -> WorkflowRun:
    if run.status != WorkflowStatus.RUNNING.value:
        raise ValueError("Only running workflow runs can complete")
    if any(step.status != WorkflowStatus.SUCCEEDED.value for step in run.steps):
        raise ValueError("All workflow steps must succeed before the run completes")
    run.status = WorkflowStatus.SUCCEEDED.value
    run.result_reference = result_reference
    run.completed_at = datetime.now(UTC)
    if commit:
        db.commit()
    return run


def fail_workflow_run(
    db: Session, run: WorkflowRun, error_code: str, *, commit: bool = True
) -> WorkflowRun:
    if run.status != WorkflowStatus.RUNNING.value:
        raise ValueError("Only running workflow runs can fail")
    run.status = WorkflowStatus.FAILED.value
    run.error_code = error_code
    run.completed_at = datetime.now(UTC)
    if commit:
        db.commit()
    return run
