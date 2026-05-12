// Phase 36 (v1.4) — client-side task re-attach helpers.
//
// Each long-running route persists a per-(kind, project, scope) row in
// localStorage so the workspace can detect "there's an in-flight task
// for this exact thing — re-attach instead of starting a fresh run."
//
// SSR-safe: every accessor short-circuits when window/localStorage is
// undefined (server-side render, tests, private mode, etc.).

export type TaskKind = "reconcile" | "retry-persona";

export type ActiveTask = {
  task_id: string;
  started_at: number;
};

function storage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function key(project: string, kind: TaskKind, scope: string): string {
  return `organon:task:${kind}:${project}:${scope}`;
}

export function readActiveTask(
  project: string,
  kind: TaskKind,
  scope: string,
): string | null {
  const s = storage();
  if (!s) return null;
  try {
    const raw = s.getItem(key(project, kind, scope));
    if (!raw) return null;
    const obj = JSON.parse(raw) as Partial<ActiveTask>;
    if (typeof obj?.task_id !== "string") return null;
    return obj.task_id;
  } catch {
    return null;
  }
}

export function writeActiveTask(
  project: string,
  kind: TaskKind,
  scope: string,
  task_id: string,
): void {
  const s = storage();
  if (!s) return;
  try {
    const payload: ActiveTask = { task_id, started_at: Date.now() };
    s.setItem(key(project, kind, scope), JSON.stringify(payload));
  } catch {
    // quota / private-mode — silently degrade
  }
}

export function clearActiveTask(
  project: string,
  kind: TaskKind,
  scope: string,
): void {
  const s = storage();
  if (!s) return;
  try {
    s.removeItem(key(project, kind, scope));
  } catch { /* ignore */ }
}

// ---------------------------------------------------------------------------
// Phase 64 (v2.2) — M3: generic SSE re-attach helper.
//
// Connects to /api/tasks/{task_id}/stream (Phase 36 substrate) and pumps
// each parsed event into a caller-supplied handler. Returns a teardown
// function that aborts the underlying fetch. SSR-safe: returns a no-op
// teardown when fetch / window are unavailable.
// ---------------------------------------------------------------------------

export type TaskStreamEvent =
  | { type: "stdout"; chunk?: string }
  | { type: "artifact"; artifact: unknown }
  | { type: "task-started"; task_id: string }
  | { type: "task-attached"; task_id: string }
  | { type: "task-completed" }
  | { type: "done"; success?: boolean; reason?: string; message?: string }
  | { type: "error"; message: string };

export function subscribeToTask(
  task_id: string,
  handler: (evt: TaskStreamEvent) => void,
): () => void {
  if (typeof window === "undefined" || typeof fetch === "undefined") {
    return () => {};
  }
  const ctrl = new AbortController();
  void (async () => {
    try {
      const res = await fetch(
        `/api/tasks/${encodeURIComponent(task_id)}/stream`,
        { signal: ctrl.signal },
      );
      if (!res.ok || !res.body) {
        handler({ type: "error", message: `task stream HTTP ${res.status}` });
        return;
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        if (ctrl.signal.aborted) break;
        buffer += decoder.decode(value, { stream: true });
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() ?? "";
        for (const block of blocks) {
          if (!block.trim()) continue;
          const lines = block.split("\n");
          const eventLine = lines.find((l) => l.startsWith("event: "));
          const dataLine = lines.find((l) => l.startsWith("data: "));
          if (!dataLine) continue;
          const eventName = eventLine ? eventLine.slice(7).trim() : "message";
          let data: Record<string, unknown> = {};
          try {
            data = JSON.parse(dataLine.slice(6)) as Record<string, unknown>;
          } catch {
            continue;
          }
          if (eventName === "artifact") {
            handler({ type: "artifact", artifact: (data as { artifact?: unknown }).artifact });
          } else if (eventName === "done") {
            handler({
              type: "done",
              success: (data as { success?: boolean }).success,
              reason: (data as { reason?: string }).reason,
              message: (data as { message?: string }).message,
            });
          } else if (eventName === "error") {
            handler({
              type: "error",
              message:
                typeof (data as { message?: string }).message === "string"
                  ? ((data as { message?: string }).message as string)
                  : "task error",
            });
          } else if (eventName === "stdout") {
            handler({
              type: "stdout",
              chunk:
                typeof (data as { chunk?: string }).chunk === "string"
                  ? (data as { chunk?: string }).chunk
                  : undefined,
            });
          } else if (eventName === "task-started" || eventName === "task-attached") {
            const tid = typeof (data as { task_id?: string }).task_id === "string"
              ? ((data as { task_id?: string }).task_id as string)
              : task_id;
            handler({ type: eventName as "task-started" | "task-attached", task_id: tid });
          } else if (eventName === "task-completed") {
            handler({ type: "task-completed" });
          }
        }
      }
    } catch (err) {
      if (!ctrl.signal.aborted) {
        handler({
          type: "error",
          message: err instanceof Error ? err.message : String(err),
        });
      }
    }
  })();
  return () => ctrl.abort();
}
