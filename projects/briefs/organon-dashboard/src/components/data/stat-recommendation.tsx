"use client";

import type { Recommendation } from "@/lib/data/stat-picker";
import { cn } from "@/lib/cn";

export type StatRecommendationProps = {
  recommendation: Recommendation;
  onRun: () => void;
  isRunning: boolean;
  disabled?: boolean;
};

const VERDICT_TONE: Record<string, string> = {
  pass: "text-good",
  warn: "text-text-dim",
  fail: "text-danger",
  unknown: "text-text-muted",
};

// Phase 12c (v1.0.1) — D-1: UNKNOWN was opaque; surface it as PENDING
// with a tooltip so the researcher knows it means "not yet evaluated"
// rather than "failed silently".
const VERDICT_LABEL: Record<string, string> = {
  pass: "pass",
  warn: "warn",
  fail: "fail",
  unknown: "pending",
};

const VERDICT_TOOLTIP: Record<string, string> = {
  unknown:
    "Status checked at run time. PENDING means the assumption hasn't been evaluated yet; it will resolve to PASS, WARN, or FAIL after the test runs.",
};

export function StatRecommendation({ recommendation, onRun, isRunning, disabled }: StatRecommendationProps) {
  const r = recommendation;
  return (
    <div className="border border-border-dim rounded bg-bg-elev px-4 py-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="mono text-[10px] uppercase tracking-wider text-text-muted">
            Rank {r.rank}
          </div>
          <div className="text-sm text-text mt-0.5">{r.test_label}</div>
          <div className="mono text-[11px] text-text-muted">{r.test_name}</div>
        </div>
        <button
          type="button"
          onClick={onRun}
          disabled={disabled || isRunning}
          className="text-xs mono uppercase tracking-wider px-3 py-1 border border-accent text-accent hover:bg-accent-faint rounded disabled:opacity-50"
        >
          {isRunning ? "Running…" : "Run"}
        </button>
      </div>
      <p className="text-sm text-text-dim mt-2 leading-snug">{r.reasoning}</p>
      {r.assumption_flags.length > 0 && (
        <ul className="mt-2 space-y-1">
          {r.assumption_flags.map((f) => (
            <li key={f.name} className="flex items-start gap-2 text-xs">
              <span
                className={cn("mono uppercase", VERDICT_TONE[f.verdict])}
                title={VERDICT_TOOLTIP[f.verdict] ?? undefined}
                data-verdict={f.verdict}
              >
                {VERDICT_LABEL[f.verdict] ?? f.verdict}
              </span>
              <span className="text-text-dim">{f.name}</span>
              {f.note && <span className="text-text-muted">— {f.note}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
