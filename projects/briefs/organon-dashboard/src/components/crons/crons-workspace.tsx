"use client";

import { useCallback, useState } from "react";
import type { CronJob } from "@/lib/crons/reader";
import { CronRow } from "./cron-row";

export type CronsWorkspaceProps = {
  initialJobs: CronJob[];
};

export function CronsWorkspace({ initialJobs }: CronsWorkspaceProps) {
  const [jobs, setJobs] = useState<CronJob[]>(initialJobs);
  const [busy, setBusy] = useState(false);
  const refresh = useCallback(async () => {
    setBusy(true);
    try {
      const res = await fetch("/api/crons");
      const json = await res.json();
      if (Array.isArray(json.jobs)) setJobs(json.jobs);
    } catch { /* keep last good */ }
    finally { setBusy(false); }
  }, []);

  const active = jobs.filter((j) => j.active).length;
  const failing = jobs.filter((j) => (j.status?.fail_count ?? 0) > 0).length;

  return (
    <div className="px-6 py-5 max-w-[1100px]">
      <header className="mb-5 flex items-start justify-between">
        <div>
          <div className="mono text-[11px] uppercase tracking-[0.2em] text-text-muted">Crons</div>
          <h1 className="text-2xl text-text mt-1">Scheduled jobs</h1>
          <p className="text-sm text-text-dim mt-1">
            Read-only view of <code className="mono text-text-dim">cron/jobs/*.md</code> + per-job status from{" "}
            <code className="mono text-text-dim">cron/status/*.json</code>. Enable / disable / run-now lands in v1.0.
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

      <div className="mb-3 mono text-[11px] uppercase tracking-[0.2em] text-text-muted flex gap-4">
        <span>{jobs.length} total</span>
        <span className="text-good">{active} active</span>
        {failing > 0 && <span className="text-danger">{failing} failing</span>}
      </div>

      {jobs.length === 0 ? (
        <div className="border border-dashed border-border-dim rounded px-8 py-16 text-center">
          <div className="mono text-[11px] uppercase tracking-[0.2em] text-text-muted">No cron jobs configured</div>
          <div className="mt-2 text-sm text-text-dim">
            Add markdown job files to <code className="mono">cron/jobs/</code> and they'll appear here.
          </div>
        </div>
      ) : (
        <ul className="border border-border-dim rounded bg-bg-elev">
          {jobs.map((j) => <CronRow key={j.id} job={j} />)}
        </ul>
      )}
    </div>
  );
}
