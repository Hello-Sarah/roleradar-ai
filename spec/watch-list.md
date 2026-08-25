# Watch List Classification and Eligibility

## Purpose

Watch List answers three different questions without collapsing them into one tier: what kind of
company this is, how strategically valuable it is, and when applying produces the best expected
return. A job is always evaluated separately from its company.

## Company dimensions

### Company type

- `ai_native_forward_deployed`
- `fintech_product`
- `cloud_data_enterprise_ai`
- `financial_institution`
- `consulting_professional_services`

### Strategic priority

- `core_target`
- `monitor`
- `opportunistic`
- `strict_filter`

### Action window

- `apply_now`
- `stretch_apply`
- `apply_in_3_to_6_months`
- `apply_after_us_relocation`
- `relationship_only`

The UI displays localized labels, while APIs and storage use stable values.

## Required company data

- name and canonical domain
- company type, strategic priority, and action window
- target role patterns, target locations, positive keywords, and exclusion keywords
- location and work-authorization notes
- official source URL, source kind, verification state, last verified time, and last checked time
- enabled state, free-form rationale, created time, and updated time

CRUD supports add, edit, enable, disable, and delete. Delete requires confirmation and is blocked
when it would orphan monitored source history; disable is the normal reversible action.

## Approved initial classification

| Companies | Company type | Initial strategic priority |
|---|---|---|
| Palantir, Sierra, Cresta, Manus, Hebbia, Decagon, Glean, Harvey, Scale AI | AI-native / Forward Deployed | Core Target |
| Ant International, Airwallex | FinTech / Product | Core Target |
| Temasek | Financial Institution | Core Target |
| Abridge, Siena AI, Gradial, OpenAI, Anthropic, Perplexity | AI-native / Forward Deployed | Monitor |
| Reap, SleekFlow | FinTech / Product | Monitor |
| Databricks | Cloud / Data / Enterprise AI | Monitor |
| Grab, Sea, ByteDance, Ramp, Stripe | FinTech / Product | Opportunistic |
| Snowflake, AWS, Microsoft, Google, Salesforce | Cloud / Data / Enterprise AI | Opportunistic |
| HSBC, Standard Chartered, JPMorgan, Goldman Sachs | Financial Institution | Strict Filter |
| Capgemini | Consulting / Professional Services | Strict Filter |

Every row is editable seed data, not a permanent product opinion. The user can add companies such
as Fano Labs, LORA Technologies, HKEX, Hang Seng, AIA, Manulife, BOCHK, or virtual banks.

## Job-level eligibility and expected-return decision

Every discovered or manually attached job receives its own:

- content fit and AI Career Fit Score
- location eligibility: eligible, future, unclear, or ineligible
- work-authorization evidence and uncertainty
- current expected-return class: apply now, stretch, build first, relocate first, relationship only,
  or skip
- inherited company rationale shown separately from job-specific evidence

“Remote USA” never implies global remote. Unknown location or authorization produces `unclear`, not
an assumed rejection or approval.

Financial institutions and consulting firms pass Strict Filter only when the JD contains credible
ownership, solution design, prototype/build, evaluation, deployment, or adoption evidence. Heavy
PMO, governance, reporting, vendor coordination, or steering-committee substance triggers review
and can override an AI title.

## Source status in V1

V1 records and manually verifies official career pages, official APIs, or verified structured
vendor feeds. It does not schedule polling or deliver proactive notifications. Source state is one
of `unverified`, `verified_manual`, `structured_ready`, `degraded`, or `disabled`; every state change
records time and reason.
