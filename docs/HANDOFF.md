# RoleRadar AI — Engineering Handoff

Last updated: 2026-09-30

This is the recovery document for the active V1 implementation plan. It records what is safe,
what is still under review, what failed previously, and the exact checks required before work is
called complete. Product requirements remain authoritative in `spec/`; detailed agent review
artifacts remain in `.superpowers/sdd/2026-08-25-role-radar-v1/`.

## Repository and recovery point

- Repository: `https://github.com/Hello-Sarah/roleradar-ai`
- Active branch: `codex/roleradar-v1`
- Persistent worktree: `/Users/shen/Documents/FDE Career Intelligence Agent/.worktrees/roleradar-v1`
- Task 7 implementation head before verification: `6d5c7cb`
- Accepted Task 6 implementation and fix head: `128b4f9`
- Stable demo through accepted Task 5: `f70f979`
- Implementation plan: `docs/superpowers/plans/2026-08-25-role-radar-v1.md`
- Detailed execution ledger: `.superpowers/sdd/2026-08-25-role-radar-v1/progress.md`

## Accepted scope

Tasks 1–6 have passed independent task review. Tasks 1–5 cover the database
foundation, bilingual message contracts, deterministic evidence-backed scoring, Watch List, and
the evidence-grounded CV Library. Task 6 adds the confirmed-action Career Copilot described below.

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

`python -m pytest -q` could not be executed with its normal addopts in this container because the
declared optional `pytest-cov` dependency was absent; `pip install -e '.[dev]'` could not download
the Hatchling build dependency through the environment proxy. CI or the project virtual environment
must rerun the unmodified command to independently confirm the repaired coverage report.

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

- Task 8: decision-first dashboard, daily digest, and weekly hiring trends.
- Task 9: runnable versioned Eval harness and synthetic/redacted Golden Dataset.
- Task 10: browser, accessibility, and immutable acceptance-evidence automation.
- Task 11: release documentation, final acceptance, and portfolio handoff.

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
findings. Then update both the SDD ledger and this document, create a normal completion commit, push
`codex/roleradar-v1`, and verify the remote hash with `git ls-remote`.

## Next-session startup checklist

1. Open this file and `.superpowers/sdd/2026-08-25-role-radar-v1/progress.md`.
2. Confirm the active worktree, branch, `git status`, local HEAD, and remote branch hash.
3. Do not re-dispatch Tasks 1–5; they are already accepted.
4. Do not resume Tasks 1–7. Task 8, decision-first Dashboard and Digest signals, is the next
   incomplete item in the approved V1 implementation plan.
5. Never claim Task 9's Eval harness is built until its runner, dataset, graders, CI checks, and
   fresh evidence report exist and pass.
6. After each accepted task, update this handoff, push GitHub, and verify the remote commit hash.
