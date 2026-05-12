"use client";

import { cn } from "@/lib/cn";

// Phase 14b (v1.0.1) — F-2 ANNOTATE mode toolbar.
//
// PEN / ARROW / TEXT / ERASER. Distinct from the MASK toolbar — these
// strokes do NOT trigger inpaint; they layer above the figure as
// metadata. ERASER selects whole strokes (NOT a pixel-eraser); the
// canvas does last-drawn-first hit testing on click.

export type AnnotateTool = "none" | "pen" | "arrow" | "text" | "eraser";

const TOOLS: { value: AnnotateTool; label: string; key: string; glyph: string }[] = [
  { value: "none",   label: "View",   key: "v", glyph: "" },
  { value: "pen",    label: "Pen",    key: "p", glyph: "✎" },
  { value: "arrow",  label: "Arrow",  key: "a", glyph: "→" },
  { value: "text",   label: "Text",   key: "t", glyph: "T" },
  { value: "eraser", label: "Eraser", key: "e", glyph: "⌫" },
];

const DEFAULT_COLORS = ["#ef4444", "#f59e0b", "#10b981", "#3b82f6", "#ffffff"] as const;

export type AnnotateToolsProps = {
  active: AnnotateTool;
  onChange: (t: AnnotateTool) => void;
  color: string;
  onColorChange: (c: string) => void;
  thickness: number;
  onThicknessChange: (n: number) => void;
  onClearAll: () => void;
  hasStrokes: boolean;
};

export function AnnotateTools({
  active,
  onChange,
  color,
  onColorChange,
  thickness,
  onThicknessChange,
  onClearAll,
  hasStrokes,
}: AnnotateToolsProps) {
  return (
    <div
      data-annotate-tools
      className="flex flex-wrap items-center gap-2"
    >
      <div className="flex items-center gap-1">
        {TOOLS.map((t) => (
          <button
            key={t.value}
            type="button"
            onClick={() => onChange(t.value)}
            data-annotate-tool={t.value}
            data-active={active === t.value ? "true" : "false"}
            title={`${t.label} (${t.key.toUpperCase()})`}
            className={cn(
              "text-xs mono uppercase tracking-wider px-2 py-1 border rounded inline-flex items-center gap-1",
              active === t.value
                ? "border-accent text-accent bg-accent-faint"
                : "border-border-dim text-text-dim hover:text-text hover:border-accent/50",
            )}
          >
            {t.glyph && <span className="text-[12px]">{t.glyph}</span>}
            <span>{t.label}</span>
          </button>
        ))}
      </div>

      <div className="flex items-center gap-1 border-l border-border-dim pl-2">
        {DEFAULT_COLORS.map((c) => (
          <button
            key={c}
            type="button"
            onClick={() => onColorChange(c)}
            data-annotate-color={c}
            data-active={color === c ? "true" : "false"}
            title={`Colour ${c}`}
            className={cn(
              "w-5 h-5 rounded border",
              color === c ? "border-accent" : "border-border-dim",
            )}
            style={{ backgroundColor: c }}
          />
        ))}
      </div>

      <label
        className="flex items-center gap-1 mono text-[10px] uppercase tracking-wider text-text-dim border-l border-border-dim pl-2"
        title="Stroke thickness (PEN + ARROW)"
      >
        <span>Thick</span>
        <input
          type="range"
          min={1}
          max={12}
          value={thickness}
          onChange={(e) => onThicknessChange(Number(e.target.value))}
          data-annotate-thickness
          className="w-24"
        />
        <span data-annotate-thickness-value className="tabular-nums w-6 text-text">
          {thickness}
        </span>
      </label>

      <button
        type="button"
        onClick={onClearAll}
        disabled={!hasStrokes}
        data-action="clear-annotations"
        title="Remove all annotation strokes"
        className="text-xs mono uppercase tracking-wider px-2 py-1 border border-border-dim text-text-dim hover:text-text rounded disabled:opacity-40 disabled:cursor-not-allowed"
      >
        Clear all
      </button>
    </div>
  );
}
