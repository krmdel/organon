"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";

/**
 * Phase 44 (v1.5) — F7 dashboard header tasks-panel.
 *
 * Bell icon in the topbar with a count badge for in-flight tasks. Click
 * opens a popover with two sections: "Running (N)" + "Recent (last 20)".
 * Each item is clickable → navigates to the originating page (e.g.
 * /draft/<slug> for a generate-section task; /hypothesis?id=<hyp_id>
 * for a reconcile task).
 *
 * Decision (brief §8.3):
 * - Pop-over, NOT full page (quick visibility, click-through to the
 *   originating page).
 * - "Recent" truncates at 20 — the route already enforces this.
 * - No retry-from-panel in v1.5.
 */

type TaskRecord = {
  task_id: string;
  kind: string;
  scope: string;
  project_slug: string;
  status: "running" | "done" | "failed" | "cancelled";
  started_at: string;
  finished_at?: string | null;
  payload?: Record<string, unknown> | null;
  last_event?: { type: string; at: string } | null;
};

type TasksResponse = {
  running: TaskRecord[];
  recent: TaskRecord[];
};

export type TasksPanelProps = {
  /** Active project slug — sent as ?project=<slug> to GET /api/tasks. */
  project: string;
};

const POLL_MS = 5_000;

function navigationFor(task: TaskRecord, project: string): string | null {
  // Build a destination link from kind + scope. Each route's payload
  // contract is documented in the runner-generator side-effects.
  const q = `project=${encodeURIComponent(project)}`;
  switch (task.kind) {
    case "reconcile":
    case "retry-persona":
    case "council-generate":
      return `/hypothesis?${q}`;
    case "generate-section":
    case "generate-title":
    case "section-action":
    case "edit-with-chat": {
      const slug =
        typeof task.payload?.manuscript_slug === "string"
          ? task.payload.manuscript_slug
          : task.scope.split(":")[0];
      return slug
        ? `/draft/${encodeURIComponent(slug)}?${q}`
        : `/draft?${q}`;
    }
    case "figure-legend":
    case "figure-lock":
    case "figure-generate":
      return `/figures?${q}`;
    case "data-chat":
    case "data-interpret":
      return `/data?${q}`;
    case "tools-run":
    case "execute":
      return `/tools?${q}`;
    default:
      return null;
  }
}

function statusBadgeClass(status: TaskRecord["status"]): string {
  if (status === "running") return "border-accent text-accent";
  if (status === "done") return "border-good text-good";
  if (status === "failed") return "border-danger text-danger";
  return "border-border-dim text-text-muted";
}

function relTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const ms = Date.now() - new Date(iso).getTime();
  if (!Number.isFinite(ms)) return "";
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  return `${h}h ago`;
}

export function TasksPanel({ project }: TasksPanelProps) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<TasksResponse>({ running: [], recent: [] });
  const popoverRef = useRef<HTMLDivElement | null>(null);

  const fetchTasks = useCallback(async () => {
    try {
      const res = await fetch(
        `/api/tasks?project=${encodeURIComponent(project)}`,
        { cache: "no-store" },
      );
      if (!res.ok) return;
      const json = (await res.json()) as TasksResponse;
      setData(json);
    } catch { /* keep last good */ }
  }, [project]);

  // Initial fetch + 5s poll while mounted.
  useEffect(() => {
    void fetchTasks();
    const id = setInterval(() => void fetchTasks(), POLL_MS);
    return () => clearInterval(id);
  }, [fetchTasks]);

  // Click-outside dismissal.
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const runningCount = data.running.length;

  return (
    <div className="relative" ref={popoverRef}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        data-tasks-panel-trigger
        className="relative mono text-[10px] uppercase tracking-wider px-2 py-1 border border-border-dim rounded text-text-muted hover:text-text hover:border-text-dim"
        title={`${runningCount} task${runningCount === 1 ? "" : "s"} running`}
      >
        <span className="mr-1">tasks</span>
        <span data-tasks-running-count={runningCount}>{runningCount}</span>
      </button>
      {open && (
        <div
          className="absolute right-0 mt-2 w-80 max-h-[28rem] overflow-y-auto rounded border border-border bg-bg-elev shadow-lg z-50"
          data-tasks-panel-popover
        >
          <div className="px-3 py-2 border-b border-border-dim mono text-[10px] uppercase tracking-wider text-text-muted">
            Running ({runningCount})
          </div>
          {runningCount === 0 ? (
            <div className="px-3 py-3 text-xs text-text-muted">
              Nothing in flight.
            </div>
          ) : (
            <ul className="divide-y divide-border-dim">
              {data.running.map((t) => (
                <TaskRow key={t.task_id} task={t} project={project} />
              ))}
            </ul>
          )}
          <div className="px-3 py-2 border-t border-b border-border-dim mono text-[10px] uppercase tracking-wider text-text-muted">
            Recent (last {Math.min(data.recent.length, 20)})
          </div>
          {data.recent.length === 0 ? (
            <div className="px-3 py-3 text-xs text-text-muted">
              No recent tasks.
            </div>
          ) : (
            <ul className="divide-y divide-border-dim">
              {data.recent.map((t) => (
                <TaskRow key={t.task_id} task={t} project={project} />
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

function TaskRow({ task, project }: { task: TaskRecord; project: string }) {
  const dest = navigationFor(task, project);
  const stamp = task.finished_at ?? task.started_at;
  const inner = (
    <div className="px-3 py-2 hover:bg-bg-soft text-xs flex items-start gap-2">
      <span
        className={`mono text-[9px] uppercase tracking-wider px-1.5 py-0.5 border rounded ${statusBadgeClass(task.status)}`}
      >
        {task.status}
      </span>
      <div className="flex-1 min-w-0">
        <div className="text-text truncate">{task.kind}</div>
        <div className="mono text-[10px] text-text-muted truncate">
          {task.scope || task.task_id} · {relTime(stamp)}
        </div>
      </div>
    </div>
  );
  return (
    <li>
      {dest ? (
        <Link href={dest} prefetch={false} className="block">
          {inner}
        </Link>
      ) : (
        <div className="block">{inner}</div>
      )}
    </li>
  );
}
