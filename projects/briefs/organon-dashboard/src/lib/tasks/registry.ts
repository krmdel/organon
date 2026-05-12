// Phase 36 (v1.4) — B3 detachable abort scope (in-memory wedge).
// Phase 44 (v1.5) — F7 deepening: on-disk persistence for the tasks-
// running header panel + survival across `npm run dev` restart. The
// in-memory subscriber map stays the source of truth for SSE
// re-attach (subscribeToTask still requires the in-memory entry); the
// on-disk surface is the source of truth for `listTasks`, which the
// header panel consumes.
//
// SERVER-ONLY — never import from a client component (uses Node fs +
// timers + closures over claude-runner output). Pitfall #10 in v1.4
// brief.

import {
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  renameSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";

export type TaskEvent = { type: string; data: unknown };

export type TaskKind = string;

/**
 * On-disk task status. One file per task at
 * <projectPath>/.organon/tasks/<task_id>.json.
 *
 * `payload` is opaque to the registry — each route stamps its own
 * scope-specific data (e.g. for generate-section: { manuscript_slug,
 * section_id }). The header panel uses `kind + scope` to build the
 * navigation link; never widens awareness of payload contents.
 */
export type TaskStatus = "running" | "done" | "failed" | "cancelled";

export type TaskRecord = {
  task_id: string;
  kind: TaskKind;
  scope: string;
  project_slug: string;
  status: TaskStatus;
  started_at: string; // ISO
  finished_at?: string | null;
  payload?: Record<string, unknown> | null;
  /** Last SSE event seen, useful for the panel preview. */
  last_event?: { type: string; at: string } | null;
};

export type BackgroundTask = {
  task_id: string;
  kind: TaskKind;
  project_slug: string;
  project_path: string;
  scope: string;
  events: TaskEvent[];
  subscribers: Set<(evt: TaskEvent) => void>;
  done: boolean;
  evictTimer: ReturnType<typeof setTimeout> | null;
  created_at: number;
};

export const MAX_BUFFER_EVENTS = 200;
export const EVICT_AFTER_MS = 10 * 60 * 1000; // 10 minutes (in-memory)

const tasks: Map<string, BackgroundTask> = new Map();

function newTaskId(): string {
  // Lightweight unique-ish id; collision-resistant enough for an
  // in-memory single-process registry.
  const ts = Date.now().toString(36);
  const rnd = Math.random().toString(36).slice(2, 10);
  return `task_${ts}_${rnd}`;
}

// ---------------------------------------------------------------------------
// On-disk surface (Phase 44)
// ---------------------------------------------------------------------------

export function tasksDir(projectPath: string): string {
  return path.join(projectPath, ".organon", "tasks");
}

export function taskFile(projectPath: string, task_id: string): string {
  return path.join(tasksDir(projectPath), `${task_id}.json`);
}

function ensureTasksDir(projectPath: string): void {
  const dir = tasksDir(projectPath);
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
}

function writeTaskFile(projectPath: string, record: TaskRecord): void {
  ensureTasksDir(projectPath);
  const target = taskFile(projectPath, record.task_id);
  const tmp = target + ".tmp";
  writeFileSync(tmp, JSON.stringify(record, null, 2));
  renameSync(tmp, target);
}

function readTaskFile(filepath: string): TaskRecord | null {
  try {
    const obj = JSON.parse(readFileSync(filepath, "utf8"));
    if (obj && typeof obj.task_id === "string") return obj as TaskRecord;
  } catch { /* ignore */ }
  return null;
}

// ---------------------------------------------------------------------------
// In-memory subscriber loop (carries over from Phase 36, with on-disk
// hooks for Phase 44).
// ---------------------------------------------------------------------------

function pushEvent(task: BackgroundTask, evt: TaskEvent): void {
  task.events.push(evt);
  while (task.events.length > MAX_BUFFER_EVENTS) {
    task.events.shift();
  }
  for (const sub of task.subscribers) {
    try { sub(evt); } catch { /* ignore subscriber failures */ }
  }
}

function scheduleEviction(task: BackgroundTask): void {
  if (task.evictTimer) {
    clearTimeout(task.evictTimer);
    task.evictTimer = null;
  }
  task.evictTimer = setTimeout(() => {
    if (task.subscribers.size === 0) {
      tasks.delete(task.task_id);
    }
  }, EVICT_AFTER_MS);
}

/**
 * Register a long-running runner. Returns the task_id.
 *
 * The registry's worker loop drains `source` to completion regardless
 * of whether anyone is subscribed; the runner outlives the request that
 * registered it. Buffered events (last MAX_BUFFER_EVENTS) replay to
 * late subscribers.
 *
 * Phase 44 — also writes a status file on disk at
 * <projectPath>/.organon/tasks/<task_id>.json with status = "running",
 * updates last_event on each event, and stamps status + finished_at on
 * completion. Atomic tmp+rename per write.
 */
export function registerTask(opts: {
  kind: TaskKind;
  project_slug: string;
  project_path: string;
  scope: string;
  source: AsyncIterable<TaskEvent>;
  payload?: Record<string, unknown> | null;
}): string {
  const task_id = newTaskId();
  const startedAtIso = new Date().toISOString();
  const task: BackgroundTask = {
    task_id,
    kind: opts.kind,
    project_slug: opts.project_slug,
    project_path: opts.project_path,
    scope: opts.scope,
    events: [],
    subscribers: new Set(),
    done: false,
    evictTimer: null,
    created_at: Date.now(),
  };
  tasks.set(task_id, task);

  // Phase 44 — initial on-disk write.
  const initial: TaskRecord = {
    task_id,
    kind: opts.kind,
    scope: opts.scope,
    project_slug: opts.project_slug,
    status: "running",
    started_at: startedAtIso,
    finished_at: null,
    payload: opts.payload ?? null,
    last_event: null,
  };
  try {
    writeTaskFile(opts.project_path, initial);
  } catch { /* on-disk failures must not block in-memory work */ }

  // Worker loop — drains the runner. Mirrors events to disk for the
  // header panel's "last event" preview.
  void (async () => {
    let lastErrorMessage: string | null = null;
    let lastDoneSuccess: boolean | null = null;
    try {
      for await (const evt of opts.source) {
        pushEvent(task, evt);
        // Stamp last_event only on meaningful types — avoid burning
        // disk write on every stdout chunk in long runs.
        if (evt.type !== "stdout" && evt.type !== "stderr") {
          try {
            const cur = readTaskFile(taskFile(opts.project_path, task_id));
            if (cur && cur.status === "running") {
              writeTaskFile(opts.project_path, {
                ...cur,
                last_event: { type: evt.type, at: new Date().toISOString() },
              });
            }
          } catch { /* ignore */ }
          if (evt.type === "done" && evt.data && typeof evt.data === "object") {
            const d = evt.data as Record<string, unknown>;
            if (typeof d.success === "boolean") lastDoneSuccess = d.success;
          }
          if (evt.type === "error" && evt.data && typeof evt.data === "object") {
            const d = evt.data as Record<string, unknown>;
            if (typeof d.message === "string") lastErrorMessage = d.message;
          }
        }
      }
    } catch (err) {
      lastErrorMessage = err instanceof Error ? err.message : String(err);
      pushEvent(task, {
        type: "error",
        data: { message: lastErrorMessage },
      });
    } finally {
      task.done = true;
      // Phase 44 — final on-disk update with status + finished_at.
      try {
        const cur = readTaskFile(taskFile(opts.project_path, task_id));
        if (cur) {
          const finalStatus: TaskStatus =
            lastErrorMessage != null ? "failed"
              : lastDoneSuccess === false ? "failed"
                : "done";
          writeTaskFile(opts.project_path, {
            ...cur,
            status: finalStatus,
            finished_at: new Date().toISOString(),
            last_event: { type: "task-completed", at: new Date().toISOString() },
          });
        }
      } catch { /* ignore */ }

      pushEvent(task, { type: "task-completed", data: { task_id } });
      // Schedule eviction if no live subscribers; if there are
      // subscribers, eviction is deferred until they all leave.
      if (task.subscribers.size === 0) {
        scheduleEviction(task);
      }
    }
  })();

  return task_id;
}

export function getTask(task_id: string): BackgroundTask | null {
  return tasks.get(task_id) ?? null;
}

/**
 * Attach a callback to the task. The callback fires once per buffered
 * event (replay), then once per live event until unsubscribed.
 *
 * Returns null on unknown task_id; otherwise returns an unsubscribe
 * function. The unsubscribe re-arms the eviction timer when the last
 * subscriber leaves AND the task is done.
 */
export function subscribeToTask(
  task_id: string,
  callback: (evt: TaskEvent) => void,
): (() => void) | null {
  const task = tasks.get(task_id);
  if (!task) return null;
  // Replay buffered events first.
  for (const evt of task.events) {
    try { callback(evt); } catch { /* ignore */ }
  }
  // If the task is already done, no live subscription needed.
  if (task.done) {
    // Cancel any pending eviction to give the late subscriber a chance
    // to read; re-schedule once they leave.
    if (task.evictTimer) {
      clearTimeout(task.evictTimer);
      task.evictTimer = null;
    }
    task.subscribers.add(callback);
    return () => {
      task.subscribers.delete(callback);
      if (task.subscribers.size === 0 && task.done) {
        scheduleEviction(task);
      }
    };
  }
  // Otherwise add to the live subscriber set.
  if (task.evictTimer) {
    clearTimeout(task.evictTimer);
    task.evictTimer = null;
  }
  task.subscribers.add(callback);
  return () => {
    task.subscribers.delete(callback);
    if (task.subscribers.size === 0 && task.done) {
      scheduleEviction(task);
    }
  };
}

/**
 * Phase 44 — listTasks reads the on-disk surface. Used by the
 * dashboard header tasks-panel; the in-memory map is irrelevant here
 * (a process restart wipes the subscriber loop but the status files
 * stay).
 *
 * Returns:
 *   running: TaskRecord[] — every task whose status is still "running"
 *                            on disk. After a restart these are
 *                            "orphans" — the worker that produced them
 *                            is gone, but the panel still shows them
 *                            so the user can mark them stale.
 *   recent : TaskRecord[] — last 20 completed tasks ordered by
 *                            finished_at descending.
 */
export function listTasks(projectPath: string): {
  running: TaskRecord[];
  recent: TaskRecord[];
} {
  const dir = tasksDir(projectPath);
  if (!existsSync(dir)) return { running: [], recent: [] };
  const entries: TaskRecord[] = [];
  for (const file of readdirSync(dir)) {
    if (!file.endsWith(".json") || file.endsWith(".tmp")) continue;
    const rec = readTaskFile(path.join(dir, file));
    if (rec) entries.push(rec);
  }
  const running = entries
    .filter((t) => t.status === "running")
    .sort((a, b) => (b.started_at ?? "").localeCompare(a.started_at ?? ""));
  const recent = entries
    .filter((t) => t.status !== "running")
    .sort((a, b) => (b.finished_at ?? "").localeCompare(a.finished_at ?? ""))
    .slice(0, 20);
  return { running, recent };
}

// Test-only helpers — not part of the public surface.
export function _resetRegistry(): void {
  for (const task of tasks.values()) {
    if (task.evictTimer) clearTimeout(task.evictTimer);
  }
  tasks.clear();
}

export function _internalsForTests() {
  return { tasks, MAX_BUFFER_EVENTS, EVICT_AFTER_MS };
}

// Re-export rmSync so the eviction module can share fs imports without
// double-importing in places that already import the registry.
export { rmSync };
