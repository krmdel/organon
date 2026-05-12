"use client";

import { useMemo, useState } from "react";
import type { FigureArtifact } from "@/lib/artifacts/types";
import { cn } from "@/lib/cn";

export type PlotHistoryProps = {
  figures: FigureArtifact[];
  activeFigId: string | null;
  project: string;
  onSelect: (fig_id: string) => void;
  onDelete: (fig_id: string) => void;
};

type DateGroup = {
  date: string;
  figures: FigureArtifact[];
};

function groupByDate(figures: FigureArtifact[]): DateGroup[] {
  const buckets = new Map<string, FigureArtifact[]>();
  for (const f of figures) {
    const key = (f.created_at ?? "").slice(0, 10) || "unknown";
    const arr = buckets.get(key);
    if (arr) arr.push(f);
    else buckets.set(key, [f]);
  }
  return Array.from(buckets.entries())
    .map(([date, figs]) => ({ date, figures: figs }))
    .sort((a, b) => (a.date < b.date ? 1 : -1));
}

export function PlotHistory({ figures, activeFigId, project, onSelect, onDelete }: PlotHistoryProps) {
  const groups = useMemo(() => groupByDate(figures), [figures]);
  const newestDate = groups[0]?.date ?? null;
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  if (figures.length === 0) {
    return (
      <div className="px-3 py-4 text-xs text-text-muted">
        No figures yet. Generate one from the plot picker.
      </div>
    );
  }

  const toggle = (date: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(date)) next.delete(date);
      else next.add(date);
      return next;
    });
  };

  const expanded = (date: string) => {
    const baseOpen = date === newestDate;
    const flipped = collapsed.has(date);
    return baseOpen ? !flipped : flipped;
  };

  return (
    <ul>
      {groups.map((g) => {
        const open = expanded(g.date);
        return (
          <li key={g.date}>
            <div className="group/header px-3 py-2 flex items-center gap-2 bg-bg-soft border-b border-border-dim">
              <button
                type="button"
                onClick={() => toggle(g.date)}
                className="mono text-[10px] text-text-muted hover:text-text"
                title={open ? "Collapse" : "Expand"}
              >
                {open ? "▾" : "▸"}
              </button>
              <div className="flex-1 min-w-0">
                <div className="mono text-[10px] uppercase tracking-[0.15em] text-text-muted">
                  {g.date}
                </div>
                <div className="mono text-[10px] text-text-muted">
                  {g.figures.length} plot{g.figures.length === 1 ? "" : "s"}
                </div>
              </div>
              <button
                type="button"
                data-plot-delete-date={g.date}
                onClick={(e) => {
                  e.stopPropagation();
                  e.preventDefault();
                  if (
                    typeof window !== "undefined" &&
                    window.confirm(
                      `Delete all ${g.figures.length} plot${g.figures.length === 1 ? "" : "s"} from ${g.date}? This cannot be undone.`,
                    )
                  ) {
                    for (const f of g.figures) onDelete(f.id);
                  }
                }}
                className="mono text-[14px] leading-none text-text-muted opacity-0 group-hover/header:opacity-100 hover:text-danger transition"
                title={`Delete all ${g.figures.length} plot${g.figures.length === 1 ? "" : "s"} from ${g.date}`}
                aria-label={`Delete all plots from ${g.date}`}
              >
                ×
              </button>
            </div>
            {open && (
              <ul className="grid grid-cols-2 gap-2 p-2">
                {g.figures.map((f) => {
                  const thumb = f.thumbnail_path ?? f.png_path;
                  const basename = thumb.split("/").pop() ?? "v1.thumb.png";
                  const url = `/api/figures/${encodeURIComponent(f.id)}/${encodeURIComponent(basename)}?project=${encodeURIComponent(project)}`;
                  const active = f.id === activeFigId;
                  const label = String(f.params.plot_kind ?? f.kind);
                  return (
                    <li key={f.id} className="group relative">
                      <button
                        type="button"
                        onClick={() => onSelect(f.id)}
                        className={cn(
                          "block w-full overflow-hidden rounded border transition",
                          active ? "border-accent" : "border-border-dim hover:border-accent/50",
                        )}
                        title={label}
                      >
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={url} alt="" className="w-full h-24 object-cover bg-bg" />
                        <div className="px-2 py-1 mono text-[10px] text-text-muted truncate">
                          {label}
                        </div>
                      </button>
                      <button
                        type="button"
                        data-plot-delete={f.id}
                        onClick={(e) => {
                          e.stopPropagation();
                          e.preventDefault();
                          if (
                            typeof window !== "undefined" &&
                            window.confirm(`Delete plot "${label}"? This cannot be undone.`)
                          ) {
                            onDelete(f.id);
                          }
                        }}
                        className="absolute top-1 right-1 px-1.5 py-0.5 rounded bg-bg/80 mono text-[12px] leading-none text-text-muted opacity-0 group-hover:opacity-100 hover:text-danger transition"
                        title="Delete plot (cannot be undone)"
                        aria-label={`Delete plot ${f.id}`}
                      >
                        ×
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </li>
        );
      })}
    </ul>
  );
}
