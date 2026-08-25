# RoleRadar AI V1 Architecture

## Shape

RoleRadar remains a modular monolith: FastAPI owns HTTP contracts, Streamlit is a thin client,
SQLAlchemy owns persistence, and PostgreSQL is the production target. Agent workflows run inside
the same deployable application with explicit steps and Pydantic contracts. No microservices are
required for V1.

## Bounded capabilities

| Capability | Responsibility | Must not do |
|---|---|---|
| Job Intake | Fetch allowed public URL or parse text, normalize, preview, deduplicate | Score or silently persist unreviewed extraction |
| Job Intelligence | Extract evidence, classify, run scoring V2, explain saved score | Let the LLM set the final score |
| Career Copilot | Answer with selected context and propose typed actions | Write directly or execute without confirmation |
| CV Tailor | Index source CVs and create evidence-grounded DOCX | Alter source CVs or invent facts |
| Watch List | CRUD taxonomy, source state, and eligibility rules | Poll or notify in V1 |
| Digest | Summarize durable job and trend records | Rescore or create untracked claims |
| Eval Runner | Execute versioned cases and emit evidence | Use private production content as committed fixture |

## Workflow execution

Every model-backed or multi-step operation creates a workflow run containing type, contract
version, status, input references, model and prompt version, timestamps, retry count, step outputs,
errors, user confirmation, and result references. Steps are idempotent where external retries can
duplicate writes. One failed capability does not block manual job entry, deterministic score access,
or application tracking.

## Required persistent entities

- candidate profiles and profile versions
- jobs, normalized fingerprints, classification, and versioned analyses
- application events
- watch companies, classifications, filters, source records, and source-state history
- CV documents, fingerprints, extracted text, generated CVs, and provenance
- chat sessions and messages
- Copilot action proposals, confirmations, and action audit
- workflow runs and workflow steps
- Eval datasets, cases, runs, and item results

All schema evolution uses Alembic; `create_all` is development bootstrap only. Historical analysis
and action audit are append-oriented and are not overwritten by profile, rubric, prompt, or model
changes.

## Failure and privacy boundaries

- Model outage returns deterministic results where available and a localized recovery message.
- Extraction failure preserves raw input for review without creating a job.
- CV evidence failure writes no generated file.
- Confirmed actions execute transactionally; failure leaves no partial write.
- Translation-key failure blocks CI; production falls back to English and logs the key.
- Credentials come only from environment variables.
- Public URL ingestion blocks local/private/reserved networks, limits redirects, size, and timeout.
- CV and conversation data are sent only when required for an explicit request.

## Observability

Use structured logs with request/workflow IDs, operation type, duration, status, and safe error code.
Never log API keys, full CV bodies, private chat text, or complete JD payloads. Health endpoints
separate API, database, model configuration, and optional source readiness.
