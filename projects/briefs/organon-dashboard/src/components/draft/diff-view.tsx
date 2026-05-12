"use client";

import { useMemo, useState } from "react";
import type { SectionDiffArtifact } from "@/lib/artifacts/types";
import {
  splitDiff,
  composeFromHunks,
  toggleHunkApplied,
  setAllChangeHunksApplied,
  detectHunkConflicts,
  type Hunk,
} from "@/lib/draft/diff-hunks";

// Phase 28 (v1.2) — DR-6+ per-hunk diff accept. Each `change` hunk
// renders an Accept toggle. "Accept all" / "Reject all" shortcuts
// at the top set every change hunk in one click. The component is
// hunk-state-owning by default; the workspace can supply
// `onAcceptHunks(composedAfter, hunks)` to commit the chosen subset.
//
// v1.1 contract preserved: when `onAccept` (full-diff accept) is
// supplied, "Accept all" calls it with the fully-applied compose.

export type DiffViewProps = {
  diff: SectionDiffArtifact;
  // v1.1 full-diff accept — invoked by "Accept all" at the top.
  onAccept: () => void;
  onReject: () => void;
  // v1.2 per-hunk accept — workspace receives the composed `after`
  // string + the hunk array (so it can render history / re-export).
  // When omitted, the per-hunk toggles still work but only mutate
  // local state; the workspace stays on the v1.1 full-diff path.
  onAcceptHunks?: (composedAfter: string, hunks: Hunk[]) => void;
};

export function DiffView({ diff, onAccept, onReject, onAcceptHunks }: DiffViewProps) {
  const initialHunks = useMemo(() => splitDiff(diff.before, diff.after), [diff.before, diff.after]);
  const [hunks, setHunks] = useState<Hunk[]>(initialHunks);

  const composed = useMemo(() => composeFromHunks(diff.before, hunks), [diff.before, hunks]);
  const changeHunks = useMemo(() => hunks.filter((h) => h.type === "change"), [hunks]);
  const appliedCount = changeHunks.filter((h) => h.applied).length;
  // Phase 32 (v1.3) — DR-6++ heuristic conflict detection. Non-blocking:
  // the strip surfaces warnings but Apply Selected stays enabled.
  const conflicts = useMemo(() => detectHunkConflicts(hunks), [hunks]);

  const acceptAll = () => {
    const allApplied = setAllChangeHunksApplied(hunks, true);
    setHunks(allApplied);
    if (onAcceptHunks) onAcceptHunks(composeFromHunks(diff.before, allApplied), allApplied);
    else onAccept();
  };
  const rejectAll = () => {
    const noneApplied = setAllChangeHunksApplied(hunks, false);
    setHunks(noneApplied);
    onReject();
  };

  return (
    <div className="border border-accent rounded bg-bg-elev shadow-2xl">
      <div className="px-4 py-2 border-b border-border-dim flex items-center justify-between">
        <div className="mono text-[10px] uppercase tracking-wider text-text-muted">
          Diff · {diff.action} · {diff.section_id} · {appliedCount}/{changeHunks.length} hunks
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            data-action="reject-all"
            onClick={rejectAll}
            className="text-xs mono uppercase tracking-wider px-3 py-1 border border-border-dim text-text-dim hover:text-text rounded"
          >
            Reject all
          </button>
          <button
            type="button"
            data-action="accept-all"
            onClick={acceptAll}
            className="text-xs mono uppercase tracking-wider px-3 py-1 border border-accent text-accent hover:bg-accent-faint rounded"
          >
            Accept all
          </button>
          {onAcceptHunks && (
            <button
              type="button"
              data-action="apply-selected"
              onClick={() => onAcceptHunks(composed, hunks)}
              disabled={appliedCount === 0 || appliedCount === changeHunks.length}
              className="text-xs mono uppercase tracking-wider px-3 py-1 border border-accent text-accent hover:bg-accent-faint rounded disabled:opacity-40"
              title={
                conflicts.warnings.length > 0
                  ? `${conflicts.warnings.length} potential conflict${conflicts.warnings.length === 1 ? "" : "s"} flagged below — review before applying`
                  : "Commit the per-hunk selection (composed from before + accepted hunks)"
              }
            >
              Apply selected
            </button>
          )}
        </div>
      </div>
      <ul data-diff-hunks className="divide-y divide-border-dim">
        {hunks.map((h) => (
          <li
            key={h.id}
            data-hunk-id={h.id}
            data-hunk-type={h.type}
            data-hunk-applied={h.type === "change" ? (h.applied ? "true" : "false") : ""}
            className={
              h.type === "change"
                ? "px-3 py-2 bg-bg-elev"
                : "px-3 py-1 bg-bg-soft"
            }
          >
            {h.type === "context" ? (
              <pre className="mono text-[11px] text-text-muted whitespace-pre-wrap">
                {h.before_lines.join("\n")}
              </pre>
            ) : (
              <div className="grid grid-cols-[1fr_auto] gap-2 items-start">
                <div className="grid grid-cols-2 gap-px bg-border-dim text-[12px]">
                  <pre className="mono whitespace-pre-wrap p-2 bg-bg-elev text-text-dim">
                    <span className="mono text-[10px] uppercase tracking-wider text-danger mr-1">
                      −
                    </span>
                    {h.before_lines.join("\n")}
                  </pre>
                  <pre className="mono whitespace-pre-wrap p-2 bg-bg-elev text-text">
                    <span className="mono text-[10px] uppercase tracking-wider text-good mr-1">
                      +
                    </span>
                    {h.after_lines.join("\n")}
                  </pre>
                </div>
                <button
                  type="button"
                  data-action="apply-hunk"
                  data-hunk-id={h.id}
                  onClick={() => setHunks((prev) => toggleHunkApplied(prev, h.id))}
                  className={
                    h.applied
                      ? "text-[11px] mono uppercase tracking-wider px-2 py-0.5 border border-accent text-accent rounded"
                      : "text-[11px] mono uppercase tracking-wider px-2 py-0.5 border border-border-dim text-text-dim hover:text-text rounded"
                  }
                >
                  {h.applied ? "Accepted" : "Reject"}
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>
      {conflicts.warnings.length > 0 && (
        <ul
          data-conflict-strip
          className="px-4 py-2 border-t border-border-dim space-y-1 bg-bg-soft"
        >
          {conflicts.warnings.map((w) => (
            <li
              key={`${w.hunk_a}:${w.hunk_b}:${w.reason}`}
              data-action="acknowledge-conflict"
              data-warning-pair={`${w.hunk_a}:${w.hunk_b}`}
              data-warning-reason={w.reason}
              className="text-xs text-text-dim flex gap-2"
            >
              <span className="text-danger">⚠</span>
              <span>
                <span className="mono uppercase text-[10px] text-text-muted">
                  {w.reason === "token-pair-conflict" ? "token conflict" : "proximity"}:{" "}
                </span>
                {w.hunk_a} vs {w.hunk_b} — review before applying
              </span>
            </li>
          ))}
        </ul>
      )}
      {(diff.rationale || (diff.warnings && diff.warnings.length > 0)) && (
        <div className="px-4 py-2 border-t border-border-dim space-y-1">
          {diff.rationale && (
            <div className="text-xs text-text-dim">
              <span className="mono uppercase text-[10px] text-text-muted">rationale: </span>
              {diff.rationale}
            </div>
          )}
          {(diff.warnings ?? []).map((w, i) => (
            <div key={i} className="text-xs text-danger">
              ⚠ {w}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
