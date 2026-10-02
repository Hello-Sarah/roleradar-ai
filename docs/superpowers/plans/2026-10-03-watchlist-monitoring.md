# Watch List Official-Source Monitoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Check verified Ashby and Greenhouse Watch List sources twice daily, persist and analyze
new matching jobs exactly once, and surface bilingual in-app alerts with auditable source health.

**Architecture:** Add typed source adapters and a transaction-aware `WatchListMonitor` inside the
existing modular monolith. A CLI worker, manual API action, and reversible macOS `launchd` schedule
all invoke the same service; Dashboard, Watch List, and Digest consume persisted run/check/alert
records through FastAPI.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, httpx, Streamlit, pytest,
SQLite/PostgreSQL-compatible persistence, macOS `launchd`.

**Spec:** `spec/watch-list-and-email.md`

## Global Constraints

- Only enabled companies with `source_state=structured_ready` and supported Ashby/Greenhouse public
  HTTPS sources may be polled.
- Enforce public-host validation, bounded redirects, timeout, response-size limit, and schema
  validation; never log full job bodies or private CV/Profile data.
- Job descriptions and source responses are untrusted data, never instructions.
- Monitoring must not require an LLM; optional explanations degrade through existing behavior.
- Job fingerprinting remains the canonical cross-source deduplication boundary.
- One active monitor run maximum; repeat and concurrent triggers cannot duplicate jobs or alerts.
- A failed company check must not roll back successful checks or block manual product workflows.
- Default schedule is 09:00 and 18:00 `Asia/Hong_Kong`; do not claim it is active until installed.
- All new user-visible copy must exist in both `en` and `zh-Hans`; source evidence keeps its language.
- Gmail ingestion, outbound email, login-protected scraping, automatic applications, and automatic
  application-state changes remain out of scope.
- Every task follows strict RED → GREEN TDD and ends with a focused passing suite and commit.

## Review Focus

- A source returns two records with different provider IDs but the same canonical job: create one
  job and one alert (`Task 3` regression).
- A process dies after creating a `running` row: a later run may recover a stale lock but must not
  overlap a genuinely active run (`Task 3` regression with explicit stale threshold).
- One source succeeds while another times out: preserve the successful job and finalize `partial`
  with bounded error evidence (`Task 3` regression).
- A Greenhouse/Ashby payload contains an unsafe or off-provider job URL: reject that record/source
  rather than feeding it to job creation (`Task 2` regression).
- The user marks an alert read while a refresh repeats the request: remain idempotently read and do
  not change the job's application status (`Task 5` regression).

---

### Task 1: Monitoring persistence and versioned contracts

**Files:**
- Modify: `app/database/models.py`
- Modify: `app/schemas.py`
- Create: `alembic/versions/20261003_07_watchlist_monitoring.py`
- Test: `tests/test_monitoring_models.py`
- Test: `tests/test_migrations.py`

**Interfaces:**
- Consumes: `Job.id`, `JobAnalysis.id`, `WatchListCompany.id`, existing timezone-aware timestamps.
- Produces: `MonitorRun`, `SourceCheck`, `JobAlert`; enums `MonitorTrigger`, `MonitorRunStatus`,
  `SourceCheckStatus`; Pydantic reads `MonitorRunRead`, `SourceCheckRead`, `JobAlertRead`.

- [ ] **Step 1: Write failing persistence tests**

  Add tests asserting required fields, relationships, one unread/read transition, unique
  `(job_id, watchlist_company_id)` alert identity, and only one `running` monitor row.

- [ ] **Step 2: Verify RED**

  Run: `.venv/bin/pytest tests/test_monitoring_models.py tests/test_migrations.py -q`

  Expected: FAIL because monitoring models, tables, and migration head do not exist.

- [ ] **Step 3: Add contracts and models**

  Define string enums and ORM models with timezone-aware timestamps, JSON match reasons, bounded
  error fields, foreign keys, relationships, and database uniqueness/index constraints. Extend Job
  and WatchListCompany relationships only where needed for eager reads.

- [ ] **Step 4: Add Alembic migration**

  Revision `20261003_07` follows `20261002_06`, creates three tables and constraints, and has a
  reversible downgrade. Update migration-head assertions.

- [ ] **Step 5: Verify GREEN and formatting**

  Run: `.venv/bin/pytest tests/test_monitoring_models.py tests/test_migrations.py -q`

  Expected: PASS.

- [ ] **Step 6: Commit**

  Commit: `feat: add watchlist monitoring persistence`

### Task 2: Safe Ashby and Greenhouse adapters

**Files:**
- Create: `app/ingestion/job_sources/__init__.py`
- Create: `app/ingestion/job_sources/contracts.py`
- Create: `app/ingestion/job_sources/http.py`
- Create: `app/ingestion/job_sources/ashby.py`
- Create: `app/ingestion/job_sources/greenhouse.py`
- Create: `app/ingestion/job_sources/registry.py`
- Test: `tests/fixtures/job_sources/ashby_replit.json`
- Test: `tests/fixtures/job_sources/greenhouse_example.json`
- Test: `tests/test_job_source_adapters.py`

**Interfaces:**
- Consumes: a verified `WatchListCompany` source URL/kind; the public-IP and response-boundary
  safeguards already used by `app.ingestion.url_fetcher`.
- Produces: `SourceJob(external_id: str, company: str, title: str, location: str,
  url: HttpUrl, posting_date: date | None, description: str, source: str)` and
  `fetch_source_jobs(company: WatchListCompany, transport: SourceTransport | None = None)
  -> list[SourceJob]`.

- [ ] **Step 1: Write failing adapter contract tests**

  Assert literal normalized values from both fixtures; reject unsupported provider URLs, private or
  rebinding hosts, unsafe redirects, off-provider job links, oversized bodies, timeout, invalid JSON,
  missing IDs/descriptions, and provider structure changes.

- [ ] **Step 2: Verify RED**

  Run: `.venv/bin/pytest tests/test_job_source_adapters.py -q`

  Expected: FAIL because source adapter modules do not exist.

- [ ] **Step 3: Implement contracts and guarded transport**

  Reuse/extract the existing pinned-address URL safety primitives rather than introducing a second
  security policy. Set explicit timeout and byte limits; ignore ambient proxies.

- [ ] **Step 4: Implement provider adapters and registry**

  Provider parsing is pure after transport, validates every record through Pydantic, retains only
  provider-hosted canonical URLs, and raises typed `SourceFetchError(code, safe_detail)`.

- [ ] **Step 5: Verify GREEN**

  Run: `.venv/bin/pytest tests/test_job_source_adapters.py tests/test_url_fetcher.py -q`

  Expected: PASS.

- [ ] **Step 6: Commit**

  Commit: `feat: add verified job source adapters`

### Task 3: Idempotent monitor service, matching, and failure isolation

**Files:**
- Create: `app/watchlist/monitoring.py`
- Create: `app/watchlist/matching.py`
- Modify: `app/services/job_service.py`
- Test: `tests/test_watchlist_monitoring.py`

**Interfaces:**
- Consumes: `fetch_source_jobs`, Task 1 models, `create_and_analyze_job(..., commit=False)`, active
  candidate profile, Watch List role/location/positive/exclusion criteria.
- Produces: `run_monitor(db: Session, settings: Settings, *, trigger: MonitorTrigger,
  fetcher: SourceFetcher = fetch_source_jobs, now: datetime | None = None) -> MonitorRun` and
  `match_source_job(company: WatchListCompany, job: SourceJob) -> MatchDecision`.

- [ ] **Step 1: Write failing matching tests**

  Cover role/location/positive/exclusion reasons, conservative unclear fields, original-language
  evidence, and no mutation of Career Fit scoring inputs.

- [ ] **Step 2: Write failing monitor workflow tests**

  Cover one new Replit job, repeat idempotency, duplicate provider IDs/canonical URLs/fingerprints,
  partial success, all-failed run, unsupported/unverified skip, active lock, recoverable stale lock,
  and commit failure without orphan alert/check rows.

- [ ] **Step 3: Verify RED**

  Run: `.venv/bin/pytest tests/test_watchlist_monitoring.py -q`

  Expected: FAIL because matching and monitor services do not exist.

- [ ] **Step 4: Implement pure matching**

  Return `MatchDecision(matches: bool, reasons: tuple[str, ...])`; do not alter score or application
  state. Exclusions take precedence and empty criteria do not silently match every source job.

- [ ] **Step 5: Implement run locking and per-company transaction boundaries**

  Acquire the database lock/run row, check each selected company independently, persist the existing
  job workflow plus exactly one alert, and finalize counters/status. Use a documented 60-minute stale
  threshold and safe compare/update so SQLite and PostgreSQL cannot both accept active runs.

- [ ] **Step 6: Verify GREEN and full domain regression**

  Run: `.venv/bin/pytest tests/test_watchlist_monitoring.py tests/test_api.py tests/test_watchlist.py -q`

  Expected: PASS.

- [ ] **Step 7: Commit**

  Commit: `feat: monitor verified watchlist sources`

### Task 4: Worker, monitoring API, and reversible macOS schedule

**Files:**
- Create: `app/workers/watchlist_monitor.py`
- Create: `app/workers/scheduler.py`
- Modify: `app/api/routes.py`
- Modify: `app/schemas.py`
- Modify: `Makefile`
- Create: `scripts/install_watchlist_schedule.sh`
- Create: `scripts/uninstall_watchlist_schedule.sh`
- Test: `tests/test_monitoring_api.py`
- Test: `tests/test_watchlist_worker.py`
- Test: `tests/test_scheduler.py`

**Interfaces:**
- Consumes: `run_monitor` from Task 3.
- Produces: CLI `python -m app.workers.watchlist_monitor --trigger scheduled`; endpoints
  `POST /api/v1/monitoring/runs`, `GET /api/v1/monitoring/runs`,
  `GET /api/v1/monitoring/runs/{id}`, and scheduler status response with truthful installed state.

- [ ] **Step 1: Write failing API and CLI tests**

  Assert manual/scheduled paths call the same service, return run/check counters, map lock contention
  and typed failures safely, and never expose full upstream payloads.

- [ ] **Step 2: Write failing scheduler tests**

  Render a user-specific LaunchAgent plist with 09:00/18:00 Asia/Hong_Kong invocations, absolute
  repository/venv paths, private logs, explicit install status, idempotent install, and reversible
  uninstall. Tests use a temporary HOME and never modify real launch agents.

- [ ] **Step 3: Verify RED**

  Run: `.venv/bin/pytest tests/test_monitoring_api.py tests/test_watchlist_worker.py tests/test_scheduler.py -q`

  Expected: FAIL because endpoints, worker, and scheduler utilities do not exist.

- [ ] **Step 4: Implement API and worker**

  Keep API invocation synchronous for the MVP but return a persisted run; bound HTTP client timeout
  above the per-source timeout. Worker exits nonzero only when the overall run failed, not partial.

- [ ] **Step 5: Implement explicit schedule installers**

  Install only when called by the user, verify with `launchctl print`, and never claim active merely
  because the plist template exists. Add `make monitor-now`, `schedule-install`, and
  `schedule-uninstall` targets.

- [ ] **Step 6: Verify GREEN**

  Run: `.venv/bin/pytest tests/test_monitoring_api.py tests/test_watchlist_worker.py tests/test_scheduler.py -q`

  Expected: PASS.

- [ ] **Step 7: Commit**

  Commit: `feat: expose and schedule watchlist monitoring`

### Task 5: Alert API and Dashboard decision surface

**Files:**
- Modify: `app/api/routes.py`
- Modify: `app/services/job_service.py`
- Modify: `app/schemas.py`
- Modify: `app/dashboard/pages/dashboard.py`
- Modify: `app/dashboard/state.py`
- Modify: `app/i18n/catalogs/en.json`
- Modify: `app/i18n/catalogs/zh-Hans.json`
- Test: `tests/test_monitoring_api.py`
- Test: `tests/test_dashboard_app.py`

**Interfaces:**
- Consumes: `JobAlertRead` and saved `JobRead` from Tasks 1–3.
- Produces: `GET /api/v1/alerts?unread_only=`, `POST /api/v1/alerts/{id}/read`, dashboard
  `unread_alert_count` and `new_job_alerts`, and exact-job UI drill-through.

- [ ] **Step 1: Write failing API behavior tests**

  Assert unread filtering/order, idempotent mark-read, missing alert 404, exact job provenance, and
  unchanged job status/application-event count under repeated read requests.

- [ ] **Step 2: Write failing bilingual Dashboard tests**

  Assert alert section precedes trends, complete source/discovery/score/reason copy, stable keys for
  duplicate job appearances, mark-read state, and exact-job navigation in both locales.

- [ ] **Step 3: Verify RED**

  Run: `.venv/bin/pytest tests/test_monitoring_api.py tests/test_dashboard_app.py -q`

  Expected: FAIL because alert API/dashboard fields are absent.

- [ ] **Step 4: Implement alert reads and Dashboard UI**

  Use persisted analysis/recommendation only; never rescore while rendering. Save/Ignore reuse the
  existing status widgets and confirmation behavior.

- [ ] **Step 5: Verify GREEN**

  Run: `.venv/bin/pytest tests/test_monitoring_api.py tests/test_dashboard_app.py -q`

  Expected: PASS with locale catalogs remaining key-identical.

- [ ] **Step 6: Commit**

  Commit: `feat: surface new job alerts on dashboard`

### Task 6: Watch List operations and Digest integration

**Files:**
- Modify: `app/dashboard/pages/watchlist.py`
- Modify: `app/dashboard/pages/digest.py`
- Modify: `app/i18n/catalogs/en.json`
- Modify: `app/i18n/catalogs/zh-Hans.json`
- Modify: `app/services/job_service.py`
- Modify: `app/schemas.py`
- Test: `tests/test_dashboard_app.py`
- Test: `tests/test_digest.py`

**Interfaces:**
- Consumes: run/check/scheduler APIs from Task 4 and alerts from Task 5.
- Produces: Watch List source-health cards and manual check action; Digest operational warnings and
  high-priority alerted jobs kept separate by schema.

- [ ] **Step 1: Write failing Watch List UI tests**

  Assert supported/verified monitoring state, truthful awaiting-verification and scheduler-not-
  installed states, last attempt/success/result, manual partial/failure handling, no raw backend
  error leakage, and unique widget keys in both locales.

- [ ] **Step 2: Write failing Digest tests**

  Assert only alert-backed high-priority discoveries enter the new-job section; source failures use
  `operations` and cannot appear as a job/company alert.

- [ ] **Step 3: Verify RED**

  Run: `.venv/bin/pytest tests/test_dashboard_app.py tests/test_digest.py -q`

  Expected: FAIL because monitoring UI and Digest fields are absent.

- [ ] **Step 4: Implement Watch List and Digest presentation**

  Manual check invokes Task 4 endpoint. All dates use existing locale formatting. Do not block other
  page content while a previous check is failed or partial.

- [ ] **Step 5: Verify GREEN**

  Run: `.venv/bin/pytest tests/test_dashboard_app.py tests/test_digest.py -q`

  Expected: PASS with key parity.

- [ ] **Step 6: Commit**

  Commit: `feat: add monitoring controls and digest signals`

### Task 7: End-to-end acceptance, operations, and handoff

**Files:**
- Modify: `tests/e2e/test_private_workflows.py`
- Modify: `spec/acceptance-v1.json`
- Modify: `README.md`
- Modify: `docs/operations.md`
- Modify: `docs/PROGRESS.md`
- Modify: `docs/HANDOFF.md`
- Test: `tests/test_acceptance_manifest.py`

**Interfaces:**
- Consumes: all Tasks 1–6.
- Produces: reproducible synthetic Replit flow evidence, documented schedule lifecycle, current
  limitation/status copy, and release-gate mappings for monitoring criteria.

- [ ] **Step 1: Write failing end-to-end and acceptance-gate tests**

  Cover manual check → one alert → exact job → mark read in English/Chinese and Chromium/WebKit;
  second check stays idempotent; partial source failure leaves manual analysis functional. Require
  passing traces/screenshots for Dashboard alerts and Watch List source health.

- [ ] **Step 2: Verify RED**

  Run: `.venv/bin/pytest tests/e2e/test_private_workflows.py tests/test_acceptance_manifest.py -q`

  Expected: FAIL because monitoring evidence mappings and flows are absent.

- [ ] **Step 3: Update operations and product documentation**

  Document source verification, manual command, explicit schedule install/uninstall/status, private
  log paths, failure recovery, no-email boundary, adapter limitations, and exact acceptance steps.
  Update stale V1 review language to the current shipped baseline before describing Phase 2.

- [ ] **Step 4: Run focused E2E and Eval**

  Run dual-browser monitoring E2E with isolated synthetic DB/source fixtures, then
  `.venv/bin/python -m app.evals.runner --dataset evals/datasets/v1.jsonl --output /tmp/roleradar-monitor-evals`.

  Expected: all E2E cases and 130 Eval items pass with zero zero-tolerance failures.

- [ ] **Step 5: Run complete verification**

  Run:

  ```bash
  .venv/bin/ruff check .
  .venv/bin/ruff format --check .
  .venv/bin/pytest -q
  .venv/bin/alembic heads
  git diff --check
  ```

  Expected: zero failures; Alembic head is `20261003_07`; working feature documentation matches the
  tested behavior.

- [ ] **Step 6: Native local smoke**

  Against an isolated database and synthetic provider transport, verify Dashboard alert, Watch List
  check result, Digest separation, bilingual switch, duplicate run, and unchanged manual analysis.
  Do not use private CV data or the user's legacy database.

- [ ] **Step 7: Commit and push after approval**

  Commit: `docs: verify watchlist monitoring release`

  Push each accepted feature commit to the private GitHub repository as requested; never include
  `.env`, databases, CVs, provider payloads, or generated acceptance secrets.
