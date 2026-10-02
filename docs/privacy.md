# RoleRadar AI V1 privacy boundaries

V1 is a local, single-user workspace, not an authenticated multi-user service. Bind both processes
to loopback. Do not publish private API routes, database files, or generated-download endpoints.
Git ignore is a repository safeguard, not encryption or a filesystem access-control boundary.

## Stored locally

The database contains Profile versions, saved JD text/analyses, application events, Watch List/source
metadata, CV fingerprints/extracted text, generated-CV provenance, conversations, prepared proposals,
workflows, and action audits. Default SQLite storage is `./roleradar.db`. Restrict file/backup access
and use disk encryption.

`CV_LIBRARY_PATH` defaults to `./data/cv_library`; `GENERATED_CV_PATH` defaults to
`./data/generated_cvs`. Scan reads DOCX, text-layer PDF, and TXT without modifying source bytes.
Unchanged fingerprints do not duplicate documents; removed sources become inactive, not purged.
Generated files use a sanitized `名字—岗位-chatgpt.docx` name in unique artifact subdirectories of
the separate output directory, avoiding overwrite. Downloads are restricted to that directory. Provenance
retains source IDs, target job, time, model/prompt version, and file hash.

Conversation deletion removes message bodies/sources and summary while retaining session metadata
and non-content action audits. It is not global erasure: saved jobs, CV extracted text, prepared
actions, generated files, filesystem snapshots, and provider-side records may remain. V1 has no
comprehensive retention timer or secure-erasure command. Do not delete source CVs or replace a live
database as a troubleshooting shortcut.

## What may leave the computer

Public-URL intake contacts the selected public host; it restricts protocols, destinations,
redirects, size, and timeouts. External JD/CV content is untrusted data, not instructions.

With a provider/key, job explanations send the selected JD, candidate Profile, and deterministic
result. Copilot proposal inference sends the request and explicitly built context (selected
job/company, relevant Profile/analysis/events, selected CVs, and conversation summary). Unattached
CVs and unrelated jobs are excluded. Opening Copilot or scanning CVs does not call a provider.

An explicit tailored-CV action sends the target JD and source CV text to the provider: ordinary
CV Library generation uses the active corpus; an explicit source-ID selection limits it to those
sources. It requires `OPENAI_API_KEY` even when `AI_EXPLANATIONS_ENABLED=false`. Scope the library to
documents you consent to share, review confirmation data use, and check the actual provider's
retention/region/security terms before using real CVs. No provider retention promise is implied.
CV facts must be exact source selections; invalid support stops output.

Use no key and `AI_EXPLANATIONS_ENABLED=false` for offline job analysis and deterministic proposal
fallbacks. Provider-independent CV generation is unavailable. Default read-only Copilot answers are
local cited job excerpts, not live LLM conversations.

## Logs, evidence, and public demo

Private-product logs are not a strict no-content channel: scan warnings can contain file paths and
parser errors; provider exceptions may contain diagnostics. Protect logs, avoid verbose HTTP/provider
tracing, and inspect/redact before sharing. Disable Streamlit telemetry with
`--browser.gatherUsageStats=false` as shown in README.

`.env`, database files, default CV folders, and acceptance evidence are ignored by Git. A custom
folder outside those patterns needs its own ignore rule; never force-add secrets/CVs. Do not share
private fixtures, database backups, conversations, or provider request captures.

The public demo is disabled by default. Its separate API uses a synthetic Profile and does not
persist submitted JD text in product storage, application logs, or reports. Provider processing
is still external when enabled. This stateless contract does not apply to the private workspace.

Acceptance uses isolated synthetic CV/JD/conversation data and deterministic test providers. Reports
store safe structured output and hashes rather than raw input. Review screenshots and traces for
names, emails, phones, tokens, and confidential employer data before publishing any evidence.
