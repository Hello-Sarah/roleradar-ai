# RoleRadar AI V1 operations

## Local startup and configuration

Use the repository root and Python 3.11+; create/activate `.venv`, install `pip install -e '.[dev]'`,
and copy `.env.example` to `.env`. Follow the two-terminal commands in [README](../README.md).
Configuration is cached per process: restart API and dashboard after edits. Environment variables
override `.env`. Dashboard uses `API_BASE_URL`, never direct database access. Health endpoints:
`http://127.0.0.1:8000/api/v1/health` and `http://127.0.0.1:8501/_stcore/health`.

Defaults: SQLite, model `gpt-4.1-mini`, optional compatible base URL, INFO logs, CV folders under
`data/`. There is no auth: keep both processes on loopback or behind independently managed access
controls. `PUBLIC_DEMO_ENABLED=false` is not an authentication switch. `DEMO_*` limits apply only
to the public demo, not private CV/Copilot calls.

## Migrations, backup, and recovery

API startup calls `upgrade_database()` before serving. The helper loads root `alembic.ini`, binds
configured `DATABASE_URL`, and upgrades to head `20260825_05`. A known legacy unversioned schema is
checked before adoption; unknown populated schemas are refused. Never drop/recreate private data
to make a migration pass.

Stop writers and back up the database, generated CV files, and protected configuration before
upgrading. Use a consistent SQLite backup or copy only after all processes stop, accounting for
WAL files. Keep file provenance and generated files together. Use an operator-managed consistent
backup for PostgreSQL. Test restore on a separate database/path before switching configuration;
do not blindly downgrade.

Apply/check the configured database explicitly:

```bash
python -c 'from app.database.session import upgrade_database; upgrade_database()'
python -c 'from alembic import command; from app.database.session import _alembic_config, settings; command.current(_alembic_config(settings.database_url))'
alembic heads
```

Bare `alembic upgrade head`/`alembic current` use the URL in `alembic.ini`, not `DATABASE_URL`. Use
the helper for environment-selected databases. For safe migration verification, set `DATABASE_URL`
to a new temporary SQLite path for each command. The Compose image includes migration assets;
container/PostgreSQL runtime needs separate smoke verification. Compose uses development credentials,
publishes ports, and has no private CV bind mounts; it is not a hardened deployment.

Unknown-schema refusal: preserve the database and inspect a copy against migration history. API
unreachable: check matching URL/port and both health endpoints. Provider failure: use deterministic
analysis/proposals; CV generation fails explicitly and must not invent fallback facts. URL failure:
paste the JD and review its preview. Stale proposal: propose again and review before confirmation.
Keep logs private as described in [privacy](privacy.md).

## Signals and the Phase 2 boundary

`python -m app.workers.daily_digest` prints persisted-record JSON on demand. An external scheduler
may invoke it, but V1 installs no scheduler and sends no email/chat notification. Watch List source
URL/kind/state and manual check time are metadata only. Company polling, new-job notifications, and
mailbox ingestion require Phase 2 adapters, deduplication, failure logging, consent, and verified
source tests before being advertised.

## Release evidence and user acceptance

The 40 Must IDs in `spec/acceptance-v1.json` are binding: 100% Pass, zero P0/P1, 100% translation keys,
all Eval thresholds met with zero zero-tolerance failures, complete screenshots/traces. Human
acceptance is separate from the automated gate.

Prerequisites: dev dependencies, `python -m playwright install chromium webkit`, Node, and
`axe-core@4.10.3` installed in a separate tooling directory. Point `ROLERADAR_NODE_MODULES` at its
`node_modules`; set `ROLERADAR_TRUSTED_NODE_PATH` to absolute trusted Node if necessary.
`PLAYWRIGHT_BROWSERS_PATH` can select a managed cache. Streamlit is pinned to 1.62.0; only its exact
reviewed sidebar ARIA exception is recorded/suppressed. Other AA/unresolved/keyboard failures block.

Commit tracked changes and confirm `git status --porcelain` is empty. Use fresh staging, **not** the
final destination: the builder refuses an existing bundle. Final location is
`artifacts/acceptance/v1/$(git rev-parse HEAD)`. Never hand-edit evidence into a pass.

```bash
export RELEASE_COMMIT="$(git rev-parse HEAD)"
export EVIDENCE_DIR="$(mktemp -d /tmp/roleradar-release.XXXXXX)"
python scripts/build_acceptance_bundle.py record --source "$EVIDENCE_DIR" --name ruff --output automated-tests/ruff.txt -- ruff check .
python scripts/build_acceptance_bundle.py record --source "$EVIDENCE_DIR" --name format --output automated-tests/format.txt -- ruff format --check .
python scripts/build_acceptance_bundle.py record --source "$EVIDENCE_DIR" --name pytest --output automated-tests/pytest-command.txt -- pytest --junitxml="$EVIDENCE_DIR/automated-tests/pytest.xml" --cov --cov-report="xml:$EVIDENCE_DIR/automated-tests/coverage.xml"
python scripts/build_acceptance_bundle.py record --source "$EVIDENCE_DIR" --name e2e --output automated-tests/e2e-results.json -- pytest tests/e2e --browser chromium --browser webkit --tracing retain-on-failure --output="$EVIDENCE_DIR/browser-results"
```

For accessibility, start isolated API/dashboard processes using a new temporary database and a
synthetic CV folder, `AI_EXPLANATIONS_ENABLED=false`, dummy key `mocked-accessibility-provider`, a
separate output folder, and matching `API_BASE_URL`. Use `scripts/run_synthetic_acceptance_api.py`
with `ACCEPTANCE_API_PORT`, and normal Streamlit with an unused loopback port. Never aim accessibility
at private data: it creates test records. Wait for both health endpoints and set `ACCEPTANCE_APP_URL`
to that isolated dashboard.

```bash
python scripts/build_acceptance_bundle.py record --source "$EVIDENCE_DIR" --name accessibility --output automated-tests/accessibility-command.txt -- node scripts/run_accessibility.mjs --base-url "$ACCEPTANCE_APP_URL" --output "$EVIDENCE_DIR/automated-tests/accessibility.json"
python scripts/build_acceptance_bundle.py record --source "$EVIDENCE_DIR" --name eval --output automated-tests/eval-command.txt -- python -m app.evals.runner --dataset evals/datasets/v1.jsonl --output "$EVIDENCE_DIR/automated-tests"
python scripts/build_acceptance_bundle.py acceptance --source "$EVIDENCE_DIR" --commit "$RELEASE_COMMIT" --environment "Local isolated synthetic acceptance"
python scripts/build_acceptance_bundle.py --source "$EVIDENCE_DIR" --output-root artifacts/acceptance --version v1 --model-id deterministic-release-v6 --prompt-version none --rubric-version eval-graders-v3 --dataset-version v1 --browser-versions chromium=playwright-managed,webkit=playwright-managed --node-version "$(node --version)"
```

Stop isolated services afterwards. Check Alembic head/current/bootstrap on a temporary database,
`git diff --check`, bundle revalidation, and replay refusal. Audit every prior bundle before/after;
they must stay byte-for-byte unchanged. Failures require an affected-ID defect, failing regression,
fix, clean commit, and entirely new evidence. Documentation changes also require new full-SHA
evidence. Recorder binds canonical commands and trusted executable identities; see
[evidence specification](../spec/test-evidence.md) and CI for the same interfaces.

Package: manifest/summary, all 40 ID records, JUnit/coverage, E2E/axe/Eval reports, screenshot index.
Desktop slots in both languages: dashboard, job-detail, watch-list, cv-library, copilot-confirmation,
error. Narrow slots: dashboard, job-detail, copilot. Both browsers produce each slot; traces are
under `browser-results/traces/`.

Review Eval summary and item grades, not only composite scores. Dataset counts: 60 JD / 20 CV /
30 normal Copilot / 20 adversarial. Adapters use production paths and deterministic provider
substitutes: this proves offline contracts/safety, not live LLM quality. Twenty-five subjective JD
labels remain provisional until product-owner review. Do not relabel to hide regressions.

For user sign-off, inspect bilingual/narrow screenshots, replay traces, execute paste→review→
analyze→save→status/follow-up→Copilot confirmation locally, and review provisional labels. Any
non-blocking P2 must be recorded in generated `summary.md` before publication; never edit an
immutable bundle. Automated READY is not human sign-off.
