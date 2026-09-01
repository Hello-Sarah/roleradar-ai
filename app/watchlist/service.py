"""Watch List persistence and lifecycle transaction boundaries."""

import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.database.models import WatchListCompany, WatchListSourceStateEvent
from app.schemas import WatchListCompanyCreate, WatchListCompanyRead, WatchListCompanyUpdate
from app.watchlist.models import SourceState

logger = logging.getLogger(__name__)


class DuplicateWatchListCompanyError(ValueError):
    pass


class SourceHistoryDeleteError(ValueError):
    pass


def _company_query():
    return select(WatchListCompany).options(selectinload(WatchListCompany.source_history))


def get_company(db: Session, company_id: int) -> WatchListCompany:
    company = db.scalar(_company_query().where(WatchListCompany.id == company_id))
    if company is None:
        raise LookupError("Watch List company not found")
    return company


def list_companies(db: Session, *, include_disabled: bool = True) -> list[WatchListCompany]:
    query = _company_query().order_by(WatchListCompany.name)
    if not include_disabled:
        query = query.where(WatchListCompany.enabled.is_(True))
    return list(db.scalars(query).all())


def _commit_company(db: Session, company: WatchListCompany) -> WatchListCompany:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateWatchListCompanyError(
            "A Watch List company with this name or canonical domain already exists"
        ) from exc
    logger.info("watchlist company changed", extra={"company_id": company.id})
    return get_company(db, company.id)


def create_company(db: Session, payload: WatchListCompanyCreate) -> WatchListCompany:
    values = payload.model_dump(mode="python")
    values["official_source_url"] = str(payload.official_source_url)
    company = WatchListCompany(**values)
    db.add(company)
    return _commit_company(db, company)


def update_company(
    db: Session, company_id: int, payload: WatchListCompanyUpdate
) -> WatchListCompany:
    company = get_company(db, company_id)
    values = payload.model_dump(mode="python", exclude_unset=True)
    reason = values.pop("source_state_reason", None)
    if "official_source_url" in values:
        values["official_source_url"] = str(payload.official_source_url)
    if "source_state" in values and values["source_state"] != company.source_state:
        company.source_history.append(
            WatchListSourceStateEvent(
                from_state=company.source_state,
                to_state=values["source_state"],
                reason=reason,
            )
        )
        company.source_state_reason = reason
    elif reason is not None:
        company.source_state_reason = reason
    for field, value in values.items():
        setattr(company, field, value)
    return _commit_company(db, company)


def _set_enabled(db: Session, company_id: int, *, enabled: bool, reason: str) -> WatchListCompany:
    company = get_company(db, company_id)
    target_state = SourceState.UNVERIFIED.value if enabled else SourceState.DISABLED.value
    company.enabled = enabled
    if company.source_state != target_state:
        company.source_history.append(
            WatchListSourceStateEvent(
                from_state=company.source_state,
                to_state=target_state,
                reason=reason,
            )
        )
        company.source_state = target_state
        company.source_state_reason = reason
    return _commit_company(db, company)


def enable_company(db: Session, company_id: int) -> WatchListCompany:
    return _set_enabled(
        db,
        company_id,
        enabled=True,
        reason="Company enabled; official source requires verification.",
    )


def disable_company(db: Session, company_id: int) -> WatchListCompany:
    return _set_enabled(
        db,
        company_id,
        enabled=False,
        reason="Company disabled by user.",
    )


def delete_company(db: Session, company_id: int, *, confirmed: bool) -> None:
    if not confirmed:
        raise ValueError("Company deletion requires confirmation")
    company = get_company(db, company_id)
    if company.source_history:
        raise SourceHistoryDeleteError("Watch List company has source history")
    db.delete(company)
    db.commit()
    logger.info("watchlist company deleted", extra={"company_id": company_id})


def to_company_read(company: WatchListCompany) -> WatchListCompanyRead:
    return WatchListCompanyRead.model_validate(company)
