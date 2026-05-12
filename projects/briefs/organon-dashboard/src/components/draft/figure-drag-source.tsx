"use client";

import { useRef, type RefObject } from "react";
import type { FigureArtifact } from "@/lib/artifacts/types";

// Phase 20 (v1.1+) — Drag-source sidebar for the figure-placement flow
// (DR-7). Lists project figures with thumbnails; each row is draggable
// and stamps `application/x-fig-id` on the dataTransfer payload at
// dragstart so the live-preview's drop handler can recover the fig_id.
//
// Phase 23 (v1.2) — Custom drag image (DR-7+). Each row mounts a
// hidden per-row <img> at the same thumbnail URL; on dragstart the
// handler calls e.dataTransfer.setDragImage(imgEl, w/2, h/2) so the
// cursor sits in the middle of a clean thumbnail-only preview (no row
// chrome / text). The hidden image stays painted via off-screen
// positioning (left:-9999px); a hidden-via-display rule would render
// a blank surface for the browser's drag-image capture.
//
// Presentational: no fetches, no state. The parent passes `figures` +
// `project` (project is needed only to compose the thumbnail URL).

export type FigureDragSourceProps = {
  figures: FigureArtifact[];
  project: string;
};

export function FigureDragSource({ figures, project }: FigureDragSourceProps) {
  // One ref per figure id, keyed in a single object so the row
  // closures can read .current at dragstart without re-renders.
  const previewRefs = useRef<Record<string, HTMLImageElement | null>>({});

  if (figures.length === 0) {
    return (
      <div className="px-3 py-2 mono text-[10px] text-text-muted">
        No figures yet — generate one on the figures workspace.
      </div>
    );
  }
  return (
    <div data-figure-drag-source className="border-t border-border-dim mt-3 pt-3">
      <div className="px-3 mono text-[10px] uppercase tracking-wider text-text-muted mb-2">
        Drag-drop figures
      </div>
      <ul className="px-3 space-y-1.5">
        {figures.map((f) => {
          const png = f.png_path.split("/").pop() ?? "v1.png";
          const url = `/api/figures/${encodeURIComponent(f.id)}/${encodeURIComponent(png)}?project=${encodeURIComponent(project)}`;
          const setPreviewRef = (el: HTMLImageElement | null) => {
            previewRefs.current[f.id] = el;
          };
          return (
            <li key={f.id}>
              {/* Hidden preview image per row. Off-screen via
                  position:absolute + left:-9999px so it stays painted. */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                ref={setPreviewRef}
                src={url}
                alt=""
                aria-hidden="true"
                data-drag-preview={f.id}
                style={{ position: "absolute", left: "-9999px", top: 0, width: 96, height: 96, pointerEvents: "none" }}
              />
              <div
                draggable
                data-fig-id={f.id}
                onDragStart={(e) => {
                  // Stamp fig_id on the dataTransfer in our custom slot.
                  // text/plain is set as a fallback so non-Organon drop
                  // targets (e.g. a text editor) get the literal token.
                  e.dataTransfer.setData("application/x-fig-id", f.id);
                  e.dataTransfer.setData("text/plain", `\\fig{${f.id}}`);
                  e.dataTransfer.effectAllowed = "copy";
                  // Phase 23: replace the default drag image with a
                  // clean thumbnail. Centre the cursor on the
                  // thumbnail (w/2, h/2). naturalWidth is 0 if the
                  // image hasn't loaded yet — fall back to the styled
                  // 96px box so the offsets still make sense.
                  const imgEl = previewRefs.current[f.id];
                  if (imgEl) {
                    const w = imgEl.naturalWidth || imgEl.width || 96;
                    const h = imgEl.naturalHeight || imgEl.height || 96;
                    e.dataTransfer.setDragImage(imgEl, w / 2, h / 2);
                  }
                }}
                className="flex items-center gap-2 cursor-grab hover:bg-bg-soft border border-border-dim rounded px-2 py-1.5"
                title={`Drag onto a section to insert \\fig{${f.id}}`}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={url}
                  alt={f.alt_text ?? f.id}
                  className="w-10 h-10 object-cover rounded border border-border-dim shrink-0"
                />
                <div className="min-w-0 flex-1">
                  <div className="mono text-[10px] text-text-muted truncate">{f.id}</div>
                  <div className="text-xs text-text truncate">
                    {f.caption ?? `${f.kind} · v${f.version}`}
                  </div>
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// Re-export the ref type so consumers (and tests) can reason about
// the shape if needed.
export type FigureDragPreviewRef = RefObject<HTMLImageElement | null>;
