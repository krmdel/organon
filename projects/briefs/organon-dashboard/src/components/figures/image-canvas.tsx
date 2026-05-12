"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { FigureArtifact } from "@/lib/artifacts/types";
import type { MaskTool } from "./mask-tools";

export type ImageCanvasProps = {
  figure: FigureArtifact;
  pngUrl: string;
  tool: MaskTool;
  onMaskChange: (blob: Blob | null) => void;
};

type Pt = { x: number; y: number };

/**
 * Renders the current figure version with an absolutely-positioned canvas
 * overlay for mask drawing. The on-screen overlay matches the displayed
 * size; on submit, the mask is rasterised at the source image dimensions
 * to satisfy FAL FLUX Fill's exact-size requirement.
 */
export function ImageCanvas({ figure, pngUrl, tool, onMaskChange }: ImageCanvasProps) {
  const imgRef = useRef<HTMLImageElement | null>(null);
  const overlayRef = useRef<HTMLCanvasElement | null>(null);
  const draftRef = useRef<HTMLCanvasElement | null>(null); // in-progress preview
  const [naturalDims, setNaturalDims] = useState<{ w: number; h: number } | null>(null);
  const [drawing, setDrawing] = useState(false);
  const [start, setStart] = useState<Pt | null>(null);
  const [last, setLast] = useState<Pt | null>(null);
  const [path, setPath] = useState<Pt[]>([]);
  const [maskExists, setMaskExists] = useState(false);

  const onLoad = useCallback(() => {
    const img = imgRef.current;
    if (!img) return;
    const w = img.naturalWidth || img.width;
    const h = img.naturalHeight || img.height;
    setNaturalDims({ w, h });
    [overlayRef, draftRef].forEach((ref) => {
      const c = ref.current;
      if (c) { c.width = w; c.height = h; }
    });
  }, []);

  // External clears
  const clearOverlays = useCallback(() => {
    [overlayRef, draftRef].forEach((ref) => {
      const c = ref.current;
      if (!c) return;
      const ctx = c.getContext("2d");
      if (ctx) ctx.clearRect(0, 0, c.width, c.height);
    });
    setMaskExists(false);
    onMaskChange(null);
  }, [onMaskChange]);

  // When the active figure version changes, blow away the mask.
  useEffect(() => {
    clearOverlays();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [figure.id, figure.version]);

  // Esc clears
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") clearOverlays();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [clearOverlays]);

  function pointFromEvent(e: React.PointerEvent): Pt {
    const overlay = overlayRef.current!;
    const rect = overlay.getBoundingClientRect();
    return {
      x: ((e.clientX - rect.left) / rect.width) * overlay.width,
      y: ((e.clientY - rect.top) / rect.height) * overlay.height,
    };
  }

  function paintMaskShape(ctx: CanvasRenderingContext2D, draw: () => void) {
    ctx.save();
    ctx.fillStyle = "rgba(255, 80, 80, 0.45)";
    ctx.strokeStyle = "rgba(255, 200, 200, 0.85)";
    ctx.lineWidth = 2;
    draw();
    ctx.restore();
  }

  function emitMask() {
    const overlay = overlayRef.current;
    if (!overlay) return;
    // Build a binary white-on-black PNG sized to the source image.
    const out = document.createElement("canvas");
    out.width = overlay.width;
    out.height = overlay.height;
    const ctx = out.getContext("2d")!;
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, out.width, out.height);
    // Read overlay alpha + write white where alpha > 0
    const src = overlay.getContext("2d")!.getImageData(0, 0, overlay.width, overlay.height);
    const dst = ctx.getImageData(0, 0, out.width, out.height);
    for (let i = 0; i < src.data.length; i += 4) {
      if (src.data[i + 3] > 10) {
        dst.data[i] = 255;
        dst.data[i + 1] = 255;
        dst.data[i + 2] = 255;
        dst.data[i + 3] = 255;
      }
    }
    ctx.putImageData(dst, 0, 0);
    out.toBlob((blob) => onMaskChange(blob), "image/png");
    setMaskExists(true);
  }

  const onPointerDown = (e: React.PointerEvent) => {
    if (tool === "none") return;
    e.preventDefault();
    overlayRef.current?.setPointerCapture(e.pointerId);
    const p = pointFromEvent(e);
    setDrawing(true);
    setStart(p);
    setLast(p);
    if (tool === "lasso") setPath([p]);
  };

  const onPointerMove = (e: React.PointerEvent) => {
    if (!drawing || tool === "none") return;
    const draft = draftRef.current!;
    const ctx = draft.getContext("2d")!;
    ctx.clearRect(0, 0, draft.width, draft.height);
    const p = pointFromEvent(e);
    if (tool === "lasso") {
      const next = [...path, p];
      setPath(next);
      paintMaskShape(ctx, () => {
        ctx.beginPath();
        next.forEach((pt, i) => (i === 0 ? ctx.moveTo(pt.x, pt.y) : ctx.lineTo(pt.x, pt.y)));
        ctx.stroke();
      });
    } else if (tool === "rectangle" && start) {
      paintMaskShape(ctx, () => {
        ctx.strokeRect(start.x, start.y, p.x - start.x, p.y - start.y);
      });
    } else if (tool === "circle" && start) {
      const r = Math.hypot(p.x - start.x, p.y - start.y);
      paintMaskShape(ctx, () => {
        ctx.beginPath();
        ctx.arc(start.x, start.y, r, 0, Math.PI * 2);
        ctx.stroke();
      });
    }
    setLast(p);
  };

  const onPointerUp = (_e: React.PointerEvent) => {
    if (!drawing) return;
    setDrawing(false);
    const overlay = overlayRef.current!;
    const overlayCtx = overlay.getContext("2d")!;
    const draft = draftRef.current!;
    const draftCtx = draft.getContext("2d")!;
    if (tool === "lasso" && path.length > 2) {
      paintMaskShape(overlayCtx, () => {
        overlayCtx.beginPath();
        path.forEach((pt, i) => (i === 0 ? overlayCtx.moveTo(pt.x, pt.y) : overlayCtx.lineTo(pt.x, pt.y)));
        overlayCtx.closePath();
        overlayCtx.fill();
      });
    } else if (tool === "rectangle" && start && last) {
      paintMaskShape(overlayCtx, () => {
        overlayCtx.fillRect(start.x, start.y, last.x - start.x, last.y - start.y);
      });
    } else if (tool === "circle" && start && last) {
      const r = Math.hypot(last.x - start.x, last.y - start.y);
      paintMaskShape(overlayCtx, () => {
        overlayCtx.beginPath();
        overlayCtx.arc(start.x, start.y, r, 0, Math.PI * 2);
        overlayCtx.fill();
      });
    }
    draftCtx.clearRect(0, 0, draft.width, draft.height);
    setStart(null);
    setLast(null);
    setPath([]);
    emitMask();
  };

  return (
    <div className="relative inline-block bg-bg border border-border-dim rounded overflow-hidden max-w-full">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        ref={imgRef}
        src={pngUrl}
        onLoad={onLoad}
        alt={figure.alt_text ?? `Figure ${figure.id}`}
        className="block max-w-full h-auto select-none pointer-events-none"
        draggable={false}
      />
      {naturalDims && (
        <>
          <canvas
            ref={overlayRef}
            className="absolute inset-0 w-full h-full"
            style={{ pointerEvents: tool === "none" ? "none" : "auto", touchAction: "none" }}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerLeave={onPointerUp}
          />
          <canvas
            ref={draftRef}
            className="absolute inset-0 w-full h-full pointer-events-none"
          />
        </>
      )}
      {tool !== "none" && !maskExists && (
        <div className="absolute top-2 left-2 mono text-[10px] uppercase tracking-wider bg-bg/80 text-text-muted px-2 py-1 rounded">
          Drag to draw — Esc clears
        </div>
      )}
    </div>
  );
}
