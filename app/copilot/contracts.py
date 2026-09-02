from datetime import date, datetime
from typing import Annotated, Literal, TypeAlias

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, StringConstraints

from app.schemas import (
    ActionItemKind,
    ApplicationStatus,
    Locale,
    WatchListCompanyCreate,
    WatchListCompanyUpdate,
)

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list[JsonScalar] | dict[str, JsonScalar]
SessionTitle = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProposalBase(StrictContract):
    proposal_version: Literal["1"] = Field(
        default="1",
        validation_alias=AliasChoices("proposal_version", "version"),
    )
    target_id: int | None


class SaveJobProposal(ProposalBase):
    proposal_type: Literal["save_job"] = "save_job"
    target_id: int
    expected_status: ApplicationStatus


class ChangeApplicationStatusProposal(ProposalBase):
    proposal_type: Literal["change_application_status"] = "change_application_status"
    target_id: int
    expected_status: ApplicationStatus
    status: ApplicationStatus


class CreateApplicationEventProposal(ProposalBase):
    proposal_type: Literal["create_application_event"] = "create_application_event"
    target_id: int
    expected_status: ApplicationStatus
    status: ApplicationStatus
    occurred_at: datetime
    channel: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=2_000)
    next_follow_up_date: date | None = None


class SetFollowUpProposal(ProposalBase):
    proposal_type: Literal["set_follow_up"] = "set_follow_up"
    target_id: int
    expected_status: ApplicationStatus
    follow_up_date: date
    notes: str | None = Field(default=None, max_length=2_000)


class AddWatchListCompanyProposal(ProposalBase):
    proposal_type: Literal["add_watchlist_company"] = "add_watchlist_company"
    target_id: None = None
    company: WatchListCompanyCreate


class UpdateWatchListCompanyProposal(ProposalBase):
    proposal_type: Literal["update_watchlist_company"] = "update_watchlist_company"
    target_id: int
    changes: WatchListCompanyUpdate


class ReanalyzeJobProposal(ProposalBase):
    proposal_type: Literal["reanalyze_job"] = "reanalyze_job"
    target_id: int
    analysis_id: int | None = None


class GenerateTailoredCVProposal(ProposalBase):
    proposal_type: Literal["generate_tailored_cv"] = "generate_tailored_cv"
    target_id: int
    source_cv_ids: list[int] = Field(min_length=0)


class CreateActionItemProposal(ProposalBase):
    proposal_type: Literal["create_action_item"] = "create_action_item"
    target_id: int | None = None
    item_kind: ActionItemKind
    title: str = Field(min_length=1, max_length=300)
    details: str | None = Field(default=None, max_length=4_000)
    due_date: date | None = None


ActionProposal = Annotated[
    SaveJobProposal
    | ChangeApplicationStatusProposal
    | CreateApplicationEventProposal
    | SetFollowUpProposal
    | AddWatchListCompanyProposal
    | UpdateWatchListCompanyProposal
    | ReanalyzeJobProposal
    | GenerateTailoredCVProposal
    | CreateActionItemProposal,
    Field(discriminator="proposal_type"),
]


class ActionTarget(StrictContract):
    record_type: str
    record_id: int | None


class PrivateDataUsage(StrictContract):
    included: bool = False
    record_ids: list[int] = Field(default_factory=list)
    purpose: str | None = None


class ActionProposalRead(StrictContract):
    id: int
    session_id: int
    proposal_type: str
    proposal_version: str
    target: ActionTarget
    current_value: dict[str, object]
    proposed_value: dict[str, object]
    side_effects: list[str]
    private_data_usage: PrivateDataUsage
    status: str
    created_at: datetime


class ActionResult(StrictContract):
    audit_id: int
    proposal_id: int
    proposal_type: str
    result_record_ids: dict[str, list[int]]
    idempotency_key: str
    error_state: str | None = None


class ProposalCreateRequest(StrictContract):
    session_id: int
    proposal: ActionProposal


class ModelActionProposal(StrictContract):
    proposal: ActionProposal


class ActionIntentRequest(StrictContract):
    session_id: int
    message: str = Field(min_length=1, max_length=20_000)
    route: str | None = Field(default=None, max_length=500)
    job_id: int | None = None
    company_id: int | None = None
    cv_document_ids: list[int] = Field(default_factory=list)


class ActionConfirmRequest(StrictContract):
    idempotency_key: str = Field(min_length=1, max_length=200)


class CopilotSessionCreate(StrictContract):
    title: SessionTitle = "New conversation"
    locale: Locale = "en"


class CopilotSessionUpdate(StrictContract):
    title: SessionTitle


class CopilotSessionRead(StrictContract):
    id: int
    title: str
    locale: Locale
    summary: str | None
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class CopilotMessageCreate(StrictContract):
    role: Literal["user", "assistant"]
    body: str = Field(min_length=1, max_length=20_000)
    sources: list[dict[str, object]] = Field(default_factory=list)


class CopilotMessageRead(StrictContract):
    id: int
    session_id: int
    role: Literal["user", "assistant"]
    body: str | None
    sources: list[dict[str, object]]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, extra="forbid")
