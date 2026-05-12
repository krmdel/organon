"use client";

import { useMemo, useState } from "react";
import type { PaperArtifact } from "@/lib/artifacts/types";
import { cn } from "@/lib/cn";
import { BulkPaperOps } from "@/components/primitives/bulk-paper-ops";
import { BibtexExport } from "./bibtex-export";

export type LibraryPanelProps = {
  papers: PaperArtifact[];
  currentProject: string;
  onRemove: (paperId: string) => void;
  onOpen: (paper: PaperArtifact) => void;
  /**
   * Phase 38 (v1.4) — F1 batch-delete. Optional so the panel renders
   * without the affordance when callers don't supply it (back-compat).
   * Receives the batch_id so the route can use ?batch=<id>.
   */
  onRemoveBatch?: (batchId: string, query: string) => void;
  /**
   * Phase 38 (v1.4) — F1 multi-id delete. Optional. Receives the list
   * of ids that the user selected with the ALL/INVERT toggles.
   */
  onRemoveIds?: (ids: string[]) => void;
};

type BatchGroup = {
  batch_id: string | null;
  query: string;
  added_at: string | null;
  papers: PaperArtifact[];
};

function groupBySearchBatch(papers: PaperArtifact[]): BatchGroup[] {
  // Phase 38 (v1.4) — F1: group by search_batch_id; legacy entries
  // (batch_id == null) cluster under one "Ungrouped" bucket.
  const map = new Map<string, BatchGroup>();
  let legacy: BatchGroup | null = null;
  for (const p of papers) {
    const id = p.search_batch_id ?? null;
    if (!id) {
      if (!legacy) {
        legacy = {
          batch_id: null,
          query: "Ungrouped (legacy entries)",
          added_at: null,
          papers: [],
        };
      }
      legacy.papers.push(p);
      continue;
    }
    const existing = map.get(id);
    if (existing) {
      existing.papers.push(p);
      continue;
    }
    map.set(id, {
      batch_id: id,
      query: p.search_batch_query ?? id,
      added_at: p.search_batch_added_at ?? null,
      papers: [p],
    });
  }
  // Sort batches by added_at descending (newest first); legacy goes last.
  const sorted = Array.from(map.values()).sort((a, b) =>
    (b.added_at ?? "").localeCompare(a.added_at ?? ""),
  );
  if (legacy) sorted.push(legacy);
  return sorted;
}

export function LibraryPanel({
  papers,
  currentProject,
  onRemove,
  onOpen,
  onRemoveBatch,
  onRemoveIds,
}: LibraryPanelProps) {
  const groups = useMemo(() => groupBySearchBatch(papers), [papers]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());
  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set());

  const toggleSelected = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };
  const handleAll = () => {
    setSelectedIds(new Set(papers.map((p) => p.id)));
  };
  const handleNone = () => {
    setSelectedIds(new Set());
  };
  const handleInvert = () => {
    setSelectedIds((prev) => {
      const next = new Set<string>();
      for (const p of papers) {
        if (!prev.has(p.id)) next.add(p.id);
      }
      return next;
    });
  };
  const handleDelete = () => {
    if (selectedIds.size === 0) return;
    const ok = window.confirm(
      `Delete ${selectedIds.size} paper${selectedIds.size === 1 ? "" : "s"} from the library? This is irrecoverable.`,
    );
    if (!ok) return;
    if (onRemoveIds) onRemoveIds(Array.from(selectedIds));
    else for (const id of selectedIds) onRemove(id);
    setSelectedIds(new Set());
  };
  const handleDeleteBatch = (batchId: string, query: string, count: number) => {
    const ok = window.confirm(
      `Delete ${count} paper${count === 1 ? "" : "s"} from batch '${query}'? This is irrecoverable.`,
    );
    if (!ok) return;
    if (onRemoveBatch) onRemoveBatch(batchId, query);
  };
  const toggleCollapse = (key: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  // Phase 61 (v2.1) — B5: copy-query affordance. Each batch header gets
  // a 📋 button that copies the search_batch_query to the clipboard so
  // the researcher can paste it into another search / a note / Slack.
  // Falls back silently on insecure contexts (clipboard API unavailable).
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const copyQuery = async (key: string, query: string) => {
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard) {
        await navigator.clipboard.writeText(query);
        setCopiedKey(key);
        setTimeout(() => {
          setCopiedKey((cur) => (cur === key ? null : cur));
        }, 1500);
      }
    } catch {
      // Insecure context or denied — swallow; the user sees no
      // confirmation, which is the right signal that copy failed.
    }
  };

  return (
    <aside className="w-80 shrink-0 border-l border-border-dim flex flex-col">
      <header className="px-5 py-4 border-b border-border-dim">
        <div className="flex items-center justify-between">
          <h3 className="mono text-[11px] uppercase tracking-[0.18em] text-text-muted">Library</h3>
          <span className="mono text-xs text-text">{papers.length}</span>
        </div>
        <div className="text-xs text-text-muted mt-1">
          {currentProject === "__root__" ? "repo root" : currentProject}
        </div>
      </header>

      {/* Phase 39 (v1.4) — F2: shared BulkPaperOps primitive. */}
      <div className="px-4 py-2 border-b border-border-dim">
        <BulkPaperOps
          onAll={handleAll}
          onNone={handleNone}
          onInvert={handleInvert}
          onDelete={handleDelete}
          selectedCount={selectedIds.size}
          totalCount={papers.length}
          deleteTitle="Delete selected papers"
        />
      </div>

      <div className="flex-1 overflow-auto">
        {papers.length === 0 ? (
          <div className="px-5 py-8 text-xs text-text-muted text-center">
            No saved papers yet.
            <br />
            Click <span className="text-text">Save</span> on any result to add it here.
          </div>
        ) : (
          <ul data-library-batches>
            {groups.map((g) => {
              const groupKey = g.batch_id ?? "__legacy__";
              const isCollapsed = collapsed.has(groupKey);
              return (
                <li
                  key={groupKey}
                  data-batch-id={g.batch_id ?? ""}
                  data-batch-query={g.query}
                >
                  <div className="px-4 py-2 flex items-center gap-2 bg-bg-soft border-b border-border-dim">
                    <button
                      type="button"
                      onClick={() => toggleCollapse(groupKey)}
                      className="mono text-[10px] text-text-muted hover:text-text"
                      title={isCollapsed ? "Expand" : "Collapse"}
                    >
                      {isCollapsed ? "▸" : "▾"}
                    </button>
                    <div className="flex-1 min-w-0">
                      <div className="text-[12px] text-text-dim truncate" title={g.query}>
                        {g.query}
                      </div>
                      <div className="mono text-[10px] text-text-muted">
                        {g.papers.length} paper{g.papers.length === 1 ? "" : "s"}
                        {g.added_at ? ` · ${g.added_at.slice(0, 10)}` : ""}
                      </div>
                    </div>
                    {/* Phase 61 (v2.1) — B5: copy-query button per batch.
                        Visible always (not hover-gated) so the researcher
                        can grab the query string at a glance. */}
                    <button
                      type="button"
                      data-copy-query={g.batch_id ?? "__legacy__"}
                      onClick={() => void copyQuery(groupKey, g.query)}
                      className="mono text-[10px] uppercase tracking-wider text-text-muted hover:text-accent px-1"
                      title="Copy this batch's search query"
                    >
                      {copiedKey === groupKey ? "copied" : "📋"}
                    </button>
                    {g.batch_id && onRemoveBatch && (
                      <button
                        type="button"
                        data-action="batch-delete"
                        onClick={() =>
                          handleDeleteBatch(g.batch_id!, g.query, g.papers.length)
                        }
                        className="mono text-[10px] uppercase tracking-wider text-text-muted hover:text-danger"
                        title="Delete entire batch"
                      >
                        delete batch
                      </button>
                    )}
                  </div>
                  {!isCollapsed && (
                    <ul>
                      {g.papers.map((p) => (
                        <li
                          key={p.id}
                          className={cn(
                            "px-5 py-3 border-b border-border-dim hover:bg-bg-soft transition group flex items-start gap-2",
                          )}
                        >
                          <input
                            type="checkbox"
                            checked={selectedIds.has(p.id)}
                            onChange={() => toggleSelected(p.id)}
                            className="mt-1 cursor-pointer"
                            data-paper-checkbox={p.id}
                          />
                          <div className="flex-1 min-w-0">
                            <button
                              onClick={() => onOpen(p)}
                              className="w-full text-left text-sm text-text hover:text-accent leading-snug"
                            >
                              {p.title}
                            </button>
                            <div className="flex items-center justify-between mt-1">
                              <span className="text-[11px] text-text-muted mono">
                                {p.year > 0 ? p.year : "n.d."} · {p.authors[0]?.split(" ")[0] ?? "—"}
                              </span>
                              <button
                                onClick={() => onRemove(p.id)}
                                className="text-[10px] text-text-muted opacity-0 group-hover:opacity-100 hover:text-danger transition mono uppercase tracking-wider"
                                title="Remove from library"
                              >
                                remove
                              </button>
                            </div>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <footer className="px-5 py-3 border-t border-border-dim">
        <BibtexExport
          papers={papers}
          filename={`${currentProject === "__root__" ? "organon" : currentProject}-${new Date().toISOString().slice(0, 10)}.bib`}
        />
      </footer>
    </aside>
  );
}
