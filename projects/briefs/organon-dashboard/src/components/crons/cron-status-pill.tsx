"use client";

import type { CronJobStatus } from "@/lib/crons/reader";
import { cn } from "@/lib/cn";

const TONE: Record<string, string> = {
  success: "border-good text-good",
  failure: "border-danger text-danger",
  running: "border-accent text-accent",
  unknown: "border-border-dim text-text-muted",
};

export function CronStatusPill(props: { status: CronJobStatus | null; active: boolean }) {
  const result = props.status?.result ?? "unknown";
  const tone = TONE[result] ?? TONE.unknown;
  const label = props.active ? result : "disabled";
  return (
    <span
      className={cn(
        "mono text-[10px] uppercase tracking-wider px-1.5 py-0.5 border rounded",
        props.active ? tone : "border-border-dim text-text-muted",
      )}
    >
      {label}
    </span>
  );
}
