from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from app.config import Settings
from app.database.models import ApplicationEvent
from app.schemas import ApplicationStatus, JobCreate
from app.services.job_service import create_and_analyze_job, get_dashboard

AS_OF = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


def _job(db: Session, slug: str):
    return create_and_analyze_job(
        db,
        JobCreate(
            company=f"{slug.title()} AI",
            title="Applied AI Engineer",
            location="Hong Kong",
            url=f"https://example.com/jobs/{slug}",
            description=(
                "Build production AI systems with customers using Python, SQL, Docker, AWS, "
                "LLMs, RAG, evaluation, deployment, and product discovery."
            ),
        ),
        Settings(ai_explanations_enabled=False),
    )


def _event(
    job,
    *,
    occurred_at: datetime,
    follow_up: date | None,
    notes: str,
) -> None:
    job.status = ApplicationStatus.APPLIED.value
    job.application_events.append(
        ApplicationEvent(
            status=ApplicationStatus.APPLIED.value,
            occurred_at=occurred_at,
            next_follow_up_date=follow_up,
            notes=notes,
        )
    )


def test_dashboard_classifies_due_and_overdue_follow_ups_and_links_jobs(db: Session) -> None:
    overdue = _job(db, "overdue")
    due = _job(db, "due")
    future = _job(db, "future")
    resolved = _job(db, "resolved")
    _event(
        overdue,
        occurred_at=datetime(2026, 9, 20, tzinfo=UTC),
        follow_up=date(2026, 9, 30),
        notes="Overdue action",
    )
    _event(
        due,
        occurred_at=datetime(2026, 9, 30, tzinfo=UTC),
        follow_up=AS_OF.date(),
        notes="Due today",
    )
    _event(
        future,
        occurred_at=datetime(2026, 9, 30, tzinfo=UTC),
        follow_up=date(2026, 10, 2),
        notes="Future action",
    )
    _event(
        resolved,
        occurred_at=datetime(2026, 9, 20, tzinfo=UTC),
        follow_up=date(2026, 9, 29),
        notes="Old reminder",
    )
    _event(
        resolved,
        occurred_at=datetime(2026, 9, 30, tzinfo=UTC),
        follow_up=None,
        notes="Reminder resolved",
    )
    db.commit()

    dashboard = get_dashboard(db, as_of=AS_OF)

    assert [item.job.id for item in dashboard.due_follow_ups] == [overdue.id, due.id]
    assert [item.timing for item in dashboard.due_follow_ups] == ["overdue", "due"]
    assert dashboard.next_action is not None
    assert dashboard.next_action.kind == "follow_up"
    assert dashboard.next_action.job.id == overdue.id
    assert dashboard.next_action.follow_up_timing == "overdue"


def test_dashboard_next_action_uses_persisted_v2_band_not_raw_score(db: Session) -> None:
    strong = _job(db, "strong-next")
    selective = _job(db, "selective-next")
    strong.analysis.fit_score = 70
    strong.analysis.recommendation = "Strong Apply"
    selective.analysis.fit_score = 84
    selective.analysis.recommendation = "Selective"
    db.commit()

    dashboard = get_dashboard(db, as_of=AS_OF)

    assert [job.id for job in dashboard.high_priority_jobs] == [strong.id]
    assert dashboard.next_action is not None
    assert dashboard.next_action.kind == "review_job"
    assert dashboard.next_action.job.id == strong.id
    assert dashboard.next_action.follow_up_timing is None
