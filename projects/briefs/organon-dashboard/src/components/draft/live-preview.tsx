"use client";

import type * as React from "react";
import { useEffect, useMemo, useState } from "react";
import type {
  FigureArtifact,
  PaperArtifact,
  SectionDraftArtifact,
} from "@/lib/artifacts/types";
import type { ManuscriptMeta } from "@/lib/draft/store";
import { renderManuscript } from "@/lib/draft/render";

export type LivePreviewProps = {
  manuscript: ManuscriptMeta;
  sections: SectionDraftArtifact[];
  figures: FigureArtifact[];
  library: PaperArtifact[];
  project: string;
  // Phase 20 (v1.1+) — DR-7 drag-drop placement. Workspace owns the
  // section state, so the preview surfaces the drop event upward with
  // section_id + line_in_section + fig_id resolved.
  onDropFigure?: (sectionId: string, line: number, figId: string) => void;
};

/**
 * Phase 7 T6.5 — debounce a value by `delay` ms. Drops trailing-edge spam
 * so the live-preview's `renderManuscript` re-run only fires once per
 * keystroke burst. No lodash dep — `setTimeout` + cleanup is enough.
 */
function useDebouncedValue<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

const PREVIEW_DEBOUNCE_MS = 100;

export function LivePreview(props: LivePreviewProps) {
  // Phase 7 T6.5 — only the section content drives the renderer's hot path
  // (figures + library + manuscript meta change at user-action speed, not
  // keystroke speed). Debouncing `sections` alone keeps Cmd+S responsive
  // (parent state stays current) while smoothing the per-keystroke render.
  const debouncedSections = useDebouncedValue(props.sections, PREVIEW_DEBOUNCE_MS);

  const html = useMemo(() => {
    const figureUrlBase = (figId: string, png: string) =>
      `/api/figures/${encodeURIComponent(figId)}/${encodeURIComponent(png)}?project=${encodeURIComponent(props.project)}`;
    return renderManuscript({
      manuscript: props.manuscript,
      sections: debouncedSections,
      figures: props.figures,
      library: props.library,
      figureUrlBase,
    }).html;
  }, [props.manuscript, debouncedSections, props.figures, props.library, props.project]);

  // Phase 20 (v1.1+) — DR-7 drag-drop. dragOver must preventDefault for
  // the drop event to fire; the drop handler walks up the DOM to the
  // nearest [data-source-line] block within a [data-section-id] section.
  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    if (!props.onDropFigure) return;
    if (e.dataTransfer.types.includes("application/x-fig-id")) {
      e.preventDefault();
      e.dataTransfer.dropEffect = "copy";
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    if (!props.onDropFigure) return;
    const figId = e.dataTransfer.getData("application/x-fig-id");
    if (!figId) return;
    e.preventDefault();
    const target = e.target as HTMLElement | null;
    if (!target) return;
    const blockEl = target.closest("[data-source-line]") as HTMLElement | null;
    const sectionEl = target.closest("[data-section-id]") as HTMLElement | null;
    if (!blockEl || !sectionEl) return;
    const lineRaw = blockEl.getAttribute("data-source-line");
    const sectionId = sectionEl.getAttribute("data-section-id");
    if (!lineRaw || !sectionId) return;
    const line = Number.parseInt(lineRaw, 10);
    if (!Number.isFinite(line)) return;
    props.onDropFigure(sectionId, line, figId);
  };

  return (
    <div className="h-full flex flex-col">
      <div className="px-3 py-2 mono text-[10px] uppercase tracking-wider text-text-muted border-b border-border-dim">
        Preview · {props.manuscript.title}
      </div>
      <div
        className="flex-1 overflow-auto px-6 py-5 prose-organon"
        onDragOver={handleDragOver}
        onDrop={handleDrop}
      >
        <div dangerouslySetInnerHTML={{ __html: html }} />
      </div>
    </div>
  );
}
