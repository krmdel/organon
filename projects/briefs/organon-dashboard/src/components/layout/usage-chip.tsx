"use client";

import type { ClaudePlanUsage, UsageReport } from "@/lib/usage-types";
import { formatTokens } from "@/lib/usage-types";

// Phase 66 (v2.2) — M5: usage chip redesign.
//
// Drops the misleading per-project $X.XX figure. Sources daily + weekly
// metrics in priority order:
//   A. plan-usage cache (Claude Code's local state, when present)
//   C. local Claude Code spawn token totals from computeUsageReport
//
// The tooltip is the honesty mechanism: when the chip falls back to
// path C (no plan cache), it explicitly explains it's measuring local
// spawn activity for THIS project, not your plan usage.

export type UsageChipProps = {
  plan: ClaudePlanUsage | null;
  report: UsageReport | null;
};

function pct(used: number, limit: number): number {
  if (!Number.isFinite(limit) || limit <= 0) return 0;
  return Math.min(100, Math.max(0, Math.round((used / limit) * 100)));
}

function resetIn(iso: string): string {
  const ms = new Date(iso).getTime() - Date.now();
  if (!Number.isFinite(ms) || ms <= 0) return "any moment";
  const hours = Math.floor(ms / 3_600_000);
  if (hours < 1) {
    const mins = Math.max(1, Math.floor(ms / 60_000));
    return `${mins}m`;
  }
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  return `${days}d`;
}

function dayName(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString([], { weekday: "short" });
}

export function UsageChip({ plan, report }: UsageChipProps) {
  // Path A — plan-usage cache landed.
  if (plan !== null) {
    const dailyPct = pct(plan.daily.used, plan.daily.limit);
    const weeklyPct = pct(plan.weekly.used, plan.weekly.limit);
    return (
      <div
        data-usage-chip="plan"
        title="Claude Code plan usage from your local state file"
        className="hidden md:flex items-center gap-3 text-xs text-text-muted mono"
      >
        <span>
          daily {dailyPct}% &middot; resets in {resetIn(plan.daily.resetAt)}
        </span>
        <span>
          weekly {weeklyPct}% &middot; resets {dayName(plan.weekly.resetAt)}
        </span>
      </div>
    );
  }

  // Path C — local-token rate fallback. No plan cache surfaced; show the
  // honest local-activity meter from the existing computeUsageReport
  // pipeline.
  if (!report) return null;
  const dailyTok = report.daily.totalTokens;
  const weeklyTok = report.weekly.totalTokens;
  return (
    <div
      data-usage-chip="local"
      title="Local Claude Code spawn activity for this project. For plan usage, run /usage in your CLI."
      className="hidden md:flex items-center gap-3 text-xs text-text-muted mono"
    >
      <span>daily {formatTokens(dailyTok)} tok</span>
      <span>weekly {formatTokens(weeklyTok)} tok</span>
    </div>
  );
}
