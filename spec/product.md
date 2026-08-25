# Product Specification

## Product statement

RoleRadar AI is a personal AI career intelligence system for tracking Applied AI job
opportunities and applications. It helps the user decide what to apply for, understand why,
identify career-building gaps, and monitor target companies.

## Long-term product workflows

`release-v1.md` is authoritative for the current release boundary. Email alerts, scheduled verified
feeds, and proactive notifications below are Phase 2 outcomes, not V1 claims.

1. Capture a job from a public link, pasted JD, approved email alert, or verified company feed.
2. Normalize and deduplicate the job before analysis.
3. Classify the role and calculate a versioned AI Career Fit Score with evidence.
4. Track the application and every status transition as an auditable timeline.
5. Maintain a target-company Watch List and notify only when a new matching role is found.
6. Produce a focused digest of new priority jobs, emerging skills, follow-ups, and hiring trends.

## Agent demo direction

The system may expose a visible workflow comprising specialized agents:

- Source Agent: receives verified feeds and approved email alerts.
- JD Intelligence Agent: extracts normalized job facts and evidence.
- Career Scoring Agent: applies the deterministic scoring rubric and flag rules.
- Watch List Agent: matches new jobs against company, role, location, and keyword preferences.
- Digest Agent: summarizes only actionable changes and overdue follow-ups.
- Career Copilot: answers with selected product context and proposes confirmed actions.
- CV Tailor: uses indexed CV evidence to create a selected-job DOCX without inventing facts.

Each stage must expose structured inputs, outputs, status, duration, errors, and retry behavior.
The orchestration can remain inside the modular monolith for the MVP.

## Non-goals

- Automated applications or outreach.
- Unauthorized LinkedIn scraping or browser automation.
- Model-generated scores without deterministic evidence.
- High-volume job-board aggregation.
