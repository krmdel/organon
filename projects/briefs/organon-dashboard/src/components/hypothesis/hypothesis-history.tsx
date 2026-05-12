"use client";

import { useMemo } from "react";
import type { HypothesisArtifact, HypothesisStatus } from "@/lib/artifacts/types";
import { StatusBadge } from "./status-badge";
import { cn } from "@/lib/cn";

const ALL_STATUSES: HypothesisStatus[] = [
  "open",
  "synthesized",
  "supported",
  "refuted",
  "archived",
];

export type HypothesisHistoryProps = {
  hypotheses: HypothesisArtifact[];
  filterStatus: HypothesisStatus[];
  filterQuery: string;
  activeId: string | null;
  focusedIdx: number;
  onFilterStatus: (next: HypothesisStatus[]) => void;
  onFilterQuery: (q: string) => void;
  onSelect: (hyp_id: string) => void;
  /** Phase 58 (v2.1) — B1: per-row × delete affordance. The handler
   *  receives the hypothesis id; the parent owns the confirm + DELETE. */
  onDelete?: (hyp_id: string) => void;
};

export function HypothesisHistory({
  hypotheses,
  filterStatus,
  filterQuery,
  activeId,
  focusedIdx,
  onFilterStatus,
  onFilterQuery,
  onSelect,
  onDelete,
}: HypothesisHistoryProps) {
  const visible = useMemo(() => {
    const q = filterQuery.trim().toLowerCase();
    return hypotheses.filter((h) => {
      if (filterStatus.length > 0 && !filterStatus.includes(h.status)) return false;
      if (q && !h.claim.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [hypotheses, filterStatus, filterQuery]);

  const toggleStatus = (s: HypothesisStatus) => {
    const set = new Set(filterStatus);
    if (set.has(s)) set.delete(s);
    else set.add(s);
    onFilterStatus(Array.from(set));
  };

  return (
    <div className="border border-border-dim rounded">
      <header className="px-3 py-2 border-b border-border-dim flex items-center gap-3 flex-wrap">
        <input
          type="text"
          value={filterQuery}
          onChange={(e) => onFilterQuery(e.target.value)}
          placeholder="Filter claims…"
          className="bg-transparent text-sm outline-none placeholder:text-text-muted flex-1 min-w-[10rem]"
        />
        <div className="flex gap-1 flex-wrap">
          {ALL_STATUSES.map((s) => {
            const on = filterStatus.includes(s);
            return (
              <button
                key={s}
                onClick={() => toggleStatus(s)}
                className={cn(
                  "mono text-[10px] uppercase tracking-wider px-2 py-0.5 border rounded transition",
                  on
                    ? "border-accent text-accent bg-accent-faint"
                    : "border-border-dim text-text-muted hover:text-text",
                )}
              >
                {s}
              </button>
            );
          })}
        </div>
        <span className="mono text-[10px] uppercase tracking-wider text-text-muted">
          {visible.length}/{hypotheses.length}
        </span>
      </header>

      <div className="max-h-[60vh] overflow-auto divide-y divide-border-dim">
        {visible.length === 0 && (
          <div className="px-4 py-6 text-center text-sm text-text-muted">
            No hypotheses match.
          </div>
        )}
        {visible.map((h, i) => (
          <div
            key={h.id}
            className={cn(
              "group relative flex items-stretch transition",
              h.id === activeId
                ? "bg-accent-faint border-l-2 border-accent -ml-[2px] pl-[2px]"
                : "hover:bg-bg-soft",
              i === focusedIdx && "ring-1 ring-accent/50",
            )}
          >
            <button
              type="button"
              onClick={() => onSelect(h.id)}
              className="flex-1 min-w-0 text-left px-3 py-2 flex items-start gap-3"
              aria-selected={h.id === activeId}
            >
              <div className="flex-1 min-w-0">
                <div className="text-sm leading-snug truncate">
                  {h.claim_short ?? truncate(h.claim, 80)}
                </div>
                <div className="mono text-[10px] text-text-muted mt-0.5">
                  {(h.critique_files?.length ?? 0)} critiques · {h.paper_ids.length} papers ·{" "}
                  {formatDate(h.created_at)}
                </div>
              </div>
              <StatusBadge status={h.status} />
            </button>
            {/* Phase 58 (v2.1) — B1: × delete affordance, visible on hover.
                Sibling button instead of nested so the click never bubbles
                into onSelect. */}
            {onDelete && (
              <button
                type="button"
                data-hypothesis-delete={h.id}
                onClick={(e) => {
                  e.stopPropagation();
                  e.preventDefault();
                  const label = h.claim_short ?? truncate(h.claim, 60);
                  if (
                    typeof window !== "undefined" &&
                    window.confirm(
                      `Delete hypothesis "${label}"? This cannot be undone.`,
                    )
                  ) {
                    onDelete(h.id);
                  }
                }}
                className="px-2 mono text-[12px] text-text-muted opacity-0 group-hover:opacity-100 hover:text-danger transition"
                title="Delete hypothesis (cannot be undone)"
                aria-label={`Delete hypothesis ${h.claim_short ?? h.id}`}
              >
                ×
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function truncate(s: string, n: number): string {
  return s.length <= n ? s : s.slice(0, n - 1) + "…";
}

function formatDate(iso?: string): string {
  if (!iso) return "—";
  return iso.slice(0, 10);
}
