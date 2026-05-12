"use client";

import { useEffect, useRef, useState } from "react";
import type { HypothesisStatus } from "@/lib/artifacts/types";
import { cn } from "@/lib/cn";

const STATUS_LABEL: Record<HypothesisStatus, string> = {
  open: "open",
  synthesized: "synthesized",
  supported: "supported",
  refuted: "refuted",
  archived: "archived",
};

const STATUS_CLASS: Record<HypothesisStatus, string> = {
  open: "border-accent text-accent",
  synthesized: "border-violet-400 text-violet-300",
  supported: "border-good text-good",
  refuted: "border-danger text-danger",
  archived: "border-border text-text-muted",
};

export type StatusBadgeProps = {
  status: HypothesisStatus;
  /** When provided, renders an interactive dropdown of valid D6 transitions. */
  onChange?: (next: HypothesisStatus) => void;
  /** Manual override of which transitions are valid. Defaults to D6 user-only set. */
  options?: HypothesisStatus[];
  size?: "sm" | "md";
};

export function StatusBadge({ status, onChange, options, size = "sm" }: StatusBadgeProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const validOptions =
    options ?? defaultUserTransitions(status).filter((s) => s !== status);

  const padding = size === "md" ? "px-2.5 py-1" : "px-2 py-0.5";

  if (!onChange) {
    return (
      <span
        className={cn(
          "inline-flex items-center border rounded mono uppercase tracking-wider",
          padding,
          size === "md" ? "text-[11px]" : "text-[10px]",
          STATUS_CLASS[status],
        )}
      >
        {STATUS_LABEL[status]}
      </span>
    );
  }

  return (
    <div className="relative inline-block" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "inline-flex items-center border rounded mono uppercase tracking-wider transition",
          padding,
          size === "md" ? "text-[11px]" : "text-[10px]",
          STATUS_CLASS[status],
          "hover:bg-bg-soft",
        )}
      >
        {STATUS_LABEL[status]} ▾
      </button>
      {open && (
        <div className="absolute z-20 top-full mt-1 right-0 min-w-[10rem] bg-bg-elev border border-border rounded shadow-lg py-1">
          {validOptions.length === 0 && (
            <div className="px-3 py-1 text-xs text-text-muted mono">No transitions</div>
          )}
          {validOptions.map((opt) => (
            <button
              key={opt}
              onClick={() => {
                onChange(opt);
                setOpen(false);
              }}
              className="w-full text-left px-3 py-1 text-xs mono uppercase tracking-wider hover:bg-bg-soft text-text-dim hover:text-text"
            >
              → {STATUS_LABEL[opt]}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/** D6 user-only transitions. Skill transitions (open → synthesized) excluded. */
function defaultUserTransitions(from: HypothesisStatus): HypothesisStatus[] {
  if (from === "open") return ["archived"];
  if (from === "synthesized") return ["supported", "refuted", "archived"];
  if (from === "supported" || from === "refuted") return ["synthesized", "archived"];
  if (from === "archived") return [];
  return [];
}
