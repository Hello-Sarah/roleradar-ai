# RoleRadar AI — Engineering Handoff

Last updated: 2026-10-02

## Current release status — overrides historical task notes below

Task 11's evidence-integrity work was accepted at
`8e80b9f796b33b7979e155f3339589f81854b721`, but the final whole-branch review
returned **CHANGES REQUIRED** for RR-F01–RR-F09. A single final fix wave addresses
those findings with named regressions, integrated browser tests and a fresh immutable
full-SHA evidence bundle. The exact candidate, verification results and bundle identity
are recorded in `.superpowers/sdd/2026-08-25-role-radar-v1/final-fix-report.md`.
Earlier bundles, including Task 10 and Task 11, are historical evidence, not authority
for this changed candidate. Independent final re-review is still required.

No push or merge is authorized in this wave. Human product-owner acceptance / 25 subjective
labels, live-provider quality, actual Docker/PostgreSQL runtime, current macOS Safari smoke,
manual assistive-technology checks and publication privacy review remain pending.
WebKit evidence does not constitute Safari smoke or human release signoff.

This is the recovery document for the active V1 implementation plan. It records what is safe,
what is still under review, what failed previously, and the exact checks required before work is
called complete. Product requirements remain authoritative in `spec/`; detailed agent review
artifacts remain in `.superpowers/sdd/2026-08-25-role-radar-v1/`.

## Repository and recovery point

- Repository: `https://github.com/Hello-Sarah/roleradar-ai`
- Active branch: `codex/roleradar-v1`
- Persistent worktree: repository-managed `.worktrees/roleradar-v1`
- Independently verified Task 7 implementation head: `583d56d`
- Independently verified Task 8 remote head: `ce268b3`
- Accepted Task 6 implementation and fix head: `128b4f9`
- Stable demo through accepted Task 5: `f70f979`
- Implementation plan: `docs/superpowers/plans/2026-08-25-role-radar-v1.md`
- Detailed execution ledger: `.superpowers/sdd/2026-08-25-role-radar-v1/progress.md`

## Accepted scope

Tasks 1–7 have passed independent task review. Tasks 1–5 cover the database
foundation, bilingual message contracts, deterministic evidence-backed scoring, Watch List, and
the evidence-grounded CV Library. Task 6 adds the confirmed-action Career Copilot, and Task 7 adds
the bilingual Calm Intelligence workspace described below.

Task 7's implementation and MVP hardening are complete. The 2026-09-30 verification mapped the
delivered shell, all eight routes, editable/cancellable intake, stable widget keys, localized state
copy, persistent locale selection, responsive Copilot confirmation, and API-only persistence to the
Task 7 plan and its applicable I18N/UI/JOB/CHAT acceptance criteria. Component and Streamlit
integration coverage exists for those contracts; the browser, screenshot, keyboard, and axe
artifacts required for final V1 acceptance remain intentionally scheduled for Task 10.

## Task 7 verification and coverage repair

Verification from commit `6d5c7cb` found two test-infrastructure issues rather than a product-flow
regression:

1. Current supported Streamlit releases copy `AppTest.from_function` render helpers into standalone
   temporary scripts. Runtime annotations referring to test-module fake client classes therefore
   raised `NameError`, even though the helpers receive those clients through `args`. The render
   helpers now omit those non-runtime annotations, restoring all 34 Streamlit integration tests on
   Streamlit 1.64 while leaving production typing unchanged.
2. pytest-cov was asked to resolve `app` itself through `--cov=app`. When collection/import order
   made the package visible before coverage source resolution, pytest could pass while coverage.py
   emitted module-not-measured/no-data diagnostics. Coverage source discovery now belongs to
   coverage.py (`[tool.coverage.run] source = ["app"]`, with relative paths) and pytest-cov is
   invoked with plain `--cov`. A configuration regression test protects this split.

The container did not include pytest-cov and network package installation was blocked by the
environment proxy, so the complete suite was run with only the unavailable coverage addopts
overridden. Results and exact commands:

```text
python -m pytest -q -o addopts='' tests/test_dashboard_app.py
34 passed

python -m pytest -q -o addopts=''
261 passed

ruff check .
All checks passed!

ruff format --check app tests alembic
89 files already formatted

alembic heads
20260825_05 (head)

git diff --check
clean
```

Task 7 was subsequently independently verified locally and fast-forwarded to
`origin/codex/roleradar-v1` at `806fc31`: plain `pytest` passed 261 tests with 85% total coverage,
`ruff check .` passed, and `ruff format --check` passed.

Three scoped review rounds then hardened the delivered workflow. Commit `164da8e` aligned Dashboard
drill-throughs with persisted `career-fit-v2` recommendation bands and scoring versions, displayed
persisted recommendations instead of reconstructing them from scores, and expanded rendered
Streamlit workflow coverage. Commit `583d56d` completed durable Copilot success destinations: the
Dashboard selects and visibly renders the exact created action item, while CV Library selects and
renders the exact generated CV with its ID, filename, and download URL. Scoped independent
re-review marked the remaining finding addressed with no new Critical or Important breakage.
Fresh controller verification after concurrent Demo work settled passed the complete tracked test
suite at 87% coverage, tracked Ruff lint/format, Alembic head, and diff checks.

Ruling: immutable browser traces, screenshots, axe output, and the release evidence bundle remain
Task 10 scope. Task 7 provides rendered Streamlit AppTest coverage and live smoke evidence; Task 10
must still produce the release-grade browser/accessibility artifacts before V1 acceptance.

## Local Watch List update

- Replit was added to the local Watch List as record `37` using its official Ashby structured feed:
  `https://jobs.ashbyhq.com/replit?locationId=2ba4ea42-0aac-4468-bc7b-cfd0d7842252`.
- The supplied location filter resolves to NYC (SoHo), so its action window is stored as
  `apply_after_us_relocation`; work authorization remains evidence-dependent per job.
- This is user data in the local ignored `roleradar.db`, not a repository seed change. Rebuilding or
  replacing the local database requires re-adding it unless the user later requests a seed update.

## Completed implementation: Task 8

Task 8 makes Dashboard and Digest signals deterministic over persisted records:

- Dashboard classifies the latest application event's follow-up as due today or overdue, excludes
  future reminders and reminders resolved by a newer event without a date, and retains the linked
  Job in every signal.
- Dashboard selects exactly one next action, prioritizing the oldest overdue/due follow-up and then
  the highest-ranked persisted V2 high-priority job.
- High-priority Dashboard and Digest jobs now use the persisted `career-fit-v2` recommendation
  bands `Must Apply` and `Strong Apply`; they do not guess priority from an ad-hoc score threshold.
- Digest uses only persisted analyses/classifications inside its 24-hour window. Regression tests
  fail if scoring or explanation/model code is invoked, exclude Selective and stale jobs, and prove
  that every empty signal category remains explicit.
- The Dashboard UI labels due and overdue follow-ups, links them to their stored Job, and avoids
  duplicating a review-job next action in the remaining high-priority list.

Task 8 followed red → green TDD. The initial focused run failed all three new tests because the
clock-controlled service interfaces did not yet exist. Final verification:

```text
python -m pytest -q -o addopts='' tests/test_dashboard.py tests/test_digest.py
4 passed

python -m pytest -q -o addopts='' tests/test_dashboard.py tests/test_digest.py tests/test_api.py tests/test_dashboard_app.py
50 passed

python -m pytest -q -o addopts=''
265 passed

ruff check .
All checks passed!

ruff format --check app tests alembic
91 files already formatted

alembic heads
20260825_05 (head)

git diff --check
clean
```

Plain `python -m pytest` was also attempted, but this container still lacks the declared optional
`pytest-cov` plugin and rejected `--cov`; the full 265-test run therefore overrode only pytest's
coverage addopts. This does not reopen Task 7's coverage result, which was independently verified at
`806fc31` as recorded above.

Two durable lessons from Task 8 are: reminder state belongs to the newest application event, so a
newer event with no follow-up date must resolve an older reminder; and downstream decision surfaces
must consume the stored version/band rather than silently reconstructing a score boundary.

Task 8 was subsequently independently verified locally and merged into
`origin/codex/roleradar-v1` at `ce268b3`: 265 tests passed with 85% total coverage, and Ruff and
Alembic checks were clean. This execution environment contains the equivalent merged Task 8 tree as
its base commit `ebab794`; fetching `ce268b3` was attempted first but the environment's GitHub proxy
returned HTTP 403, so no history was rewritten or existing work discarded.

## Completed implementation: Task 9

Task 9 adds the runnable, versioned V1 Eval harness and initial synthetic Golden Dataset:

- `python -m app.evals.runner --dataset PATH --output DIR` validates and grades JSONL, then emits
  privacy-safe `eval-summary.json` and `eval-items.jsonl` reports.
- Deterministic graders cover schema fields, repeat-score stability and accepted range, evidence-ID
  validity, database write counts, bilingual parity, CV claim support, and DOCX package structure.
- Unsupported CV claims, invalid evidence, unauthorized writes, and invalid DOCX structure are
  zero-tolerance failures. A high composite or future model-based clarity score cannot override one.
- Dataset validation enforces unique IDs, per-suite labels and score ranges, synthetic/redaction
  markers, suite minimum counts, mutual cross-locale pair references, 20–30 user-review JD labels,
  and rejection of private-looking emails or phone numbers.
- The committed `v1.jsonl` contains 60 JD, 20 CV-to-JD, 30 normal Copilot, and 20 adversarial cases.
  It includes mutual Chinese/English release-critical pairs and marks 25 subjective JD preference
  cases `user_review_required` without treating those labels as final.
- Item reports preserve dataset/item identity, input/output hashes, safe structured output, expected
  labels/ranges, grader results/version, model ID, prompt version, runner version, and latency. Input
  text is never copied into reports.

Task 9 followed red → green TDD. The first focused invocation failed because the new Eval modules
did not exist; after implementation, parity and raw bilingual-reference failures were also observed
and corrected before the final green run. Evidence:

```text
python -m pytest -q -o addopts='' --noconftest tests/test_eval_graders.py tests/test_eval_runner.py
7 passed

python -m app.evals.runner --dataset evals/datasets/v1.jsonl --output /tmp/roleradar-evals
passed=true; item_count=130; failed_items=0; zero_tolerance_failures=0

ruff check .
All checks passed!

ruff format --check .
98 files already formatted

alembic heads
20260825_05 (head)

git diff --check
clean
```

The normal focused and full pytest commands were attempted first, but this container is missing the
declared `python-docx`, `pypdf`, and `pytest-cov` packages. Collection stops in the existing global
`tests/conftest.py` when `app.services.cv_service` imports `docx`; network and apt installation both
failed. `--noconftest` was therefore used only for the self-contained Eval tests. A provisioned
project environment must rerun plain focused pytest and the full suite before independent acceptance.

Durable lessons: validate privacy before Pydantic normalization so even malformed items cannot hide
private data; make bilingual links mutual rather than accepting one-way references; and record safe
structured output plus its full hash instead of copying unbounded provider text into release reports.

### Task 9 independent-review follow-up

Independent review found an Important parity gap: the grader compared legacy `score` and `class`
keys, while committed JD outputs use `scores`, `classification_label`, `recommendation`,
`available_evidence_ids`, and `evidence_ids`. A Chinese result could therefore disagree on its class,
recommendation, or repeated scores while the parity grade still passed. Regression tests first
reproduced all three false passes and a Copilot `write_count` false pass.

The parity grader is now contract-aware. It compares the five structured JD decision fields, the
Copilot `action` and `write_count` fields, or the three structured CV artifact fields, depending on
the paired output schema. Locale-specific prose is deliberately excluded. Tests also load a real
release-critical English/Chinese pair from the committed dataset and require it to pass. The Ruff
Markdown formatter was applied to the implementation plan to fix the independent CI format failure.

Follow-up verification:

```text
python -m pytest -q -o addopts='' --noconftest tests/test_eval_graders.py tests/test_eval_runner.py
12 passed

python -m app.evals.runner --dataset evals/datasets/v1.jsonl --output /tmp/roleradar-evals
passed=true; item_count=130; failed_items=0; zero_tolerance_failures=0

ruff check .
All checks passed!

ruff format --check .
98 files already formatted

ruff format --preview --check docs/superpowers/plans/2026-08-25-role-radar-v1.md
1 file already formatted

alembic heads
20260825_05 (head)

git diff --check
clean
```

Lesson: bilingual parity fields must be derived from the versioned output contract, not from legacy
or display-oriented names; write-count parity is part of Copilot safety, not merely an output detail.

## Completed review: Task 6

Task 6 adds persisted Career Copilot conversations, typed action proposals, mandatory confirmation,
idempotent execution, workflow records, and non-content audit history. Initial implementation is
commit `845ceef`. Independent review found no Critical issues and five Important issues:

1. A post-commit ORM refresh failure could delete a durably committed generated CV file.
2. Confirmation did not revalidate every input used by a prepared job analysis or CV generation.
3. Current mutable Profile content could be attributed to an older Profile version.
4. Failed confirmations rolled back the workflow and audit records needed to explain the failure.
5. A proposal could create an action item for a Job deleted after proposal time; SQLite foreign-key
   enforcement also required explicit activation.

The reviewer also noted two Minor issues: client-supplied audit actor identity and whitespace-only
conversation titles. Fixes and regression tests were partially completed before a usage-limit
interruption and saved in WIP commit `221233a`, then completed in `128b4f9`. Scoped independent
re-review marked all five Important and both Minor findings addressed, with no new Critical or
Important breakage. The implementer reported 31 focused and 189 full tests passing.

## Remaining plan

- Independently re-review the final RR-F01–RR-F09 fix wave and its fresh bundle.
- Resolve explicitly pending human/runtime/manual acceptance items before release claims.

## Completed implementation: Task 10

Task 10 supplies the release-quality evidence gate for the full V1 product. It runs the primary
workflow in Chromium and WebKit at desktop and mobile widths, captures bilingual screenshots,
checks eight routes and twelve dynamic states for accessibility and keyboard operation, executes
the 130-case deterministic Eval suite, and records every Must acceptance criterion in an immutable
full-commit-SHA evidence bundle.

Independent review deliberately attacked the gate across five rounds. The accepted implementation
rejects executable substitution and attacker-controlled `PATH`, binds command results and exact
tool identities into the hashed manifest, refuses replay/overwrite, detects incomplete or duplicated
test evidence, invokes production JD/CV/Copilot paths, and prevents expected intent or parameters
from leaking into the system under test. The final review report is
`.superpowers/sdd/2026-08-25-role-radar-v1/task-10-rereview-5.md` and contains no open Critical,
Important, or Minor finding.

Accepted commit and evidence:

```text
commit: ecaded9a2850e36c7960809785a1770c309a495d
bundle: artifacts/acceptance/v1/ecaded9a2850e36c7960809785a1770c309a495d
pytest: 421 passed; 87% coverage
reviewer focused suite: 95 passed
browser E2E: 20 passed across Chromium and WebKit
Eval: 130/130 passed; 0 zero-tolerance failures
acceptance: 40 Pass; 0 Fail; 0 Blocked
accessibility: 8 routes; 12 dynamic states; 0 AA/unresolved/keyboard failures
```

All six earlier candidate bundles remain immutable and hash-consistent. The evidence builder refuses
to overwrite the accepted bundle, and the ignored user `roleradar.db` remained unchanged throughout
the Task 10 verification cycle.

## Problems encountered and lessons

### Ephemeral worktree loss

An earlier worktree under `/private/tmp` was removed during a usage rollover. Git commits survived,
but uncommitted Task 4 work did not. All continuing work now uses the persistent `.worktrees/`
directory. Create a WIP checkpoint before a usage limit when a clean reviewed commit is not yet
possible, and label it clearly so it cannot be mistaken for accepted work.

### Durable database commit versus file compensation

Task 5 and Task 6 exposed the same boundary error: cleanup code must compensate files only before or
during a failed database commit. Once provenance is durably committed, a later refresh/logging/read
failure must never delete the referenced artifact. Tests must simulate both commit failure and
post-commit ORM failure.

### Evidence validation must cover final claims

Checking whether a source quote exists is insufficient if generated headings or rewritten claims add
unsupported meaning. V1 intentionally prefers exact selected evidence and controlled labels over
more polished but unverifiable prose. Unsupported facts, metrics, dates, skills, and experience are
release-blocking.

### Prepared actions become stale

A valid proposal can become unsafe before confirmation because a Job, Profile, JD, classification,
or target role changed. Confirmation must revalidate target existence and a fingerprint/version of
every decision-relevant input, not merely the proposal type and ID.

### Failure evidence must survive rollback

Business mutations should be atomic, but the audit/workflow record describing a failed attempt must
be persisted in a separate safe boundary. A single rollback that erases both the mutation and its
failure evidence defeats the audit requirement.

### Rich JD extraction false positives

Free-text extraction can infer a supported company such as AWS from a technology mention even when
another employer appears in the heading. Task 7 must keep an editable extraction preview before
persistence and treat this as a release-blocking user-visible regression.

### SQLite behavior differs from PostgreSQL

SQLite does not enforce foreign keys unless enabled per connection. Tests that rely on PostgreSQL
constraints can therefore pass incorrectly unless the SQLite connection hook enables them and the
service still validates user-facing targets explicitly.

## Attempts that did not work

- Treating agent-reported tests as completion evidence: independent review subsequently found
  transaction and staleness defects. Fresh controller verification and task review remain mandatory.
- Publishing generated files before establishing correct compensation boundaries: this allowed
  committed provenance to point at deleted or overwritten files.
- Relying only on database foreign keys for confirmation safety: target state can change between
  proposal and confirmation, and local SQLite may not enforce the same constraints by default.
- Keeping progress only in chat context: usage interruptions and context compaction made recovery
  ambiguous. The SDD ledger plus this committed handoff document are now the source of continuity.

## Verification before accepting a task

Run from the persistent worktree using the project virtual environment:

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check app tests alembic
.venv/bin/alembic heads
git status --short
```

For Task 6, also run:

```bash
.venv/bin/pytest -q tests/test_copilot_actions.py tests/test_copilot_api.py tests/test_copilot_context.py
```

The independent reviewer must inspect the exact fix diff and return no open Critical or Important
findings. Then update both the SDD ledger and this document and create a normal completion commit.
Do not push or merge without new explicit authorization.

## Next-session startup checklist

1. Open this file and `.superpowers/sdd/2026-08-25-role-radar-v1/progress.md`.
2. Confirm the active worktree, branch, `git status`, local HEAD, and remote branch hash.
3. Do not re-dispatch Tasks 1–5; they are already accepted.
4. Do not redispatch historical Tasks 1–11. Continue only the final review/fix/re-review state
   recorded above and in the SDD ledger.
5. Use the fresh full-SHA bundle for the current candidate. Earlier passing catalogs do not
   override the final review's demonstrated product coverage gaps.
6. Update this handoff and the ledger after review. No push/merge without explicit authorization.

## 2026-10-02 Safari acceptance follow-up

- Merged the reviewed V1 candidate into local `main` at merge commit `20cb01b` and reran the full
  suite successfully before beginning native Safari checks.
- Ran the app in current macOS Safari against an isolated SQLite database. Verified Chinese and
  English switching, dashboard, Analyze Job, Jobs, Applications, Watch List, CV Library, Digest,
  Profile, deterministic score evidence, and grounded read-only Copilot answers.
- Safari exposed a bilingual action-routing defect: `把这个职位标记为已申请` was treated as a
  read-only question, while the deterministic proposal fallback only recognized English status
  labels and action verbs. The fix adds bilingual intent detection and Chinese status aliases.
- Added regression coverage at both UI intent-routing and deterministic proposal boundaries. The
  natural Chinese request now renders a pending confirmation showing `新增` → `已申请`; cancelling
  leaves the job `New` and creates no application event.
- Fresh post-fix verification: `511 passed`, 88% aggregate coverage, and `ruff check app tests`
  reports no findings. Native Safari desktop smoke passed. Narrow Safari remains covered by the
  existing 390px WebKit E2E rather than a separate native-window run.
- The repository's older unversioned local `roleradar.db` was not modified. Startup intentionally
  refused to migrate that unknown schema; use a new database or design an explicit export/migration
  path before attempting to reuse it.
