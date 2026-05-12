"use client";

/**
 * Phase 16 (v1.0.1) — Expandable export error panel (EX-1).
 *
 * The export route returns 422 with `unresolved_cites` + `unresolved_figs`
 * when the assembler can't resolve a token. The pre-Phase-16 UI showed
 * these as a single truncated mono pill (`exportLog` text), so the
 * researcher had to copy the message and grep their sections by hand.
 *
 * This panel renders the unresolved tokens as click-to-expand entries,
 * each with a "fix in editor" affordance that switches the workspace
 * to the section containing the offending token.
 *
 * Design notes:
 *   - Pill collapsed by default (preserves the existing visual weight);
 *     click toggles the detail panel below it.
 *   - "fix in editor" for each entry calls `onJumpToSection` with the
 *     section id the parent located via `findSectionForToken`. If the
 *     parent can't find a host section (rare — token in a removed slot)
 *     `targetSectionId` is null and the button renders disabled.
 *   - Panel auto-clears when the parent re-attempts an export (via the
 *     parent setting the props to null).
 */

import { useState } from "react";

export type ExportErrorEntry = {
  token: string;                    // e.g. "Smith2026" or "fig-1"
  kind: "cite" | "fig";
  targetSectionId: string | null;   // null when no host section found
  targetSectionTitle: string | null;
};

export type ExportErrorPanelProps = {
  format: string;
  entries: ExportErrorEntry[];
  onJumpToSection: (sectionId: string) => void;
  onDismiss: () => void;
};

export function ExportErrorPanel({
  format,
  entries,
  onJumpToSection,
  onDismiss,
}: ExportErrorPanelProps) {
  const [expanded, setExpanded] = useState(false);

  if (entries.length === 0) return null;

  const citeCount = entries.filter((e) => e.kind === "cite").length;
  const figCount = entries.filter((e) => e.kind === "fig").length;

  return (
    <div
      className="border border-danger/40 bg-danger/10 rounded text-xs"
      data-export-error-panel
    >
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full px-3 py-1.5 flex items-center justify-between gap-3 mono uppercase tracking-wider text-danger hover:bg-danger/20"
        data-export-error-pill
        aria-expanded={expanded}
      >
        <span>
          {format} → {entries.length} unresolved (
          {citeCount > 0 ? `${citeCount} cite` : ""}
          {citeCount > 0 && figCount > 0 ? ", " : ""}
          {figCount > 0 ? `${figCount} fig` : ""}
          )
        </span>
        <span className="flex items-center gap-2">
          <span className="text-[10px] opacity-70">{expanded ? "▾" : "▸"}</span>
        </span>
      </button>
      {expanded && (
        <div
          className="px-3 py-2 border-t border-danger/40 flex flex-col gap-1.5"
          data-export-error-list
        >
          {entries.map((entry, i) => (
            <div
              key={`${entry.kind}-${entry.token}-${i}`}
              className="flex items-center justify-between gap-3"
              data-export-error-entry
              data-entry-kind={entry.kind}
              data-entry-token={entry.token}
            >
              <div className="mono text-[11px] flex items-center gap-2 min-w-0">
                <span className="px-1.5 py-0.5 bg-bg-soft border border-border-dim rounded text-text-muted text-[10px] uppercase tracking-wider">
                  {entry.kind}
                </span>
                <span className="truncate text-text" title={entry.token}>
                  {entry.token}
                </span>
                {entry.targetSectionTitle ? (
                  <span className="text-[10px] text-text-muted truncate">
                    in {entry.targetSectionTitle}
                  </span>
                ) : (
                  <span className="text-[10px] text-text-muted italic">
                    (no host section)
                  </span>
                )}
              </div>
              <button
                type="button"
                onClick={() =>
                  entry.targetSectionId
                    ? onJumpToSection(entry.targetSectionId)
                    : undefined
                }
                disabled={!entry.targetSectionId}
                className="mono text-[10px] uppercase tracking-wider px-2 py-0.5 border border-accent text-accent hover:bg-accent-faint rounded disabled:opacity-40 disabled:cursor-not-allowed"
                data-action="fix-in-editor"
                data-target-section-id={entry.targetSectionId ?? ""}
              >
                fix in editor
              </button>
            </div>
          ))}
          <div className="flex justify-end pt-1">
            <button
              type="button"
              onClick={onDismiss}
              className="mono text-[10px] uppercase tracking-wider text-text-muted hover:text-text"
              data-action="dismiss-export-error"
            >
              dismiss
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
