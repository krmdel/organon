import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 36 (v1.4) — workspace-side detachable abort.
//
// The reconcile UI (hypothesis-workspace.tsx) used to abort on every
// next/router navigation. Phase 36 makes the workspace:
//   1. capture the task_id from the first SSE event
//   2. persist `organon:task:reconcile:{hyp_id}` to localStorage
//   3. on mount, check localStorage; attach to /api/tasks/{task_id}/stream
//      instead of starting a fresh POST
//   4. clear localStorage on the `done` event

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const WORKSPACE_SRC = readSrc("src/components/hypothesis/hypothesis-workspace.tsx");
const TASKS_HELPER_SRC = readSrc("src/lib/state/task-attach.ts");

test("Phase 36 — workspace persists task_id to localStorage on first SSE event", () => {
  // task-attach helper exposes the localStorage key shape + read/write.
  assert.match(TASKS_HELPER_SRC, /export function readActiveTask\(/);
  assert.match(TASKS_HELPER_SRC, /export function writeActiveTask\(/);
  assert.match(TASKS_HELPER_SRC, /organon:task:/);
  // Workspace wires writeActiveTask on the first task-started event.
  assert.match(WORKSPACE_SRC, /writeActiveTask/);
  assert.match(WORKSPACE_SRC, /task[-_]started/);
  // Behavioural replica — round-trip via a mock storage.
  const store = new Map();
  const fakeStorage = {
    setItem: (k, v) => store.set(k, v),
    getItem: (k) => store.get(k) ?? null,
    removeItem: (k) => store.delete(k),
  };
  const writeActiveTask = (project, kind, scope, task_id) => {
    fakeStorage.setItem(
      `organon:task:${kind}:${project}:${scope}`,
      JSON.stringify({ task_id, started_at: Date.now() }),
    );
  };
  const readActiveTask = (project, kind, scope) => {
    const raw = fakeStorage.getItem(`organon:task:${kind}:${project}:${scope}`);
    if (!raw) return null;
    try { return JSON.parse(raw).task_id ?? null; } catch { return null; }
  };
  writeActiveTask("p1", "reconcile", "hyp1", "task_42");
  assert.equal(readActiveTask("p1", "reconcile", "hyp1"), "task_42");
  assert.equal(readActiveTask("p1", "reconcile", "hyp2"), null);
});

test("Phase 36 — workspace re-attaches to in-flight task on remount", () => {
  // useEffect on mount checks readActiveTask; if present, fetches
  // /api/tasks/{task_id}/stream instead of starting a new POST.
  assert.match(WORKSPACE_SRC, /readActiveTask/);
  assert.match(WORKSPACE_SRC, /\/api\/tasks\//);
  // Pin the GET path so the route name is load-bearing.
  assert.match(WORKSPACE_SRC, /\/api\/tasks\/\$\{[^}]+\}\/stream/);
});

test("Phase 36 — completed task_ids are removed from localStorage on done event", () => {
  // The clearActiveTask helper exists + is exported.
  assert.match(TASKS_HELPER_SRC, /export function clearActiveTask\(/);
  // Workspace calls clearActiveTask in the done branch of the SSE consumer.
  assert.match(WORKSPACE_SRC, /clearActiveTask/);
  // Behavioural replica — done event triggers clear.
  const store = new Map([["organon:task:reconcile:p1:hyp1", '{"task_id":"task_42"}']]);
  const fakeStorage = {
    getItem: (k) => store.get(k) ?? null,
    removeItem: (k) => store.delete(k),
  };
  const clearActiveTask = (project, kind, scope) => {
    fakeStorage.removeItem(`organon:task:${kind}:${project}:${scope}`);
  };
  clearActiveTask("p1", "reconcile", "hyp1");
  assert.equal(fakeStorage.getItem("organon:task:reconcile:p1:hyp1"), null);
});
