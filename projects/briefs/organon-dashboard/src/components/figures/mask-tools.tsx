"use client";

import { cn } from "@/lib/cn";

export type MaskTool = "circle" | "lasso" | "rectangle" | "none";

export type MaskToolsProps = {
  active: MaskTool;
  onChange: (t: MaskTool) => void;
  onClear: () => void;
  hasMask: boolean;
};

const TOOLS: { value: MaskTool; label: string; key: string }[] = [
  { value: "none",      label: "View",      key: "v" },
  { value: "circle",    label: "Circle",    key: "c" },
  { value: "lasso",     label: "Lasso",     key: "l" },
  { value: "rectangle", label: "Rectangle", key: "r" },
];

export function MaskTools({ active, onChange, onClear, hasMask }: MaskToolsProps) {
  return (
    <div className="flex items-center gap-1">
      {TOOLS.map((t) => (
        <button
          key={t.value}
          type="button"
          onClick={() => onChange(t.value)}
          title={`${t.label} (${t.key.toUpperCase()})`}
          className={cn(
            "text-xs mono uppercase tracking-wider px-2 py-1 border rounded",
            active === t.value
              ? "border-accent text-accent bg-accent-faint"
              : "border-border-dim text-text-dim hover:text-text hover:border-accent/50",
          )}
        >
          {t.label}
        </button>
      ))}
      <button
        type="button"
        onClick={onClear}
        disabled={!hasMask}
        title="Clear mask (Esc)"
        className="text-xs mono uppercase tracking-wider px-2 py-1 border border-border-dim text-text-dim hover:text-text rounded disabled:opacity-40 disabled:cursor-not-allowed"
      >
        Clear
      </button>
    </div>
  );
}
