# RoleRadar AI Specifications

`spec/` defines product behavior before implementation. Specifications describe user value,
scope, acceptance criteria, data contracts, failure behavior, and migration expectations.

Current specifications:

- [`product.md`](product.md): product purpose, major workflows, and boundaries.
- [`scoring-v2.md`](scoring-v2.md): version 2 AI Career Fit Score and flag rules.
- [`watch-list-and-email.md`](watch-list-and-email.md): future Phase 2 monitoring and email ingestion.
- [`cv-library.md`](cv-library.md): private CV indexing and evidence-grounded tailoring.
- [`release-v1.md`](release-v1.md): approved V1 scope, deliverables, dependencies, and exclusions.
- [`design-system.md`](design-system.md): Calm Intelligence visual language and responsive behavior.
- [`i18n.md`](i18n.md): complete Chinese/English product behavior and terminology.
- [`watch-list.md`](watch-list.md): company taxonomy, action windows, and job-level eligibility.
- [`copilot.md`](copilot.md): contextual ChatGPT entry point and confirmed action execution.
- [`evals.md`](evals.md): AI quality datasets, graders, thresholds, and regression policy.
- [`architecture-v1.md`](architecture-v1.md): modular-monolith components, workflows, and data model.
- [`acceptance-v1.md`](acceptance-v1.md): executable V1 acceptance criteria.
- [`test-evidence.md`](test-evidence.md): evidence bundle and failure-to-retest release loop.

When implementation behavior changes, update the relevant specification and tests in the same
change. Historical analyses must retain the scoring version that produced them.
