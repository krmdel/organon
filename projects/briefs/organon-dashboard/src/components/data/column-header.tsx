"use client";

import { useState } from "react";
import type { ColumnStats, ColumnType, DataframeColumn } from "@/lib/artifacts/types";
import { cn } from "@/lib/cn";

export type ColumnHeaderProps = {
  column: DataframeColumn;
  onChangeType?: (next: ColumnType) => void;
  busy?: boolean;
};

const TYPE_OPTIONS: { value: ColumnType; label: string; tone: string }[] = [
  { value: "numeric", label: "num", tone: "text-accent" },
  { value: "categorical", label: "cat", tone: "text-good" },
  { value: "datetime", label: "date", tone: "text-text" },
  { value: "text", label: "txt", tone: "text-text-dim" },
];

function statsLine(type: ColumnType, stats: ColumnStats): string {
  if (type === "numeric") {
    const s = stats as { count: number; mean?: number | null; min?: number | null; max?: number | null };
    const mean = s.mean ?? null;
    const min = s.min ?? null;
    const max = s.max ?? null;
    const parts: string[] = [];
    if (min !== null && max !== null) parts.push(`${min}–${max}`);
    if (mean !== null) parts.push(`μ ${Number(mean).toFixed(2)}`);
    return parts.join(" · ");
  }
  if (type === "categorical") {
    const s = stats as { unique_count: number; top: [string, number][] };
    const tops = s.top.slice(0, 2).map(([k, v]) => `${k}(${v})`).join(", ");
    return `${s.unique_count} uniq${tops ? ` · ${tops}` : ""}`;
  }
  if (type === "datetime") {
    const s = stats as { min?: string | null; max?: string | null };
    return [s.min, s.max].filter(Boolean).join(" → ");
  }
  const s = stats as { count: number; unique_count?: number; avg_length?: number };
  const parts: string[] = [];
  if (s.unique_count != null) parts.push(`${s.unique_count} uniq`);
  if (s.avg_length != null) parts.push(`avg ${s.avg_length} ch`);
  return parts.join(" · ");
}

export function ColumnHeader({ column, onChangeType, busy }: ColumnHeaderProps) {
  const [open, setOpen] = useState(false);
  const tone = TYPE_OPTIONS.find((o) => o.value === column.type)?.tone ?? "text-text-dim";

  return (
    <div className="flex flex-col gap-0.5 py-2 px-3 text-left whitespace-nowrap">
      <div className="flex items-center gap-2">
        <span className="text-sm text-text font-medium">{column.name}</span>
        <button
          type="button"
          onClick={() => onChangeType && setOpen((o) => !o)}
          disabled={busy || !onChangeType}
          className={cn(
            "mono text-[10px] uppercase tracking-wider px-1.5 py-0.5 border border-border-dim rounded",
            tone,
            onChangeType && "hover:border-accent cursor-pointer",
          )}
          title={
            onChangeType
              ? `Inferred ${column.type_inferred_by} — click to override`
              : column.type
          }
        >
          {column.type}
        </button>
        {column.null_count > 0 && (
          <span className="mono text-[10px] text-text-muted">
            {column.null_count} null
          </span>
        )}
      </div>
      <div className="mono text-[10px] text-text-muted">
        {statsLine(column.type, column.stats)}
      </div>
      {open && onChangeType && (
        <div className="mt-1 flex gap-1">
          {TYPE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => {
                setOpen(false);
                if (opt.value !== column.type) onChangeType(opt.value);
              }}
              className={cn(
                "mono text-[10px] uppercase px-1.5 py-0.5 border rounded",
                opt.value === column.type
                  ? "border-accent text-accent"
                  : "border-border-dim text-text-dim hover:text-text",
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
