import { test } from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync, rmSync, readFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 6 (fix-sprint) — direct-Python stat test runner.
// /api/data/analyze pivoted from runClaude (60s+ LLM) to a deterministic
// scipy subprocess. These tests are split into:
//   1. Source-text scans that the route + lib are wired to the new path
//      (no runClaude import in the route, lib uses spawn + saveResult).
//   2. End-to-end subprocess smokes against the live venv:
//      ttest_ind, pearson, anova_oneway, power_t_test, error mapping.
//      Skipped (with a console note) when the .venv python is missing,
//      so the test file works on CI without the data-analysis venv.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const ORGANON_ROOT = join(ROOT, "..", "..", "..");
const VENV_PY = join(ORGANON_ROOT, ".venv", "bin", "python");
const SCRIPT = join(ROOT, "scripts", "run_stat_test.py");
const HAS_VENV = existsSync(VENV_PY) && existsSync(SCRIPT);

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

// ---- Source-text scans (always run) ---------------------------------------

test("analyze route no longer imports runClaude (direct-Python path only)", () => {
  const src = readSrc("src/app/api/data/analyze/route.ts");
  assert.doesNotMatch(src, /from "@\/lib\/claude-runner"/,
    "analyze route must not import runClaude (numeric path is direct-Python)");
  assert.doesNotMatch(src, /\brunClaude\(/,
    "analyze route must not call runClaude");
  assert.match(src, /from "@\/lib\/data\/stat-test"/,
    "analyze route must import the new stat-test lib");
  assert.match(src, /\brunStatTest\(/,
    "analyze route must call runStatTest");
  // Plain JSON POST shape (mirrors plot route): 201 on success, JSON body.
  assert.match(src, /Response\.json\(\s*\{\s*result\s*\}/,
    "analyze route must return { result } JSON, not SSE");
  assert.match(src, /status:\s*201/,
    "analyze route must use 201 on success");
});

test("stat-test lib spawns the python script with the documented contract", () => {
  const src = readSrc("src/lib/data/stat-test.ts");
  assert.match(src, /run_stat_test\.py/,
    "stat-test lib must reference scripts/run_stat_test.py");
  assert.match(src, /from "node:child_process"/,
    "stat-test lib must spawn a subprocess");
  for (const flag of ["--run-id", "--project-slug", "--file-id", "--test", "--params-json"]) {
    assert.ok(src.includes(`"${flag}"`),
      `stat-test lib must pass ${flag} on the CLI`);
  }
  assert.match(src, /TIMEOUT_MS/,
    "stat-test lib must enforce a timeout");
  assert.match(src, /SIGKILL/,
    "stat-test lib must SIGKILL on timeout");
  assert.match(src, /saveResult\(/,
    "stat-test lib must persist via saveResult");
  // Error-status mapping.
  assert.match(src, /requires statsmodels/,
    "stat-test lib must surface the logistic_regression hint");
  assert.match(src, /code\s*===\s*2\s*\?\s*400\s*:\s*500/,
    "stat-test lib must map exit code 2 → 400 and other non-zero → 500");
});

test("interpret route is a separate SSE wrapper (opt-in narrative only)", () => {
  const src = readSrc("src/app/api/data/interpret/route.ts");
  assert.match(src, /from "@\/lib\/claude-runner"/,
    "interpret route is the LLM path and must use runClaude");
  assert.match(src, /\brunClaude\(/);
  assert.match(src, /readResult\(/,
    "interpret route must look up the existing result by run_id");
  assert.match(src, /text\/event-stream/,
    "interpret route must stream via SSE");
});

test("data-workspace consumes plain JSON for analyze (no SSE parsing)", () => {
  const src = readSrc("src/components/data/data-workspace.tsx");
  // The old analyzeStream state has been removed.
  assert.doesNotMatch(src, /analyzeStream/,
    "data-workspace must drop the analyzeStream SSE buffer");
  // handleRunRec must consume json.result, not iterate a reader.
  const handler = src.split("handleRunRec")[1] ?? "";
  assert.ok(handler.includes("json.result"),
    "handleRunRec must read json.result from the plain POST");
  assert.ok(!handler.includes("res.body.getReader"),
    "handleRunRec must not iterate an SSE body reader anymore");
});

test("StatResultCard exposes an Interpret button gated on project slug", () => {
  const src = readSrc("src/components/data/stat-result-card.tsx");
  assert.match(src, /Interpret/,
    "StatResultCard must render an Interpret button");
  assert.match(src, /\/api\/data\/interpret/,
    "Interpret button must POST to /api/data/interpret");
  // The button is disabled without project slug; the prop is optional.
  assert.match(src, /project\?:\s*string/,
    "project prop must be optional (the card still renders without Interpret)");
  assert.match(src, /disabled=\{interpretBusy \|\| !project\}/,
    "Interpret must be disabled while busy or when project is missing");
});

// ---- Subprocess smokes (require .venv with pandas + scipy) ----------------

function runScript(args, opts = {}) {
  return new Promise((resolve) => {
    const child = spawn(VENV_PY, [SCRIPT, ...args], {
      cwd: ORGANON_ROOT,
      stdio: ["ignore", "pipe", "pipe"],
      ...opts,
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (c) => { stdout += c.toString("utf8"); });
    child.stderr.on("data", (c) => { stderr += c.toString("utf8"); });
    child.on("close", (code) => resolve({ code, stdout, stderr }));
  });
}

function makeFixture() {
  const dir = mkdtempSync(join(tmpdir(), "stat-test-"));
  const csv = join(dir, "fixture.csv");
  const rows = [
    "id,group,outcome,baseline",
    "1,A,12.5,8.1",
    "2,A,11.2,7.9",
    "3,A,13.4,9.0",
    "4,A,10.8,8.2",
    "5,A,12.1,8.5",
    "6,A,11.9,7.6",
    "7,B,15.2,8.0",
    "8,B,14.8,8.3",
    "9,B,16.1,8.7",
    "10,B,15.5,8.4",
    "11,B,15.9,7.8",
    "12,B,14.3,8.1",
  ];
  writeFileSync(csv, rows.join("\n") + "\n", "utf8");
  return { dir, csv };
}

const skipIfNoVenv = HAS_VENV ? false : { skip: "venv missing — skipping subprocess smokes" };

test("ttest_ind on a known fixture: t-statistic, p-value, Cohen's d", skipIfNoVenv, async () => {
  const { dir, csv } = makeFixture();
  try {
    const r = await runScript([
      "--data-path", csv,
      "--run-id", "stat-test-fixture",
      "--project-slug", "__test__",
      "--file-id", "data-test",
      "--test", "ttest_ind",
      "--params-json", JSON.stringify({
        value_col: "outcome", group_col: "group", paired: false, alpha: 0.05, equal_var: false,
      }),
    ]);
    assert.equal(r.code, 0, `expected exit 0, got ${r.code}: ${r.stderr}`);
    const line = r.stdout.split("\n").find((l) => l.startsWith("{"));
    assert.ok(line, "must emit one JSON line");
    const art = JSON.parse(line);
    assert.equal(art._artifact, "stat-result");
    assert.equal(art.test_name, "ttest_ind");
    assert.equal(art.id, "stat-test-fixture");
    assert.equal(art.project_slug, "__test__");
    assert.equal(art.n, 12);
    assert.ok(typeof art.test_statistic === "number" && art.test_statistic < 0,
      `t-stat should be negative (B > A), got ${art.test_statistic}`);
    assert.ok(art.p_value !== null && art.p_value < 0.001,
      `p should be < 0.001, got ${art.p_value}`);
    assert.equal(art.effect_size.name, "cohens_d");
    assert.ok(Math.abs(art.effect_size.value) > 1.0,
      `Cohen's d should be large, got ${art.effect_size.value}`);
    // Assumption checks must include shapiro x2 + levene + min_group_n.
    const names = (art.assumption_checks ?? []).map((a) => a.name);
    assert.ok(names.includes("normality_shapiro"));
    assert.ok(names.includes("equal_variance_levene"));
    assert.ok(names.includes("min_group_n"));
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("pearson correlation: r ≈ 0.20 between outcome and baseline (weak linear)", skipIfNoVenv, async () => {
  const { dir, csv } = makeFixture();
  try {
    const r = await runScript([
      "--data-path", csv,
      "--run-id", "pearson-fixture",
      "--project-slug", "__test__",
      "--file-id", "data-test",
      "--test", "pearson",
      "--params-json", JSON.stringify({ x_col: "outcome", y_col: "baseline", alpha: 0.05 }),
    ]);
    assert.equal(r.code, 0, `expected exit 0, got ${r.code}: ${r.stderr}`);
    const art = JSON.parse(r.stdout.split("\n").find((l) => l.startsWith("{")));
    assert.equal(art.test_name, "pearson");
    assert.equal(art.n, 12);
    assert.ok(typeof art.test_statistic === "number");
    assert.ok(art.effect_size.name === "pearson_r");
    assert.ok(typeof art.effect_size.ci_low === "number");
    assert.ok(typeof art.effect_size.ci_high === "number");
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("anova_oneway: F-statistic, p-value, η² for two groups", skipIfNoVenv, async () => {
  const { dir, csv } = makeFixture();
  try {
    const r = await runScript([
      "--data-path", csv,
      "--run-id", "anova-fixture",
      "--project-slug", "__test__",
      "--file-id", "data-test",
      "--test", "anova_oneway",
      "--params-json", JSON.stringify({ value_col: "outcome", group_col: "group", alpha: 0.05 }),
    ]);
    assert.equal(r.code, 0, `expected exit 0, got ${r.code}: ${r.stderr}`);
    const art = JSON.parse(r.stdout.split("\n").find((l) => l.startsWith("{")));
    assert.equal(art.test_name, "anova_oneway");
    assert.ok(art.test_statistic > 10, `F should be large, got ${art.test_statistic}`);
    assert.ok(art.p_value < 0.01);
    assert.equal(art.effect_size.name, "eta_squared");
    assert.ok(art.effect_size.value > 0.5);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("power_t_test target=0.8, d=0.5, α=0.05 → required n ≈ 64 per group", skipIfNoVenv, async () => {
  // Power tests don't need a CSV (--data-path is omitted).
  const r = await runScript([
    "--run-id", "power-fixture",
    "--project-slug", "__test__",
    "--test", "power_t_test",
    "--params-json", JSON.stringify({
      test_kind: "t-test", effect_size: 0.5, alpha: 0.05, power_target: 0.8,
    }),
  ]);
  assert.equal(r.code, 0, `expected exit 0, got ${r.code}: ${r.stderr}`);
  const art = JSON.parse(r.stdout.split("\n").find((l) => l.startsWith("{")));
  assert.equal(art.test_name, "power_t_test");
  assert.equal(art.mode, "power");
  // G*Power's classic answer for the same input is n=64 per group.
  assert.ok(art.n >= 60 && art.n <= 70,
    `expected n ≈ 64 per group for d=0.5/α=0.05/power=0.8, got ${art.n}`);
  assert.ok(art.effect_size.value >= 0.79,
    `achieved power should be ≥ 0.79, got ${art.effect_size.value}`);
});

test("logistic_regression returns the statsmodels-required hint with non-zero exit", skipIfNoVenv, async () => {
  const r = await runScript([
    "--run-id", "logistic-fixture",
    "--project-slug", "__test__",
    "--test", "logistic_regression",
    "--params-json", "{}",
  ]);
  assert.notEqual(r.code, 0, "logistic_regression must exit non-zero (no statsmodels)");
  assert.match(r.stderr, /requires statsmodels/);
});

test("missing column → exit 2 with a clear ValueError message", skipIfNoVenv, async () => {
  const { dir, csv } = makeFixture();
  try {
    const r = await runScript([
      "--data-path", csv,
      "--run-id", "missing-col",
      "--project-slug", "__test__",
      "--file-id", "data-test",
      "--test", "ttest_ind",
      "--params-json", JSON.stringify({
        value_col: "nonexistent_column", group_col: "group", paired: false, alpha: 0.05,
      }),
    ]);
    assert.equal(r.code, 2,
      `expected exit 2 (ValueError contract), got ${r.code}: ${r.stderr}`);
    assert.match(r.stderr, /\{"error":/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
