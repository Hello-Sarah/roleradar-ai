# RoleRadar AI V1 Release Contract

## 中文执行摘要

RoleRadar AI V1 是一个可日常使用、可演示、可通过证据验收的个人 AI 职业情报工作台。
它帮助用户完成一个闭环：发现或录入岗位、理解岗位实质、获得确定性匹配评分、决定是否申请、
记录投递、生成有证据约束的定制 CV，并通过 Dashboard 与 Copilot 决定下一步。

V1 不以职位数量为目标。核心成功标准是用户能更快且更可信地回答：这个岗位是否值得申请、
为什么、我缺什么、现在应做什么，以及这次申请进展到哪里。

## English executive summary

RoleRadar AI V1 is a daily-use, demo-ready, evidence-verifiable AI career intelligence
workspace. It closes the loop from job discovery and analysis to application decisions,
tracking, evidence-grounded CV tailoring, and next-action guidance through a contextual
Career Copilot. V1 optimizes for decision quality, not job volume.

## Primary user loop

```text
Discover or enter a job
→ extract, normalize, and deduplicate
→ classify and compute AI Career Fit Score V2
→ inspect evidence, gaps, flags, eligibility, and action window
→ save or apply and record progress
→ generate a tailored CV when explicitly requested
→ review next actions and trends in Dashboard or Career Copilot
```

## V1 deliverables

| Area | Required user outcome |
|---|---|
| Product shell | Switch the complete UI between Chinese and English and retain the choice. |
| Dashboard | See high-priority jobs, follow-ups, gaps, trends, and one clear next action. |
| Analyze Job | Import by public URL or full pasted JD, review extraction, save, and analyze. |
| Job Intelligence | Receive versioned deterministic scoring, evidence, flags, gaps, and action. |
| Jobs | Search, filter, compare, inspect, and explicitly reanalyze stored jobs. |
| Applications | Track current state plus dated history, channel, notes, and follow-up. |
| Watch List | Maintain companies across company type, strategic priority, and action window. |
| CV Library | Index private CVs and generate an evidence-grounded DOCX for a selected job. |
| Daily Digest | Review only high-value jobs, companies, skills, and hiring signals. |
| Career Copilot | Discuss current product context and execute validated actions after confirmation. |
| Evals | Measure extraction, classification, grounding, CV faithfulness, Copilot, and bilingual parity. |
| Evidence | Produce an acceptance bundle tied to a Git commit and a fresh test run. |

## Required target roles

- AI Product Manager / GenAI Product Manager / Technical Product Manager – AI
- Forward Deployed Product Manager / Deployment Strategist / AI Strategist
- AI Solutions Engineer / Applied AI Engineer / GenAI or Agent Engineer
- Applied AI / GenAI Consultant when the work includes design, build, evaluation, and deployment
- Hong Kong hidden-title roles whose substance matches the above outcomes

Research-heavy MLE, model training, CUDA, distributed ML infrastructure, generic PMO, and
coordination-only roles are not target outcomes even when the title contains “AI”.

## V1 exclusions

- Dedicated mailbox authorization or LinkedIn/JobsDB alert ingestion
- Scheduled polling of official career sources and proactive notification delivery
- Automatic applications, LinkedIn outreach, cover letters, authentication, payments, or mobile app
- Unauthorized scraping, login-state extraction, or bypassing access controls
- Background bulk CV generation or model-created career facts
- Cross-device chat synchronization

Watch List source configuration and manual source health are included so scheduled monitoring can
be added later without redesigning company records.

## Runtime and privacy assumptions

- Local development uses SQLite; production-compatible deployment uses PostgreSQL.
- Model-backed features use an explicitly configured OpenAI-compatible API.
- CVs, extracted private text, chats, API keys, generated CVs, and acceptance data containing
  personal information are excluded from Git.
- No model call occurs merely because the user opens a page or scans a CV folder.
- The product is single-user in V1; lack of authentication must be stated in every deployment guide.

## Release definition

V1 is released only when every Must acceptance item in `acceptance-v1.md` passes against one Git
commit, Eval thresholds in `evals.md` pass, and the corresponding evidence bundle defined in
`test-evidence.md` exists. A previous run cannot serve as evidence for a new commit.
