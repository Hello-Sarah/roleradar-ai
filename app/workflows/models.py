from enum import StrEnum

from pydantic import BaseModel, Field


class WorkflowStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class WorkflowRunCreate(BaseModel):
    workflow_type: str = Field(min_length=1, max_length=100)
    contract_version: str = Field(min_length=1, max_length=50)
    input_reference: str | None = Field(default=None, max_length=500)
    model_version: str | None = Field(default=None, max_length=200)
    prompt_version: str | None = Field(default=None, max_length=100)


class WorkflowStepCreate(BaseModel):
    step_name: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=50)
    input_reference: str | None = Field(default=None, max_length=500)
