from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.config import Settings
from app.schemas import JobCreate
from app.services import job_service
from app.services.job_service import create_and_analyze_job, get_daily_digest

AS_OF = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


def _job(db: Session, slug: str, *, score: int, band: str, created_at: datetime):
    job = create_and_analyze_job(
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
    job.created_at = created_at
    job.analysis.fit_score = score
    job.analysis.recommendation = band
    db.commit()
    return job


def test_digest_uses_persisted_v2_bands_and_excludes_low_value_jobs(
    db: Session, monkeypatch
) -> None:
    must_apply = _job(
        db, "must", score=85, band="Must Apply", created_at=AS_OF - timedelta(hours=2)
    )
    strong_apply = _job(
        db, "strong", score=70, band="Strong Apply", created_at=AS_OF - timedelta(hours=3)
    )
    _job(db, "selective", score=84, band="Selective", created_at=AS_OF - timedelta(hours=4))
    _job(db, "old", score=90, band="Must Apply", created_at=AS_OF - timedelta(days=2))

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Digest must use persisted analysis without scoring or model calls")

    monkeypatch.setattr(job_service, "score_job_v2", fail_if_called)
    monkeypatch.setattr(job_service, "explain_fit", fail_if_called)

    digest = get_daily_digest(db, as_of=AS_OF)

    assert [job.id for job in digest.high_priority_jobs] == [must_apply.id, strong_apply.id]
    assert isinstance(digest.new_companies, list)
    assert isinstance(digest.emerging_skills, list)
    assert isinstance(digest.hiring_trends, list)


def test_empty_digest_keeps_every_signal_category_explicit(db: Session) -> None:
    digest = get_daily_digest(db, as_of=AS_OF)

    assert digest.high_priority_jobs == []
    assert digest.new_companies == []
    assert digest.emerging_skills == []
    assert digest.hiring_trends == []
