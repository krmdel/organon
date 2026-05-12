"use client";

import { useState } from "react";
import type { SectionDraftArtifact, SectionStatus } from "@/lib/artifacts/types";
import { cn } from "@/lib/cn";
import { StatusBadgeSection } from "./status-badge-section";
import { SectionGenerateButton } from "./section-generate-button";

export type SectionListProps = {
  ordering: string[];
  sections: SectionDraftArtifact[];
  activeSectionId: string | null;
  /** Phase 10 (v1.0.1): set of section_ids currently being generated. */
  generatingIds?: Set<string>;
  onSelect: (id: string) => void;
  onReorder: (next: string[]) => void;
  onStatusChange: (id: string, next: SectionStatus) => void;
  onCreateSection: () => void;
  /** Phase 10 (v1.0.1): per-section "Generate with AI" affordance. */
  onGenerateSection?: (id: string) => void;
  /** Phase 51 (v2.0): per-section linkage override editor. Workspace
   *  opens the modal mounting the same LinkageEditModal pattern as
   *  Phase 41's SourceLinkagePanel. */
  onEditSectionOverrides?: (id: string) => void;
  /** Phase 52 (v2.0): import a Jupyter `.ipynb` as a new section. The
   *  workspace reads the file and POSTs to /api/draft/[slug]/
   *  import-notebook; the parser flattens cells to markdown. */
  onImportNotebook?: (file: File) => void;
};

export function SectionList(props: SectionListProps) {
  const {
    ordering,
    sections,
    activeSectionId,
    generatingIds,
    onSelect,
    onReorder,
    onStatusChange,
    onCreateSection,
    onGenerateSection,
    onEditSectionOverrides,
    onImportNotebook,
  } = props;
  const byId = new Map(sections.map((s) => [s.section_id, s]));

  // Phase 7 T6.4 — HTML5 drag-and-drop reorder. ▲▼ buttons remain as the
  // keyboard / discoverability fallback (and they share the same onReorder
  // pipeline so the API is identical).
  const [dragId, setDragId] = useState<string | null>(null);
  const [overId, setOverId] = useState<string | null>(null);

  const move = (idx: number, dir: -1 | 1) => {
    const next = [...ordering];
    const target = idx + dir;
    if (target < 0 || target >= next.length) return;
    [next[idx], next[target]] = [next[target], next[idx]];
    onReorder(next);
  };

  const reorderTo = (sourceId: string, targetId: string) => {
    if (sourceId === targetId) return;
    const next = [...ordering];
    const fromIdx = next.indexOf(sourceId);
    const toIdx = next.indexOf(targetId);
    if (fromIdx < 0 || toIdx < 0) return;
    next.splice(fromIdx, 1);
    next.splice(toIdx > fromIdx ? toIdx : toIdx, 0, sourceId);
    onReorder(next);
  };

  const onDragStart = (id: string) => (e: React.DragEvent<HTMLLIElement>) => {
    e.dataTransfer.setData("text/plain", id);
    e.dataTransfer.effectAllowed = "move";
    setDragId(id);
  };
  const onDragOver = (id: string) => (e: React.DragEvent<HTMLLIElement>) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    if (overId !== id) setOverId(id);
  };
  const onDragLeave = (id: string) => () => {
    if (overId === id) setOverId(null);
  };
  const onDrop = (targetId: string) => (e: React.DragEvent<HTMLLIElement>) => {
    e.preventDefault();
    const sourceId = e.dataTransfer.getData("text/plain") || dragId;
    setDragId(null);
    setOverId(null);
    if (!sourceId) return;
    reorderTo(sourceId, targetId);
  };
  const onDragEnd = () => { setDragId(null); setOverId(null); };

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 border-b border-border-dim mono text-[11px] uppercase tracking-[0.2em] text-text-muted flex items-center justify-between gap-2">
        <span>Sections ({ordering.length})</span>
        <div className="flex items-center gap-2">
          {onImportNotebook && (
            <label
              data-import-notebook
              className="mono text-[10px] uppercase tracking-wider text-text-muted hover:text-text cursor-pointer"
              title="Import Jupyter .ipynb as a new section"
            >
              + .ipynb
              <input
                type="file"
                accept=".ipynb,application/x-ipynb+json,application/json"
                className="sr-only"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) onImportNotebook(f);
                  e.currentTarget.value = "";
                }}
              />
            </label>
          )}
          <button
            type="button"
            onClick={onCreateSection}
            className="mono text-[10px] uppercase tracking-wider text-text-muted hover:text-text"
            title="Add custom section"
          >
            + new
          </button>
        </div>
      </div>
      <ul className="flex-1 overflow-auto divide-y divide-border-dim">
        {ordering.map((id, idx) => {
          const sect = byId.get(id);
          if (!sect) return null;
          const isActive = id === activeSectionId;
          const isDragging = dragId === id;
          const isOver = overId === id && dragId !== null && dragId !== id;
          const isGenerating = generatingIds?.has(id) ?? false;
          // Phase 10: skip the generate affordance on auto-populated
          // sections — references are derived from \cite{} blocks, not
          // drafted by the LLM.
          const canGenerate = onGenerateSection != null && id !== "references";
          return (
            // Phase 61 (v2.1) — B4: two-row layout. The section label
            // gets its own row at full width (no truncation when the
            // sidebar is narrow); the action chips (GENERATE / DRAFT /
            // ⚙ src / ▲▼) sit on a second row beneath. data-* sentinels
            // unchanged so prior tests still pin.
            <li
              key={id}
              draggable
              onDragStart={onDragStart(id)}
              onDragOver={onDragOver(id)}
              onDragLeave={onDragLeave(id)}
              onDrop={onDrop(id)}
              onDragEnd={onDragEnd}
              data-section-row={id}
              className={cn(
                "group px-3 py-2 cursor-pointer transition-colors",
                isActive ? "bg-accent-faint" : "hover:bg-bg-soft",
                isDragging && "opacity-40",
                isOver && "border-t-2 border-accent",
              )}
              onClick={() => onSelect(id)}
            >
              <div className="flex items-start gap-2">
                <span
                  className="mono text-text-muted text-[11px] select-none mt-0.5"
                  title="Drag to reorder"
                >⋮⋮</span>
                <div className="flex-1 min-w-0">
                  <div
                    data-section-label={id}
                    className={cn(
                      "text-sm leading-snug break-words",
                      isActive ? "text-text" : "text-text-dim",
                    )}
                  >
                    ## {sect.section_id}
                  </div>
                  <div className="mono text-[10px] text-text-muted mt-0.5">
                    {sect.section_type} · v{sect.version}
                  </div>
                </div>
              </div>
              <div
                data-section-actions={id}
                className="mt-1.5 flex items-center gap-1 flex-wrap pl-5"
              >
                {canGenerate && (
                  <SectionGenerateButton
                    sectionId={id}
                    onGenerate={onGenerateSection!}
                    running={isGenerating}
                  />
                )}
                <StatusBadgeSection
                  status={sect.status}
                  onAdvance={(next) => onStatusChange(id, next)}
                />
                {onEditSectionOverrides && id !== "references" && (
                  <button
                    type="button"
                    data-section-override-edit={id}
                    onClick={(e) => {
                      e.stopPropagation();
                      onEditSectionOverrides(id);
                    }}
                    className="opacity-0 group-hover:opacity-100 mono text-[10px] uppercase tracking-wider text-text-muted hover:text-accent px-1"
                    title="Override which papers/figures this section pulls from (Phase 51)"
                  >
                    ⚙ src
                  </button>
                )}
                <div className="ml-auto opacity-0 group-hover:opacity-100 flex items-center gap-0.5">
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); move(idx, -1); }}
                    className="mono text-[10px] text-text-muted hover:text-text px-1"
                    title="Move up"
                  >▲</button>
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); move(idx, 1); }}
                    className="mono text-[10px] text-text-muted hover:text-text px-1"
                    title="Move down"
                  >▼</button>
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
