from app.database.session import SessionLocal, create_tables
from app.services.job_service import get_daily_digest


def main() -> None:
    """Print the digest as JSON so cron or a scheduler can deliver it."""
    create_tables()
    with SessionLocal() as db:
        print(get_daily_digest(db).model_dump_json(indent=2))


if __name__ == "__main__":
    main()
