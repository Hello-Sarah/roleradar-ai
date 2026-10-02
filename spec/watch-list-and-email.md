# Watch List Monitoring and Future Email Ingestion

> **Status / 状态:** Phase 2 Watch List monitoring design approved on 2026-10-03. Email ingestion
> and outbound email reminders are deferred. / Phase 2 Watch List 监控设计已于 2026-10-03
> 确认；邮箱读取和邮件发送暂缓。

## Product outcome / 产品目标

RoleRadar checks reliable official job sources for enabled Watch List companies twice per day,
adds only genuinely new matching jobs, analyzes them through the existing deterministic career-fit
pipeline, and surfaces explainable in-app alerts. A source failure must never block manual intake,
job analysis, application tracking, or checks for other companies.

RoleRadar 每天两次检查已启用目标公司的可靠官方职位源，只保存真正新增且匹配的岗位，
使用现有确定性职业匹配流程进行分析，并生成可解释的应用内提醒。单个来源失败不得影响手动
录入、职位分析、投递记录或其他公司的检查。

## Approved scope / 本期范围

- Verified public Ashby and Greenhouse structured job sources.
- A reusable monitor worker invoked by a scheduler and by a manual **Check now / 立即检查** action.
- Default schedule at 09:00 and 18:00 Asia/Hong_Kong.
- Normalization, canonical deduplication, classification, deterministic scoring, and persistence of
  newly discovered jobs.
- Persistent monitor-run, per-source-check, and new-job-alert records.
- Dashboard, Watch List, and Digest presentation in complete English and Simplified Chinese.
- Read/unread alert state and links to the exact saved job.
- Source-health reporting that is visually and semantically separate from new-job alerts.

This phase does **not** read Gmail, send email, scrape login-protected pages, bypass anti-bot
controls, apply for jobs, or automatically change application status. Companies without a verified
structured source remain visible as awaiting verification and are not described as actively
monitored.

本期不读取 Gmail、不发送邮件、不抓取需要登录的页面、不绕过反爬机制、不自动投递，也不
自动改变申请状态。没有可靠结构化来源的公司继续保留并显示“等待验证”，不能被描述为
“正在监控”。

## Architecture / 架构

The feature stays inside the existing modular monolith:

```text
external scheduler / manual UI
              |
              v
      WatchListMonitor service
       /        |          \
 source adapter |     monitoring records
 (Ashby/GH)     |
                v
 normalize -> deduplicate -> classify -> deterministic score
                |
                v
          saved Job + JobAlert
                |
                v
       Dashboard / Watch List / Digest
```

The scheduler only invokes the worker. Source selection, locking, retries, job creation, analysis,
and alert creation remain application services so a future cloud scheduler can replace the local
macOS scheduler without changing product logic. This phase adds no microservice.

调度器只负责触发 Worker。来源选择、运行锁、重试、职位创建、分析和提醒均保留在应用服务
层，因此未来可以替换为云端调度器而不改写业务逻辑。本期不新增微服务。

## Source contracts / 来源契约

Each adapter receives a verified source configuration and returns versioned Pydantic records with:

- external source ID
- company, title, location, canonical URL
- posting date when provided
- complete available description
- source name and retrieval timestamp

Adapters must enforce HTTPS, approved public hosts, bounded redirects, timeout, response-size limit,
schema validation, and the existing private/reserved-network protections. Job content is untrusted
data and can never become an instruction. An adapter cannot write jobs or alerts directly.

Ashby and Greenhouse adapters have fixture-backed contract tests. Structural changes, malformed
records, timeouts, and non-success responses produce typed failures rather than partial jobs.

## Persistence / 持久化

### `monitor_runs`

- `id`, `trigger` (`scheduled` or `manual`)
- `status` (`running`, `succeeded`, `partial`, `failed`, `skipped_locked`)
- `started_at`, `completed_at`
- checked/succeeded/failed source counts
- discovered/new/matching/alert counts
- scheduler/version metadata

Only one run may be active. A second trigger records or returns `skipped_locked` without creating
jobs or alerts.

### `source_checks`

- monitor run and Watch List company IDs
- source adapter/version and source URL
- status, started/completed timestamps
- fetched/valid/new/matching counts
- stable error code and localized-display-safe detail

Every enabled, verified source selected for a run receives one check record. One failed check does
not roll back successful companies.

### `job_alerts`

- exact saved job and Watch List company IDs
- source-check ID and discovery timestamp
- match reasons and deterministic score/recommendation snapshot references
- `read_at` nullable timestamp

A unique job/source discovery constraint prevents repeat alerts. Marking an alert read never changes
the job's application status.

Existing job fingerprints remain the canonical job deduplication boundary. Historical jobs,
analyses, checks, and alerts are append-only except for explicit alert read state and operational
source-state updates.

## Monitoring workflow / 监控流程

1. Acquire the monitor lock and create a run record.
2. Select enabled Watch List companies whose source is verified and supported.
3. Check each company independently through its adapter.
4. Validate and normalize every returned job.
5. Deduplicate by source external ID/canonical URL and existing job fingerprint.
6. Apply company role, location, and keyword matching without changing Career Fit Score rules.
7. Persist each new matching job through the existing create/analyze service.
8. Create exactly one alert referencing the saved job and its persisted analysis.
9. Save source results, update operational source state, and finalize the run as succeeded, partial,
   failed, or skipped.

Retries reuse the same idempotency boundaries. Previously saved jobs and alerts remain untouched.
No LLM is required for monitoring; optional explanations degrade safely when the provider is
unavailable.

## Scheduling / 调度

- Default: 09:00 and 18:00 Asia/Hong_Kong every day.
- The repository provides one worker command shared by scheduled and manual execution.
- Local macOS scheduling invokes that command; schedule installation is explicit and reversible.
- Missed executions are not replayed in a burst. The next run performs a normal source comparison.
- The Watch List UI reports the next planned check, but does not claim scheduling is active until
  the local scheduler is installed and verified.

## User experience / 用户体验

### Dashboard / 仪表盘

- **New job alerts / 新职位提醒** appears before lower-priority trend content.
- Shows unread count and the highest-priority alerts.
- Each alert displays company, role, location, source, discovery time, fit score, recommendation,
  and concise match reasons.
- Actions: **View job / 查看职位**, **Mark as read / 标记已读**, **Save / 收藏**, and
  **Ignore / 忽略**. Save/Ignore continue to use existing confirmed application-state behavior.

### Watch List / 关注列表

- Shows source kind/state, adapter support, last attempt, last success, latest result, and next
  planned check.
- **Check now / 立即检查** invokes the same worker path and renders progress/success/partial/failure
  states without blocking navigation.
- Unsupported or unverified sources display **Awaiting verification / 等待验证**, never
  **Monitoring / 正在监控**.

### Digest / 每日报告

- Includes only new high-priority matching jobs, new companies, emerging skill signals, and
  meaningful hiring trends.
- Source-health failures appear in an operations section and never masquerade as job alerts.

All new labels, statuses, errors, empty states, and success messages require matching `en` and
`zh-Hans` catalog entries. Company names, job titles, URLs, and quoted source evidence retain their
original language.

## Failure behavior / 失败处理

- Timeout, oversized response, invalid schema, unsupported source, unsafe redirect, duplicate
  payload, and lock contention have distinct typed error codes.
- A failed company check is committed independently; successful checks and new jobs remain durable.
- A failed source never deletes or deactivates historical jobs.
- Repeated failures update source health and show an operational warning. They do not create a new
  job alert.
- Manual job entry, analysis, Applications, CV Library, and Copilot remain available during source
  failures.
- Logs contain identifiers and bounded diagnostics, not complete private CV/Profile data or full
  untrusted job bodies.

## Tests and evidence / 测试与证据

Automated coverage must include:

- Ashby and Greenhouse happy-path fixture contracts.
- timeout, invalid JSON/schema, unsafe URL/redirect, oversized response, and structural change.
- duplicate external IDs, canonical URLs, fingerprints, and repeat monitor runs.
- partial success across multiple companies and active-run lock contention.
- new job normalization, classification, deterministic scoring, Watch List matching, and exactly-once
  alert creation.
- read/unread alerts and no implicit application-state change.
- manual and scheduled triggers using the same service.
- bilingual Dashboard, Watch List, Digest, empty/error/success states, and stable widget keys.
- migrations on SQLite and PostgreSQL-compatible SQLAlchemy behavior.

Evidence includes unit/API tests, Streamlit component tests, dual-browser E2E for the main alert
flow, Eval regression where monitoring touches analysis, migration verification, and a native local
smoke using synthetic source responses. Live official sources are verified separately and never
substituted by fixtures in user-facing source-status claims.

## Acceptance criteria / 验收标准

1. A verified Replit Ashby fixture exposes one new matching role; one monitor run creates exactly
   one saved job, one analysis, one source check, and one unread alert.
2. Repeating the same run creates zero additional jobs, analyses, or alerts.
3. Dashboard, Watch List, and Digest display the same durable job and source provenance in English
   and Chinese.
4. Marking the alert read clears unread state without changing the job's application status.
5. One failed source plus one successful source produces a partial run, retains the successful job,
   and exposes an actionable operational error.
6. Manual **Check now** and a scheduled trigger produce equivalent durable results.
7. Concurrent triggers cannot double-create jobs or alerts.
8. Companies without verified supported sources are skipped and truthfully labeled.
9. Manual job analysis remains functional while all monitored sources fail.
10. Ruff, formatting, full pytest, relevant Eval/E2E/accessibility checks, migrations, and GitHub CI
    pass with recorded evidence before the feature is called complete.

## Deferred Gmail ingestion / 暂缓的 Gmail 功能

A future separately approved phase may use a dedicated Gmail account with minimum read-only scope,
allowlisted senders, provider message-ID cursors, recognized LinkedIn/JobsDB templates, and a manual
failure-review queue. It must not send mail, delete mail, modify read state, or expose unrelated
messages. Email ingestion will reuse this monitoring pipeline after its own design, permissions,
privacy review, and acceptance plan are approved.
