"use client";

import { useEffect, useRef } from "react";
import type { FigureArtifact, PaperArtifact } from "@/lib/artifacts/types";

export type AutocompleteKind = "fig" | "cite";
export type AutocompleteItem = { id: string; label: string; sub?: string };

export type EmbedAutocompleteProps = {
  kind: AutocompleteKind;
  query: string;
  figures: FigureArtifact[];
  library: PaperArtifact[];
  onPick: (id: string) => void;
  onClose: () => void;
};

function score(item: AutocompleteItem, q: string): number {
  if (!q) return 1;
  const target = (item.id + " " + item.label).toLowerCase();
  return target.includes(q.toLowerCase()) ? 1 : 0;
}

export function EmbedAutocomplete(props: EmbedAutocompleteProps) {
  const { kind, query, figures, library, onPick, onClose } = props;
  const wrapRef = useRef<HTMLDivElement | null>(null);
  // Phase 5 (fix-sprint): cite picker offers paper.cite_key (e.g. "Shah2026")
  // as the inserted token, not paper.id (e.g. "pmid-41889156"). Library is
  // sorted by saved_at recency so the most recently-added papers float to
  // the top — mirrors the bibtex export ordering and the dashboard's
  // mental model of "what did I just save?". Falls back to paper.id only
  // when cite_key is missing (legacy un-backfilled rows).
  const orderedLibrary = [...library].sort((a, b) =>
    (b.saved_at ?? "").localeCompare(a.saved_at ?? ""));
  const items: AutocompleteItem[] = (kind === "fig"
    ? figures.map((f) => ({
        id: f.id,
        label: String(f.params?.prompt ?? f.kind),
        sub: f.backend,
      }))
    : orderedLibrary.map((p) => ({
        id: p.cite_key ?? p.id,
        label: p.title,
        sub: `${p.authors.slice(0, 2).join(", ")}${p.authors.length > 2 ? "…" : ""} · ${p.year ?? "?"} · ${p.id}`,
      }))
  ).filter((it) => score(it, query) > 0).slice(0, 8);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      ref={wrapRef}
      className="absolute z-20 left-2 bottom-full mb-1 w-80 max-h-64 overflow-auto bg-bg-elev border border-border rounded shadow-2xl"
    >
      <div className="px-2 py-1.5 mono text-[10px] uppercase tracking-wider text-text-muted border-b border-border-dim flex items-center justify-between">
        <span>\\{kind}{`{${query}…}`}</span>
        <span>{items.length} match{items.length === 1 ? "" : "es"}</span>
      </div>
      {items.length === 0 ? (
        <div className="px-3 py-3 text-xs text-text-muted">
          No {kind === "fig" ? "figures" : "library papers"} match. Try a different query.
        </div>
      ) : (
        <ul>
          {items.map((it) => (
            <li key={it.id}>
              <button
                type="button"
                onClick={() => onPick(it.id)}
                className="w-full text-left px-3 py-2 text-sm hover:bg-bg-soft border-b border-border-dim last:border-b-0"
              >
                <div className="text-text truncate">{it.label}</div>
                <div className="mono text-[10px] text-text-muted truncate">{it.id} · {it.sub}</div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
