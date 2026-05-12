import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 44 (v1.5) — F7 retrofit of the remaining 11 SSE routes.
//
// Phase 36 (v1.4) wedged reconcile + retry-persona; Phase 44 deepens
// to all 13. The retrofitted routes follow the runner-generator
// pattern: register a task → drop request.signal abort wiring → SSE
// reads from the registry buffer.
//
// Plus: NEW GET /api/tasks?project=<slug> returns
// { running: TaskSummary[], recent: TaskSummary[] } for the header
// panel; NEW <TasksPanel /> mounts in the Topbar and fetches the
// route on open.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const ROUTES_TO_REGISTER = [
  "src/app/api/draft/[slug]/generate-section/route.ts",
  "src/app/api/draft/[slug]/edit-with-chat/route.ts",
  "src/app/api/draft/[slug]/generate-title/route.ts",
  "src/app/api/draft/[slug]/action/route.ts",
  "src/app/api/tools/run/route.ts",
  "src/app/api/images/lock/route.ts",
  "src/app/api/images/generate/route.ts",
  "src/app/api/execute/route.ts",
  "src/app/api/data/chat/route.ts",
  "src/app/api/data/figures/[fig_id]/legend/route.ts",
  "src/app/api/data/interpret/route.ts",
];

const TASKS_ROUTE_SRC = readSrc("src/app/api/tasks/route.ts");
const PANEL_SRC = readSrc("src/components/header/tasks-panel.tsx");
const TOPBAR_SRC = readSrc("src/components/shell/topbar.tsx");

test("Phase 44 — all 11 remaining SSE routes register a task_id", () => {
  // Each route either calls registerTask directly OR routes through
  // the shared streamTaskAsSse helper (which calls registerTask
  // internally). Both shapes are accepted.
  for (const rel of ROUTES_TO_REGISTER) {
    const src = readSrc(rel);
    const registers =
      /registerTask\(/.test(src) || /streamTaskAsSse\(/.test(src);
    assert.ok(
      registers,
      `Expected ${rel} to call registerTask(...) or streamTaskAsSse(...) — Phase 44 retrofit missing`,
    );
  }
});

test("Phase 44 — none of those routes still wire request.signal → abort.abort()", () => {
  // After the refactor, the runner generator owns the abort signal;
  // request lifetime no longer kills the underlying skill subprocess.
  for (const rel of ROUTES_TO_REGISTER) {
    const src = readSrc(rel);
    assert.doesNotMatch(
      src,
      /request\.signal\.addEventListener\(\s*["']abort["']/,
      `Expected ${rel} to NOT bind request.signal → abort wiring (Phase 44 dropped this)`,
    );
  }
});

test("Phase 44 — GET /api/tasks?project=<slug> returns running + recent", () => {
  // GET handler shape; reads ?project=<slug> + calls listTasks.
  assert.match(TASKS_ROUTE_SRC, /export async function GET\(/);
  assert.match(TASKS_ROUTE_SRC, /listTasks\(/);
  // Returns the running + recent shape.
  assert.match(TASKS_ROUTE_SRC, /running/);
  assert.match(TASKS_ROUTE_SRC, /recent/);
});

test("Phase 44 — header tasks-panel mounts and fetches /api/tasks on open", () => {
  // Component exports a named function and uses fetch on the new route.
  assert.match(PANEL_SRC, /export function TasksPanel/);
  assert.match(PANEL_SRC, /\/api\/tasks\?project=/);
  // Bell-icon trigger surfaces a count badge for in-flight tasks via a
  // stable data-attr.
  assert.match(PANEL_SRC, /data-tasks-panel-trigger/);
  assert.match(PANEL_SRC, /data-tasks-running-count/);
  // The Topbar mounts <TasksPanel /> so every page sees it.
  assert.match(
    TOPBAR_SRC,
    /import\s*\{[^}]*TasksPanel[^}]*\}\s*from\s*["']@\/components\/header\/tasks-panel["']/,
  );
  assert.match(TOPBAR_SRC, /<TasksPanel/);
});
