"use client";

import type { CronJob } from "@/lib/crons/reader";
import { CronStatusPill } from "./cron-status-pill";

function relTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return iso;
  const diff = Date.now() - t;
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function CronRow({ job }: { job: CronJob }) {
  return (
    <li className="px-4 py-3 border-b border-border-dim last:border-b-0">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-sm text-text">{job.name}</span>
            <CronStatusPill status={job.status} active={job.active} />
            {job.launch_agent && (
              <span className="mono text-[10px] uppercase tracking-wider px-1.5 py-0.5 border border-border-dim text-text-muted rounded" title={job.launch_agent}>
                LaunchAgent
              </span>
            )}
          </div>
          <div className="mono text-[11px] text-text-muted mt-0.5">
            {job.schedule ?? "(no schedule)"} · last run {relTime(job.status?.last_run)}
            {job.status?.fail_count ? ` · ${job.status.fail_count} fail(s)` : ""}
          </div>
          {job.prompt_excerpt && (
            <div className="mt-1 text-xs text-text-dim line-clamp-2">{job.prompt_excerpt}</div>
          )}
          {job.status?.last_log_excerpt && (
            <pre className="mono text-[11px] text-text-muted bg-bg-soft border border-border-dim rounded p-2 mt-1 overflow-x-auto whitespace-pre-wrap">
              {job.status.last_log_excerpt.split("\n").slice(-4).join("\n")}
            </pre>
          )}
        </div>
      </div>
    </li>
  );
}
