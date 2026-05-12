import { test } from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { readFileSync, existsSync, readdirSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 4 fix-sprint regression tests — runner heartbeat + timeout +
// structured exit + SSE route forwarding + RunStateCard component shape.
//
// Why source-text + child_process tests instead of importing the runner:
// `node --test tests/**/*.test.mjs` runs the tests under plain Node ESM;
// importing the .ts runner directly hits the relative-import-no-extension
// resolver gap (TS allows it, Node strict ESM doesn't). Source-text scans
// + harness binary smoke + dispatched-spawn behaviour cover the contract
// without forcing a TS build step into the test harness.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const FAKE = join(__dirname, "fixtures", "fake-claude.mjs");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

test("RunEvent type carries heartbeat + timeout + structured exit", () => {
  const runs = readSrc("src/lib/runs.ts");
  assert.match(runs, /type RunExitReason/, "RunExitReason union must be exported");
  for (const reason of ["ok", "timeout", "cancelled", "failed", "spawn-error"]) {
    assert.ok(
      runs.includes(`"${reason}"`),
      `RunExitReason must include "${reason}"`,
    );
  }
  // RunEvent variants
  assert.match(runs, /\| \{ type: "heartbeat";/, "RunEvent must include heartbeat variant");
  assert.match(runs, /\| \{ type: "timeout";/, "RunEvent must include timeout variant");
  // Exit variant carries reason + success + message
  assert.match(runs, /reason\?:\s*RunExitReason/);
  assert.match(runs, /success\?:\s*boolean/);
  // Status union widened
  assert.match(
    runs,
    /status:\s*"running"\s*\|\s*"ok"\s*\|\s*"error"\s*\|\s*"timeout"\s*\|\s*"cancelled"/,
    "RunSummary.status must include timeout + cancelled",
  );
});

test("runner spawns a watchdog timer + heartbeat interval + classifies exits", () => {
  const runner = readSrc("src/lib/claude-runner.ts");
  // Defaults exposed for tests + caller overrides
  assert.match(runner, /export const DEFAULT_TIMEOUT_MS\b/);
  assert.match(runner, /export const DEFAULT_HEARTBEAT_MS\b/);
  // RunnerOptions surface
  assert.match(runner, /timeoutMs\?:\s*number/);
  assert.match(runner, /heartbeatMs\?:\s*number/);
  // Pre-aborted abortSignal short-circuits
  assert.match(
    runner,
    /opts\.abortSignal\?\.aborted/,
    "must short-circuit when abortSignal is already aborted",
  );
  // Heartbeat + timeout watchdog wiring
  assert.match(runner, /setInterval\(\(\) => \{[\s\S]+?heartbeat/);
  assert.match(runner, /setTimeout\(\(\) => \{[\s\S]+?timeout/);
  // Classification at close
  for (const reason of [`reason = "timeout"`, `reason = "cancelled"`, `reason = "ok"`, `reason = "failed"`, `reason: "spawn-error"`]) {
    assert.ok(runner.includes(reason), `runner must classify ${reason}`);
  }
  // SIGKILL grace fallback
  assert.match(runner, /SIGKILL/);
  assert.match(runner, /SIGTERM/);
});

test("every SSE route captures lastExit + enriches the `done` payload", () => {
  const routes = [
    // Phase 6 (fix-sprint): /api/data/analyze is now direct-Python (plain JSON
    // POST, no SSE). The opt-in LLM narrative lives at /api/data/interpret,
    // which still routes through runClaude and must follow the lastExit
    // contract. analyze's contract is asserted in tests/data-stat-test.test.mjs.
    "src/app/api/data/interpret/route.ts",
    "src/app/api/draft/[slug]/action/route.ts",
    "src/app/api/hypothesis/reconcile/route.ts",
    "src/app/api/images/generate/route.ts",
    "src/app/api/images/lock/route.ts",
    "src/app/api/tools/run/route.ts",
    "src/app/api/execute/route.ts",
  ];
  for (const rel of routes) {
    const src = readSrc(rel);
    assert.match(
      src,
      /let lastExit:[\s\S]+?\| null = null;/,
      `${rel} must capture lastExit`,
    );
    assert.match(
      src,
      /if \(evt\.type === "exit"\) lastExit = evt;/,
      `${rel} must record exit event into lastExit`,
    );
    assert.ok(
      // images/lock combines (lastExit?.success ?? false) && captionLanded;
      // others use the bare lastExit?.success ?? false. Accept either.
      src.includes("lastExit?.success ?? false"),
      `${rel} must forward success from lastExit in done payload`,
    );
    assert.ok(
      src.includes(`lastExit?.reason ?? "failed"`),
      `${rel} must forward reason from lastExit in done payload`,
    );
  }
});

test("RunStateCard component handles every state with appropriate copy", () => {
  const card = readSrc("src/components/primitives/run-state-card.tsx");
  for (const state of ["idle", "running", "succeeded", "failed", "timeout", "cancelled"]) {
    assert.ok(card.includes(`"${state}"`), `RunStateCard must handle state="${state}"`);
  }
  // Cancel button gates on state="running" + onCancel.
  assert.ok(
    card.includes(`state === "running" && onCancel`),
    "Cancel button must require running state + onCancel handler",
  );
  // Retry button shows for failed/timeout/cancelled.
  assert.ok(
    card.includes(`state === "failed" || state === "timeout" || state === "cancelled"`)
      && card.includes(`onRetry ? (`),
    "Retry button must be gated on failed/timeout/cancelled + onRetry handler",
  );
  // ARIA role on failure surfaces
  assert.ok(
    card.includes(`role={state === "failed" || state === "timeout" ? "alert" : "status"}`),
    "RunStateCard must mark failed/timeout as role=alert",
  );
});

test("hypothesis workspace consumes done events + exposes Retry/Cancel", () => {
  const ws = readSrc("src/components/hypothesis/hypothesis-workspace.tsx");
  // RunStateCard mounted
  assert.match(ws, /import \{ RunStateCard\b[\s\S]*from "@\/components\/primitives\/run-state-card"/);
  // Workspace state mirrors runner reasons
  for (const state of ['"succeeded"', '"failed"', '"timeout"', '"cancelled"']) {
    assert.ok(ws.includes(state), `hypothesis-workspace must handle RunState ${state}`);
  }
  // applyDone branches on reason
  assert.match(ws, /case "timeout":/);
  assert.match(ws, /case "spawn-error":/);
  // Last params kept for Retry replay
  assert.match(ws, /lastGenParamsRef = useRef/);
  // consumeSse returns a done summary
  assert.match(ws, /Promise<SseDone \| null>/);
});

// --- Test harness binary smoke ---
// These exercise tests/fixtures/fake-claude.mjs end-to-end so future
// runner-failure tests that DO import the TS runner (once we land a build
// shim) can rely on fake-claude as a deterministic stand-in for `claude -p`.

test("fake-claude harness: success mode exits 0 with stdout", async () => {
  const r = await runFake(["--mode=success"]);
  assert.equal(r.code, 0);
  assert.match(r.stdout, /^ok\b/);
});

test("fake-claude harness: fail-with mode exits non-zero", async () => {
  const r = await runFake(["--mode=fail-with=2"]);
  assert.equal(r.code, 2);
  assert.match(r.stderr, /failing with code 2/);
});

test("fake-claude harness: stdout-loop survives until SIGTERM", async () => {
  // Start the loop, wait for at least one tick, SIGTERM it.
  const child = spawn("node", [FAKE, "--mode=stdout-loop=20"], { stdio: ["ignore", "pipe", "pipe"] });
  const lines = [];
  child.stdout.on("data", (chunk) => lines.push(chunk.toString()));
  await waitForLine(child, 250);
  child.kill("SIGTERM");
  const code = await new Promise((r) => child.on("close", r));
  // SIGTERM kill returns null code, NOT 0.
  assert.ok(code === null || code !== 0, `expected non-zero/null code from SIGTERM, got ${code}`);
  assert.ok(
    lines.some((l) => l.includes("tick")),
    "expected at least one stdout tick before SIGTERM",
  );
});

test("dogfood library has not regressed since Phase 3", () => {
  // Phase 4 doesn't touch persistence — sanity-check that Phase 3 is still
  // green so a regression here can't slip in unnoticed.
  const papersDir = join(
    ROOT, "..", "..", "..", "projects", "briefs",
    "dogfood-glp1-weight-regain", "papers",
  );
  if (!existsSync(papersDir)) return;
  for (const f of readdirSync(papersDir)) {
    if (!f.endsWith(".json")) continue;
    assert.doesNotMatch(f, /^pmid-pmid:/,
      `Phase 3 regression: ${f} re-acquired the double prefix`);
    if (statSync(join(papersDir, f)).isFile()) {
      const obj = JSON.parse(readFileSync(join(papersDir, f), "utf8"));
      assert.ok(typeof obj.cite_key === "string" && obj.cite_key.length > 0,
        `Phase 3 regression: ${f} lost its cite_key`);
    }
  }
});

// --- helpers ---

function runFake(args) {
  return new Promise((resolve) => {
    const child = spawn("node", [FAKE, ...args], { stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (c) => { stdout += c.toString(); });
    child.stderr.on("data", (c) => { stderr += c.toString(); });
    child.on("close", (code) => resolve({ code, stdout, stderr }));
  });
}

function waitForLine(child, timeoutMs) {
  return new Promise((resolve, reject) => {
    const t = setTimeout(() => reject(new Error("timeout waiting for stdout line")), timeoutMs);
    const onData = () => { clearTimeout(t); child.stdout.off("data", onData); resolve(); };
    child.stdout.on("data", onData);
  });
}
