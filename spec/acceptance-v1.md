# RoleRadar AI V1 Acceptance Criteria

## How to use this specification

Every criterion is a Must unless marked Should. The evidence row must point to a fresh artifact for
the tested Git commit. Test data uses seeded synthetic jobs, companies, CVs, and conversations.

## Product shell and bilingual UI

### I18N-001 — First-visit language

Given no saved preference, when browser language is Chinese, then the first rendered page uses
Chinese. Given any other browser language, it uses English. Evidence: automated browser test in
both browser-language configurations and two screenshots.

### I18N-002 — Persistent switch

Given the user switches `中文 / EN`, when the page refreshes and the app is reopened, then the
selected language remains and current durable records are unchanged. Evidence: browser test plus
database before/after assertion.

### I18N-003 — Complete product copy

When every V1 route and required component state is rendered, then no untranslated key or mixed
system copy appears; company names and source evidence retain source language. Evidence: catalog
key-set unit test, E2E route sweep, and bilingual screenshots.

### UI-001 — Calm Intelligence desktop

At 1440px, each required route uses the approved tokens, hierarchy, one dominant action per region,
and persistent navigation. Evidence: screenshot set and token/style assertions.

### UI-002 — Narrow-screen non-blocking behavior

At 390px, navigation and Copilot use drawers, no page has horizontal viewport overflow, and a user
can analyze a pasted job, save it, change status, and open Copilot. Evidence: browser flow video or
trace plus screenshots.

### UI-003 — Accessibility basics

All primary flows are keyboard reachable, focus is visible, accessible names exist, and automated
WCAG AA contrast checks have no critical failure. Evidence: accessibility report and keyboard E2E.

## Job intake and intelligence

### JOB-001 — Pasted JD preview

Given a full JD, when extraction completes, then company, title, location, URL/date when present,
and description are editable before persistence; cancelling creates no job. Evidence: API and E2E.

### JOB-002 — Public URL safeguards

Given an allowed public job URL, the app records and analyzes extractable content. Given localhost,
private/reserved IP, unsafe redirect, oversized response, or timeout, it rejects the request with a
localized recovery message and stores no job. Evidence: parameterized security integration tests.

### JOB-003 — Duplicate prevention

Importing the same normalized company/title/location/URL content twice creates one job and returns a
clear duplicate result. Evidence: database row-count assertion.

### SCORE-001 — V2 dimensions and total

Every analyzed job stores all six dimensions with maximums 20/20/20/15/15/10; their sum equals the
displayed 0–100 score. Evidence: unit property tests and API schema assertion.

### SCORE-002 — Recommendation boundaries

Scores 85, 70, 55, and 54 map respectively to Must Apply, Strong Apply, Selective, and Skip in both
languages. Evidence: boundary unit tests.

### SCORE-003 — Evidence and flags

Every non-zero dimension and every Red/Green Flag references JD evidence. Unsupported flags are not
displayed. Evidence: Golden Dataset Eval and evidence-ID validator.

### SCORE-004 — AI-title PMO warning

For reviewed PMO-heavy AI-title fixtures, the warning appears and score reduction follows the
versioned rule. For build-heavy fixtures with incidental coordination, no false warning appears.
Evidence: reviewed positive/negative Eval cases.

### SCORE-005 — Version preservation

After profile or rubric changes, historical analysis is unchanged. Explicit reanalysis creates a
new version linked to its profile/rubric/model/prompt versions. Evidence: integration test.

## Application tracking

### APP-001 — State and history

Changing New → Saved → Applied updates current state and appends exactly one dated event per change;
history remains ordered and previous events are immutable. Evidence: API integration test.

### APP-002 — Detailed record

The user can record date, channel, notes, and optional follow-up; invalid dates or oversized notes
return localized validation without partial writes. Evidence: validation tests and E2E.

### APP-003 — Follow-up visibility

Due and overdue follow-ups appear on Dashboard with job and next action; resolved or future items do
not appear as overdue. Evidence: clock-controlled integration and browser tests.

## Watch List

### WATCH-001 — Three-dimensional classification

Create and edit a company with exactly one company type, strategic priority, and action window;
changing one dimension does not alter the others. Evidence: model/API tests and E2E.

### WATCH-002 — Seed classification

The initial data matches `watch-list.md`, including Financial Institution for HSBC/Standard
Chartered/JPMorgan/Goldman Sachs and Consulting for Capgemini. Evidence: seed snapshot test.

### WATCH-003 — Lifecycle

Users can add, edit, enable, disable, and confirm delete. Deleting an entity with source history is
blocked with a disable alternative. Evidence: integration tests and bilingual E2E.

### WATCH-004 — Job-level independence

A job from a Core Target is not automatically Must Apply, and a Strict Filter company job may rank
high only when its own evidence passes strict rules. Evidence: paired Golden Dataset cases.

### WATCH-005 — Eligibility uncertainty

Remote geography and work authorization are stored as evidence-backed eligible/future/unclear/
ineligible. Missing evidence yields unclear. Evidence: parameterized JD Eval cases.

### WATCH-006 — V1 source boundary

The UI can maintain source URL, kind, verification state, and manual check time but exposes no claim
that scheduled monitoring or notification is active. Evidence: API test and screenshot.

## CV Library

### CV-001 — Read-only indexed library

Scanning supported DOCX, text-layer PDF, and TXT sources creates fingerprinted records; rescanning
unchanged files creates no duplicate; removed files become inactive; source bytes remain unchanged.
Evidence: file-hash integration tests.

### CV-002 — Explicit tailored generation

Only an explicit selected-job action generates a DOCX in the configured output folder named
`名字—岗位-chatgpt.docx`. Opening pages or scanning never invokes generation. Evidence: mocked call
count, filesystem assertion, and E2E.

### CV-003 — Factual support

Every generated claim has validated source evidence; any unsupported claim stops generation and
writes no DOCX. Evidence: zero-tolerance CV Eval and output-directory assertion.

### CV-004 — Provenance and download

The result records job, source CV IDs, model/prompt version, generated time, and output hash. Only
files inside the configured output directory can be downloaded. Evidence: API and path-traversal tests.

## Career Copilot

### CHAT-001 — Contextual panel

Opening Copilot on a job displays that job as current context without calling the model; changing
page updates the visible context. Evidence: browser test and mocked model call count.

### CHAT-002 — Minimal context and sources

An answer lists record IDs/versions used and sends no unattached CV or unrelated job text. Evidence:
captured provider request fixture and response assertions.

### CHAT-003 — Bilingual grounded answer

The active language controls answer language while cited source text remains original; unsupported
personal facts are absent. Evidence: bilingual Eval pair.

### CHAT-004 — Typed proposal

For each supported operation, Copilot returns a valid versioned proposal or a clear clarification;
malformed or ambiguous targets execute nothing. Evidence: schema and intent Eval.

### CHAT-005 — Mandatory confirmation

Before confirmation, database writes and file generation equal zero. The confirmation view displays
target, current value, proposed value, side effects, and private-data usage. Evidence: API row-count
tests and screenshot.

### CHAT-006 — Exactly-once execution

Confirming once executes one transaction and creates one audit entry. Repeating the idempotency key
returns the original result and creates no duplicate. Evidence: concurrency-safe integration test.

### CHAT-007 — Conversation lifecycle

Create, rename, continue, and delete work locally. Delete removes message bodies while retaining
non-content action audit. Evidence: persistence tests and E2E.

### CHAT-008 — Forbidden actions

Bulk edit, source-CV overwrite, automatic application, and unconfirmed delete cannot be executed by
Copilot, including when requested inside untrusted JD/CV text. Evidence: adversarial Eval suite.

## Dashboard and Digest

### DASH-001 — Decision-first dashboard

Dashboard shows high-priority jobs, due follow-ups, skill gaps, hiring trends, and one next action;
each metric links to its underlying records. Evidence: seeded integration and E2E.

### DIGEST-001 — Signal-only digest

Digest contains only high-priority new jobs, new companies, emerging skills, and important trends;
empty categories state that no signal exists. Evidence: time-controlled API tests.

## Eval and release evidence

### EVAL-001 — Dataset and graders

The versioned V1 dataset meets minimum counts in `evals.md`; every item stores expected outcome and
grader results. Evidence: dataset validator output.

### EVAL-002 — Release thresholds

Every metric in `evals.md` meets its threshold for the release commit; zero-tolerance metrics have
zero failures. Evidence: Eval summary and item report.

### REL-001 — Fresh complete evidence

The release commit has a complete evidence directory matching `test-evidence.md`; all Must items are
Pass, no P0/P1 remains, and all automated commands were run after the final code change. Evidence:
manifest checksums and `summary.md`.
