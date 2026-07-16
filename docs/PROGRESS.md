# RoleRadar AI — Project Progress

Last updated: 2026-07-16

## Current status

The production-quality MVP foundation is implemented as a modular monolith using
FastAPI, Pydantic, SQLAlchemy, Streamlit, PostgreSQL-compatible persistence, Docker,
and GitHub Actions.

## Completed

- Structured candidate profile with target roles, locations, strengths, and gaps.
- Manual job ingestion with normalization and fingerprint-based duplicate detection.
- One-box job ingestion: users can paste an entire job page and automatically extract
  company, title, location, URL, posting date, and the full description.
- Transparent role classification with confidence and evidence.
- Deterministic 100-point fit scoring across role, location, domain, and technical fit.
- Structured AI explanations that cannot modify the deterministic score, with a safe
  non-LLM fallback when no API key is configured.
- Application states: New, Saved, Applied, Interview, Rejected, Offer, Ignored.
- Streamlit dashboard with high-priority jobs, recent jobs, gap trends, weekly trends,
  profile editing, application tracking, and daily digest.
- Official-careers allowlist for the selected companies; no unreliable scraping.
- Local SQLite workflow and Docker Compose PostgreSQL deployment path.
- CI, linting, formatting, unit/API tests, logging, error handling, and documentation.

## Validation snapshot

- Ruff lint: passed.
- Ruff format check: passed.
- Pytest: 8 passed.
- Coverage: 70%.
- Running API exposes `/api/v1/jobs/from-text`.
- Local Dashboard returned HTTP 200 at `http://127.0.0.1:8501`.

## Next recommended milestone

1. Add an editable extraction preview before persisting a pasted job.
2. Version scoring rubrics and candidate profiles before supporting reanalysis.
3. Add verified structured-feed adapters one company at a time with contract tests.
4. Add golden evaluation data for classification and skill-gap precision.
5. Add Alembic migrations before evolving a persistent production database.
