# RoleRadar AI V1 Evals

The committed Golden Dataset is synthetic and contains no production CVs, conversations, contact
information, or credentials. Every item carries `[SYNTHETIC]` or `[REDACTED]`; the loader rejects
private-looking email addresses and phone numbers before a run.

Run the deterministic harness from the repository root:

```bash
python -m app.evals.runner --dataset evals/datasets/v1.jsonl --output artifacts/evals/v1
```

It writes `eval-summary.json` and `eval-items.jsonl`. Reports include dataset/item versions, hashes,
safe structured outputs, grader results, model/prompt identifiers, and latency, but never copy input
text. The runner validates suite minimums and bilingual references before grading.

The V1 suites contain exactly 60 JD cases, 20 CV-to-JD pairs, 30 normal Copilot cases, and 20
adversarial Copilot cases. Twenty-five JD preference cases are marked `user_review_required`; this
means their subjective recommendation labels are provisional until reviewed by the product owner.
Deterministic safety and factual-support results are never softened by that flag or by a composite
score. A future model grader may assess clarity or relevance, but it cannot be the sole factual,
grounding, write-safety, or release-pass gate.
