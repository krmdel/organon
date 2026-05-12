// Phase 44 (v1.5) — F7 task eviction.
//
// Sweeps <projectPath>/.organon/tasks/ removing status files older
// than 24h, and caps the directory at 200 entries per project (oldest
// dropped first). Eviction is read-time (called on dashboard mount +
// every 5min via interval); never fires on write so task creation
// stays O(1).

import { existsSync, readFileSync, readdirSync, rmSync } from "node:fs";
import path from "node:path";
import { tasksDir, type TaskRecord } from "./registry";

export const MAX_AGE_MS = 24 * 60 * 60 * 1000; // 24h
export const MAX_TASKS_PER_PROJECT = 200;

function readRecord(file: string): TaskRecord | null {
  try {
    const obj = JSON.parse(readFileSync(file, "utf8"));
    if (obj && typeof obj.task_id === "string") return obj as TaskRecord;
  } catch { /* ignore */ }
  return null;
}

/**
 * Sweep stale + over-cap files. Returns the count removed.
 *
 * Algorithm:
 *   1. List <projectPath>/.organon/tasks/*.json
 *   2. Drop any record whose finished_at (or started_at if running)
 *      is older than 24h.
 *   3. If > 200 entries remain, drop the oldest by started_at to bring
 *      the count back to 200.
 */
export function evictOldTasks(projectPath: string, nowMs: number = Date.now()): number {
  const dir = tasksDir(projectPath);
  if (!existsSync(dir)) return 0;
  type FileRec = { file: string; rec: TaskRecord };
  const records: FileRec[] = [];
  for (const name of readdirSync(dir)) {
    if (!name.endsWith(".json") || name.endsWith(".tmp")) continue;
    const file = path.join(dir, name);
    const rec = readRecord(file);
    if (rec) records.push({ file, rec });
  }

  let removed = 0;
  // Step 1 — drop stale.
  const fresh: FileRec[] = [];
  for (const { file, rec } of records) {
    const stamp = rec.finished_at ?? rec.started_at;
    const stampMs = new Date(stamp).getTime();
    if (Number.isFinite(stampMs) && nowMs - stampMs > MAX_AGE_MS) {
      try { rmSync(file); removed++; } catch { /* ignore */ }
    } else {
      fresh.push({ file, rec });
    }
  }

  // Step 2 — cap by count.
  if (fresh.length > MAX_TASKS_PER_PROJECT) {
    const sorted = [...fresh].sort(
      (a, b) =>
        new Date(a.rec.started_at).getTime() -
        new Date(b.rec.started_at).getTime(),
    );
    const overflow = sorted.length - MAX_TASKS_PER_PROJECT;
    for (let i = 0; i < overflow; i++) {
      try { rmSync(sorted[i].file); removed++; } catch { /* ignore */ }
    }
  }

  return removed;
}
