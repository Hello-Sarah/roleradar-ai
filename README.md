# RoleRadar AI

RoleRadar AI turns an unstructured job description into an explainable career decision. It helps
Applied AI professionals decide which roles deserve attention, understand why a role fits, identify
skill gaps, and choose a next action. It is intentionally not a job board.

## Product value

The final V1 review candidate is not a human-signed-off release. See
[current handoff](docs/HANDOFF.md) for the review status and remaining Safari, human-label,
live-provider and Docker/PostgreSQL verification boundaries.

In **Jobs**, use **Associate company** to explicitly attach a saved role to a Watch List company.
The card shows independent location/authorization/Strict Filter evidence and expected return;
company rationale is separate and never contributes JD scoring evidence. Scores, all six
dimensions, red/green flags, critical PMO warnings and version context are visible on the card.
In Career Copilot, normal questions receive a read-only, cited answer in the current UI language;
action requests still require a separate confirmation. Long JDs are presented as bounded excerpts.
Private explanations select verified JD evidence, and generated CV claims must map to a specific
source document body, never its filename. Apply the current Alembic head before starting the API.

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
persistence, and Streamlit is a thin client. JD extraction, classification, and scoring are
deterministic and stay separate from optional LLM explanations, so decisions remain inspectable when
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
mkdir -p data/cv_library data/generated_cvs
python -c 'from app.database.session import upgrade_database; upgrade_database()'
uvicorn app.main:app --reload --host 127.0.0.1
```

In a second terminal:

```bash
source .venv/bin/activate
streamlit run app/dashboard/streamlit_app.py --server.address=127.0.0.1 --browser.gatherUsageStats=false
```

Open the dashboard at `http://localhost:8501`; API documentation is at
`http://localhost:8000/docs`. The application has safe development defaults, so values in `.env`
are optional unless you need to override them. API startup also upgrades the configured database
through Alembic; never delete an existing database to upgrade. See [operations](docs/operations.md)
for backups, migration checks, troubleshooting, and the clean-release workflow.

Without `OPENAI_API_KEY`, job scoring/explanations and supported Copilot proposals have deterministic
fallbacks; tailored CV generation requires a key. `AI_EXPLANATIONS_ENABLED=false` disables provider
explanations and Copilot proposal inference, but does **not** disable provider-backed CV generation.
`OPENAI_MODEL` defaults to `gpt-4.1-mini`; `OPENAI_BASE_URL` optionally selects a compatible provider.
The private API has no authentication: keep API and dashboard on loopback or behind access controls.

An optional development Compose configuration starts PostgreSQL, the API, and dashboard:

```bash
docker compose up --build
```

Compose uses development credentials and publishes ports; it is not a hardened public deployment.
The V1 acceptance environment is local SQLite, not a live PostgreSQL/container smoke test. Configure
private persistent CV mounts separately before using containerized CV generation.

## Use the private workspace

The eight routes are Dashboard, Analyze Job, Jobs, Applications, Watch List, CV Library, Digest,
and Profile. First-visit Chinese browser preferences select Simplified Chinese; other languages
select English. `中文 / EN` persists in the browser and URL without changing saved records. Company
names and source evidence remain in their original language. At 390px, navigation and Copilot use
drawers; the primary workflow remains available.

Start in Profile, then paste a JD in Analyze Job, review/edit the extraction, and confirm analysis.
Cancel leaves no job. Inspect the six evidence-backed `career-fit-v2` dimensions (20/20/20/15/15/10),
flags, and recommendation: 85+ Must Apply, 70–84 Strong Apply, 55–69 Selective, below 55 Skip.
Save the job, change its application status, and record dated events/channel/notes/follow-up.
Dashboard shows due/overdue follow-ups and one next action; Digest uses persisted signals rather
than rerunning the model. Profile edits do not silently rescore history; explicitly reanalyze.

Watch List keeps three independent classifications: company type, strategic priority, and action
window. These describe company strategy, not a job's score or authorization. Missing eligibility
evidence stays unclear. Maintain verified source URL/kind/state and manual check time; disable a
company with source history instead of deleting it. See [the taxonomy](spec/watch-list.md).

Scan a dedicated read-only DOCX/text-layer PDF/TXT folder in CV Library, select a saved job, and
explicitly generate a draft. Facts must be exact verified source selections; unsupported claims
stop generation. Outputs and provenance are separate from source files. See [privacy](docs/privacy.md).

Copilot opening/context selection invokes no model. Its default read-only answer quotes the selected
job with record citations; provider-backed proposal inference is optional. Review the exact target,
current/proposed values, side effects, and private-data use before confirming a supported action.
Cancel makes no business mutation; repeat confirmation returns the original idempotent result.
Bulk edits, source-CV overwrite, auto-application, and Copilot deletion are forbidden. Conversation
deletion clears message bodies and retains non-content action audit records.

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

The release harness exercises production paths with synthetic data and deterministic provider
substitutes. It does not establish live-provider accuracy. Twenty-five subjective JD labels still
require product-owner review; a passing automated gate is not human acceptance. Full Chromium/WebKit,
axe accessibility, immutable acceptance evidence, and screenshot review instructions are in
[operations](docs/operations.md#release-evidence-and-user-acceptance).

## Privacy and public-demo status

The private product stores the records a user chooses to manage. CV inputs, extracted CV text, and
generated CV files are local private data and are ignored by Git.

The opt-in public, signed-out job-description demo is a separate stateless API surface.
Its privacy contract is explicit: submitted job-description text is processed for that request and
is not stored in the product database, filesystem, analytics, error reports, traces, or application
logs. It uses a versioned synthetic profile rather than private CV or profile data. No public
account, CV upload, saved job, application tracking, Watch List, or write-enabled Copilot action
will be exposed.

The public endpoint also has intentionally bounded input, request rate, provider budget,
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
- The public-demo rate/budget guard is designed for one application instance until a shared
  store replaces its in-memory state.
- Watch List monitoring, new-job notifications, dedicated-mailbox ingestion, and email/chat delivery
  are Phase 2, not active V1 features. A source marked structured-ready does not schedule checks.
- Scanned/image-only PDFs need external text extraction; V1 does not OCR them.
- The accessibility gate pins Streamlit 1.62.0 and records only its exact reviewed sidebar ARIA
  exception; upgrades require a new audit. Automated checks do not replace human assistive-tech QA.

See [project progress](docs/PROGRESS.md), [operations](docs/operations.md), and
[privacy boundaries](docs/privacy.md) for the release handoff.

## Public release checks

Before publishing or linking this repository, complete the
[public repository release checklist](docs/public-repository-checklist.md). In particular, review
the repository in a signed-out browser, run secret and dependency checks, and use GitHub `noreply`
identity for future commits. Rewriting legacy history is a separate destructive operation and is not
part of normal release preparation.

## License

This portfolio MVP is provided under the MIT License.
