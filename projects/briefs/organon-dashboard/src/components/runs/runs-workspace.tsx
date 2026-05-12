"use client";

import { useCallback, useState } from "react";
import type { RunSummary } from "@/lib/runs";
import { cn } from "@/lib/cn";
import { RunDetailDrawer } from "./run-detail-drawer";

export type RunsWorkspaceProps = {
  project: string;
  initialRuns: RunSummary[];
};

const STATUS_TONE: Record<string, string> = {
  ok: "text-good",
  error: "text-danger",
  running: "text-accent",
};

function relTime(iso: string): string {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return iso;
  const diff = Date.now() - t;
  if (diff < 60_000) return "just now";
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return `${Math.floor(diff / 86_400_000)}d ago`;
}

export function RunsWorkspace({ project, initialRuns }: RunsWorkspaceProps) {
  const [runs, setRuns] = useState<RunSummary[]>(initialRuns);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    setBusy(true);
    try {
      const res = await fetch(`/api/runs?project=${encodeURIComponent(project)}&limit=200`);
      const json = await res.json();
      if (Array.isArray(json.runs)) setRuns(json.runs);
    } catch { /* keep last good */ }
    finally { setBusy(false); }
  }, [project]);

  return (
    <div className="px-6 py-5 max-w-[1300px]">
      <header className="mb-5 flex items-start justify-between">
        <div>
          <div className="mono text-[11px] uppercase tracking-[0.2em] text-text-muted">Runs</div>
          <h1 className="text-2xl text-text mt-1">{project}</h1>
          <p className="text-sm text-text-dim mt-1">
            Full run history. Click a row for prompt + stdout + stderr + linked artifacts.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void refresh()}
          disabled={busy}
          className="text-xs mono uppercase tracking-wider px-3 py-1 border border-border-dim text-text-dim hover:text-text rounded disabled:opacity-50"
        >
          {busy ? "Refreshing…" : "↻ refresh"}
        </button>
      </header>

      {runs.length === 0 ? (
        <div className="border border-dashed border-border-dim rounded px-8 py-16 text-center">
          <div className="mono text-[11px] uppercase tracking-[0.2em] text-text-muted">No runs yet</div>
          <div className="mt-2 text-sm text-text-dim">
            Fire a skill from any workspace and it'll show up here.
          </div>
        </div>
      ) : (
        <ul className="border border-border-dim rounded bg-bg-elev divide-y divide-border-dim">
          {runs.map((r) => (
            <li
              key={r.id}
              className="px-4 py-3 cursor-pointer hover:bg-bg-soft"
              onClick={() => setActiveRunId(r.id)}
            >
              <div className="flex items-start gap-3">
                <span className={cn("mono text-[10px] uppercase tracking-wider w-14 shrink-0", STATUS_TONE[r.status] ?? "text-text-muted")}>
                  {r.status}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="text-sm text-text truncate">
                    {r.skill ?? "no skill"} · {relTime(r.ts)}
                    {r.durationMs !== null && ` · ${(r.durationMs / 1000).toFixed(1)}s`}
                  </div>
                  <div className="mono text-[11px] text-text-muted truncate">{r.prompt.slice(0, 200)}</div>
                  {r.excerpt && (
                    <div className="mt-1 text-xs text-text-dim line-clamp-2">{r.excerpt}</div>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}

      <RunDetailDrawer
        project={project}
        runId={activeRunId}
        onClose={() => setActiveRunId(null)}
      />
    </div>
  );
}
