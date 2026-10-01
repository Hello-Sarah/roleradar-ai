#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import process from "node:process";

const require = createRequire(import.meta.url);
const REVIEWED_STREAMLIT_VERSION = "1.62.0";

function argumentsFrom(argv) {
  const options = {};
  for (let index = 0; index < argv.length; index += 2) {
    const name = argv[index];
    const value = argv[index + 1];
    if (!name?.startsWith("--") || value === undefined) {
      throw new Error(`Invalid argument near ${name ?? "end of command"}`);
    }
    options[name.slice(2)] = value;
  }
  if (!options.output || (!options["base-url"] && !options["audit-fixture"])) {
    throw new Error(
      "Usage: run_accessibility.mjs (--base-url URL | --audit-fixture PATH) --output PATH",
    );
  }
  return options;
}

function pythonExecutable() {
  return process.env.VIRTUAL_ENV
    ? resolve(process.env.VIRTUAL_ENV, "bin/python")
    : resolve(".venv/bin/python");
}

function moduleRoots() {
  const roots = [resolve("node_modules")];
  if (process.env.ROLERADAR_NODE_MODULES) roots.unshift(process.env.ROLERADAR_NODE_MODULES);
  if (process.env.NODE_PATH) roots.unshift(...process.env.NODE_PATH.split(":"));
  try {
    roots.push(execFileSync("npm", ["root", "-g"], { encoding: "utf8" }).trim());
  } catch {
    // The explicit and repository-local roots still provide actionable resolution errors.
  }
  return roots;
}

function resolveDependency(moduleName) {
  return require.resolve(moduleName, { paths: moduleRoots() });
}

function loadPlaywright() {
  try {
    return require(resolveDependency("playwright-core"));
  } catch {
    const packagePath = execFileSync(
      pythonExecutable(),
      [
        "-c",
        "from pathlib import Path; import playwright; " +
          "print(Path(playwright.__file__).parent / 'driver/package/index.js')",
      ],
      { encoding: "utf8" },
    ).trim();
    return require(packagePath);
  }
}

function streamlitVersion() {
  return execFileSync(
    pythonExecutable(),
    ["-c", "import streamlit; print(streamlit.__version__)"],
    { encoding: "utf8" },
  ).trim();
}

function exactSidebarFinding(violation) {
  return (
    violation.id === "aria-allowed-attr" &&
    violation.nodes?.length === 1 &&
    violation.nodes[0].target?.length === 1 &&
    violation.nodes[0].target[0] === ".stSidebar" &&
    violation.nodes[0].failureSummary?.includes('aria-expanded="true"')
  );
}

function buildReport({
  routes,
  dynamic_states: dynamicStates = [],
  streamlit_version: installedVersion,
  base_url = null,
  engine = {},
}) {
  const versionReviewed = installedVersion === REVIEWED_STREAMLIT_VERSION;
  const auditedSurfaces = [
    ...routes,
    ...dynamicStates.map((state) => ({ ...state, route: `dynamic:${state.state}` })),
  ];
  const findings = auditedSurfaces.flatMap((route) =>
    (route.violations ?? []).map((violation) => ({ route: route.route, ...violation })),
  );
  const suppressed = versionReviewed ? findings.filter(exactSidebarFinding) : [];
  const aaFailures = findings.filter((violation) => !suppressed.includes(violation));
  const incomplete = auditedSurfaces.flatMap((route) =>
    (route.incomplete ?? []).map((finding) => ({ route: route.route, ...finding })),
  );
  const incompleteReviews = auditedSurfaces.flatMap((route) =>
    (route.incomplete_reviews ?? []).map((review) => ({ route: route.route, ...review })),
  );
  const unresolvedIncomplete = incomplete.flatMap((finding) =>
    (finding.nodes ?? [])
      .filter((node) => {
        const target = node.target?.[0];
        return !incompleteReviews.some(
          (review) =>
            review.route === finding.route &&
            review.rule_id === finding.id &&
            review.target === target &&
            review.status === "pass",
        );
      })
      .map((node) => ({ route: finding.route, rule_id: finding.id, node })),
  );
  const keyboardFailures = routes
    .filter(
      (route) =>
        route.keyboard?.all_controls_reached !== true ||
        route.keyboard?.all_controls_named !== true ||
        route.keyboard?.all_focus_visible !== true ||
        (route.activation && route.activation.passed !== true),
    )
    .map((route) => ({ route: route.route, ...route.keyboard }));
  const dynamicKeyboardFailures = dynamicStates
    .filter(
      (state) =>
        state.keyboard?.all_controls_reached !== true ||
        state.keyboard?.all_controls_named !== true ||
        state.keyboard?.all_focus_visible !== true ||
        state.activation?.passed !== true,
    )
    .map((state) => ({ state: state.state, keyboard: state.keyboard, activation: state.activation }));
  const requiredDynamicStates = [
    "extracted-review",
    "analyzed-job",
    "application-event",
    "watchlist-form",
    "copilot-panel",
    "copilot-session",
  ];
  const missingDynamicStates = base_url
    ? requiredDynamicStates.filter(
        (requiredState) => !dynamicStates.some((state) => state.state === requiredState),
      )
    : [];
  return {
    schema_version: 2,
    base_url,
    tested_at: new Date().toISOString(),
    standard: "WCAG 2.2 AA",
    engine: engine.name ?? "axe-core",
    engine_version: engine.version ?? "fixture",
    streamlit_version: installedVersion,
    suppression_policy: {
      reason:
        "The reviewed Streamlit release renders aria-expanded on its framework-owned sidebar section.",
      exact_signature_only: true,
      reviewed_streamlit_version: REVIEWED_STREAMLIT_VERSION,
      status: versionReviewed ? "reviewed version matched" : "re-review required for Streamlit version",
    },
    suppressed_findings: suppressed,
    aa_failure_count: aaFailures.length,
    aa_failures: aaFailures,
    incomplete_review_count: incompleteReviews.length,
    incomplete_reviews: incompleteReviews,
    unresolved_incomplete_count: unresolvedIncomplete.length,
    unresolved_incomplete_findings: unresolvedIncomplete,
    incomplete_findings: incomplete,
    keyboard_failure_count: keyboardFailures.length,
    keyboard_failures: keyboardFailures,
    dynamic_keyboard_failure_count: dynamicKeyboardFailures.length,
    dynamic_keyboard_failures: dynamicKeyboardFailures,
    dynamic_states: dynamicStates,
    missing_dynamic_states: missingDynamicStates,
    routes,
    passed:
      aaFailures.length === 0 &&
      unresolvedIncomplete.length === 0 &&
      keyboardFailures.length === 0 &&
      dynamicKeyboardFailures.length === 0 &&
      missingDynamicStates.length === 0 &&
      versionReviewed,
  };
}

async function reviewIncomplete(page, incomplete) {
  const reviews = [];
  for (const finding of incomplete) {
    for (const node of finding.nodes ?? []) {
      const target = node.target?.[0];
      if (finding.id !== "color-contrast" || typeof target !== "string") {
        reviews.push({
          rule_id: finding.id,
          target: target ?? null,
          status: "unresolved",
          reason: "Automated review is only defined for measurable text contrast.",
        });
        continue;
      }
      const measurement = await page.evaluate((selector) => {
        const parseColor = (value) => {
          const match = value.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/);
          if (!match) return null;
          return {
            rgb: [Number(match[1]), Number(match[2]), Number(match[3])],
            alpha: match[4] === undefined ? 1 : Number(match[4]),
          };
        };
        const luminance = (rgb) => {
          const values = rgb.map((value) => {
            const channel = value / 255;
            return channel <= 0.04045
              ? channel / 12.92
              : ((channel + 0.055) / 1.055) ** 2.4;
          });
          return 0.2126 * values[0] + 0.7152 * values[1] + 0.0722 * values[2];
        };
        const element = document.querySelector(selector);
        if (!element) return null;
        const style = getComputedStyle(element);
        const foreground = parseColor(style.color);
        let ancestor = element;
        let background = null;
        while (ancestor && !background) {
          const candidate = parseColor(getComputedStyle(ancestor).backgroundColor);
          if (candidate?.alpha === 1) background = candidate;
          ancestor = ancestor.parentElement;
        }
        background ??= { rgb: [255, 255, 255], alpha: 1 };
        if (!foreground) return null;
        const foregroundLuminance = luminance(foreground.rgb);
        const backgroundLuminance = luminance(background.rgb);
        const contrastRatio =
          (Math.max(foregroundLuminance, backgroundLuminance) + 0.05) /
          (Math.min(foregroundLuminance, backgroundLuminance) + 0.05);
        const fontSize = Number.parseFloat(style.fontSize);
        const fontWeight = Number.parseInt(style.fontWeight, 10) || 400;
        const requiredRatio = fontSize >= 24 || (fontSize >= 18.66 && fontWeight >= 700) ? 3 : 4.5;
        return {
          foreground: style.color,
          background: `rgb(${background.rgb.join(", ")})`,
          font_size_px: fontSize,
          font_weight: fontWeight,
          contrast_ratio: Number(contrastRatio.toFixed(2)),
          required_ratio: requiredRatio,
        };
      }, target);
      reviews.push({
        rule_id: finding.id,
        target,
        status:
          measurement && measurement.contrast_ratio >= measurement.required_ratio
            ? "pass"
            : "fail",
        ...(measurement ?? { reason: "Target or computed colors could not be measured." }),
      });
    }
  }
  return reviews;
}

async function keyboardAudit(page) {
  const controls = await page.locator(
    'button, a[href], input, textarea, select, [role="button"], [role="tab"], ' +
      '[role="radio"], [role="combobox"]',
  ).evaluateAll((items) => {
    let index = 0;
    let groupIndex = 0;
    return items
      .filter((item) => {
        const style = getComputedStyle(item);
        const bounds = item.getBoundingClientRect();
        return (
          !item.disabled &&
          item.getAttribute("aria-disabled") !== "true" &&
          !item.closest('[aria-hidden="true"], [inert]') &&
          (typeof item.checkVisibility !== "function" ||
            item.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })) &&
          style.visibility !== "hidden" &&
          style.display !== "none" &&
          bounds.width > 0 &&
          bounds.height > 0 &&
          item.tabIndex >= 0
        );
      })
      .map((item) => {
        const id = `rr-a11y-${index++}`;
        item.setAttribute("data-rr-a11y-id", id);
        const radioGroup = item.closest('[role="radiogroup"]');
        if (radioGroup && !radioGroup.getAttribute("data-rr-a11y-group")) {
          radioGroup.setAttribute("data-rr-a11y-group", `rr-radio-group-${groupIndex++}`);
        }
        const label =
          item.getAttribute("aria-label") ||
          item.getAttribute("title") ||
          item.getAttribute("placeholder") ||
          item.labels?.[0]?.textContent ||
          item.textContent ||
          item.getAttribute("value") ||
          "";
        return {
          id,
          label: label.trim().replace(/\s+/g, " "),
          tag: item.tagName.toLowerCase(),
          role: item.getAttribute("role"),
          type: item.getAttribute("type"),
          group: radioGroup?.getAttribute("data-rr-a11y-group") ?? null,
        };
      });
  });
  await page.evaluate(() => {
    document.body.tabIndex = -1;
    document.body.focus();
  });
  const reached = new Set();
  const invisibleFocus = new Set();
  const focusSequence = [];
  for (let attempt = 0; attempt < controls.length * 2 + 12; attempt += 1) {
    await page.keyboard.press("Tab");
    const active = await page.evaluate(() => {
      const element = document.activeElement;
      if (!element) return null;
      const style = getComputedStyle(element);
      const labelledControl = [...(element.labels ?? [])]
        .flatMap((label) => [...label.querySelectorAll("[data-rr-a11y-id]")])
        .find((candidate) => candidate.getAttribute("role") === "radio");
      return {
        id:
          element.getAttribute("data-rr-a11y-id") ||
          labelledControl?.getAttribute("data-rr-a11y-id"),
        tag: element.tagName.toLowerCase(),
        role: element.getAttribute("role"),
        label:
          element.getAttribute("aria-label") ||
          element.labels?.[0]?.textContent?.trim().replace(/\s+/g, " ") ||
          element.textContent?.trim().replace(/\s+/g, " ") ||
          "",
        visible:
          style.outlineStyle !== "none" ||
          style.outlineWidth !== "0px" ||
          style.boxShadow !== "none",
      };
    });
    if (active?.id) focusSequence.push(active);
    if (active?.id) {
      reached.add(active.id);
      if (!active.visible) invisibleFocus.add(active.id);
    }
    if (reached.size === controls.length) break;
  }
  const reachedGroups = new Set(
    controls.filter((control) => reached.has(control.id) && control.group).map((control) => control.group),
  );
  for (const control of controls) {
    if (control.group && reachedGroups.has(control.group)) reached.add(control.id);
  }
  const missing = controls.filter((control) => !reached.has(control.id));
  const unnamed = controls.filter((control) => !control.label);
  return {
    control_count: controls.length,
    reached_count: reached.size,
    unnamed_controls: unnamed,
    unreachable_controls: missing,
    invisible_focus_controls: [...invisibleFocus],
    focus_sequence: focusSequence,
    all_controls_reached: missing.length === 0,
    all_controls_named: unnamed.length === 0,
    all_focus_visible: invisibleFocus.size === 0,
  };
}

async function waitForStreamlit(page) {
  await page.waitForTimeout(100);
  await page.waitForFunction(() => !document.querySelector('[data-stale="true"]'));
  await page.evaluate(
    () => new Promise((resolveFrame) => requestAnimationFrame(() => requestAnimationFrame(resolveFrame))),
  );
}

async function activateByKeyboard(locator, key = "Enter") {
  await locator.waitFor({ state: "visible" });
  await locator.focus();
  const focusVisible = await locator.evaluate((element) => {
    const style = getComputedStyle(element);
    return (
      document.activeElement === element &&
      (style.outlineStyle !== "none" || style.outlineWidth !== "0px" || style.boxShadow !== "none")
    );
  });
  await locator.press(key);
  await waitForStreamlit(locator.page());
  return focusVisible;
}

async function auditState(page, axeSource, state, activation) {
  await page.evaluate(axeSource);
  const result = await page.evaluate(async () =>
    globalThis.axe.run(document, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"] },
    }),
  );
  return {
    state,
    passes: result.passes.length,
    incomplete: result.incomplete,
    incomplete_reviews: await reviewIncomplete(page, result.incomplete),
    violations: result.violations,
    keyboard: await keyboardAudit(page),
    activation,
  };
}

async function scanDynamicPrimaryLoop(page, axeSource) {
  const states = [];
  const route = page.getByRole("radio", { name: "Analyze Job", exact: true });
  const routeFocus = await activateByKeyboard(route, "Space");
  await page.getByRole("heading", { name: "Analyze Job", exact: true }).waitFor();

  const pasteTab = page.getByRole("tab", { name: "Paste job text", exact: true });
  const tabFocus = await activateByKeyboard(pasteTab);
  const rawText = page.getByRole("textbox", { name: "Paste job text", exact: true });
  await rawText.fill(
    "[SYNTHETIC]\nCompany: Keyboard Signal Labs\nJob Title: Forward Deployed AI Engineer\n" +
      "Location: Hong Kong\nBuild production AI systems with customers using Python and APIs.",
  );
  const extractFocus = await activateByKeyboard(
    page.getByRole("button", { name: "Extract fields", exact: true }),
  );
  await page.getByLabel("Company", { exact: true }).waitFor();
  states.push(
    await auditState(page, axeSource, "extracted-review", {
      control: "Extract fields",
      passed: routeFocus && tabFocus && extractFocus,
    }),
  );

  const confirmFocus = await activateByKeyboard(
    page.getByRole("button", { name: "Confirm & analyze", exact: true }),
  );
  await page.getByText("Analysis complete", { exact: false }).waitFor();
  states.push(
    await auditState(page, axeSource, "analyzed-job", {
      control: "Confirm & analyze",
      passed: confirmFocus,
    }),
  );

  const applications = page.getByRole("radio", { name: "Applications", exact: true });
  const applicationsFocus = await activateByKeyboard(applications, "Space");
  await page.getByRole("heading", { name: "Applications", exact: true }).waitFor();
  await page.getByLabel("Notes", { exact: true }).fill("[SYNTHETIC] Keyboard event");
  const addFocus = await activateByKeyboard(page.getByRole("button", { name: "Add", exact: true }));
  await page.getByRole("paragraph").filter({ hasText: "[SYNTHETIC] Keyboard event" }).waitFor();
  states.push(
    await auditState(page, axeSource, "application-event", {
      control: "Add",
      passed: applicationsFocus && addFocus,
    }),
  );

  const watchList = page.getByRole("radio", { name: "Watch List", exact: true });
  const watchFocus = await activateByKeyboard(watchList, "Space");
  await page.getByRole("heading", { name: "Watch List", exact: true }).waitFor();
  const addCompany = page
    .locator("details")
    .filter({ hasText: "Add Watch List company" })
    .locator("summary");
  const formFocus = await activateByKeyboard(addCompany);
  await page.getByLabel("Company name", { exact: true }).waitFor();
  states.push(
    await auditState(page, axeSource, "watchlist-form", {
      control: "Add Watch List company",
      passed: watchFocus && formFocus,
    }),
  );

  states.push(
    await auditState(page, axeSource, "copilot-panel", {
      control: "Persistent Career Copilot panel",
      passed: true,
    }),
  );
  const newSession = page.getByRole("button", { name: "New conversation", exact: true }).last();
  const sessionFocus = await activateByKeyboard(newSession);
  await page.getByRole("combobox", { name: "Conversation title", exact: true }).waitFor();
  states.push(
    await auditState(page, axeSource, "copilot-session", {
      control: "New conversation",
      passed: sessionFocus,
    }),
  );
  return states;
}

async function scanApplication(options) {
  const { chromium } = loadPlaywright();
  const axeSource = readFileSync(resolveDependency("axe-core/axe.min.js"), "utf8");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1100 },
    locale: "en-US",
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  const routeNames = [
    "Dashboard",
    "Analyze Job",
    "Jobs",
    "Applications",
    "Watch List",
    "CV Library",
    "Digest",
    "Profile",
  ];
  const routeResults = [];
  let dynamicStates = [];
  try {
    await page.goto(`${options["base-url"].replace(/\/$/, "")}/?lang=en`);
    await page.getByText("RoleRadar AI", { exact: true }).first().waitFor({ state: "visible" });
    await waitForStreamlit(page);
    for (const route of routeNames) {
      const control = page.getByRole("radio", { name: route, exact: true });
      const activationFocusVisible = await activateByKeyboard(control, "Space");
      await page.waitForFunction(
        (routeName) =>
          [...document.querySelectorAll('input[type="radio"]')].some(
            (control) =>
              control.checked === true &&
              [...(control.labels ?? [])].some(
                (label) => label.textContent?.trim() === routeName,
              ),
          ),
        route,
      );
      await waitForStreamlit(page);
      await page.evaluate(axeSource);
      const result = await page.evaluate(async () =>
        globalThis.axe.run(document, {
          runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"] },
        }),
      );
      routeResults.push({
        route,
        passes: result.passes.length,
        incomplete: result.incomplete,
        incomplete_reviews: await reviewIncomplete(page, result.incomplete),
        violations: result.violations,
        keyboard: await keyboardAudit(page),
        activation: { control: `Navigate to ${route}`, passed: activationFocusVisible },
      });
    }
    dynamicStates = await scanDynamicPrimaryLoop(page, axeSource);
    return buildReport({
      routes: routeResults,
      dynamic_states: dynamicStates,
      streamlit_version: streamlitVersion(),
      base_url: options["base-url"],
      engine: {
        name: "axe-core",
        version: require(resolveDependency("axe-core/package.json")).version,
      },
    });
  } finally {
    await context.close();
    await browser.close();
  }
}

async function main() {
  const options = argumentsFrom(process.argv.slice(2));
  const report = options["audit-fixture"]
    ? buildReport(JSON.parse(readFileSync(resolve(options["audit-fixture"]), "utf8")))
    : await scanApplication(options);
  mkdirSync(dirname(resolve(options.output)), { recursive: true });
  writeFileSync(resolve(options.output), `${JSON.stringify(report, null, 2)}\n`, "utf8");
  console.log(
    `passed=${report.passed}; routes=${report.routes.length}; aa=${report.aa_failure_count}; ` +
      `incomplete=${report.incomplete_review_count}; unresolved=${report.unresolved_incomplete_count}; ` +
      `keyboard=${report.keyboard_failure_count}; ` +
      `suppressed=${report.suppressed_findings.length}; output=${resolve(options.output)}`,
  );
  process.exitCode = report.passed ? 0 : 1;
}

main().catch((error) => {
  console.error(error.stack ?? error.message);
  process.exitCode = 2;
});
