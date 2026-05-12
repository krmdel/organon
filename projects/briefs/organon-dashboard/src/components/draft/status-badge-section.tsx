"use client";

import type { SectionStatus } from "@/lib/artifacts/types";
import { cn } from "@/lib/cn";

const TONE: Record<SectionStatus, string> = {
  draft:    "border-border-dim text-text-muted",
  reviewed: "border-accent text-accent",
  final:    "border-good text-good",
};

const NEXT: Record<SectionStatus, SectionStatus> = {
  draft: "reviewed",
  reviewed: "final",
  final: "draft",
};

export function StatusBadgeSection(props: {
  status: SectionStatus;
  onAdvance?: (next: SectionStatus) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => props.onAdvance && props.onAdvance(NEXT[props.status])}
      disabled={!props.onAdvance}
      className={cn(
        "mono text-[10px] uppercase tracking-wider px-1.5 py-0.5 border rounded",
        TONE[props.status],
        props.onAdvance && "hover:opacity-80 cursor-pointer",
      )}
      title={props.onAdvance ? `Click to advance to ${NEXT[props.status]}` : undefined}
    >
      {props.status}
    </button>
  );
}
