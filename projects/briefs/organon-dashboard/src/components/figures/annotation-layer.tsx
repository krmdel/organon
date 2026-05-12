"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { FigureArtifact } from "@/lib/artifacts/types";
import type { AnnotationStroke, Pt } from "@/lib/figures/annotations";
import type { AnnotateTool } from "./annotate-tools";

// Phase 14b (v1.0.1) — F-2 annotation rendering + drawing.
//
// SVG-based layer above the figure. PEN draws a polyline as the user
// drags; ARROW emits a line + arrowhead on pointer-up; TEXT prompts
// for the string on click; ERASER removes the topmost stroke under
// the click via last-drawn-first hit test.
//
// ANNOTATE mode is mutually exclusive with EDIT WITH AI mode at the
// workspace level. This component does NOT interact with the FAL Fill
// pipeline — strokes are pure metadata.

export type AnnotationLayerProps = {
  figure: FigureArtifact;
  pngUrl: string;
  tool: AnnotateTool;
  color: string;
  thickness: number;
  strokes: AnnotationStroke[];
  onChange: (next: AnnotationStroke[]) => void;
};

const ARROW_HEAD_LENGTH = 14;

function newId(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.floor(Math.random() * 1e6).toString(36)}`;
}

function dist(a: Pt, b: Pt): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function distToSegment(p: Pt, a: Pt, b: Pt): number {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  if (dx === 0 && dy === 0) return dist(p, a);
  const t = Math.max(0, Math.min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / (dx * dx + dy * dy)));
  return dist(p, { x: a.x + t * dx, y: a.y + t * dy });
}

// Last-drawn-first hit test. Returns the stroke index to delete (or -1).
export function pickStrokeForErase(
  strokes: AnnotationStroke[],
  click: Pt,
  imgW: number,
  imgH: number,
): number {
  // Tolerance grows with image size so an eraser click on a 4K render
  // stays usable; capped to avoid runaway radius on tiny images.
  const tol = Math.max(8, Math.min(24, Math.max(imgW, imgH) / 80));
  for (let i = strokes.length - 1; i >= 0; i--) {
    const s = strokes[i];
    if (s.kind === "pen") {
      for (let j = 0; j < s.points.length - 1; j++) {
        if (distToSegment(click, s.points[j], s.points[j + 1]) <= tol + s.thickness / 2) {
          return i;
        }
      }
    } else if (s.kind === "arrow") {
      if (distToSegment(click, s.from, s.to) <= tol + s.thickness / 2) {
        return i;
      }
    } else if (s.kind === "text") {
      // Approximate text bbox — height ~= size, width ~= 0.6 * size *
      // chars. Coarse but enough for the picker.
      const w = Math.max(20, 0.6 * s.size * s.text.length);
      if (
        click.x >= s.at.x - tol &&
        click.x <= s.at.x + w + tol &&
        click.y >= s.at.y - s.size - tol &&
        click.y <= s.at.y + tol
      ) {
        return i;
      }
    }
  }
  return -1;
}

export function AnnotationLayer({
  figure,
  pngUrl,
  tool,
  color,
  thickness,
  strokes,
  onChange,
}: AnnotationLayerProps) {
  const imgRef = useRef<HTMLImageElement | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [naturalDims, setNaturalDims] = useState<{ w: number; h: number } | null>(null);
  const [drafting, setDrafting] = useState<AnnotationStroke | null>(null);

  const onLoad = useCallback(() => {
    const img = imgRef.current;
    if (!img) return;
    setNaturalDims({ w: img.naturalWidth || img.width, h: img.naturalHeight || img.height });
  }, []);

  const pointFromEvent = useCallback((e: React.PointerEvent | React.MouseEvent): Pt => {
    const svg = svgRef.current!;
    const rect = svg.getBoundingClientRect();
    const dims = naturalDims ?? { w: rect.width, h: rect.height };
    return {
      x: ((e.clientX - rect.left) / rect.width) * dims.w,
      y: ((e.clientY - rect.top) / rect.height) * dims.h,
    };
  }, [naturalDims]);

  const onPointerDown = (e: React.PointerEvent) => {
    if (tool === "none" || !naturalDims) return;
    const p = pointFromEvent(e);
    if (tool === "pen") {
      svgRef.current?.setPointerCapture(e.pointerId);
      setDrafting({
        kind: "pen",
        id: newId("pen"),
        color,
        thickness,
        points: [p],
        t: new Date().toISOString(),
      });
    } else if (tool === "arrow") {
      svgRef.current?.setPointerCapture(e.pointerId);
      setDrafting({
        kind: "arrow",
        id: newId("arrow"),
        color,
        thickness,
        from: p,
        to: p,
        t: new Date().toISOString(),
      });
    } else if (tool === "text") {
      const text = typeof window !== "undefined" ? window.prompt("Annotation text:", "") : null;
      if (!text || !text.trim()) return;
      const next: AnnotationStroke = {
        kind: "text",
        id: newId("text"),
        color,
        size: Math.max(14, thickness * 4),
        at: p,
        text: text.trim(),
        t: new Date().toISOString(),
      };
      onChange([...strokes, next]);
    } else if (tool === "eraser") {
      const idx = pickStrokeForErase(strokes, p, naturalDims.w, naturalDims.h);
      if (idx >= 0) {
        const next = strokes.slice();
        next.splice(idx, 1);
        onChange(next);
      }
    }
  };

  const onPointerMove = (e: React.PointerEvent) => {
    if (!drafting) return;
    const p = pointFromEvent(e);
    if (drafting.kind === "pen") {
      setDrafting({ ...drafting, points: [...drafting.points, p] });
    } else if (drafting.kind === "arrow") {
      setDrafting({ ...drafting, to: p });
    }
  };

  const onPointerUp = () => {
    if (!drafting) return;
    if (drafting.kind === "pen" && drafting.points.length < 2) {
      setDrafting(null);
      return;
    }
    if (drafting.kind === "arrow" && dist(drafting.from, drafting.to) < 4) {
      setDrafting(null);
      return;
    }
    onChange([...strokes, drafting]);
    setDrafting(null);
  };

  // Reset drafting when the figure version changes.
  useEffect(() => {
    setDrafting(null);
  }, [figure.id, figure.version]);

  const renderStrokes = drafting ? [...strokes, drafting] : strokes;

  return (
    <div
      data-annotation-layer
      className="relative inline-block bg-bg border border-border-dim rounded overflow-hidden max-w-full"
    >
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
        <svg
          ref={svgRef}
          viewBox={`0 0 ${naturalDims.w} ${naturalDims.h}`}
          preserveAspectRatio="none"
          className="absolute inset-0 w-full h-full"
          style={{
            pointerEvents: tool === "none" ? "none" : "auto",
            touchAction: "none",
            cursor: tool === "eraser" ? "not-allowed" : tool === "text" ? "text" : "crosshair",
          }}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerLeave={onPointerUp}
        >
          {renderStrokes.map((s) => {
            if (s.kind === "pen") {
              const d = s.points
                .map((p, i) => `${i === 0 ? "M" : "L"}${p.x},${p.y}`)
                .join(" ");
              return (
                <path
                  key={s.id}
                  data-stroke-id={s.id}
                  data-stroke-kind="pen"
                  d={d}
                  stroke={s.color}
                  strokeWidth={s.thickness}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  fill="none"
                />
              );
            }
            if (s.kind === "arrow") {
              const dx = s.to.x - s.from.x;
              const dy = s.to.y - s.from.y;
              const len = Math.hypot(dx, dy) || 1;
              const ux = dx / len;
              const uy = dy / len;
              const perpX = -uy;
              const perpY = ux;
              const headBaseX = s.to.x - ux * ARROW_HEAD_LENGTH;
              const headBaseY = s.to.y - uy * ARROW_HEAD_LENGTH;
              const headHalf = ARROW_HEAD_LENGTH * 0.5;
              return (
                <g key={s.id} data-stroke-id={s.id} data-stroke-kind="arrow">
                  <line
                    x1={s.from.x}
                    y1={s.from.y}
                    x2={s.to.x}
                    y2={s.to.y}
                    stroke={s.color}
                    strokeWidth={s.thickness}
                    strokeLinecap="round"
                  />
                  <polygon
                    points={`${s.to.x},${s.to.y} ${headBaseX + perpX * headHalf},${headBaseY + perpY * headHalf} ${headBaseX - perpX * headHalf},${headBaseY - perpY * headHalf}`}
                    fill={s.color}
                  />
                </g>
              );
            }
            if (s.kind === "text") {
              return (
                <text
                  key={s.id}
                  data-stroke-id={s.id}
                  data-stroke-kind="text"
                  x={s.at.x}
                  y={s.at.y}
                  fill={s.color}
                  fontSize={s.size}
                  fontFamily="ui-sans-serif, system-ui, -apple-system"
                >
                  {s.text}
                </text>
              );
            }
            return null;
          })}
        </svg>
      )}
      {tool !== "none" && (
        <div className="absolute top-2 left-2 mono text-[10px] uppercase tracking-wider bg-bg/80 text-text-muted px-2 py-1 rounded">
          {tool === "eraser"
            ? "Click a stroke to remove"
            : tool === "text"
              ? "Click to drop text"
              : "Drag to draw"}
        </div>
      )}
    </div>
  );
}
