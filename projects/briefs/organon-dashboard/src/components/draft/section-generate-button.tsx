"use client";

import { cn } from "@/lib/cn";

/**
 * Phase 10 (v1.0.1) — DR-3 per-section "Generate with AI" button.
 *
 * Visually distinct from StatusBadgeSection (which is a small chip
 * advancing draft → reviewed → final) — this button uses the accent
 * palette + a wand glyph + the literal label "Generate" to read as
 * an action affordance, not a state indicator. Test
 * `section-generate-button is visually distinct from the status badge`
 * pins this contract.
 *
 * The button is presentational: the parent workspace owns the SSE
 * and the section refresh after the route persists. While the run is
 * in flight the parent passes `running={true}` so the button shows a
 * pulsing spinner and self-disables.
 */

export type SectionGenerateButtonProps = {
  sectionId: string;
  onGenerate: (sectionId: string) => void;
  running?: boolean;
  disabled?: boolean;
  className?: string;
};

export function SectionGenerateButton({
  sectionId,
  onGenerate,
  running,
  disabled,
  className,
}: SectionGenerateButtonProps) {
  return (
    <button
      type="button"
      data-section-generate-button
      data-running={running ? "true" : "false"}
      onClick={(e) => {
        e.stopPropagation();
        if (!running && !disabled) onGenerate(sectionId);
      }}
      disabled={disabled || running}
      aria-label={`Generate ${sectionId} with AI`}
      title="Generate this section with AI from linked papers + stats + figures"
      className={cn(
        "inline-flex items-center gap-1 rounded border px-2 py-0.5 mono text-[10px] uppercase tracking-wider transition-colors",
        running
          ? "border-accent text-accent bg-accent-faint animate-pulse"
          : "border-accent/60 text-accent hover:bg-accent-faint",
        (disabled || running) && "cursor-not-allowed opacity-80",
        className,
      )}
    >
      <WandGlyph />
      <span>{running ? "Generating…" : "Generate"}</span>
    </button>
  );
}

function WandGlyph() {
  return (
    <svg
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="size-3 shrink-0"
    >
      <path d="M3 13l8-8" />
      <path d="M11 5l1-1 1 1-1 1z" />
      <path d="M14 8l-1 1M8 2l-1 1" />
      <circle cx="13.5" cy="2.5" r="0.5" fill="currentColor" />
      <circle cx="2.5" cy="9.5" r="0.5" fill="currentColor" />
    </svg>
  );
}
