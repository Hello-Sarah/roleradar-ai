# Test Evidence and Acceptance Loop

## Evidence bundle

Every candidate release writes:

```text
artifacts/acceptance/<version>/<git-commit>/
  manifest.json
  summary.md
  automated-tests/
    ruff.txt
    format.txt
    pytest.xml
    coverage.xml
    e2e-results.json
    accessibility.json
    eval-summary.json
    eval-items.jsonl
  screenshots/
    zh/
    en/
    narrow/
  browser-results/
    traces/
  defects/
```

Successful Chromium and WebKit runs retain named ZIP traces for the desktop primary loop,
narrow primary loop, and Copilot confirmation under `browser-results/traces/`. The E2E fixtures own
these contexts so the canonical `--tracing retain-on-failure` plugin option cannot delete successful
release traces. Each required ZIP must contain Playwright trace events with the named workflow,
matching browser identity, and completed actions. The six trace paths belong to the E2E command's
recorded artifact inventory and manifest hashes. Prior bundles without these traces are historical,
not evidence for the strengthened final-release gate.

`manifest.json` records version, full Git commit, dirty-worktree status, UTC start/end, OS, Python,
browser versions, model ID, prompt/rubric/dataset versions, command exit codes, and SHA-256 hashes of
every evidence file. Each command record includes the full HEAD, dirty status, commit time, exact
canonical argv, evidence-source root, and exhaustive expected artifact paths captured at execution
time. It also binds the resolved interpreter/tool path, executable SHA-256, and version output. The
validator resolves each canonical tool independently, so a PATH or basename substitution cannot
produce release evidence. A dirty worktree, command substitution, stale or copied command
provenance, missing hash, or unexpected evidence file cannot produce release evidence.

New Task 11 release bundles additionally bind output digests at command completion, not only when
assembling the bundle. The self-referential JSON command record is hashed by the bundle manifest;
its referenced screenshot/trace/ledger artifacts are hashed in the command record itself. Later
artifact substitution cannot be legitimized by recomputing only the final manifest hashes.

Screenshot capture writes `browser-results/screenshot-captures.json` from the actual browser,
observed URL locale, visible allowlisted system heading/route, visible confirmation/error/dialog
state, and viewport. It records capture time/run/commit, PNG dimensions, file and decoded-pixel
digests. The validator checks all 30 slots, exact identities, PNG decoding/CRC/dimensions and unique
pixel content; EN-to-ZH, browser, route or viewport substitution is invalid. The ledger deliberately
excludes arbitrary page text, source records and private payloads. Manual visual review remains
required; semantic capture identity is not an automated pixel-level design assessment.

Each required passing trace has exactly one browser/test/viewport context within the recorded run,
complete nonempty action identities with successful completions, ordered workflow-specific action
and expectation checkpoints, DOM snapshots, network stream and referenced replay resources.
Duplicate archive/content identities, failed actions, missing call IDs/resources, truncated traces
and minimal event-only traces cannot pass. Compact committed synthetic validator fixtures are not
release evidence. Historical bundles remain byte-for-byte preserved and are not retroactively
claimed to satisfy these stronger requirements.

## Acceptance record fields

Each acceptance ID in the versioned `spec/acceptance-v1.json` catalog records requirement,
preconditions, steps, expected result, automated evidence,
visual evidence when required, actual result, Pass/Fail/Blocked, tested time, environment, commit,
and linked defect. Every catalog criterion names its own automated check. The generator derives its
status from that named test, browser flow, accessibility result, Eval result, or release gate;
generic or unconditional Pass records are invalid. Blocked is not Pass and prevents release for
Must items.

Every named required JUnit case must actually pass. Skipped/xfail/disabled/not-run cases are Blocked,
including any member of an explicitly required parameterized population; pytest exit zero alone
does not establish a Must criterion's execution.

## Required fresh commands

```bash
ruff check .
ruff format --check .
pytest --junitxml=<bundle>/automated-tests/pytest.xml --cov --cov-report=xml:<bundle>/automated-tests/coverage.xml
pytest tests/e2e --browser chromium --browser webkit --tracing retain-on-failure --output=<bundle>/browser-results
node scripts/run_accessibility.mjs --base-url http://127.0.0.1:8501 --output <bundle>/automated-tests/accessibility.json
python -m app.evals.runner --dataset evals/datasets/v1.jsonl --output <bundle>/automated-tests
```

The implementation plan must create the referenced E2E, accessibility, and Eval entry points with
these interfaces. `<bundle>` is replaced by the exact evidence directory for the release commit.

## Failure-to-release loop

1. Run the relevant acceptance suite against a clean commit.
2. Record every failing acceptance ID and preserve raw output.
3. Create a defect with severity, reproduction, expected/actual result, and affected IDs.
4. Add or correct a failing automated/Eval case before changing implementation when feasible.
5. Implement the smallest in-scope correction.
6. Run the affected test until it passes.
7. Run the entire release regression and Evals again from a clean commit.
8. Generate a new immutable evidence bundle; never edit a previous bundle into a pass.
9. Release only after the gate below passes.

## Gate

- 100% Must acceptance criteria Pass
- Ruff, format, unit, API integration, and release-critical browser E2E pass
- translation key coverage 100%
- all Eval thresholds pass; zero-tolerance failures equal zero
- no open P0 or P1 defect
- P2 may defer only when it cannot block the primary user loop and is recorded in `summary.md`
- documentation, migration instructions, and runtime behavior agree
- screenshots exist for every visual evidence requirement

## Evidence privacy

Committed evidence uses synthetic or redacted data. Private CVs, personal chats, API payloads, and
tokens stay outside Git. Screenshots are reviewed for names, email, phone, and confidential employer
data before publishing a portfolio build.
