"use client";

import type { UsageReport } from "@/lib/usage-types";
import { UsageCharts } from "./usage-charts";

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}
function fmtDollars(c: number): string {
  return `$${(c / 100).toFixed(2)}`;
}

export function UsageWorkspace({ report }: { report: UsageReport }) {
  return (
    <div className="px-6 py-5 max-w-[1100px]">
      <header className="mb-5">
        <div className="mono text-[11px] uppercase tracking-[0.2em] text-text-muted">Usage</div>
        <h1 className="text-2xl text-text mt-1">Token + cost report</h1>
        <p className="text-sm text-text-dim mt-1">
          Computed from <code className="mono">~/.claude/projects/&lt;encoded-cwd&gt;/*.jsonl</code> session logs.
          Last updated {new Date(report.computedAt).toLocaleString()}.
        </p>
      </header>

      <div className="grid grid-cols-3 gap-3 mb-6">
        <Stat label="5-hour window" tokens={report.fiveHour.totalTokens} cost={report.fiveHour.cost} sessions={report.fiveHour.sessions} />
        <Stat label="Today" tokens={report.daily.totalTokens} cost={report.daily.cost} sessions={report.daily.sessions} />
        <Stat label="This week" tokens={report.weekly.totalTokens} cost={report.weekly.cost} sessions={report.weekly.sessions} />
      </div>

      <UsageCharts report={report} />

      <section className="mt-6 border border-border-dim rounded bg-bg-elev p-4">
        <div className="mono text-[10px] uppercase tracking-[0.2em] text-text-muted mb-2">
          Weekly split · Sonnet vs Opus
        </div>
        <div className="grid grid-cols-2 gap-3 text-sm text-text-dim">
          <div>
            <div className="mono text-[10px] text-text-muted">Sonnet</div>
            <div>{fmt(report.weeklySonnet.totalTokens)} tokens · {fmtDollars(report.weeklySonnet.cost)}</div>
          </div>
          <div>
            <div className="mono text-[10px] text-text-muted">Opus</div>
            <div>{fmt(report.weeklyOpus.totalTokens)} tokens · {fmtDollars(report.weeklyOpus.cost)}</div>
          </div>
        </div>
      </section>
    </div>
  );
}

function Stat(props: { label: string; tokens: number; cost: number; sessions: number }) {
  return (
    <div className="border border-border-dim rounded bg-bg-elev p-4">
      <div className="mono text-[10px] uppercase tracking-[0.2em] text-text-muted">{props.label}</div>
      <div className="mt-1 text-xl text-text">{fmt(props.tokens)}</div>
      <div className="mono text-[11px] text-text-muted mt-0.5">
        {fmtDollars(props.cost)} · {props.sessions} session{props.sessions === 1 ? "" : "s"}
      </div>
    </div>
  );
}
