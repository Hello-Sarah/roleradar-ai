# Task 7 Report — Bilingual Calm Intelligence Workspace

Date: 2026-09-03

## Status

Complete. The legacy Streamlit monolith is now an English/Simplified Chinese,
Apple-inspired Calm Intelligence workspace backed exclusively by the existing FastAPI
contracts. Completion commit: `feat: add bilingual Calm Intelligence workspace` (this
report is included in that commit; the SHA is supplied in the Task 7 handoff).

## Delivered behavior

- Added the exact light visual tokens, typography stack, 1440 px content cap, 16 px body,
  13 px metadata, 18 px cards, strong focus rings, reduced-motion handling, and responsive
  390 px rules from the design system.
- Split the UI into eight focused pages: Dashboard, Analyze Job, Jobs, Applications,
  Watch List, CV Library, Digest, and Profile. The shell uses one localized navigation
  source and suppresses Streamlit's duplicate generated page tree.
- Added browser-locale detection plus explicit EN/中文 selection persisted in `?lang=`.
  Stable machine values remain untranslated; visible dates are localized at render time.
- Added reusable localized empty, error, success, disabled, and low-confidence states.
  Low-confidence output uses the exact required `Needs review / 需要复核` warning.
- Added decision-first job cards with canonical score bands, evidence, strengths, gaps,
  status transitions, posting links, and explicit Career Copilot context selection.
- Preserved text and URL job intake. Text extraction remains an unsaved, fully editable
  preview with separate confirm/cancel paths.
- Added Watch List add/edit/enable/disable/confirmed-delete flows while preserving neutral
  enum values and independent dimensions.
- Added an always-available desktop Career Copilot panel and a full-screen mobile drawer.
  Session create/select/rename/confirmed-delete flows use the persistent Task 6 API.
  Action confirmations show target, current value, proposed value, side effects, and
  private-data usage before separate confirm/cancel actions.
- Scoped desktop/mobile session widget state and rotated widget identity after create/delete
  so hidden responsive variants cannot overwrite the active conversation.

## TDD evidence

Every added behavior began with a focused failure and then a minimal implementation. Key
RED observations included:

- missing dashboard state/navigation modules and all eight page modules;
- missing exact design tokens, primary-action invariant, localized state copy, and stable keys;
- extraction cancellation retaining unsaved state and missing low-confidence warning;
- duplicate Streamlit navigation and host dark-theme text leaking onto a white canvas;
- mixed-language UI during locale changes and stale job context in Copilot;
- incomplete 390 px drawer styling and non-contrasting primary-button text;
- 204 DELETE responses raising `JSONDecodeError`;
- missing localized session-management confirmation and remote icon-font fallbacks;
- a new Copilot session losing to stale selectbox state, followed by a desktop/mobile state race;
- duplicated Chinese low-confidence copy instead of the required bilingual sentence;
- raw ISO dates leaking into localized presentation.

Representative RED commands were targeted `pytest -q ... -k <behavior>` runs and produced
the expected assertion/import failures before implementation. The final focused GREEN run:

```text
.venv/bin/pytest -q tests/test_dashboard_components.py tests/test_i18n.py
52 passed
```

## Verification

```text
.venv/bin/pytest -q
223 passed; total coverage 76%

.venv/bin/ruff check .
All checks passed!

.venv/bin/ruff format --check app tests
81 files already formatted

.venv/bin/alembic heads
20260825_05 (head)

git diff --check
clean

GET http://127.0.0.1:8017/api/v1/health
{"status":"ok"}

GET http://127.0.0.1:8517/_stcore/health
ok
```

The repo-wide `.venv/bin/ruff format --check .` was also run. It reports only the untouched,
pre-existing Markdown code samples in `docs/superpowers/plans/2026-08-25-role-radar-v1.md`;
all application and test Python files pass the formatter check.

## UI smoke and accessibility observations

- Desktop 1440×900: all eight navigation choices opened the expected single H1 with zero
  browser alerts; document width equaled viewport width.
- Locale: switching Profile to 中文 produced `?lang=zh-Hans`; a hard reload kept the Chinese
  shell and page copy. The locale change reruns atomically, so no mixed-language frame remains.
- Mobile 390×844: navigation collapses to a drawer; Career Copilot opens as a 390×844 white
  full-screen dialog with `overflow-y: auto`; document `scrollWidth` remained 390. The desktop
  panel is hidden and the mobile launcher is visible.
- Primary action text computed as white on the approved blue. Keyboard focus styles are explicit,
  semantic Streamlit labels are present, and reduced-motion CSS is active.
- Local/offline Material icon-name leakage was removed from the custom navigation and Copilot
  chat presentation by using local glyph/emoji fallbacks.
- Rich-JD regression: a synthetic Example Robotics posting mentioning AWS was extracted with
  the incorrect company `AWS`; the preview exposed every field as editable and stated nothing
  was saved. Cancel left `/api/v1/jobs` empty. Repeating the flow, correcting the company to
  `Example Robotics`, and confirming created the correct job and analysis card.
- Copilot proposal smoke displayed all five confirmation fields for `Save this job`; no mutation
  occurred because confirmation was deliberately not submitted.

## Changed files

- `.streamlit/config.toml`
- `app/dashboard/client.py`
- `app/dashboard/streamlit_app.py`
- `app/dashboard/theme.py`
- `app/dashboard/state.py`
- `app/dashboard/components/{__init__,navigation,states,copilot_panel,job_card}.py`
- `app/dashboard/pages/{__init__,dashboard,analyze,jobs,applications,watchlist,cv_library,digest,profile}.py`
- `app/i18n/catalogs/{en,zh-Hans}.json`
- `tests/test_dashboard_components.py`
- `README.md`
- `docs/PROGRESS.md`
- `.superpowers/sdd/2026-08-25-role-radar-v1/task-7-report.md`

## Self-review

- Confirmed `app/dashboard/` imports no SQLAlchemy/database session and accesses persistence
  only through `RoleRadarClient`.
- Confirmed durable enum/status/source values are not localized before API submission.
- Confirmed destructive Watch List and Copilot actions require explicit confirmation.
- Confirmed no task-external generated database, screenshot, or secret was added.

## Concerns

- The untouched planning Markdown noted above prevents a literal repo-root Ruff format check
  from being clean; changing it was intentionally excluded from Task 7 scope.
- Browser smoke used an isolated SQLite database under `/tmp`; its synthetic job and Copilot
  sessions are not part of the repository or the user's normal database.
