"use client";

import { useMemo } from "react";
import type { HypothesisArtifact } from "@/lib/artifacts/types";
import { BulkPaperOps } from "@/components/primitives/bulk-paper-ops";

/**
 * Phase 42 (v1.5) — F5 hypothesis-multiselect.
 *
 * Shared primitive surfaced by:
 *   (a) DraftList's "+ new manuscript" form (inline picker — feeds
 *       `linked_hypothesis_ids[]` into the create POST body).
 *   (b) SourceLinkagePanel's hypothesis edit affordance (modal — feeds
 *       a PATCH to /api/draft/[slug]).
 *
 * Multi-select via checkboxes; ALL / NONE / INVERT via the Phase 39
 * BulkPaperOps primitive. DELETE is intentionally NOT wired — picking
 * hypotheses for a manuscript should never delete them.
 *
 * Decision (brief §6.3):
 * - Multi-select, NOT single-select. A manuscript can legitimately span
 *   multiple related hypotheses (e.g. "main effect + sensitivity").
 * - Optional at create time. Empty selection is valid (manuscript may
 *   not have a hypothesis yet — methods paper, etc.).
 */

export type HypothesisMultiselectProps = {
  hypotheses: HypothesisArtifact[];
  selectedIds: string[];
  onChange: (next: string[]) => void;
  /** Optional className appended to the wrapper. */
  className?: string;
};

export function HypothesisMultiselect({
  hypotheses,
  selectedIds,
  onChange,
  className,
}: HypothesisMultiselectProps) {
  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);

  const toggle = (id: string) => {
    const next = new Set(selectedSet);
    if (next.has(id)) next.delete(id); else next.add(id);
    onChange(Array.from(next));
  };
  const all = () => onChange(hypotheses.map((h) => h.id));
  const none = () => onChange([]);
  const invert = () => {
    const next = hypotheses
      .filter((h) => !selectedSet.has(h.id))
      .map((h) => h.id);
    onChange(next);
  };

  return (
    <div
      data-hypothesis-multiselect
      className={`border border-border-dim rounded bg-bg ${className ?? ""}`}
    >
      <div className="flex items-center justify-between px-2 py-1 border-b border-border-dim">
        <BulkPaperOps
          onAll={all}
          onNone={none}
          onInvert={invert}
          selectedCount={selectedIds.length}
          totalCount={hypotheses.length}
          label="hypotheses"
        />
      </div>
      {hypotheses.length === 0 ? (
        <div className="text-xs text-text-muted px-3 py-3">
          No hypotheses in this project yet — start one from the /hypothesis page.
        </div>
      ) : (
        <ul className="max-h-64 overflow-y-auto divide-y divide-border-dim">
          {hypotheses.map((h) => {
            const checked = selectedSet.has(h.id);
            const claimText = h.claim_short ?? h.claim ?? h.id;
            return (
              <li key={h.id}>
                <label
                  className="flex items-start gap-2 px-2 py-1 hover:bg-bg-soft cursor-pointer"
                  data-hypothesis-id={h.id}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggle(h.id)}
                    className="mt-1"
                    data-hypothesis-checkbox
                  />
                  <span className="flex-1 text-xs">
                    <div className="text-text">{claimText}</div>
                    <div className="mono text-[10px] text-text-muted mt-0.5">
                      {h.id} · {h.status}
                    </div>
                  </span>
                </label>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
