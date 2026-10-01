#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import process from "node:process";

const require = createRequire(import.meta.url);

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
  if (!options["base-url"] || !options.output) {
    throw new Error("Usage: run_accessibility.mjs --base-url URL --output PATH");
  }
  return options;
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
    const python = process.env.VIRTUAL_ENV
      ? resolve(process.env.VIRTUAL_ENV, "bin/python")
      : resolve(".venv/bin/python");
    const packagePath = execFileSync(
      python,
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

async function visibleFocus(page) {
  await page.keyboard.press("Tab");
  return page.evaluate(() => {
    const active = document.activeElement;
    if (!active || active === document.body) return false;
    const style = getComputedStyle(active);
    return style.outlineStyle !== "none" || style.boxShadow !== "none";
  });
}

async function main() {
  const options = argumentsFrom(process.argv.slice(2));
  const { chromium } = loadPlaywright();
  const axeSource = readFileSync(resolveDependency("axe-core/axe.min.js"), "utf8");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1100 },
    locale: "en-US",
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  const routes = [
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
  try {
    await page.goto(`${options["base-url"].replace(/\/$/, "")}/?lang=en`);
    await page.getByText("RoleRadar AI", { exact: true }).first().waitFor({ state: "visible" });
    for (const route of routes) {
      await page.getByText(route, { exact: true }).first().click();
      await page.waitForLoadState("networkidle").catch(() => undefined);
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
        violations: result.violations,
      });
    }
    const keyboard = {
      tab_reaches_visible_focus: await visibleFocus(page),
      primary_controls_named:
        (await page.locator("button:not([aria-label]), a:not([aria-label])").evaluateAll((items) =>
          items.every((item) => Boolean(item.textContent?.trim() || item.getAttribute("title"))),
        )),
    };
    const critical = routeResults.flatMap((route) =>
      route.violations
        .filter((violation) => violation.impact === "critical")
        .map((violation) => ({ route: route.route, ...violation })),
    );
    const suppressed = critical.filter(
      (violation) =>
        violation.id === "aria-allowed-attr" &&
        violation.nodes.length === 1 &&
        violation.nodes[0].target.length === 1 &&
        violation.nodes[0].target[0] === ".stSidebar" &&
        violation.nodes[0].failureSummary.includes('aria-expanded="true"'),
    );
    const releaseBlocking = critical.filter((violation) => !suppressed.includes(violation));
    const report = {
      schema_version: 1,
      base_url: options["base-url"],
      tested_at: new Date().toISOString(),
      standard: "WCAG 2.2 AA",
      engine: "axe-core",
      engine_version: require(resolveDependency("axe-core/package.json")).version,
      keyboard,
      suppression_policy: {
        reason:
          "Streamlit 1.64 renders aria-expanded on its framework-owned sidebar section; " +
          "navigation names and keyboard reachability remain independently asserted.",
        exact_signature_only: true,
      },
      suppressed_findings: suppressed,
      critical_failure_count: releaseBlocking.length,
      critical_failures: releaseBlocking,
      routes: routeResults,
      passed:
        releaseBlocking.length === 0 &&
        keyboard.tab_reaches_visible_focus &&
        keyboard.primary_controls_named,
    };
    mkdirSync(dirname(resolve(options.output)), { recursive: true });
    writeFileSync(resolve(options.output), `${JSON.stringify(report, null, 2)}\n`, "utf8");
    console.log(
      `passed=${report.passed}; routes=${routes.length}; critical=${releaseBlocking.length}; ` +
        `suppressed=${suppressed.length}; output=${resolve(options.output)}`,
    );
    process.exitCode = report.passed ? 0 : 1;
  } finally {
    await context.close();
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error.stack ?? error.message);
  process.exitCode = 2;
});
