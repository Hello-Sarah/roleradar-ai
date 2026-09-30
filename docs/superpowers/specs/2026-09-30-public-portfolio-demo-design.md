# RoleRadar AI Public Portfolio and Stateless Demo — Design

Date: 2026-09-30
Status: Proposed for implementation

## 1. Purpose

Create a public, recruiter-facing RoleRadar AI product page that immediately communicates the
product's value, demonstrates a real end-to-end job analysis, and links to a polished public GitHub
repository. The page is a portfolio case study, not a second private application and not a general
marketing site.

Success means a recruiter can, without signing in:

1. understand the product within the first screen;
2. paste a job description and receive a useful, explainable result;
3. see how deterministic scoring, LLM explanation, guardrails, and human review fit together;
4. inspect public source code and evidence without encountering a private-repository 404; and
5. encounter no request for personal information and leave no stored job-description data behind.

## 2. Audience and positioning

Primary audience:

- AI Product Manager and Technical Product Manager hiring teams;
- Applied AI, AI Solutions, and Forward Deployed Engineering hiring teams; and
- financial-services and enterprise-AI product leaders.

Positioning:

> RoleRadar AI turns an unstructured job description into an explainable career decision using
> deterministic scoring, evidence-grounded LLM output, and explicit human control.

The public page must distinguish the product from a generic job board or an LLM wrapper. It should
show product judgment, technical fluency, and trustworthy-AI design while stating current limits
plainly.

## 3. Product-first page structure

The approved direction is a product-first portfolio inspired by the user's CitySignal case study.
It keeps the reference's evidence-led storytelling but moves the live product and calls to action
above the narrative.

### 3.1 Hero

- Product name: `RoleRadar AI`
- Primary statement: `Turn a job description into an explainable career decision.`
- Supporting copy: analyze fit, identify skill gaps, and choose the next action without relying on
  a black-box score.
- Primary CTA: `Try the demo`
- Secondary CTA: `View GitHub`
- A compact working-product preview, not a decorative dashboard.

### 3.2 Interactive demo

- One large job-description input.
- Example input control using synthetic content.
- Explicit privacy copy: input is processed for this request and is not stored.
- Analyze action with loading, rate-limit, budget-limit, validation, provider-failure, and fallback
  states.
- Result includes classification, deterministic fit score, score breakdown, evidence, strengths,
  gaps, red/green flags, recommendation, and a grounded summary.
- Result must clearly distinguish deterministic output from model-generated explanation.
- No save, application tracking, CV generation, account, or private Copilot action is available in
  public-demo mode.

### 3.3 Product evidence

Three concise proof blocks:

1. Deterministic scoring — an LLM may extract and explain but cannot overwrite the score.
2. Human control — consequential actions in the private product require preview, validation, and
   explicit confirmation.
3. Auditable evidence — versioned decisions, source-grounded claims, regression tests, and release
   evidence.

Only capabilities that exist in the referenced public commit may be described as built. The Eval
Harness must be described as a designed framework until Task 9's runner, dataset, graders, CI gate,
and fresh evidence report are complete.

### 3.4 Case study

- Problem: job boards optimize for volume while candidates need decisions.
- 0-to-1 product scope and MVP trade-offs.
- How the scoring and explanation boundary works.
- How human review and confirmed actions work in the private product.
- Bilingual product design.
- Technical architecture and stack.
- Current capabilities and explicit limitations.
- Final Demo and GitHub CTAs.

## 4. Architecture

The public portfolio and public analysis API are separate deployable surfaces with a narrow
contract.

```text
Recruiter browser
  -> static portfolio application
       -> POST /api/v1/demo/analyze
            -> request validation and abuse controls
            -> deterministic extraction/classification/scoring
            -> optional server-side LLM explanation
            -> structured response or deterministic fallback
```

### 4.1 Static portfolio

- A small responsive static application stored in the repository under an isolated portfolio
  directory.
- No direct database access, API key, tracking pixel, authentication, or personal-data form.
- Calls only the configured public demo API origin.
- Includes an explicit environment value for the Demo API base URL.
- GitHub CTA points to the public repository's default `main` branch.

### 4.2 Stateless Demo API

Add a dedicated public endpoint rather than reusing persistence-backed job creation routes.

Contract:

```text
POST /api/v1/demo/analyze
input:  { text: string, locale: "en" | "zh-Hans" }
output: DemoAnalysisResponse
```

The endpoint:

- accepts a bounded text payload only;
- performs no database read or write;
- creates no Job, Profile, Analysis, Conversation, Workflow, Audit, CV, log payload, or file;
- uses a versioned, synthetic public-demo profile rather than the owner's private profile;
- returns stable English machine values plus localized presentation copy;
- uses the existing deterministic scoring and explanation contracts where safe;
- keeps the model provider credential exclusively on the server;
- returns deterministic fallback explanation when the provider is disabled, unavailable, timed out,
  or over budget; and
- never returns internal exceptions, prompts, provider credentials, or private configuration.

## 5. Privacy and data handling

Public-demo job descriptions are ephemeral.

- Request bodies must not be stored in the product database, filesystem, analytics, error reports,
  traces, or application logs.
- Structured logs may contain request ID, outcome class, latency, input length, locale, rate-limit
  result, model identifier, and token counts, but never job-description content or extracted text.
- No cookies are required except infrastructure-level abuse protection where unavoidable.
- No user identity, email, CV, or account is collected.
- The UI states this behavior beside the input, not only in a footer.
- Automated tests prove zero database writes, zero generated files, and redacted logs for successful
  and failed requests.

## 6. Abuse, cost, and reliability controls

The public endpoint must include defense in depth:

- strict request-body and text-length limits;
- per-IP or infrastructure-equivalent rate limiting;
- a configurable daily model-call budget;
- provider timeout and bounded retry behavior;
- deterministic fallback when model access is unavailable;
- allowed-model and allowed-base-URL configuration;
- Pydantic validation of model output;
- prompt-injection treatment: submitted text is untrusted evidence, never system instruction;
- CORS allowlist restricted to the portfolio origin and approved local development origins; and
- generic client-facing errors with request IDs for support.

The implementation must not claim that IP limiting is a security boundary when deployed behind an
untrusted proxy. Trusted proxy configuration and the effective client-IP source must be explicit.

## 7. Public GitHub readiness

The public repository is part of the product experience and must be safe before the page links it.

Required preparation:

- finish Task 7 review and place the accepted product state on `main`;
- remove user-specific absolute paths from tracked documentation;
- use a GitHub `noreply` author email for future commits;
- decide separately whether to rewrite existing public Git history containing the personal email;
- ensure `.env`, databases, CV inputs, generated CVs, evidence bundles containing private text, and
  local agent artifacts remain ignored;
- add a recruiter-oriented README with product screenshots, architecture, local setup, test
  evidence, limits, and security/privacy notes;
- enable GitHub secret scanning and dependency alerts where available; and
- confirm every public link from a signed-out browser.

History rewriting and force-pushing are destructive release operations. They require a separate
impact review immediately before execution and are not implied by implementation approval for this
design.

## 8. Visual and interaction design

- Product-first, light, calm, Apple-inspired visual language consistent with RoleRadar V1.
- English default with an English/Simplified Chinese switch; core meaning and demo result parity are
  required across locales.
- Strong typographic hierarchy, restrained blue accent, opaque content surfaces, and no decorative
  metrics.
- Responsive from 320 px through desktop with no horizontal overflow.
- Native keyboard order, visible focus, semantic headings, labeled controls, accessible status and
  error announcements, and 44 px coarse-pointer targets.
- No autoplay, heavy animation, remote icon font, or large framework solely for visual effects.

## 9. Deployment boundaries

The static portfolio and stateless Demo API may deploy independently. Deployment provider choice is
an implementation-plan decision, but the design requires:

- HTTPS public origins;
- separate preview and production environments;
- server-side secrets managed by the hosting provider;
- health checks and bounded resource configuration;
- a configurable portfolio origin and API origin;
- no connection from public-demo deployment to the owner's private production database; and
- a documented rollback to the deterministic-only demo.

The implementation must prefer the smallest operational surface that satisfies these constraints;
it must not introduce a new microservice architecture beyond the static frontend and the existing
FastAPI application with an isolated demo route.

## 10. Testing and evidence

### 10.1 API tests

- Valid English and Chinese requests return schema-valid results.
- Empty, short, oversized, malformed, and unsupported-locale requests fail safely.
- Database write count and generated-file count remain zero on success and every failure path.
- Request text is absent from captured logs.
- LLM-disabled, timeout, invalid-output, rate-limit, and daily-budget cases return the specified
  fallback or error.
- Prompt-injection fixtures cannot change scoring rules, system behavior, or response schema.
- CORS behavior accepts only configured origins.

### 10.2 Portfolio tests

- Hero, Demo, product evidence, case study, limitations, and final CTAs render in both locales.
- Demo covers loading, success, validation, fallback, rate-limit, and budget-exhausted states.
- GitHub and Demo links resolve from a signed-out browser.
- Keyboard and accessible-name checks pass.
- Desktop and 390 x 844 mobile browser smoke show no horizontal overflow.

### 10.3 Release evidence

- CI test summary and commit hash.
- Browser screenshots for desktop and mobile in both locales.
- Redacted API smoke output.
- Signed-out verification of the public GitHub link.
- A privacy test report proving no persistence or content logging.

## 11. Acceptance criteria

The feature is complete only when all of the following are true:

1. A signed-out visitor can load the public portfolio and repository.
2. A visitor can paste a JD and receive an explainable result without authentication.
3. The request creates zero durable records and leaves no submitted content in logs or files.
4. Deterministic scoring remains available when the LLM provider fails or the daily budget is
   exhausted.
5. Server credentials are absent from client assets and repository history.
6. Rate limit, size limit, timeout, fallback, and prompt-injection tests pass.
7. English and Simplified Chinese outputs have equivalent score, class, evidence, and action
   meaning.
8. Public copy distinguishes built capabilities from planned Eval Harness work.
9. The public `main` README matches the deployed behavior and documents limitations.
10. Fresh CI and browser evidence is attached to the release commit.

## 12. Out of scope

- Public accounts, authentication, saved jobs, application tracking, CV upload, or CV generation.
- Access to the owner's candidate profile, private database, Copilot conversations, or Watch List.
- Public write-enabled Copilot actions.
- Payments, analytics profiles, newsletters, or lead-capture forms.
- Rebuilding the private Streamlit application in a second frontend framework.
- Claiming Task 9 Eval Harness completion before its runnable artifacts and evidence exist.
