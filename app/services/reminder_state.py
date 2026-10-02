"""One canonical newest-event/reminder state for Dashboard and confirmation."""

from datetime import UTC

from app.database.models import ApplicationEvent, Job


def latest_application_event(job: Job) -> ApplicationEvent | None:
    return max(
        job.application_events,
        key=lambda event: (
            event.occurred_at.replace(tzinfo=UTC)
            if event.occurred_at.tzinfo is None
            else event.occurred_at,
            event.id,
        ),
        default=None,
    )


def reminder_snapshot(job: Job) -> dict[str, object]:
    event = latest_application_event(job)
    return {
        "status": job.status,
        "application_event_id": event.id if event else None,
        "next_follow_up_date": event.next_follow_up_date.isoformat()
        if event and event.next_follow_up_date
        else None,
    }
