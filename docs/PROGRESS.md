# RoleRadar AI — Project Progress

Last updated: 2026-08-25

## Current status

The production-quality MVP foundation is implemented as a modular monolith using
FastAPI, Pydantic, SQLAlchemy, Streamlit, PostgreSQL-compatible persistence, Docker,
and GitHub Actions.

## Completed

- Structured candidate profile with target roles, locations, strengths, and gaps.
- Manual job ingestion with normalization and fingerprint-based duplicate detection.
- One-box job ingestion: users can paste an entire job page and automatically extract
  company, title, location, URL, posting date, and the full description.
- Editable extraction preview: extraction is read-only until the user reviews, corrects,
  and confirms every field; only then is the job persisted and analyzed.
- Public job-link ingestion with automatic recording and analysis, structured JobPosting
  metadata support, redirect validation, response limits, and private-network blocking.
- Transparent role classification with confidence and evidence.
- Deterministic 100-point fit scoring across role, location, domain, and technical fit.
- Structured AI explanations that cannot modify the deterministic score, with a safe
  non-LLM fallback when no API key is configured.
- Application states: New, Saved, Applied, Interview, Rejected, Offer, Ignored.
- Application records with a per-job timeline, channel, notes, next follow-up date, and
  automatic event creation when the current application status changes.
- Private CV library scanning with file fingerprints, changed-file updates, inactive-file
  handling, and support for DOCX, text-layer PDF, and TXT sources.
- Explicit per-job tailored Word CV generation with exact-source evidence validation,
  safe output naming, separate output storage, and authenticated model configuration.
- Streamlit dashboard with high-priority jobs, recent jobs, gap trends, weekly trends,
  profile editing, application tracking, and daily digest.
- Official-careers allowlist for the selected companies; no unreliable scraping.
- Local SQLite workflow and Docker Compose PostgreSQL deployment path.
- CI, linting, formatting, unit/API tests, logging, error handling, and documentation.

## Validation snapshot

- Ruff lint: passed.
- Ruff format check: passed.
- Pytest: 19 passed.
- Coverage: 63%.
- Running API exposes `/api/v1/jobs/from-text`.
- Local Dashboard returned HTTP 200 at `http://127.0.0.1:8501`.

## Next recommended milestone

1. Introduce versioned analysis storage and implement AI Career Fit Score V2 without
   overwriting legacy results.
2. Build Watch List CRUD and new-matching-job notification rules.
3. Add read-only dedicated-mailbox ingestion for allowlisted job alerts.
4. Add visible, retryable Agent workflow execution records inside the modular monolith.
5. Add verified structured-feed adapters one company at a time with contract tests.
6. Add Alembic migrations before evolving a persistent production database.
