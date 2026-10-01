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

`manifest.json` records version, full Git commit, dirty-worktree status, UTC start/end, OS, Python,
browser versions, model ID, prompt/rubric/dataset versions, command exit codes, and SHA-256 hashes of
every evidence file. Each command record includes the full HEAD, dirty status, commit time, exact
canonical command, and exhaustive expected artifact paths captured at execution time. A dirty
worktree, command substitution, stale or copied command provenance, missing hash, or unexpected
evidence file cannot produce release evidence.

## Acceptance record fields

Each acceptance ID in the versioned `spec/acceptance-v1.json` catalog records requirement,
preconditions, steps, expected result, automated evidence,
visual evidence when required, actual result, Pass/Fail/Blocked, tested time, environment, commit,
and linked defect. Blocked is not Pass and prevents release for Must items.

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
