"use client";

import { useState } from "react";
import type { FigureArtifact, LegendHistoryEntry } from "@/lib/artifacts/types";

// Phase 19 (v1.1+) — F-5 detailed-legend card.
//
// Renders the existing detailed_legend (or empty state). Offers
// Generate / Regenerate / Refine-with-prompt affordances, all routed
// through the workspace's `onGenerateLegend` callback so the SSE +
// streaming state stays parent-owned (Phase 10 pattern).
//
// Mounted only when the active figure is locked — see
// figures-workspace.tsx. An unlocked figure could mutate via a future
// edit, so the legend would invalidate immediately.
//
// Phase 24 (v1.2) — F-5+ legend history strip. Renders
// `figure.legend_history` newest-first; clicking an older version
// fires `onRevertLegend(version)` so the workspace can drive the
// revert call. Initial Generate (version 1) is filtered out at
// render-time per brief — too noisy.

export type LegendCardProps = {
  figure: FigureArtifact;
  onGenerateLegend: (opts?: { refine_prompt?: string }) => Promise<void> | void;
  /**
   * Phase 24 — revert the active legend to the named history entry's
   * text. Workspace owns the fetch + state pump.
   */
  onRevertLegend?: (version: number) => Promise<void> | void;
  busy?: boolean;
  // Streaming text the workspace pipes back during the active SSE.
  // When set, the card surfaces it instead of the persisted legend so
  // the user sees the in-flight result.
  streamingLegend?: string | null;
};

export function LegendCard({
  figure,
  onGenerateLegend,
  onRevertLegend,
  busy,
  streamingLegend,
}: LegendCardProps) {
  const [showRefine, setShowRefine] = useState(false);
  const [refinePrompt, setRefinePrompt] = useState("");

  const persistedLegend = figure.detailed_legend ?? null;
  const display = streamingLegend ?? persistedLegend;
  const hasLegend = !!persistedLegend;

  // Phase 24: legend_history strip. Backfill `[]` for legacy figures.
  // Surface from version ≥ 2 only — the initial Generate is too noisy
  // to chip out per brief §6.3.
  const history: LegendHistoryEntry[] = (figure.legend_history ?? []).filter(
    (e) => e.version >= 2,
  );
  // Newest-first ordering: sort ascending then reverse so the chip
  // strip reads v(latest) ← v(prev) ← … in left-to-right order.
  const newestFirst = [...history].sort((a, b) => a.version - b.version).reverse();

  return (
    <div
      data-legend-card
      data-fig-id={figure.id}
      className="border border-border-dim rounded bg-bg-elev px-4 py-3"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1">
          <div className="mono text-[10px] uppercase tracking-wider text-text-muted">
            Detailed legend · v{figure.version}
          </div>
          {display ? (
            <div className="mt-2 text-sm text-text whitespace-pre-wrap leading-relaxed">
              {display}
            </div>
          ) : (
            <div className="mt-2 text-sm text-text-muted italic">
              Not generated yet. The detailed legend expands the one-line caption into a
              multi-paragraph description suitable for figure-legend slots in a manuscript.
            </div>
          )}
        </div>
        <div className="flex flex-col gap-1.5 shrink-0">
          {!hasLegend ? (
            <button
              type="button"
              data-action="generate-legend"
              onClick={() => onGenerateLegend()}
              disabled={busy}
              className="text-xs mono uppercase tracking-wider px-3 py-1 border border-accent text-accent hover:bg-accent-faint rounded disabled:opacity-50"
            >
              {busy ? "Generating…" : "Generate"}
            </button>
          ) : (
            <button
              type="button"
              data-action="regenerate-legend"
              onClick={() => onGenerateLegend()}
              disabled={busy}
              className="text-xs mono uppercase tracking-wider px-3 py-1 border border-border-dim text-text-dim hover:text-text rounded disabled:opacity-50"
            >
              {busy ? "Regenerating…" : "Regenerate"}
            </button>
          )}
          <button
            type="button"
            data-action="toggle-refine-legend"
            onClick={() => setShowRefine((v) => !v)}
            disabled={busy}
            className="text-[10px] mono uppercase tracking-wider px-2 py-0.5 text-text-muted hover:text-text rounded"
          >
            {showRefine ? "Cancel refine" : "Refine…"}
          </button>
        </div>
      </div>
      {showRefine && (
        <div className="mt-3 border-t border-border-dim pt-3">
          <label className="mono text-[10px] uppercase tracking-wider text-text-muted">
            Steering for the refine pass
          </label>
          <textarea
            data-refine-prompt
            value={refinePrompt}
            onChange={(e) => setRefinePrompt(e.target.value)}
            rows={3}
            placeholder="e.g. emphasize the cohort-split rationale; mention the n=42 sample size…"
            className="mt-1 w-full bg-bg-soft border border-border-dim rounded text-sm px-2 py-1 text-text"
          />
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              data-action="refine-legend"
              onClick={async () => {
                const prompt = refinePrompt.trim();
                if (!prompt) return;
                await onGenerateLegend({ refine_prompt: prompt });
                setShowRefine(false);
              }}
              disabled={busy || !refinePrompt.trim()}
              className="text-xs mono uppercase tracking-wider px-3 py-1 border border-accent text-accent hover:bg-accent-faint rounded disabled:opacity-50"
            >
              {busy ? "Refining…" : "Refine"}
            </button>
          </div>
        </div>
      )}
      {newestFirst.length > 0 && (
        <div
          data-legend-history
          className="mt-3 border-t border-border-dim pt-3"
        >
          <div className="mono text-[10px] uppercase tracking-wider text-text-muted mb-1.5">
            Earlier versions
          </div>
          <ul className="flex flex-wrap gap-1.5">
            {newestFirst.map((entry) => (
              <li
                key={entry.version}
                data-legend-history-entry
                data-legend-version={entry.version}
                title={
                  entry.refine_prompt
                    ? `v${entry.version} · ${entry.refine_prompt}`
                    : `v${entry.version}`
                }
              >
                <button
                  type="button"
                  data-action="revert-legend"
                  data-legend-version={entry.version}
                  disabled={busy || !onRevertLegend}
                  onClick={() => onRevertLegend?.(entry.version)}
                  className="text-[10px] mono px-2 py-0.5 border border-border-dim text-text-muted hover:text-text hover:border-border rounded disabled:opacity-50"
                >
                  v{entry.version}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
