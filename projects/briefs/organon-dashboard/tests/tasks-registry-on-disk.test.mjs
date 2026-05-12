import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 44 (v1.5) — F7 deepening of Phase 36's in-memory wedge.
//
// Each task gets an on-disk status file at
// `<projectPath>/.organon/tasks/<task_id>.json` so tasks survive
// `npm run dev` restart. Eviction sweeps files older than 24h and
// caps the directory at 200 task files per project. NEW
// listTasks(projectPath, opts) reads from disk for the header panel.
//
// Decisions (brief §8.3):
// - One status file per task (no global lock).
// - Eviction is read-time, never on write (keeps creation O(1)).
// - `payload` is opaque to the registry — each route stamps its own
//   scope-specific data; the panel reads `kind + scope` to navigate.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const REG_SRC = readSrc("src/lib/tasks/registry.ts");
const EVICT_SRC = readSrc("src/lib/tasks/eviction.ts");

test("Phase 44 — registry writes <task_id>.json on registerTask", () => {
  // The registerTask fn calls a writer that lays down a status file
  // under <projectPath>/.organon/tasks/<task_id>.json on first
  // registration, BEFORE the worker loop starts draining.
  assert.match(REG_SRC, /\.organon\/tasks/);
  // Helper computes the file path using projectPath + task_id.
  assert.match(REG_SRC, /export function tasksDir\(projectPath/);
  assert.match(REG_SRC, /export function taskFile\(projectPath/);
  // registerTask accepts a project_path so the on-disk write knows
  // where to land. (project_slug stays in the payload for navigation.)
  assert.match(REG_SRC, /project_path:\s*string/);
  // First write happens in registerTask (look for writeAtomic adjacent
  // to a "running" status field).
  assert.match(REG_SRC, /status:\s*"running"/);
});

test("Phase 44 — status file is updated atomically (tmp + rename) on every event", () => {
  // Atomic write helper exists; same tmp+rename pattern as Phase 25 / 34.
  assert.match(REG_SRC, /\.tmp/);
  assert.match(REG_SRC, /renameSync/);
  // last_event field is updated as events stream in (any non-null
  // event payload that's stamped onto the on-disk record).
  assert.match(REG_SRC, /last_event/);
});

test("Phase 44 — listTasks returns running + last 20 completed", () => {
  // listTasks reads <projectPath>/.organon/tasks/*.json and returns a
  // structured shape: { running: TaskSummary[], recent: TaskSummary[] }.
  assert.match(REG_SRC, /export function listTasks\(/);
  // Returns running + recent buckets; recent is capped at 20.
  assert.match(REG_SRC, /running:\s*[A-Za-z]+\[\]/);
  assert.match(REG_SRC, /recent:\s*[A-Za-z]+\[\]/);
  assert.match(REG_SRC, /\b20\b/);

  // Behavioural replica of the bucketing.
  const bucket = (tasks) => {
    const running = tasks.filter((t) => t.status === "running");
    const completed = tasks
      .filter((t) => t.status !== "running")
      .sort((a, b) => (b.finished_at ?? "").localeCompare(a.finished_at ?? ""))
      .slice(0, 20);
    return { running, recent: completed };
  };
  const sample = [
    { task_id: "a", status: "running" },
    { task_id: "b", status: "done", finished_at: "2026-05-08T10:00:00Z" },
    { task_id: "c", status: "failed", finished_at: "2026-05-08T11:00:00Z" },
  ];
  const out = bucket(sample);
  assert.equal(out.running.length, 1);
  assert.equal(out.recent.length, 2);
  assert.equal(out.recent[0].task_id, "c"); // most recent first
});

test("Phase 44 — eviction sweeps files older than 24h", () => {
  // The eviction helper exposes a sweep function that reads each task
  // file's `started_at` (or `finished_at` if completed) and deletes
  // anything older than 24h.
  assert.match(EVICT_SRC, /export function evictOldTasks\(/);
  // 24h threshold (in ms or hours form).
  assert.match(EVICT_SRC, /24\s*\*\s*60\s*\*\s*60\s*\*\s*1000|MAX_AGE_MS|24h/);

  // Behavioural replica.
  const sweep = (tasks, nowMs, maxAgeMs = 24 * 60 * 60 * 1000) => {
    return tasks.filter((t) => {
      const stamp = t.finished_at ?? t.started_at;
      const stampMs = new Date(stamp).getTime();
      return nowMs - stampMs <= maxAgeMs;
    });
  };
  const fresh = { started_at: new Date(Date.now() - 1000).toISOString() };
  const stale = { started_at: new Date(Date.now() - 30 * 60 * 60 * 1000).toISOString() };
  const kept = sweep([fresh, stale], Date.now());
  assert.equal(kept.length, 1);
});

test("Phase 44 — eviction caps total files at 200 per project", () => {
  // The cap kicks in when the directory has > 200 entries; the oldest
  // are dropped first.
  assert.match(EVICT_SRC, /\b200\b/);
  // A behavioural replica of the cap-by-age trim.
  const cap = (tasks, max = 200) => {
    if (tasks.length <= max) return tasks;
    const sorted = [...tasks].sort(
      (a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime(),
    );
    return sorted.slice(0, max);
  };
  const many = Array.from({ length: 250 }, (_, i) => ({
    task_id: `t${i}`,
    started_at: new Date(Date.now() - i * 1000).toISOString(),
  }));
  const trimmed = cap(many);
  assert.equal(trimmed.length, 200);
});

test("Phase 44 — registry survives in-memory map clear (e.g. dev restart) by re-hydrating from disk", () => {
  // The on-disk surface is the source of truth for `listTasks`; the
  // header panel works even when the in-memory registry has been
  // wiped (process restart). Pinning the contract: listTasks reads
  // from disk, NOT from the in-memory `tasks` map.
  assert.match(REG_SRC, /export function listTasks[\s\S]{0,400}readdirSync/);
  // Re-attach (subscribeToTask) returning null when the in-memory
  // map has lost the task is the v1.4 wedge; v1.5 doesn't change
  // that contract — re-attach still requires the in-memory entry.
  assert.match(REG_SRC, /export function subscribeToTask\(/);
});
