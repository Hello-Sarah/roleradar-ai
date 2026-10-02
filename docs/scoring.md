# Scoring model (Legacy V1)

> This document describes the rubric currently implemented in code. The approved target model is
> [AI Career Fit Score V2](../spec/scoring-v2.md). V2 must be introduced as a versioned migration;
> existing analyses must not be silently overwritten.

RoleRadar separates deterministic decisions from generative explanation. This makes a
score repeatable, testable, and inspectable even when no model endpoint is available.

## Rubric

| Dimension | Maximum | Rule |
|---|---:|---|
| Role alignment | 35 | 35 for a target-role match; otherwise 10 |
| Location alignment | 15 | 15 preferred, 8 future, otherwise 2 |
| Domain alignment | 20 | 7 per explicit profile domain match, capped at 20 |
| Technical alignment | 30 | matched required skills divided by detected required skills |

If no supported technical skill is detected, the technical dimension receives a neutral
10 rather than assuming either a perfect or zero match.

## Recommendations

| Score | Recommendation |
|---:|---|
| 75–100 | Apply Now |
| 55–74 | Consider |
| 35–54 | Build Skills First |
| 0–34 | Skip |

## Evidence contract

Each analysis stores the score breakdown, strengths, gaps, evidence, recommendation,
summary, model identifier, and profile identifier. This preserves why the decision was
made. An LLM receives this fixed result and can improve phrasing, but its response is
validated and never includes a replacement score.

## Evaluation plan

Before changing weights, create a versioned golden dataset of representative jobs and
human rankings. Measure classification accuracy, recommendation agreement, gap precision,
and score stability. Treat user status transitions and explicit feedback as signals, not
automatic labels. Version the rubric whenever weights or skill aliases change.
