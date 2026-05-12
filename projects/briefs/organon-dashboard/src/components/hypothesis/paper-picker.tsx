"use client";

import { useMemo, useState } from "react";
import type { PaperArtifact } from "@/lib/artifacts/types";
import { cn } from "@/lib/cn";
import { BulkSelect } from "@/components/primitives/bulk-select";
import { BulkPaperOps } from "@/components/primitives/bulk-paper-ops";

export type PaperPickerProps = {
  library: PaperArtifact[];
  value: string[];
  onChange: (ids: string[]) => void;
};

const VISIBLE_DEFAULT = 8;

type BatchGroup = {
  batch_id: string | null;
  query: string;
  added_at: string | null;
  papers: PaperArtifact[];
};

function groupBySearchBatch(papers: PaperArtifact[]): BatchGroup[] {
  // Phase 59 (v2.1) — B2: same shape as library-panel's groupBySearchBatch
  // so the picker reads the Phase-38 substrate consistently. Legacy /
  // via-skill saves (no batch_id) bucket under "Ungrouped".
  const map = new Map<string, BatchGroup>();
  let ungrouped: BatchGroup | null = null;
  for (const p of papers) {
    const id = p.search_batch_id ?? null;
    if (!id) {
      if (!ungrouped) {
        ungrouped = { batch_id: null, query: "Ungrouped", added_at: null, papers: [] };
      }
      ungrouped.papers.push(p);
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
  const sorted = Array.from(map.values()).sort((a, b) =>
    (b.added_at ?? "").localeCompare(a.added_at ?? ""),
  );
  if (ungrouped) sorted.push(ungrouped);
  return sorted;
}

export function PaperPicker({ library, value, onChange }: PaperPickerProps) {
  const [query, setQuery] = useState("");
  const [showAll, setShowAll] = useState(false);
  const selected = useMemo(() => new Set(value), [value]);
  // Phase 59 (v2.1) — B2: default-collapsed batches. The picker can be
  // overwhelming with many batches across many papers; the user opens
  // batches on demand.
  const [expandedBatches, setExpandedBatches] = useState<Set<string>>(
    () => new Set(),
  );
  // Whether to group by batch (default) or render the legacy flat list.
  // The library-panel substrate (Phase 38) makes batch_id available on
  // every freshly-saved paper; pre-Phase-38 saves cluster under
  // "Ungrouped" so the picker still works on legacy projects.

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return library;
    return library.filter((p) => {
      return (
        p.title.toLowerCase().includes(q) ||
        (p.journal ?? "").toLowerCase().includes(q) ||
        String(p.year).includes(q)
      );
    });
  }, [library, query]);

  const visible = showAll ? filtered : filtered.slice(0, VISIBLE_DEFAULT);
  // Phase 59 (v2.1) — B2: only group when the user has NOT typed a
  // query. With an active query the flat filtered list reads more
  // naturally (no surprise collapsed batches hiding matches).
  const grouped = query.trim().length === 0;
  const batches = useMemo(
    () => (grouped ? groupBySearchBatch(visible) : []),
    [visible, grouped],
  );

  const toggle = (id: string) => {
    const next = new Set(value);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onChange(Array.from(next));
  };

  const toggleBatchExpanded = (key: string) => {
    setExpandedBatches((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const selectedPapers = library.filter((p) => selected.has(p.id));

  if (library.length === 0) {
    return (
      <div
        aria-label="linked-papers"
        className="border border-dashed border-border-dim rounded px-4 py-6 text-center text-sm text-text-muted"
      >
        Library is empty. Save papers in <span className="text-accent">/lit</span> first, then they&apos;ll appear here.
      </div>
    );
  }

  return (
    <div aria-label="linked-papers" className="border border-border-dim rounded">
      <div className="px-3 py-2 border-b border-border-dim flex items-center gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter library by title / journal / year"
          className="flex-1 bg-transparent text-sm mono text-text outline-none placeholder:text-text-muted"
        />
        <span className="mono text-[10px] uppercase text-text-muted tracking-wider">
          {value.length}/{library.length}
        </span>
      </div>

      {/* Phase 13d (H-2): BulkSelect All / None / Invert against the full
          library (not the search-filtered view). Operating on the full
          library keeps semantics simple and predictable across query
          changes — "All" always means every paper, regardless of what
          the active search shows. The count chip + selected-papers
          chip strip below stay live with the new selection. */}
      <div className="px-3 py-2 border-b border-border-dim">
        <BulkSelect
          items={library}
          keyOf={(p) => p.id}
          selectedKeys={selected}
          onChange={(next) =>
            onChange(library.filter((p) => next.has(p.id)).map((p) => p.id))
          }
          label="papers"
        />
      </div>

      <div className="max-h-72 overflow-auto divide-y divide-border-dim">
        {grouped ? (
          <ul data-picker-batches>
            {batches.map((g) => {
              const groupKey = g.batch_id ?? "__ungrouped__";
              const isExpanded = expandedBatches.has(groupKey);
              const groupSelectedCount = g.papers.filter((p) => selected.has(p.id)).length;
              return (
                <li
                  key={groupKey}
                  data-picker-batch-id={g.batch_id ?? ""}
                  data-picker-batch-query={g.query}
                  className="border-b border-border-dim last:border-b-0"
                >
                  <button
                    type="button"
                    onClick={() => toggleBatchExpanded(groupKey)}
                    className="w-full px-3 py-2 flex items-center gap-2 text-left bg-bg-soft hover:bg-bg-elev transition"
                    title={g.query}
                    aria-expanded={isExpanded}
                  >
                    <span className="mono text-[10px] text-text-muted">
                      {isExpanded ? "▾" : "▸"}
                    </span>
                    <span className="flex-1 min-w-0 truncate text-[12px] text-text-dim">
                      {g.query}
                    </span>
                    <span className="mono text-[10px] uppercase tracking-wider text-text-muted">
                      {groupSelectedCount > 0 ? `${groupSelectedCount}/` : ""}
                      {g.papers.length}
                    </span>
                  </button>
                  {isExpanded && (
                    <ul>
                      {g.papers.map((p) => {
                        const isOn = selected.has(p.id);
                        return (
                          <li key={p.id}>
                            <label
                              className={cn(
                                "flex items-start gap-3 px-3 py-2 cursor-pointer transition",
                                isOn ? "bg-accent-faint" : "hover:bg-bg-soft",
                              )}
                            >
                              <input
                                type="checkbox"
                                checked={isOn}
                                onChange={() => toggle(p.id)}
                                className="mt-1 accent-accent"
                              />
                              <div className="min-w-0 flex-1">
                                <div className="text-sm leading-snug truncate">{p.title}</div>
                                <div className="mono text-[10px] text-text-muted mt-0.5">
                                  {p.year > 0 ? p.year : "—"} · {p.authors[0] ?? "?"}
                                  {p.authors.length > 1 ? " et al." : ""}
                                  {p.journal ? ` · ${p.journal}` : ""}
                                </div>
                              </div>
                            </label>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </li>
              );
            })}
          </ul>
        ) : (
          visible.map((p) => {
            const isOn = selected.has(p.id);
            return (
              <label
                key={p.id}
                className={cn(
                  "flex items-start gap-3 px-3 py-2 cursor-pointer transition",
                  isOn ? "bg-accent-faint" : "hover:bg-bg-soft",
                )}
              >
                <input
                  type="checkbox"
                  checked={isOn}
                  onChange={() => toggle(p.id)}
                  className="mt-1 accent-accent"
                />
                <div className="min-w-0 flex-1">
                  <div className="text-sm leading-snug truncate">{p.title}</div>
                  <div className="mono text-[10px] text-text-muted mt-0.5">
                    {p.year > 0 ? p.year : "—"} · {p.authors[0] ?? "?"}
                    {p.authors.length > 1 ? " et al." : ""}
                    {p.journal ? ` · ${p.journal}` : ""}
                  </div>
                </div>
              </label>
            );
          })
        )}
        {!grouped && filtered.length > VISIBLE_DEFAULT && (
          // Phase 59 (v2.1) — B3: explicit type="button" so this control
          // never submits the parent <ClaimForm>. The default <button>
          // type is "submit" inside a <form>, which was firing
          // generate-council mid-edit on click.
          <button
            type="button"
            onClick={() => setShowAll((s) => !s)}
            className="w-full px-3 py-2 mono text-[10px] uppercase tracking-wider text-text-dim hover:text-text"
          >
            {showAll ? "Show fewer" : `Show all ${filtered.length}`}
          </button>
        )}
      </div>

      {selectedPapers.length > 0 && (
        <div className="border-t border-border-dim">
          <div className="px-3 py-2 flex flex-wrap gap-1.5">
            {selectedPapers.map((p) => (
              <span
                key={p.id}
                className="inline-flex items-center gap-1 mono text-[10px] uppercase tracking-wider px-2 py-0.5 border border-accent text-accent rounded"
              >
                {(p.authors[0] ?? p.id).split(" ")[0]}
                {p.year > 0 ? ` ${p.year}` : ""}
                {/* Phase 59 (v2.1) — B3: explicit type="button" so the
                    chip "remove" click stays inside the picker. */}
                <button
                  type="button"
                  onClick={() => toggle(p.id)}
                  className="ml-1 opacity-70 hover:opacity-100"
                  aria-label={`Remove ${p.title}`}
                >
                  ✕
                </button>
              </span>
            ))}
          </div>
          {/* Phase 39 (v1.4) — F2: shared BulkPaperOps with un-link
              semantics. ALL/INVERT operate on the LINKED set
              (functionally equivalent to BulkSelect above, but the
              DELETE action is unique to this primitive — it clears
              every linked paper from the claim). */}
          <div className="px-3 py-2 border-t border-border-dim">
            <BulkPaperOps
              onAll={() => onChange(library.map((p) => p.id))}
              onNone={() => onChange([])}
              onInvert={() => {
                const next: string[] = [];
                for (const p of library) {
                  if (!selected.has(p.id)) next.push(p.id);
                }
                onChange(next);
              }}
              onDelete={() => {
                if (value.length === 0) return;
                const ok = window.confirm(
                  `Un-link all ${value.length} paper${value.length === 1 ? "" : "s"} from this claim?`,
                );
                if (ok) onChange([]);
              }}
              selectedCount={value.length}
              totalCount={library.length}
              label="linked"
              deleteTitle="Un-link all papers from this claim"
            />
          </div>
        </div>
      )}
    </div>
  );
}
