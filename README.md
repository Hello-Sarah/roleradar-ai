# RoleRadar AI

RoleRadar AI turns an unstructured job description into an explainable career decision. It helps
Applied AI professionals decide which roles deserve attention, understand why a role fits, identify
skill gaps, and choose a next action. It is intentionally not a job board.

## Product value

- Extract and normalize a job description pasted as text or fetched from a public URL, with an
  editable review step before it is saved.
- Classify the role and calculate an evidence-backed, deterministic Career Fit Score. The LLM can
  provide a validated explanation; it cannot overwrite the score.
- Show strengths, gaps, green and red flags, and a recommended next action instead of a black-box
  number.
- Maintain a private candidate profile, job pipeline, application timeline, Watch List, and daily
  decision signals.
- Create selected-job, evidence-grounded CV drafts from a local private CV library.
- Use a bilingual English/Simplified Chinese workspace, with explicit confirmation required for
  Career Copilot actions that can change private records.

## Architecture

RoleRadar AI is a modular monolith: FastAPI provides the HTTP boundary, SQLAlchemy owns private
persistence, and Streamlit is a thin client. Deterministic classification and scoring stay separate
from optional LLM extraction and explanation so the decision remains inspectable and available when
the provider is unavailable.

```text
app/
  api/          HTTP contracts and error mapping
  analysis/     classification and validated explanations
  copilot/      typed proposals and confirmed private actions
  database/     SQLAlchemy models and session boundaries
  dashboard/    Streamlit client
  ingestion/    normalization and safe URL/text intake
  scoring/      deterministic Career Fit Score rules
  services/     private-product use cases
  evals/        runnable evaluation harness and graders
tests/          unit and end-to-end regression coverage
```

The private-product request flow is `API → service → normalization/classification/scoring → optional
LLM explanation → database`. Product specifications, including scoring and public-demo design, are
in [`spec/`](spec/README.md) and [`docs/`](docs/).

## Run locally

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

Open the dashboard at `http://localhost:8501`; API documentation is at
`http://localhost:8000/docs`. The application has safe development defaults, so values in `.env`
are optional unless you need to override them. Set `OPENAI_API_KEY` only to enable provider-backed
explanations or CV generation.

To run PostgreSQL, the API, and dashboard together:

```bash
docker compose up --build
```

## Tests and evaluation

```bash
ruff check .
ruff format --check .
pytest
python -m app.evals.runner --dataset evals/datasets/v1.jsonl --output /tmp/roleradar-evals
```

The repository includes a runnable Eval Harness with a versioned, synthetic 130-item Golden Dataset.
It validates deterministic score stability, evidence IDs, database-write safety, bilingual parity,
CV-claim support, and DOCX structure without copying source text into reports. See
[`evals/README.md`](evals/README.md) for the contract and report format.

## Privacy and public-demo status

The private product stores the records a user chooses to manage. CV inputs, extracted CV text, and
generated CV files are local private data and are ignored by Git.

The public, signed-out job-description demo is being implemented as a separate stateless surface.
Its privacy contract is explicit: submitted job-description text is processed for that request and
is not stored in the product database, filesystem, analytics, error reports, traces, or application
logs. It will use a versioned synthetic profile rather than private CV or profile data. No public
account, CV upload, saved job, application tracking, Watch List, or write-enabled Copilot action
will be exposed.

The planned public endpoint also has intentionally bounded input, request rate, provider budget,
and timeout controls. Until that endpoint and its portfolio are deployed, use the local private
application described above rather than treating this repository as a hosted service.

## Current limitations

- Keyword classification and skill extraction are transparent baselines, not semantic models.
  Low-confidence categories are marked for review.
- Profile edits do not silently rewrite historical analyses; explicit reanalysis appends a new result
  tied to the active profile and scoring versions.
- The private Career Copilot is local-only. Every allowed operation is also available through a
  typed, confirmed API action.
- The daily digest runs on demand or through an external scheduler; email and chat delivery remain
  out of scope.
- The future public-demo rate/budget guard is designed for one application instance until a shared
  store replaces its in-memory state.

## Public release checks

Before publishing or linking this repository, complete the
[public repository release checklist](docs/public-repository-checklist.md). In particular, review
the repository in a signed-out browser, run secret and dependency checks, and use GitHub `noreply`
identity for future commits. Rewriting legacy history is a separate destructive operation and is not
part of normal release preparation.

## License

This portfolio MVP is provided under the MIT License.
