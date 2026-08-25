# RoleRadar AI V1 Product and System Design

## Decision record

This design was approved through section-by-section review on 2026-08-25. The approved choices are:

- modular specification structure (方案 A)
- complete Chinese/English UI with persistent one-click switching
- Calm Intelligence visual direction, not editorial minimalism or spatial glass
- Watch List with independent company type, strategic priority, and action window
- contextual Career Copilot in a persistent right panel
- Copilot may execute typed actions only after explicit user confirmation
- software tests plus AI Evals and a fresh, commit-bound evidence bundle
- V1 Watch List CRUD/source configuration, with scheduled official-source monitoring deferred

## Product outcome

RoleRadar AI is a personal career intelligence workspace for transitioning from coordination and
consulting toward AI product ownership, technical solutioning, and build-and-ship experience. It
optimizes the expected value of applying now, not generic qualification or job volume.

The end-to-end loop is job intake → structured evidence → versioned deterministic score → career
decision → application history → evidence-grounded CV → next action through Dashboard or Copilot.

## System design

The system remains a FastAPI/Streamlit/SQLAlchemy/PostgreSQL modular monolith. Job Intake, Job
Intelligence, Career Copilot, CV Tailor, Watch List, Digest, and Eval Runner are bounded capabilities
with Pydantic contracts. Agent steps are recorded, retryable where safe, and auditable; no model has
direct database access. Deterministic scoring remains outside the LLM.

Career Copilot receives minimal selected context, cites stored records, and produces typed action
proposals. The server validates them, the UI previews exact impact, and the user confirms before a
transaction or generated file occurs. Idempotency prevents duplicate execution.

## Quality design

Acceptance criteria are executable and evidence-bound. Software tests verify contracts and state;
Evals measure probabilistic extraction, classification, explanation grounding, CV faithfulness,
Copilot behavior, bilingual parity, and adversarial safety. Release evidence is regenerated for the
final clean commit and cannot be inherited from earlier code.

## Detailed specifications

- `spec/release-v1.md`
- `spec/design-system.md`
- `spec/i18n.md`
- `spec/watch-list.md`
- `spec/copilot.md`
- `spec/scoring-v2.md`
- `spec/cv-library.md`
- `spec/evals.md`
- `spec/architecture-v1.md`
- `spec/acceptance-v1.md`
- `spec/test-evidence.md`

These documents together are the V1 release contract. In a conflict, `release-v1.md` sets scope,
`acceptance-v1.md` sets observable release behavior, and the domain specification sets internal
rules. Any change to approved scope requires user review before implementation.
