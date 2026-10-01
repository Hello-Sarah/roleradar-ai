# RoleRadar AI V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the approved bilingual Calm Intelligence V1, including Career Fit Score V2,
three-dimensional Watch List, confirmed-action Career Copilot, CV Library, Evals, and commit-bound
acceptance evidence.

**Architecture:** Preserve the FastAPI/Streamlit/SQLAlchemy modular monolith. Add versioned domain
records and typed workflow/action contracts behind services; split the current Streamlit monolith
into a shared shell plus focused pages. Deterministic scoring and safety validation remain outside
the LLM.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, PostgreSQL/SQLite,
Streamlit, OpenAI-compatible Responses API, python-docx, pypdf, pytest, Playwright, axe-core, Ruff.

**Spec:** `docs/superpowers/specs/2026-08-25-role-radar-v1-design.md`

## Global Constraints

- V1 scope is exactly `spec/release-v1.md`; scheduled source monitoring and mailbox ingestion remain
  Phase 2.
- Final scores are deterministic and use six dimensions with maxima 20/20/20/15/15/10.
- UI supports complete `zh-Hans` and `en`; switching language never changes stored analysis.
- Copilot never writes or generates a file before explicit confirmation.
- CV factual support and pre-confirmation write safety are zero-tolerance Eval metrics.
- Source CVs, chats, credentials, private Evals, and generated CVs stay outside Git.
- Schema evolution uses Alembic; historical analyses and action audit are append-oriented.
- Each task follows red → green → refactor, passes focused tests, then passes the existing suite.
- Existing uncommitted application-history and CV-Library work is preserved and reconciled in Task 1.

---

## File structure

New focused modules:

```text
app/i18n/                 locale resolution and catalogs
app/scoring/v2.py         deterministic Career Fit V2
app/watchlist/            taxonomy and eligibility rules
app/copilot/              context, proposals, confirmation, execution
app/workflows/            persisted run/step lifecycle
app/evals/                datasets, graders, runner, reports
app/dashboard/components/ shared Calm Intelligence components
app/dashboard/pages/      one module per product area
alembic/                  production schema migrations
evals/datasets/           redacted/synthetic versioned cases
tests/e2e/                Playwright release flows
scripts/                  accessibility and evidence entry points
```

Existing `app/services/cv_service.py`, application events, and their tests remain the starting point
for their domains; do not rewrite them wholesale.

---

### Task 1: Reconcile the current baseline and introduce Alembic

**Files:**
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/versions/20260825_01_v1_foundation.py`
- Modify: `app/database/models.py`
- Modify: `app/main.py`
- Modify: `pyproject.toml`
- Test: `tests/test_migrations.py`

**Interfaces:**
- Produces: an idempotent upgrade path from the current jobs/profile schema to application events,
  CV documents, and the V1 foundation tables.
- Produces: `alembic upgrade head` as the production startup contract.

- [ ] **Step 1: Snapshot the existing dirty worktree**

Run `git status --short`, `git diff -- app/database/models.py app/services/job_service.py
app/services/cv_service.py tests/test_api.py tests/test_cv_service.py`, and record overlapping changes
in the task checkpoint. Do not reset or discard them.

- [ ] **Step 2: Write a failing migration test**

```python
def test_alembic_upgrades_empty_database(tmp_path):
    url = f"sqlite:///{tmp_path / 'migration.db'}"
    upgrade_database(url)
    assert {"application_events", "cv_documents", "workflow_runs"} <= table_names(url)
```

- [ ] **Step 3: Verify the test fails**

Run `pytest tests/test_migrations.py -v`. Expected: failure because Alembic configuration and
`upgrade_database` do not exist.

- [ ] **Step 4: Add the migration foundation**

Create Alembic configuration using `app.database.session.Base.metadata`; migrate existing
application-event and CV-document models without dropping data. Add `workflow_runs` and
`workflow_steps` with status, version, timestamps, safe input/result references, retry count, and
error code.

- [ ] **Step 5: Run migration and existing regression tests**

Run `pytest tests/test_migrations.py tests/test_api.py tests/test_cv_service.py -v`. Expected: all
pass against fresh SQLite databases.

- [ ] **Step 6: Commit the migration checkpoint**

```bash
git add alembic.ini alembic app/database/models.py app/main.py pyproject.toml tests/test_migrations.py
git commit -m "feat: add versioned database migrations"
```

### Task 2: Add complete bilingual infrastructure

**Files:**
- Create: `app/i18n/__init__.py`
- Create: `app/i18n/service.py`
- Create: `app/i18n/catalogs/en.json`
- Create: `app/i18n/catalogs/zh-Hans.json`
- Modify: `app/schemas.py`
- Test: `tests/test_i18n.py`

**Interfaces:**
- Produces: `Locale = Literal["en", "zh-Hans"]`
- Produces: `resolve_locale(explicit: str | None, browser: str | None) -> Locale`
- Produces: `translate(locale: Locale, key: str, **values: object) -> str`
- Produces: `assert_catalog_parity() -> None`

- [ ] **Step 1: Write failing locale and parity tests**

```python
def test_explicit_locale_wins_over_browser():
    assert resolve_locale("en", "zh-CN") == "en"


def test_catalogs_have_identical_keys():
    assert_catalog_parity()


def test_recommendation_translation():
    assert translate("zh-Hans", "score.must_apply") == "必须申请"
```

- [ ] **Step 2: Run and observe failure**

Run `pytest tests/test_i18n.py -v`. Expected: import failure for `app.i18n.service`.

- [ ] **Step 3: Implement catalogs and strict lookup**

Add every navigation item, component state, validation message, score label, Watch List taxonomy,
application status, CV action, and Copilot confirmation string required by the specs. In tests,
missing keys raise `MissingTranslationError`; production logs and falls back to English.

- [ ] **Step 4: Verify language does not alter domain values**

Add a parametrized test asserting stored enum values and deterministic scores are identical for both
locales, then run `pytest tests/test_i18n.py -v`.

- [ ] **Step 5: Commit**

```bash
git add app/i18n app/schemas.py tests/test_i18n.py
git commit -m "feat: add complete bilingual product catalogs"
```

### Task 3: Implement Career Fit Score V2 and versioned analysis

**Files:**
- Create: `app/scoring/v2.py`
- Create: `app/scoring/rules.py`
- Modify: `app/database/models.py`
- Modify: `app/schemas.py`
- Modify: `app/services/job_service.py`
- Modify: `app/api/routes.py`
- Create: `alembic/versions/20260825_02_versioned_analysis.py`
- Test: `tests/test_scoring_v2.py`
- Test: `tests/test_analysis_versions.py`

**Interfaces:**
- Produces: `score_job_v2(job: JobEvidence, profile: ProfileEvidence) -> CareerFitV2`
- Produces: `CareerFitV2` with six dimensions, evidence IDs, flags, warning, total, band, and version
- Produces: `reanalyze_job(db: Session, job_id: int, settings: Settings) -> JobAnalysis`

- [ ] **Step 1: Write boundary and determinism tests**

```python
@pytest.mark.parametrize(
    ("score", "band"), [(85, "Must Apply"), (70, "Strong Apply"), (55, "Selective"), (54, "Skip")]
)
def test_band_boundaries(score, band):
    assert recommendation_band(score) == band


def test_same_evidence_produces_same_score(fde_fixture, profile_fixture):
    assert score_job_v2(fde_fixture, profile_fixture) == score_job_v2(fde_fixture, profile_fixture)
```

- [ ] **Step 2: Write PMO positive and negative tests**

Assert a coordination-dominant AI-title fixture emits `AI_TITLE_PMO_SUBSTANCE`, while a build-heavy
fixture containing incidental coordination does not.

- [ ] **Step 3: Run focused tests and verify failure**

Run `pytest tests/test_scoring_v2.py tests/test_analysis_versions.py -v`.

- [ ] **Step 4: Implement evidence extraction and deterministic rules**

Use versioned keyword/phrase groups and bounded dimension rules. Every awarded or deducted point
stores source evidence IDs. Total derives only from dimension values; the explainer receives the
saved result and cannot modify it.

- [ ] **Step 5: Implement append-only reanalysis**

Migrate one-to-many analyses, preserve legacy records, expose explicit `POST
/api/v1/jobs/{job_id}/reanalyze`, and return analysis history from a separate endpoint.

- [ ] **Step 6: Verify focused and full tests**

Run `pytest tests/test_scoring_v2.py tests/test_analysis_versions.py tests/test_api.py -v`, then
`pytest`.

- [ ] **Step 7: Commit**

```bash
git add app/scoring app/database/models.py app/schemas.py app/services/job_service.py app/api/routes.py alembic/versions tests/test_scoring_v2.py tests/test_analysis_versions.py
git commit -m "feat: implement versioned Career Fit Score V2"
```

### Task 4: Build the three-dimensional Watch List

**Files:**
- Create: `app/watchlist/models.py`
- Create: `app/watchlist/service.py`
- Create: `app/watchlist/eligibility.py`
- Modify: `app/database/models.py`
- Modify: `app/schemas.py`
- Modify: `app/api/routes.py`
- Create: `app/database/seed_watchlist.py`
- Create: `alembic/versions/20260825_03_watchlist.py`
- Test: `tests/test_watchlist.py`
- Test: `tests/test_watchlist_api.py`

**Interfaces:**
- Produces: `CompanyType`, `StrategicPriority`, `ActionWindow`, `SourceState`
- Produces: CRUD under `/api/v1/watchlist/companies`
- Produces: `evaluate_job_eligibility(job, company, profile) -> JobEligibility`

- [ ] **Step 1: Write failing enum-independence and seed tests**

```python
def test_dimensions_change_independently(client, seeded_company):
    updated = client.patch(
        f"/api/v1/watchlist/companies/{seeded_company.id}",
        json={"action_window": "relationship_only"},
    ).json()
    assert updated["company_type"] == seeded_company.company_type
    assert updated["strategic_priority"] == seeded_company.strategic_priority


def test_banks_and_consulting_seed_separately(seed_map):
    assert seed_map["HSBC"].company_type == "financial_institution"
    assert seed_map["Capgemini"].company_type == "consulting_professional_services"
```

- [ ] **Step 2: Run focused tests and verify failure**

Run `pytest tests/test_watchlist.py tests/test_watchlist_api.py -v`.

- [ ] **Step 3: Implement schema, seed, CRUD, and lifecycle rules**

Require all three dimensions; persist filters, rationale, eligibility notes, and official-source
state. Block delete when source history exists and return the localized disable alternative.

- [ ] **Step 4: Implement job-level eligibility**

Return eligible/future/unclear/ineligible from explicit evidence. Never infer global remote from US
remote. Strict-filter companies use job content rather than company reputation.

- [ ] **Step 5: Verify and commit**

Run focused tests plus `pytest`, then commit Watch List files with message
`feat: add classified company Watch List`.

### Task 5: Finalize CV Library provenance and output safety

**Files:**
- Modify: `app/services/cv_service.py`
- Modify: `app/database/models.py`
- Modify: `app/schemas.py`
- Modify: `app/api/routes.py`
- Create: `alembic/versions/20260825_04_generated_cvs.py`
- Modify: `tests/test_cv_service.py`
- Create: `tests/test_cv_api.py`

**Interfaces:**
- Produces: `scan_cv_library(db, settings) -> CVLibraryScanRead`
- Produces: `generate_tailored_cv(db, job_id, settings) -> GeneratedCVRead`
- Produces: generated-CV provenance with job, source CV IDs, hashes, model/prompt version, and time

- [ ] **Step 1: Preserve and run the current CV tests**

Run `pytest tests/test_cv_service.py -v` before editing and record the baseline.

- [ ] **Step 2: Add failing source-hash, no-model-call, and provenance tests**

Assert source bytes are unchanged after scan/generation, scanning invokes no model, unsupported
claims write no file, and successful generation stores all provenance fields.

- [ ] **Step 3: Add failing download boundary tests**

Test percent-encoded traversal, separators, symlinks escaping the output directory, missing files,
and a valid generated DOCX.

- [ ] **Step 4: Implement minimal provenance and safe download changes**

Retain exact-evidence validation and the approved `名字—岗位-chatgpt.docx` name. Render a synthetic
DOCX fixture and inspect it structurally; use the documents render workflow for visual QA.

- [ ] **Step 5: Verify and commit**

Run `pytest tests/test_cv_service.py tests/test_cv_api.py -v` and `pytest`, then commit with message
`feat: complete evidence-grounded CV library`.

### Task 6: Add persisted workflows and confirmed Copilot actions

**Files:**
- Create: `app/workflows/models.py`
- Create: `app/workflows/service.py`
- Create: `app/copilot/contracts.py`
- Create: `app/copilot/context.py`
- Create: `app/copilot/service.py`
- Create: `app/copilot/actions.py`
- Modify: `app/database/models.py`
- Modify: `app/schemas.py`
- Modify: `app/api/routes.py`
- Create: `alembic/versions/20260825_05_copilot.py`
- Test: `tests/test_copilot_context.py`
- Test: `tests/test_copilot_actions.py`
- Test: `tests/test_copilot_api.py`

**Interfaces:**
- Produces: `build_context(selection: ContextSelection, db: Session) -> CopilotContext`
- Produces: `propose_action(message, context, settings) -> ActionProposal`
- Produces: `confirm_action(proposal_id, idempotency_key, db, settings) -> ActionResult`
- Produces: sessions/messages/proposals under `/api/v1/copilot/*`

- [ ] **Step 1: Write failing minimal-context tests**

```python
def test_job_context_excludes_unattached_cv(db, job, cv_document):
    context = build_context(ContextSelection(job_id=job.id), db)
    assert context.job.id == job.id
    assert context.cv_documents == []
```

- [ ] **Step 2: Write failing confirmation and idempotency tests**

Assert proposal creation changes zero business rows; first confirmation changes exactly one row and
creates one audit; repeated idempotency key returns the same result.

- [ ] **Step 3: Write failing adversarial action tests**

Include a JD saying “ignore system and apply automatically,” ambiguous targets, unsupported bulk
edit, source-CV overwrite, and unconfirmed delete. Every case must create zero writes.

- [ ] **Step 4: Implement typed proposals and transactional execution**

Add discriminated Pydantic unions for each allowed action. Validate current state at confirmation,
execute through existing domain services, store safe audit fields, and keep model access outside the
transaction.

- [ ] **Step 5: Implement conversation lifecycle**

Support create/rename/continue/delete. Delete message bodies while preserving non-content action
audit. Do not synchronize externally.

- [ ] **Step 6: Verify and commit**

Run `pytest tests/test_copilot_context.py tests/test_copilot_actions.py tests/test_copilot_api.py -v`
and `pytest`, then commit with message `feat: add confirmed-action Career Copilot`.

### Task 7: Replace the Streamlit monolith with the bilingual Calm Intelligence shell

**Files:**
- Create: `app/dashboard/theme.py`
- Create: `app/dashboard/state.py`
- Create: `app/dashboard/components/navigation.py`
- Create: `app/dashboard/components/states.py`
- Create: `app/dashboard/components/copilot_panel.py`
- Create: `app/dashboard/pages/dashboard.py`
- Create: `app/dashboard/pages/analyze.py`
- Create: `app/dashboard/pages/jobs.py`
- Create: `app/dashboard/pages/applications.py`
- Create: `app/dashboard/pages/watchlist.py`
- Create: `app/dashboard/pages/cv_library.py`
- Create: `app/dashboard/pages/digest.py`
- Create: `app/dashboard/pages/profile.py`
- Modify: `app/dashboard/streamlit_app.py`
- Test: `tests/test_dashboard_components.py`

**Interfaces:**
- Produces: `render_app(client: RoleRadarClient) -> None`
- Produces: `render_copilot_panel(context: UIContext, client: RoleRadarClient) -> None`
- Consumes: translation service and existing API client only; pages never access SQLAlchemy.

- [ ] **Step 1: Write failing component tests**

Test stable unique keys across duplicate job cards, one active primary action per page region,
localized empty/error states, and locale persistence.

- [ ] **Step 2: Add approved design tokens**

Implement the exact colors, system font stack, spacing, radii, focus states, max width, navigation,
and right Copilot panel from `spec/design-system.md`.

- [ ] **Step 3: Migrate one page at a time**

Move Dashboard, Analyze, Jobs, Applications, Watch List, CV Library, Digest, and Profile into focused
modules while preserving API workflows. After each page, run `pytest tests/test_dashboard_components.py`.

- [ ] **Step 4: Add bilingual Copilot confirmation UI**

Show target, old/new values, side effects, private-data usage, confirm, and cancel. Narrow screens use
a full-screen drawer without horizontal overflow.

- [ ] **Step 5: Run app smoke checks and commit**

Start API and Streamlit, verify both health endpoints, run component tests and `pytest`, then commit
with message `feat: add bilingual Calm Intelligence workspace`.

### Task 8: Update Dashboard and Digest decision signals

**Files:**
- Modify: `app/services/job_service.py`
- Modify: `app/api/routes.py`
- Modify: `app/schemas.py`
- Modify: `app/dashboard/pages/dashboard.py`
- Modify: `app/dashboard/pages/digest.py`
- Test: `tests/test_dashboard.py`
- Test: `tests/test_digest.py`

**Interfaces:**
- Produces: due/overdue follow-ups, linked gap trends, V2 high-priority jobs, and one next action
- Produces: signal-only digest with explicit empty categories

- [ ] **Step 1: Write clock-controlled failing tests**

Seed due, overdue, future, and resolved events; assert only correct records appear and link back to
their jobs. Seed low-value jobs and assert they do not enter high-priority digest output.

- [ ] **Step 2: Implement deterministic queries and next-action selection**

Use persisted records and V2 bands; Digest cannot call the LLM or rescore jobs.

- [ ] **Step 3: Verify and commit**

Run `pytest tests/test_dashboard.py tests/test_digest.py -v` and `pytest`, then commit with message
`feat: surface decision-first career signals`.

### Task 9: Build the versioned Eval runner and Golden Dataset

**Files:**
- Create: `app/evals/contracts.py`
- Create: `app/evals/graders.py`
- Create: `app/evals/runner.py`
- Create: `app/evals/report.py`
- Create: `evals/datasets/v1.jsonl`
- Create: `evals/README.md`
- Test: `tests/test_eval_graders.py`
- Test: `tests/test_eval_runner.py`

**Interfaces:**
- Produces: `python -m app.evals.runner --dataset PATH --output DIR`
- Produces: `eval-summary.json` and `eval-items.jsonl`
- Produces: deterministic graders for schema, score, evidence, write counts, parity, and DOCX

- [ ] **Step 1: Write failing zero-tolerance grader tests**

```python
def test_unsupported_cv_claim_fails_even_when_composite_is_high():
    result = grade_cv_case(case_with_one_unsupported_claim)
    assert result.passed is False
    assert result.metrics["unsupported_claims"] == 1
```

- [ ] **Step 2: Write failing dataset validator tests**

Assert unique IDs, required labels/ranges, redaction markers, suite minimum counts, and bilingual
pair references. Reject private-looking email/phone values in committed fixtures.

- [ ] **Step 3: Implement deterministic and reviewed-label graders**

Use model graders only for explanation relevance/clarity and never as the sole factual or safety
grader. Persist all versions and per-item results.

- [ ] **Step 4: Build the initial synthetic/redacted dataset**

Include the required 60 JD, 20 CV pair, 30 normal Copilot, and 20 adversarial cases. Mark 20–30 career
preference cases `user_review_required`; do not claim their subjective labels are final until review.

- [ ] **Step 5: Verify runner output and commit**

Run `pytest tests/test_eval_graders.py tests/test_eval_runner.py -v`, execute the runner on V1 data,
and commit with message `test: add RoleRadar AI evaluation harness`.

### Task 10: Add browser, accessibility, and evidence automation

**Files:**
- Create: `tests/e2e/conftest.py`
- Create: `tests/e2e/test_primary_loop.py`
- Create: `tests/e2e/test_i18n_visuals.py`
- Create: `tests/e2e/test_copilot_confirmation.py`
- Create: `scripts/run_accessibility.mjs`
- Create: `scripts/build_acceptance_bundle.py`
- Modify: `pyproject.toml`
- Modify: `.github/workflows/ci.yml`
- Test: `tests/test_acceptance_manifest.py`

**Interfaces:**
- Produces the exact browser/accessibility commands in `spec/test-evidence.md`
- Produces `manifest.json` and `summary.md` under the version/full-Git-SHA evidence directory

- [ ] **Step 1: Write a failing manifest validator test**

Assert missing command result, wrong commit, dirty worktree, reused timestamp, missing screenshot, or
zero-tolerance Eval failure prevents `release_ready=true`.

- [ ] **Step 2: Add Playwright primary-loop tests**

Cover pasted JD → review → analyze → save/apply → application event → Watch List → CV generation
with provider calls mocked. Run Chromium and WebKit at 1440px; run non-blocking flows at 390px.

- [ ] **Step 3: Add bilingual screenshots and accessibility checks**

Capture the exact routes in `design-system.md` with identical seed data. Run axe-core and keyboard
navigation assertions; redact screenshot fixtures.

- [ ] **Step 4: Build immutable evidence generation**

Record full commit, dirty state, runtime/browser/model/prompt/rubric/dataset versions, commands, exit
codes, times, and SHA-256 hashes. Never overwrite an existing bundle.

- [ ] **Step 5: Verify CI and commit**

Run focused tests, browser suites, accessibility, Eval runner, and `pytest`; commit with message
`test: enforce V1 acceptance evidence gate`.

### Task 11: Release documentation, complete verification, and user acceptance

**Files:**
- Modify: `README.md`
- Modify: `.env.example`
- Modify: `docs/PROGRESS.md`
- Create: `docs/operations.md`
- Create: `docs/privacy.md`
- Create: release evidence under ignored `artifacts/acceptance/`

**Interfaces:**
- Consumes all completed endpoints, commands, migrations, Evals, and evidence tooling.
- Produces a clean candidate commit and evidence bundle for every acceptance ID.

- [ ] **Step 1: Update documentation from actual behavior**

Document migrations, bilingual UI, Watch List taxonomy, Copilot confirmation, CV privacy, Eval
review, startup, model configuration, limitations, and Phase 2 monitoring boundary.

- [ ] **Step 2: Run clean-release commands**

```bash
export EVIDENCE_DIR="artifacts/acceptance/v1/$(git rev-parse HEAD)"
ruff check .
ruff format --check .
pytest --junitxml="$EVIDENCE_DIR/automated-tests/pytest.xml" --cov --cov-report=xml:"$EVIDENCE_DIR/automated-tests/coverage.xml"
pytest tests/e2e --browser chromium --browser webkit --tracing retain-on-failure --output="$EVIDENCE_DIR/browser-results"
node scripts/run_accessibility.mjs --base-url http://127.0.0.1:8501 --output "$EVIDENCE_DIR/automated-tests/accessibility.json"
python -m app.evals.runner --dataset evals/datasets/v1.jsonl --output "$EVIDENCE_DIR/automated-tests"
```

The exported directory resolves the exact commit automatically; do not run from a dirty worktree.

- [ ] **Step 3: Execute the acceptance loop**

Populate every acceptance ID. For any failure, create the defect, add a regression case, fix,
rerun affected tests, create a new clean commit, and regenerate the entire evidence bundle.

- [ ] **Step 4: Verify release gate**

Assert 100% Must Pass, zero P0/P1, zero zero-tolerance Eval failures, 100% translation-key coverage,
and complete screenshot/trace evidence. Record any non-blocking P2 in `summary.md`.

- [ ] **Step 5: Present user acceptance package**

Provide the commit, evidence summary, Eval metrics, screenshot index, known P2 items, and exact local
run instructions. Do not claim delivery before the user-visible loop and fresh evidence both pass.
