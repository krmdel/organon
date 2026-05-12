"use client";

/**
 * Phase 14a (v1.0.1) — F-4 figures guided-flow step indicator.
 *
 * Five canonical steps across the top of /figures:
 *   1. Generate · 2. Mask · 3. Edit prompt · 4. Apply edit · 5. Lock + caption
 *
 * Each step renders as a chip with three states: complete (✓), available
 * (filled), or locked (dim). The indicator is purely visualisation —
 * the workspace already enforces progressive disclosure; this surface
 * just exposes the implicit state to the user so they know where they
 * are in the flow at a glance.
 */

export type Step = {
  /** Display label — short, fits in a chip. */
  label: string;
  /** This step has been completed for the active figure. */
  complete: boolean;
  /** This step is reachable from the current state. */
  available: boolean;
};

export const FIGURE_STEP_LABELS = [
  "Generate",
  "Mask",
  "Edit prompt",
  "Apply edit",
  "Lock + caption",
] as const;

export type StepIndicatorProps = {
  steps: Step[];
  /** 1-indexed currently-focused step. Optional — derived from the
   *  first non-complete + available step if omitted. */
  currentStep?: number;
};

export function StepIndicator({ steps, currentStep }: StepIndicatorProps) {
  // Derive the focused step when the caller doesn't pin one. Prefer
  // the first available-but-not-complete step; fall back to the last
  // complete step; default to 1.
  const focused =
    currentStep ??
    (() => {
      const idx = steps.findIndex((s) => s.available && !s.complete);
      if (idx >= 0) return idx + 1;
      const lastComplete = steps.map((s) => s.complete).lastIndexOf(true);
      return lastComplete >= 0 ? lastComplete + 1 : 1;
    })();

  return (
    <ol
      data-step-indicator
      data-current-step={focused}
      className="flex items-stretch gap-2 mb-5"
    >
      {steps.map((step, i) => {
        const idx = i + 1;
        const state = step.complete
          ? "complete"
          : step.available
            ? "available"
            : "locked";
        const isFocused = focused === idx;
        const stateClass =
          state === "complete"
            ? "border-good text-good bg-good/5"
            : state === "available"
              ? isFocused
                ? "border-accent text-accent bg-accent/5"
                : "border-accent/60 text-accent/80"
              : "border-border-dim text-text-muted opacity-60";
        return (
          <li
            key={step.label}
            data-step-index={idx}
            data-step-state={state}
            data-step-focused={isFocused ? "true" : "false"}
            className={`flex-1 min-w-0 border rounded px-3 py-2 mono text-[10px] uppercase tracking-wider flex items-center gap-2 ${stateClass}`}
          >
            <span
              data-step-marker
              className="inline-flex items-center justify-center w-5 h-5 rounded-full border border-current text-[10px] flex-shrink-0"
            >
              {step.complete ? "✓" : idx}
            </span>
            <span className="truncate">{step.label}</span>
          </li>
        );
      })}
    </ol>
  );
}
