# RoleRadar AI

RoleRadar AI is an explainable career intelligence MVP for professionals moving into
Applied AI roles. It helps answer which jobs deserve attention, why they fit, which
skills are missing, and what action to take next. It is intentionally not a job board.

## What works

- Paste an entire job page into one text box and automatically extract its company,
  title, location, URL, date, and description. Review and edit the extraction before
  normalized storage and duplicate detection.
- Paste a public job URL to retrieve, record, and analyze the posting automatically.
  URL ingestion rejects private-network destinations, validates redirects, and keeps
  the text-paste workflow as a fallback for JavaScript-only or access-controlled pages.
  The job then receives role classification,
  a deterministic fit score, evidence, strengths, gaps, and a recommendation.
- Maintain a structured candidate profile and track jobs through New, Saved, Applied,
  Interview, Rejected, Offer, Ignored.
- Keep an application timeline for every job with date, channel, notes, next follow-up,
  and automatic history entries whenever the current status changes.
- Scan a private folder of existing `.docx`, `.pdf`, and `.txt` CVs, then generate an
  evidence-grounded Word CV for a selected job as `名字—岗位-chatgpt.docx`.
- Use local Career Copilot sessions with minimum selected-record context. Copilot actions
  are stored as typed previews and cannot change jobs, applications, Watch List companies,
  analyses, CV artifacts, or action items until an idempotent confirmation is submitted.
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
| `CV_LIBRARY_PATH` | Read-only folder containing source CVs | `./data/cv_library` |
| `GENERATED_CV_PATH` | Folder for tailored Word CVs | `./data/generated_cvs` |

Never commit `.env` or API keys.

To use the CV Library, place source CVs in `CV_LIBRARY_PATH`, open the **CV Library**
tab, scan the folder, select a saved job, and generate the tailored CV. Generation
requires `OPENAI_API_KEY`; scanning does not. CV text is sent to the configured
OpenAI-compatible provider only when you explicitly generate a CV. Source files and
generated files are excluded from Git by default.

## Architecture

The project is a modular monolith: one deployable API, one database, and a thin
Streamlit client. This is the appropriate reliability/complexity tradeoff for the MVP.

```text
app/
  api/          HTTP boundary and validation
  analysis/     deterministic classification and LLM explanation
  copilot/      minimum context, typed proposals, and confirmed actions
  database/     SQLAlchemy session and persistence models
  dashboard/    Streamlit UI and API client
  ingestion/    normalization, fingerprinting, source allowlist
  scoring/      deterministic 100-point scoring rubric
  services/     use cases and transaction boundaries
  workflows/    persisted retryable workflow lifecycle
  workers/      scheduler-friendly digest entry point
tests/          unit and end-to-end API tests
docs/           decisions and scoring documentation
```

The request flow is `API → service → normalization/classification/scoring → optional
LLM explanation → database`. The dashboard only uses public API contracts.

Product and implementation specifications live in [`spec/`](spec/README.md), including the
target Career Fit Score V2 and Watch List/email-ingestion behavior.

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
- Profile edits do not silently rewrite historical analyses; explicit reanalysis appends
  a new immutable result tied to the active profile and rubric versions.
- Copilot conversations are local-only and do not synchronize across devices. The current
  deterministic natural-language fallback proposes save/status actions; every allowed
  operation is also available through the strict typed proposal endpoint.
- The daily digest is generated on demand or by an external scheduler; delivery by email
  or chat is intentionally out of scope.

## License

This portfolio MVP is provided under the MIT License.
