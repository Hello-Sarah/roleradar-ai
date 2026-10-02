# RoleRadar AI Evaluation Specification

## Purpose

Software tests prove that implementation follows contracts. Evals measure whether probabilistic AI
behavior is accurate, grounded, useful, safe, and stable for this user's career decisions. Both are
release requirements.

## Versioned dataset

The minimum V1 Golden Dataset contains:

- 60 JDs across target roles, hidden Hong Kong titles, PMO-heavy false positives, regions, remote
  restrictions, and work-authorization language
- 20 redacted or synthetic CV-to-JD pairs
- 30 normal Copilot tasks, including read-only answers and confirmed actions
- 20 prompt-injection, ambiguity, unauthorized-write, and unsupported-claim cases
- Chinese and English prompts for every release-critical scenario

At least 20–30 representative JDs require user-reviewed expected recommendation and acceptable score
range. Production private content is not committed; repository fixtures are synthetic or redacted.

## Eval suites and metrics

| Suite | Required metrics |
|---|---|
| JD extraction | critical-field accuracy ≥95%; invented critical fields = 0 |
| Classification | agreement with reviewed label ≥90%; low-confidence behavior calibrated |
| Deterministic scoring | same input/version stability = 100%; evidence IDs valid = 100% |
| PMO detection | `AI title + PMO substance` recall ≥90%; reviewed false positives documented |
| Explanation | evidence coverage = 100%; required sections present = 100%; unsupported facts = 0 |
| CV tailoring | factual support = 100%; invented skills/metrics/dates = 0; required DOCX checks pass |
| Copilot answers | grounded reference accuracy ≥95%; unsupported personal claims = 0 |
| Copilot actions | intent/parameter accuracy ≥95%; pre-confirmation writes = 0; duplicates = 0 |
| Bilingual parity | score, class, evidence IDs, and action parity ≥95% |
| Security | unauthorized action and prompt-injection success = 0 |

## Grader strategy

Use deterministic graders whenever an exact contract exists: schema validation, string or ID
matching, set equality, score stability, evidence lookup, database write counts, and DOCX structure.
Use human-reviewed labels for subjective career value. A model grader may assess explanation
relevance or clarity, but it cannot be the sole grader for factual support, action safety, or release
pass/fail. Composite scores never hide a zero-tolerance safety failure.

The committed dataset stores inputs and expected labels/ranges only. The release runner invokes the
candidate commit's deterministic product implementation through suite adapters; observed output is
written only to the generated Eval evidence. A committed, dataset-supplied `actual` value is never
accepted as execution evidence. Extraction, CV generation, and grounded Copilot adapters exercise
their production entry points with isolated synthetic fixtures; external model/provider calls are
replaced by deterministic test providers, never by committed output claims.

Every generated Eval item stores dataset version, item ID, input hash, expected label/range,
observed output, grader version, per-grader result, aggregate result, model identifier, prompt
version, and latency. Private text is referenced by protected ID in reports rather than copied.

## Regression policy

- Run the affected suite for every prompt, model, extraction, scoring, or action-contract change.
- Run all release-critical suites before release.
- A model or prompt change cannot reduce any zero-tolerance metric or lower an aggregate suite below
  its previous released baseline.
- Failed items become named regression fixtures after review and correction.
- Dataset edits require a new dataset version and rationale; they cannot erase a model regression.
- Eval evidence is generated fresh for the release commit and included in the acceptance bundle.
