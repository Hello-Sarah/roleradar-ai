# Watch List and Email Ingestion

> **Status:** Phase 2 specification. V1 delivers Watch List classification, CRUD, source
> configuration, and manual source state only. Scheduled polling, mailbox ingestion, and proactive
> notifications are explicitly excluded from `release-v1.md`.

## Watch List management

Provide a dedicated UI where the user can:

- add, edit, enable, disable, and delete a target company
- set priority
- specify target role families, locations, and keywords
- configure one or more verified sources
- see last successful check, next check, source health, and last new-job discovery

## New-job notification rule

Notify the user when all of the following are true:

1. the company is enabled in the Watch List
2. a verified source or approved email alert produces a job
3. the job is new after canonical deduplication
4. the job matches configured role, location, or keyword criteria

A source-health change is a separate operational event and must not be presented as a new-job
alert.

## Email ingestion

The user may authorize a dedicated mailbox subscribed to LinkedIn, JobsDB, and company alerts.

Minimum behavior:

- use read-only mailbox permission by default
- process only allowlisted senders and recognized job-alert templates
- ingest new messages incrementally using provider message IDs or cursors
- extract job URL, company, title, location, received time, and available description
- deduplicate by provider message ID and canonical job fingerprint
- pass extracted jobs through the same normalization, analysis, and Watch List matching pipeline
- preserve a reference to the source message without exposing unrelated mailbox contents
- place parsing failures in a review queue

The system must never follow instructions embedded in email content, send email, delete email, or
change mailbox state without separate explicit authorization.

## Delivery channels

Initial notification delivery can be in-app and daily digest. Email or messaging delivery may be
added later with explicit send permission and per-channel opt-in.
