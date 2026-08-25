# AI Career Fit Score V2

## Purpose

Score how strongly a job builds toward hands-on Applied AI, FDE, AI Product, and AI-native
career options. The calculation is deterministic; an LLM may extract evidence but cannot set
or modify points.

## Dimensions

| Dimension | Max | Evaluation question |
|---|---:|---|
| AI Depth | 20 | Does the work genuinely involve agents, RAG, LLMs, evaluation, or AI architecture? |
| Ownership | 20 | Is the candidate an owner and decision-maker rather than a coordinator? |
| Build & Ship | 20 | Does the role take prototypes through production deployment and iteration? |
| Product Exposure | 15 | Does it include discovery, roadmap, prioritization, metrics, and iteration? |
| Technical Exposure | 15 | Does it require APIs, architecture, data, code, integration, or system design? |
| Career Option Value | 10 | Does it build credible next-step options toward AI-native, FDE, AI PM, or US tech roles? |

Total: 100 points.

## Recommendation bands

| Score | Recommendation |
|---:|---|
| 85–100 | Must Apply |
| 70–84 | Strong Apply |
| 55–69 | Selective |
| 0–54 | Skip |

## Green Flags

Green Flags provide positive evidence within the relevant dimension; they are not a separate
pool of bonus points above 100.

- Agent / agentic
- RAG
- LLM
- tool calling
- workflow orchestration
- evaluation
- rapid prototyping
- API integration
- customer deployment
- production
- product roadmap
- user discovery
- AI platform
- technical architecture
- hands-on
- proof of concept
- 0→1
- end-to-end ownership

## Red Flags

Red Flags reduce Ownership, Build & Ship, Product Exposure, or Technical Exposure when they
dominate the JD without counterbalancing build evidence:

- coordination
- status tracking
- reporting
- steering committee
- governance
- vendor management
- PMO
- documentation
- requirement gathering

Counter-evidence includes build, prototype, deploy, design, experiment, evaluate, architecture,
and AI agent responsibilities.

## Critical warning: AI title + PMO substance

Flag `AI_TITLE_PMO_SUBSTANCE` when the title suggests AI ownership but the responsibilities are
primarily coordination, reporting, governance, vendor management, or documentation, with little
hands-on building, experimentation, architecture, evaluation, or deployment.

The warning must be visually prominent and include the exact JD evidence that triggered it.

## Required output

Every result must store:

- scoring version (`career-fit-v2`)
- total score and six dimension scores
- recommendation band
- positive evidence by dimension
- missing or weak evidence by dimension
- matched Green Flags
- matched Red Flags
- critical warnings
- concise explanation and recommended next action

## Migration

Existing analyses retain their original rubric and display a legacy label. Reanalysis is explicit;
deploying V2 must not silently overwrite historical results.
