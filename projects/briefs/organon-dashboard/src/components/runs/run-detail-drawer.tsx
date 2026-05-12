"use client";

import { useEffect, useState } from "react";
import type { RunDetail } from "@/lib/runs";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/cn";

export type RunDetailDrawerProps = {
  project: string;
  runId: string | null;
  onClose: () => void;
};

export function RunDetailDrawer({ project, runId, onClose }: RunDetailDrawerProps) {
  const router = useRouter();
  const [run, setRun] = useState<RunDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) { setRun(null); return; }
    let cancelled = false;
    setLoading(true);
    setError(null);
    void (async () => {
      try {
        const res = await fetch(`/api/runs/${encodeURIComponent(runId)}?project=${encodeURIComponent(project)}`);
        const json = await res.json();
        if (cancelled) return;
        if (!res.ok) throw new Error(json?.error ?? `HTTP ${res.status}`);
        setRun(json.run as RunDetail);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [project, runId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!runId) return null;

  return (
    <div
      className="fixed inset-0 z-40 flex justify-end bg-black/60"
      onClick={onClose}
    >
      <aside
        className="w-full max-w-2xl h-full bg-bg-elev border-l border-border overflow-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="px-5 py-3 border-b border-border-dim flex items-start justify-between">
          <div className="min-w-0 flex-1">
            <div className="mono text-[10px] uppercase tracking-[0.2em] text-text-muted">Run · {runId}</div>
            <div className="text-sm text-text mt-0.5 truncate">
              {run?.skill ?? "no skill"} · exit {run?.exitCode ?? "?"} · {run?.durationMs ?? "?"}ms
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="mono text-[10px] uppercase tracking-wider text-text-muted hover:text-text"
          >
            close (esc)
          </button>
        </header>

        {loading && <div className="p-5 mono text-xs text-text-muted">Loading…</div>}
        {error && <div className="p-5 mono text-xs text-danger">⚠ {error}</div>}
        {run && (
          <div className="p-5 space-y-4">
            <section>
              <div className="mono text-[10px] uppercase tracking-wider text-text-muted">Prompt</div>
              <pre className="mt-1 mono text-[12px] text-text-dim bg-bg border border-border-dim rounded p-3 whitespace-pre-wrap max-h-48 overflow-auto">
                {run.prompt}
              </pre>
            </section>
            {run.linkedArtifacts.length > 0 && (
              <section>
                <div className="mono text-[10px] uppercase tracking-wider text-text-muted">
                  Linked artifacts ({run.linkedArtifacts.length})
                </div>
                <ul className="mt-1 space-y-1">
                  {run.linkedArtifacts.map((a, i) => (
                    <li
                      key={i}
                      className="mono text-xs text-text-dim cursor-pointer hover:text-text"
                      onClick={() => {
                        if (!a.id) return;
                        if (a.type === "paper")
                          router.push(`/lit?project=${encodeURIComponent(project)}&paper=${encodeURIComponent(a.id)}`);
                        else if (a.type === "hypothesis")
                          router.push(`/hypothesis?project=${encodeURIComponent(project)}&hyp=${encodeURIComponent(a.id)}`);
                        else if (a.type === "figure")
                          router.push(`/figures?project=${encodeURIComponent(project)}&fig=${encodeURIComponent(a.id)}`);
                      }}
                    >
                      <span className="text-good">{a.type}</span>{a.id ? ` · ${a.id}` : ""}
                    </li>
                  ))}
                </ul>
              </section>
            )}
            <section>
              <div className="mono text-[10px] uppercase tracking-wider text-text-muted">stdout</div>
              <pre className={cn("mt-1 mono text-[12px] bg-bg border border-border-dim rounded p-3 whitespace-pre-wrap max-h-96 overflow-auto", run.stdout ? "text-text" : "text-text-muted italic")}>
                {run.stdout || "(empty)"}
              </pre>
            </section>
            {run.stderr && (
              <section>
                <div className="mono text-[10px] uppercase tracking-wider text-danger">stderr</div>
                <pre className="mt-1 mono text-[12px] text-danger bg-bg border border-danger/30 rounded p-3 whitespace-pre-wrap max-h-48 overflow-auto">
                  {run.stderr}
                </pre>
              </section>
            )}
          </div>
        )}
      </aside>
    </div>
  );
}
