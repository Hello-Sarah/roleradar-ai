# Calm Intelligence Design System

## Design intent

RoleRadar should feel like a quiet, trustworthy Apple-native productivity tool: restrained,
content-first, responsive, and precise. Visual polish must clarify career decisions rather than
advertise the interface. The approved direction is **Calm Intelligence**.

## Design tokens

| Token | Value | Use |
|---|---|---|
| Canvas | `#F5F5F7` | Page background |
| Surface | `#FFFFFF` or 88% white | Cards, panels, navigation |
| Primary text | `#1D1D1F` | Titles and body |
| Secondary text | `#6E6E73` | Metadata and help copy |
| System blue | `#0071E3` | Primary action, selected state, links |
| Success | `#248A3D` | Verified success only |
| Warning | `#B35C00` | Review or eligibility warning |
| Danger | `#D70015` | Destructive or blocking failure |
| Hairline | `#D2D2D7` | Low-emphasis boundaries |

Fonts use `-apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "PingFang SC",
"Helvetica Neue", Arial, sans-serif`. Body is at least 16px; supporting copy is at least 13px.
Spacing follows an 8px base grid. Cards use 16–20px radii, subtle borders, and shadows only when
needed to clarify elevation. Large gradients, decorative glass, neon, and dense badge clouds are
not permitted.

## Information architecture

Desktop uses a persistent left navigation and a lightweight top utility bar.

1. Dashboard
2. Analyze Job
3. Jobs
4. Applications
5. Watch List
6. CV Library
7. Digest
8. Profile

The top-right utility area contains language, model/data-source health, and settings. Career
Copilot opens as a persistent right panel without hiding the current job or company context; it may
expand into a full conversation page. At 390px, both navigation and Copilot become full-screen
drawers.

## Page hierarchy

- One H1 and one sentence of supporting copy per page.
- One visually dominant action per page region.
- Decision and next action precede raw JD text and metadata.
- Fit results always show number, label, evidence, and recommendation; color is supplementary.
- Tables become grouped cards on narrow screens when a horizontal table would block use.
- Destructive actions require explicit confirmation and never share styling with a primary action.

## Required component states

| State | Required behavior |
|---|---|
| Loading | Local skeleton or progress label; unrelated page areas remain usable. |
| Empty | Explain why it is empty and provide one clear next step. |
| Error | Explain cause, unaffected saved data, and a retry or recovery action. |
| Success | Confirm the durable result and link to it. |
| Disabled | State the missing prerequisite in visible copy or tooltip. |
| Low confidence | Display “Needs review / 需要复核”; never imply certainty. |
| Pending confirmation | Show exact Copilot action, target record, old value, and new value. |

## Accessibility and responsive behavior

- Text and meaningful controls meet WCAG 2.2 AA contrast.
- All controls are keyboard reachable with visible focus rings.
- Icon-only controls have accessible names; status is never conveyed by color alone.
- Motion respects reduced-motion preferences and is not required to understand state.
- 1440px is the release screenshot baseline; 1024px preserves full functionality.
- At 390px there is no horizontal page overflow and the primary user loop remains executable.
- V1 does not promise a separately optimized mobile data-table experience.

## Visual acceptance evidence

Capture Dashboard, Job Detail, Watch List, CV Library, Copilot confirmation, and one error state in
both languages at 1440px. Capture Dashboard, Job Detail, and Copilot at 390px. Screenshots must use
the same seeded dataset so bilingual comparisons are meaningful.
