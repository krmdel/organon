import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 64 (v2.2) — M3: figures-workspace mount-time re-attach.
// On mount: fetch /api/tasks filtered by kind === "figure-generate"
// (and the active project), render running placeholders, subscribe via
// subscribeToTask, prepend completed figures, surface failures with a
// retry affordance.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const WORKSPACE_SRC = readSrc("src/components/figures/figures-workspace.tsx");
const ATTACH_SRC = readSrc("src/lib/state/task-attach.ts");
const GENERATE_ROUTE_SRC = readSrc("src/app/api/images/generate/route.ts");

test("Phase 64 — task-attach exposes a subscribeToTask helper figures-workspace can import", () => {
  // Helper must exist by name + accept (task_id, handler) callable signature.
  assert.match(
    ATTACH_SRC,
    /export\s+function\s+subscribeToTask\s*\(/,
    "task-attach must export subscribeToTask",
  );
  // It must connect to the task SSE stream (Phase 36 substrate).
  assert.match(
    ATTACH_SRC,
    /\/api\/tasks\/\$\{encodeURIComponent\(task_id\)\}\/stream/,
    "subscribeToTask must fetch /api/tasks/${task_id}/stream",
  );
});

test("Phase 64 — figures-workspace imports subscribeToTask from @/lib/state/task-attach", () => {
  assert.match(
    WORKSPACE_SRC,
    /import\s*\{[^}]*\bsubscribeToTask\b[^}]*\}\s*from\s*"@\/lib\/state\/task-attach"/,
    "figures-workspace must import subscribeToTask from @/lib/state/task-attach",
  );
});

test("Phase 64 — figures-workspace fetches /api/tasks on mount with project query param", () => {
  assert.match(
    WORKSPACE_SRC,
    /fetch\(\s*`\/api\/tasks\?project=\$\{encodeURIComponent\(project\)\}`/,
    "figures-workspace must fetch /api/tasks?project=${project} on mount",
  );
});

test("Phase 64 — figures-workspace filters tasks to kind === 'figure-generate'", () => {
  // Pin the literal kind string — must match the route at images/generate
  // line 120 to avoid silent re-attach drift.
  assert.match(
    GENERATE_ROUTE_SRC,
    /kind:\s*"figure-generate"/,
    "images/generate route must still register tasks with kind=figure-generate (don't drift)",
  );
  assert.match(
    WORKSPACE_SRC,
    /kind\s*===\s*"figure-generate"/,
    "figures-workspace must filter running tasks to kind === 'figure-generate'",
  );
});

test("Phase 64 — figures-workspace renders running cards with data-figure-running sentinel", () => {
  assert.match(
    WORKSPACE_SRC,
    /data-figure-running/,
    "figures-workspace must mark each running placeholder with data-figure-running",
  );
});

test("Phase 64 — successful task-done event prepends the new figure (does not replace)", () => {
  // Source-text contract: handler must spread prev AFTER the new figure
  // to land it at index 0. Handler also drops the running placeholder
  // for that task_id.
  assert.match(
    WORKSPACE_SRC,
    /setFigures\(\(prev\)\s*=>\s*\[\s*fig\s*,\s*\.\.\.prev/,
    "figures-workspace must prepend [fig, ...prev] on a successful figure-generate task-done",
  );
  assert.match(
    WORKSPACE_SRC,
    /setRunningTasks\(\(prev\)\s*=>\s*prev\.filter/,
    "figures-workspace must drop the running placeholder for a completed task",
  );
});

test("Phase 64 — failed task surfaces error with retry affordance, does NOT prepend a figure", () => {
  // Failure path keeps the placeholder visible (a red dot + retry); the
  // figures list itself stays untouched.
  assert.match(
    WORKSPACE_SRC,
    /data-figure-retry/,
    "figures-workspace must render a data-figure-retry button on failed running cards",
  );
  // Branch must distinguish failed from success — at least one ternary
  // or conditional gating on a status === 'failed' (or similar).
  assert.match(
    WORKSPACE_SRC,
    /status:\s*"failed"|status\s*===\s*"failed"/,
    "figures-workspace must mark failed running cards with status === 'failed'",
  );
});
