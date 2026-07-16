# RoleRadar AI

RoleRadar AI is an explainable career intelligence MVP for professionals moving into
Applied AI roles. It helps answer which jobs deserve attention, why they fit, which
skills are missing, and what action to take next. It is intentionally not a job board.

## What works

- Paste a job and receive normalized storage, duplicate detection, role classification,
  a deterministic fit score, evidence, strengths, gaps, and a recommendation.
- Maintain a structured candidate profile and track jobs through New, Saved, Applied,
  Interview, Rejected, Offer, Ignored.
- View high-priority and recent jobs, skill-gap trends, weekly trends, and a daily digest.
- Use an OpenAI-compatible API for structured explanations. Without an API key, every
  workflow remains functional through a deterministic explanation fallback.
- Run locally with SQLite or as a Docker Compose stack with PostgreSQL.

## Quick start

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
uvicorn app.main:app --reload
```

In a second terminal:

```bash
source .venv/bin/activate
streamlit run app/dashboard/streamlit_app.py
```

Open the dashboard at `http://localhost:8501`; API documentation is available at
`http://localhost:8000/docs`.

Or start PostgreSQL, the API, and dashboard together:

```bash
docker compose up --build
```

## Configuration

Copy `.env.example` to `.env`. Important variables:

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy connection URL | `sqlite:///./roleradar.db` |
| `OPENAI_API_KEY` | Enables LLM explanations | unset |
| `OPENAI_BASE_URL` | Optional compatible endpoint | unset |
| `OPENAI_MODEL` | Explanation model | `gpt-4.1-mini` |
| `AI_EXPLANATIONS_ENABLED` | Explicit explanation switch | `true` |
| `API_BASE_URL` | Dashboard-to-API URL | `http://localhost:8000` |

Never commit `.env` or API keys.

## Architecture

The project is a modular monolith: one deployable API, one database, and a thin
Streamlit client. This is the appropriate reliability/complexity tradeoff for the MVP.

```text
app/
  api/          HTTP boundary and validation
  analysis/     deterministic classification and LLM explanation
  database/     SQLAlchemy session and persistence models
  dashboard/    Streamlit UI and API client
  ingestion/    normalization, fingerprinting, source allowlist
  scoring/      deterministic 100-point scoring rubric
  services/     use cases and transaction boundaries
  workers/      scheduler-friendly digest entry point
tests/          unit and end-to-end API tests
docs/           decisions and scoring documentation
```

The request flow is `API → service → normalization/classification/scoring → optional
LLM explanation → database`. The dashboard only uses public API contracts.

## Explainability and scoring

The score is always deterministic and totals 100 possible points:

- role alignment: 35
- location alignment: 15
- domain alignment: 20
- technical alignment: 30

The LLM cannot set or modify the score. It receives the score and evidence and returns
only a validated structured explanation. Failures are logged and fall back safely.
See [docs/scoring.md](docs/scoring.md) for details and limitations.

## API examples

```bash
curl -X POST http://localhost:8000/api/v1/jobs \
  -H 'Content-Type: application/json' \
  -d '{
    "company": "Example AI",
    "title": "Applied AI Engineer",
    "location": "Hong Kong",
    "description": "Build production AI products for banking customers using Python, SQL, Docker, and AWS.",
    "source": "manual"
  }'

curl http://localhost:8000/api/v1/dashboard
curl http://localhost:8000/api/v1/digest/daily
```

Generate a scheduler-friendly digest with `python -m app.workers.daily_digest`.

## Quality checks

```bash
ruff check .
ruff format --check .
pytest
```

CI runs all three checks for pushes and pull requests.

## Monitoring policy and roadmap

`app/ingestion/sources.py` lists the requested companies and their official career
pages. They deliberately remain `manual_review`: RoleRadar does not scrape HTML. In
Phase 2, each company may be enabled only when an official or vendor-supported
structured feed is verified and covered by a contract test.

- Phase 1 (implemented): repository, persistence, manual intake, explainable analysis,
  dashboard, tracker, digest/trend foundations.
- Phase 2: verified structured company adapters, scheduled monitoring, stronger
  canonical duplicate detection, delivery channels.
- Phase 3: UI polish, feedback-driven weights, prompt evaluation, golden datasets.

## Current limitations

- Keyword classification and skill extraction are transparent baselines, not semantic
  models. Low-confidence categories are explicitly marked for review.
- Profile edits do not silently rewrite historical analyses. A future reanalysis endpoint
  should version both the profile and rubric.
- `create_all` bootstraps the MVP schema. Add Alembic migrations before evolving a
  persistent production deployment.
- The daily digest is generated on demand or by an external scheduler; delivery by email
  or chat is intentionally out of scope.

## License

This portfolio MVP is provided under the MIT License.

