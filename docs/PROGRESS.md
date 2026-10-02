# RoleRadar AI — Project Progress

Last updated: 2026-10-02

## Current status

Final whole-branch review at `8e80b9f` required changes (RR-F01–RR-F09).
The final fix candidate adds pinned URL connections, document-body CV evidence maps,
selection-only private explanations, real bilingual Copilot answers, visible dimension/flag/PMO
detail, explicit Jobs → Watch List company association with independent eligibility, conservative
visa polarity, bounded answer excerpts, and event-version-bound follow-up confirmation.
The strengthened catalog now requires rendered/API and dual-browser decision flows, not helpers
alone. Exact fresh verification and immutable full-SHA bundle are in
`.superpowers/sdd/2026-08-25-role-radar-v1/final-fix-report.md`; independent final re-review remains
required. No push/merge is authorized. Safari smoke, human signoff/25 labels, live-provider quality,
actual Docker/PostgreSQL runtime, assistive-tech and publication privacy review remain pending.

The production-quality MVP foundation is implemented as a modular monolith using
FastAPI, Pydantic, SQLAlchemy, Streamlit, PostgreSQL-compatible persistence, Docker,
and GitHub Actions.

## Completed

- Structured candidate profile with target roles, locations, strengths, and gaps.
- Manual job ingestion with normalization and fingerprint-based duplicate detection.
- One-box job ingestion: users can paste an entire job page and automatically extract
  company, title, location, URL, posting date, and the full description.
- Editable extraction preview: extraction is read-only until the user reviews, corrects,
  and confirms every field; only then is the job persisted and analyzed.
- Public job-link ingestion with automatic recording and analysis, structured JobPosting
  metadata support, redirect validation, response limits, and private-network blocking.
- Transparent role classification with confidence and evidence.
- Deterministic evidence-backed `career-fit-v2` scoring across six dimensions with maxima
  20/20/20/15/15/10 and Profile/rubric/model/prompt version preservation.
- Structured AI explanations that cannot modify the deterministic score, with a safe
  non-LLM fallback when no API key is configured.
- Application states: New, Saved, Applied, Interview, Rejected, Offer, Ignored.
- Application records with a per-job timeline, channel, notes, next follow-up date, and
  automatic event creation when the current application status changes.
- Private CV library scanning with file fingerprints, changed-file updates, inactive-file
  handling, and support for DOCX, text-layer PDF, and TXT sources.
- Explicit per-job tailored Word CV generation with exact-source evidence validation,
  safe output naming, separate output storage, and provider API-key configuration.
- Bilingual Calm Intelligence Streamlit workspace with eight focused pages, responsive
  navigation, decision-first job cards, editable extraction preview, and persistent Career
  Copilot on desktop and mobile.
- Public-URL safeguards and Watch List official-source metadata; no active monitoring service.
- Local SQLite workflow and Docker Compose PostgreSQL deployment path.
- CI, linting, formatting, unit/API tests, logging, error handling, and documentation.

## Newly accepted

- Task 6 implements persistent local Career Copilot sessions, typed action proposals, mandatory
  confirmation, workflow records, idempotent execution, and non-content audits.
- Task 7 presents those workflows through the bilingual Calm Intelligence workspace, including
  session lifecycle controls and explicit target/current/proposed/side-effect/private-data review.
- Task 7 completed three scoped review rounds through `583d56d`; durable Copilot success links now
  select and visibly render the exact created action item or generated CV. The final scoped
  re-review found no new Critical or Important breakage.
- Independent review identified transaction, stale-input, Profile-version, failure-audit, and
  deleted-target issues. Commit `128b4f9` fixed them; scoped re-review marked all findings addressed
  with no new Critical or Important breakage. See `docs/HANDOFF.md` for recovery details and lessons.
- Task 8 makes Dashboard and Digest decisions deterministic from persisted recommendation and
  application-event state.
- Task 9 provides the versioned 130-case Golden Dataset and deterministic Eval runner used by the
  release gate.
- Task 10 is accepted at `ecaded9` after five adversarial review rounds. Its immutable evidence
  bundle records dual-browser workflows, bilingual/mobile screenshots, accessibility, Eval,
  acceptance criteria, command provenance, and artifact hashes.

## Validation snapshot

- Ruff lint: passed.
- Ruff format check: passed.
- Task 6 implementer verification: 31 focused tests and 189 full tests passed.
- Task 6 independent scoped re-review: all 5 Important and 2 Minor findings addressed; no new
  Critical or Important breakage.
- Running API exposes `/api/v1/jobs/from-text` and persisted `/api/v1/copilot/*` flows.
- Local Dashboard returned HTTP 200 at `http://127.0.0.1:8501`.
- Fresh 2026-10-01 controller verification passed the complete tracked pytest suite with 87%
  coverage, tracked Ruff lint/format, Alembic head `20260825_05`, and `git diff --check`.
- Task 10 final verification: 421 tests at 87% coverage, 20/20 Chromium/WebKit E2E, 130/130 Eval,
  40/40 Must acceptance criteria, and zero unresolved accessibility or keyboard failures across
  eight routes and twelve dynamic states. Independent rereview round 5 returned APPROVED with no
  Critical, Important, or Minor findings.

## Next recommended milestone

Task 11 documents actual migration/startup, bilingual workflow, Watch List taxonomy, confirmed
Copilot actions, provider configuration, and CV/privacy boundaries. It also fixes missing Alembic
image assets with a packaging regression. See [operations](operations.md) and [privacy](privacy.md).
The final gate also retains and validates passing-flow traces for desktop/narrow primary loops and
Copilot confirmation in both browsers; earlier Task 10 bundles did not retain passing traces.
Screenshot review also found internal route slugs in Copilot's context caption and toolbar overlap
of top utility/status copy. Localized navigation labels now replace visible slugs without changing
stable API keys; extra top spacing clears the framework toolbar at desktop and narrow widths.
Rendered bilingual-route and spacing regressions protect both corrections. Generated summaries
explicitly list known P2 items (or None) instead of hiding them behind a READY flag.

The Task 11 behavior candidate `550c84627f4d564edad97da6673cbc9e0c9b01cb` passed fresh verification:
444 tests at 88% coverage; 20/20 Chromium/WebKit E2E; 130/130 Eval with zero zero-tolerance failures;
40/40 Must IDs; 372/372 bilingual keys; 30 screenshots and six required passing-flow traces;
zero AA, unresolved, or keyboard failures across eight routes and twelve dynamic states. All older
bundles remained byte-for-byte unchanged. This snapshot is not evidence for a later documentation
commit: the final documentation candidate must generate its own complete full-SHA bundle.

Final Task 11 verification is generated from its clean full-SHA candidate into
`artifacts/acceptance/v1/<full-SHA>/`; inspect that commit's summary/manifest before claiming a pass.
Ignored evidence is local, not included in a clone. The Task 10 snapshot above is historical,
not Task 11 verification.

Remaining acceptance/limitations:

- Product-owner sign-off and review of 25 provisional JD labels are pending. Offline synthetic
  Evals validate contracts/safety, not live-provider quality.
- Container/PostgreSQL runtime smoke verification is separate from SQLite acceptance. Compose
  needs separate persistent CV mounts and uses development credentials.
- OCR, semantic extraction, retention automation, and manual assistive-tech QA are not promised by
  automated checks. Streamlit upgrades require a fresh audit.
- Phase 2: add read-only allowlisted-mailbox ingestion and verified adapters with contract tests,
  then explicitly implement scheduling/new-job notification. Source metadata is not monitoring.
