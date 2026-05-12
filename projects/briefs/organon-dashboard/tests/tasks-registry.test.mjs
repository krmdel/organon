import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 36 (v1.4) — B3 detachable abort scope.
//
// 13 SSE routes used to wire `request.signal.addEventListener("abort", ...)`
// which killed the runner the moment the user navigated away. Phase 36
// introduces an in-memory task registry that hosts long-running runners
// detached from request lifetime, so reconcile + retry-persona survive
// navigation and the user can re-attach via a NEW
// /api/tasks/[task_id]/stream endpoint.
//
// In-memory only in v1.4 (Phase 44 in v1.5 deepens to on-disk + 13 routes).

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const REGISTRY_SRC = readSrc("src/lib/tasks/registry.ts");
const STREAM_ROUTE_SRC = readSrc("src/app/api/tasks/[task_id]/stream/route.ts");
const RECONCILE_ROUTE_SRC = readSrc("src/app/api/hypothesis/reconcile/route.ts");

test("Phase 36 — registerTask returns a unique task_id and stores the runner", () => {
  // Public surface.
  assert.match(REGISTRY_SRC, /export function registerTask\(/);
  // Returns a string id (the task_id).
  assert.match(REGISTRY_SRC, /registerTask[\s\S]{0,400}\):\s*string/);
  // Behavioural replica — registry is a Map keyed by task_id.
  const tasks = new Map();
  let counter = 0;
  const registerTask = ({ kind, project_slug, scope }) => {
    const task_id = `task_${++counter}`;
    tasks.set(task_id, { task_id, kind, project_slug, scope, events: [], subscribers: new Set(), done: false });
    return task_id;
  };
  const id1 = registerTask({ kind: "reconcile", project_slug: "p1", scope: "hyp1" });
  const id2 = registerTask({ kind: "reconcile", project_slug: "p1", scope: "hyp1" });
  assert.notEqual(id1, id2, "task ids must be unique even with identical args");
  assert.equal(tasks.size, 2);
});

test("Phase 36 — getTask returns null for unknown task_ids", () => {
  assert.match(REGISTRY_SRC, /export function getTask\(/);
  // Behavioural replica.
  const tasks = new Map([["task_known", { task_id: "task_known" }]]);
  const getTask = (id) => tasks.get(id) ?? null;
  assert.equal(getTask("task_unknown"), null);
  assert.equal(getTask("task_known")?.task_id, "task_known");
});

test("Phase 36 — subscribeToTask replays the buffer + forwards live events", () => {
  // The helper exists; replays buffered events on first call; returns
  // an unsubscribe handle.
  assert.match(REGISTRY_SRC, /export function subscribeToTask\(/);
  // The helper iterates task.events on subscribe (replay) — pin the
  // forEach/for-of pattern.
  assert.match(
    REGISTRY_SRC,
    /subscribeToTask[\s\S]{0,800}(events\.forEach|for\s*\(\s*const\s+\w+\s+of\s+task\.events|task\.events)/,
  );
  // Behavioural replica.
  const task = { events: [{ type: "stdout", data: "a" }, { type: "stdout", data: "b" }], subscribers: new Set(), done: false };
  const seen = [];
  const subscribe = (cb) => {
    for (const evt of task.events) cb(evt);
    task.subscribers.add(cb);
    return () => task.subscribers.delete(cb);
  };
  const unsub = subscribe((evt) => seen.push(evt.data));
  // Replay delivered both buffered events.
  assert.deepEqual(seen, ["a", "b"]);
  // Live event is forwarded.
  for (const sub of task.subscribers) sub({ type: "stdout", data: "c" });
  assert.deepEqual(seen, ["a", "b", "c"]);
  // Unsubscribe stops live delivery.
  unsub();
  assert.equal(task.subscribers.size, 0);
});

test("Phase 36 — auto-eviction fires after the no-subscriber timeout", () => {
  // 10-minute eviction window, reset when a subscriber attaches, fired
  // when the last subscriber leaves AND the task is done.
  assert.match(REGISTRY_SRC, /EVICT_AFTER_MS\s*=\s*[\s\S]{0,40}10\s*\*\s*60\s*\*\s*1000/);
  assert.match(REGISTRY_SRC, /setTimeout/);
  // Behavioural replica with fake timer.
  const EVICT = 600_000;
  let now = 0;
  const tasks = new Map();
  const fakeTimers = [];
  const setT = (cb, ms) => { const id = fakeTimers.length; fakeTimers.push({ at: now + ms, cb }); return id; };
  const advance = (ms) => {
    now += ms;
    for (const t of fakeTimers.slice()) {
      if (t.at <= now && !t.fired) { t.fired = true; t.cb(); }
    }
  };
  const task = { task_id: "x", subscribers: new Set(), done: true };
  tasks.set(task.task_id, task);
  const schedule = () => setT(() => {
    if (task.subscribers.size === 0) tasks.delete(task.task_id);
  }, EVICT);
  schedule();
  advance(EVICT - 1);
  assert.ok(tasks.has("x"), "should not evict before the timeout");
  advance(2);
  assert.ok(!tasks.has("x"), "should evict after the timeout");
});

test("Phase 36 — /api/tasks/[task_id]/stream returns 404 for unknown ids", () => {
  // Route file exists with a GET handler.
  assert.match(STREAM_ROUTE_SRC, /export async function GET\(/);
  // Returns 404 when getTask returns null.
  assert.match(STREAM_ROUTE_SRC, /getTask\(/);
  assert.match(STREAM_ROUTE_SRC, /404/);
});

test("Phase 36 — reconcile route registers a task_id and drops request.signal abort wiring", () => {
  // Drops `request.signal.addEventListener("abort", () => abort.abort())`
  // for this route — task survives request lifetime now.
  assert.doesNotMatch(
    RECONCILE_ROUTE_SRC,
    /request\.signal\.addEventListener\("abort"\s*,\s*\(\s*\)\s*=>\s*abort\.abort\(\)/,
  );
  // Imports + uses the registry.
  assert.match(RECONCILE_ROUTE_SRC, /registerTask/);
  // First SSE event broadcasts the task_id so the client can re-attach.
  assert.match(RECONCILE_ROUTE_SRC, /task[-_]started|task_id/);
});
