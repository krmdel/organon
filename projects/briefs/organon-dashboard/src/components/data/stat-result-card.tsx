"use client";

import { useCallback, useState } from "react";
import type { StatResultArtifact } from "@/lib/artifacts/types";
import { cn } from "@/lib/cn";

export type StatResultCardProps = {
  result: StatResultArtifact;
  /** Project slug used for the optional Interpret POST. Required for Interpret. */
  project?: string;
  onCiteInDraft?: () => void;
  /**
   * Phase 12a (v1.0.1) — D-7 soft archive. Parent owns the API call and
   * state mutation; this card just emits the intent. When omitted, the ×
   * button is hidden (e.g. if the surface is read-only).
   */
  onArchive?: (runId: string) => void;
  /** When true, render the unarchive (↺) button instead of × in the header. */
  isArchived?: boolean;
  onUnarchive?: (runId: string) => void;
  /**
   * Phase 12c (v1.0.1) — D-3 outcome-mismatch hint. When non-null AND
   * different from the result's own outcome, the card surfaces an inline
   * chip telling the researcher the result was for a different outcome
   * than the picker currently displays. null means "no picker context"
   * (read-only surfaces); the hint is suppressed.
   */
  currentPickerOutcome?: string | null;
};

function _resultOutcome(params: Record<string, unknown>): string | null {
  // The picker's mode-specific outcome maps to one of these keys.
  // First-non-null wins, matching the picker's emit order in
  // stat-test-picker.tsx (group → regression → contingency).
  const v = params.value_col ?? params.target_col ?? params.row_col;
  return typeof v === "string" && v.length > 0 ? v : null;
}

const VERDICT_TONE: Record<string, string> = {
  pass: "text-good",
  warn: "text-text-dim",
  fail: "text-danger",
};

function fmtP(p: number | null | undefined): string {
  if (p === null || p === undefined) return "—";
  if (p < 0.001) return "< 0.001";
  if (p < 0.01) return p.toExponential(1);
  return p.toFixed(3);
}

export function StatResultCard({
  result,
  project,
  onCiteInDraft,
  onArchive,
  isArchived,
  onUnarchive,
  currentPickerOutcome,
}: StatResultCardProps) {
  // D-3: surface a divergence chip when the result's outcome differs
  // from what the picker currently shows. Suppresses when the picker
  // hasn't told us what its outcome is (null) or the values match.
  const resultOutcome = _resultOutcome(result.params as Record<string, unknown>);
  const showOutcomeMismatch =
    !!currentPickerOutcome &&
    !!resultOutcome &&
    currentPickerOutcome !== resultOutcome;
  const [interpretation, setInterpretation] = useState<string>("");
  const [interpretBusy, setInterpretBusy] = useState(false);
  const [interpretError, setInterpretError] = useState<string | null>(null);

  const handleInterpret = useCallback(async () => {
    if (!project) {
      setInterpretError("Interpret requires the project slug.");
      return;
    }
    setInterpretBusy(true);
    setInterpretError(null);
    setInterpretation("");
    let buf = "";
    try {
      const res = await fetch("/api/data/interpret", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project, run_id: result.id }),
      });
      if (!res.ok || !res.body) {
        const detail = await res.text();
        throw new Error(`HTTP ${res.status}: ${detail.slice(0, 200)}`);
      }
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const events = buf.split("\n\n");
        buf = events.pop() ?? "";
        for (const evt of events) {
          const dataLine = evt.split("\n").find((l) => l.startsWith("data:"));
          if (!dataLine) continue;
          try {
            const data = JSON.parse(dataLine.slice(5).trim());
            if (typeof data.chunk === "string") {
              setInterpretation((prev) => prev + data.chunk);
            }
            if (data.message && evt.includes("event: error")) {
              setInterpretError(data.message);
            }
          } catch { /* ignore non-JSON */ }
        }
      }
    } catch (err) {
      setInterpretError(err instanceof Error ? err.message : String(err));
    } finally {
      setInterpretBusy(false);
    }
  }, [project, result.id]);

  return (
    <div
      className="border border-border-dim rounded bg-bg-elev px-4 py-3 group/result"
      data-archived={isArchived ? "true" : "false"}
    >
      {showOutcomeMismatch ? (
        <div
          className="mono text-[10px] text-text-dim mb-2"
          data-testid="outcome-mismatch-hint"
          data-result-outcome={resultOutcome ?? ""}
          data-picker-outcome={currentPickerOutcome ?? ""}
        >
          <span className="text-danger">⚠</span> result is for outcome <span className="text-text">{resultOutcome}</span>, picker shows <span className="text-text">{currentPickerOutcome}</span>
        </div>
      ) : null}
      <div className="flex items-start justify-between">
        <div>
          <div className="mono text-[10px] uppercase tracking-wider text-text-muted">
            Result · {result.id}
          </div>
          <div className="text-sm text-text mt-0.5">{result.test_label}</div>
        </div>
        <div className="flex gap-2 items-start">
          <button
            type="button"
            onClick={handleInterpret}
            disabled={interpretBusy || !project}
            title={
              project
                ? "Run sci-data-analysis to write a plain-English narrative for this result"
                : "Interpret requires the project slug"
            }
            className="text-xs mono uppercase tracking-wider px-3 py-1 border border-border-dim text-text-dim hover:border-accent hover:text-accent rounded disabled:opacity-50"
          >
            {interpretBusy ? "Interpreting…" : "Interpret"}
          </button>
          <button
            type="button"
            disabled
            title="Phase 5 — link a result into a manuscript section"
            className="text-xs mono uppercase tracking-wider px-3 py-1 border border-border-dim text-text-muted rounded opacity-50 cursor-not-allowed"
            onClick={onCiteInDraft}
          >
            Cite in draft
          </button>
          {isArchived && onUnarchive ? (
            <button
              type="button"
              onClick={() => onUnarchive(result.id)}
              title="Restore this archived result"
              data-action="unarchive-result"
              className="text-xs mono uppercase tracking-wider px-2 py-1 border border-border-dim text-text-dim hover:border-accent hover:text-accent rounded"
              aria-label="Restore result"
            >
              ↺
            </button>
          ) : null}
          {!isArchived && onArchive ? (
            <button
              type="button"
              onClick={() => onArchive(result.id)}
              title="Archive this result (keeps the file on disk; toggle 'Show archived' to restore)"
              data-action="archive-result"
              className="text-text-muted hover:text-danger transition px-1.5 py-1 rounded opacity-40 group-hover/result:opacity-100"
              aria-label="Archive result"
            >
              <span className="mono text-[14px] leading-none">×</span>
            </button>
          ) : null}
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
        {result.test_statistic !== null && result.test_statistic !== undefined && (
          <div>
            <div className="mono text-[10px] uppercase text-text-muted">statistic</div>
            <div className="text-text">{Number(result.test_statistic).toFixed(3)}</div>
          </div>
        )}
        <div>
          <div className="mono text-[10px] uppercase text-text-muted">p-value</div>
          <div className="text-text">{fmtP(result.p_value)}</div>
        </div>
        {result.effect_size && (
          <div>
            <div className="mono text-[10px] uppercase text-text-muted">
              effect size · {result.effect_size.name}
            </div>
            <div className="text-text">
              {Number(result.effect_size.value).toFixed(3)}
              {result.effect_size.ci_low !== undefined && result.effect_size.ci_high !== undefined && (
                <span className="text-text-muted mono text-[11px]">
                  {" "}
                  · CI [{Number(result.effect_size.ci_low).toFixed(2)},{" "}
                  {Number(result.effect_size.ci_high).toFixed(2)}]
                </span>
              )}
            </div>
          </div>
        )}
        <div>
          <div className="mono text-[10px] uppercase text-text-muted">n</div>
          <div className="text-text">{result.n}</div>
        </div>
      </div>

      {result.assumption_checks && result.assumption_checks.length > 0 && (
        <div className="mt-3">
          <div className="mono text-[10px] uppercase text-text-muted mb-1">
            Assumption checks
          </div>
          <ul className="space-y-0.5">
            {result.assumption_checks.map((a) => (
              <li key={a.name} className="flex items-start gap-2 text-xs">
                <span className={cn("mono uppercase", VERDICT_TONE[a.verdict] ?? "text-text-muted")}>
                  {a.verdict}
                </span>
                <span className="text-text-dim">{a.name}</span>
                {a.p_value !== undefined && (
                  <span className="text-text-muted mono">p={fmtP(a.p_value)}</span>
                )}
                {a.note && <span className="text-text-muted">— {a.note}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {result.interpretation && (
        <p className="mt-3 text-sm text-text-dim leading-snug">{result.interpretation}</p>
      )}

      {(interpretation || interpretError) && (
        <div className="mt-3 border-t border-border-dim pt-3">
          <div className="mono text-[10px] uppercase tracking-wider text-text-muted mb-1">
            AI interpretation
          </div>
          {interpretError ? (
            <p className="text-xs text-danger mono">{interpretError}</p>
          ) : (
            <p className="text-sm text-text-dim leading-snug whitespace-pre-wrap">
              {interpretation}
              {interpretBusy && <span className="text-text-muted">▍</span>}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
