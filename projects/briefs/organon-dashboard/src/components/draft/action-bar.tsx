"use client";

import type { SectionAction } from "@/lib/artifacts/types";
import { cn } from "@/lib/cn";

export type ActionBarProps = {
  onFire: (action: SectionAction) => void;
  isRunning: SectionAction | null;
  disabled?: boolean;
};

const ACTIONS: { value: SectionAction; label: string; hint: string }[] = [
  { value: "rewrite",  label: "Rewrite",  hint: "Re-clarity (sci-writing)" },
  { value: "tighten",  label: "Tighten",  hint: "Cut 15-25% (sci-writing)" },
  { value: "check",    label: "Check claims", hint: "Inline audit (sci-writing)" },
  { value: "humanize", label: "Humanize", hint: "Strip AI tells (tool-humanizer)" },
];

export function ActionBar({ onFire, isRunning, disabled }: ActionBarProps) {
  return (
    <div className="flex flex-wrap gap-1.5 px-3 py-2 border-t border-border-dim bg-bg-elev">
      {ACTIONS.map((a) => {
        const running = isRunning === a.value;
        const otherRunning = isRunning !== null && isRunning !== a.value;
        return (
          <button
            key={a.value}
            type="button"
            onClick={() => onFire(a.value)}
            disabled={disabled || running || otherRunning}
            title={a.hint}
            className={cn(
              "text-xs mono uppercase tracking-wider px-2.5 py-1 border rounded",
              running
                ? "border-accent text-accent bg-accent-faint"
                : "border-border-dim text-text-dim hover:text-text hover:border-accent/50",
              (disabled || otherRunning) && "opacity-50 cursor-not-allowed",
            )}
          >
            {running ? `${a.label}…` : a.label}
          </button>
        );
      })}
    </div>
  );
}
