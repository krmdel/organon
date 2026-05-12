"use client";

import { cn } from "@/lib/cn";

/**
 * Phase 4 (fix-sprint) — surface the current runner state for any SSE
 * flow. Replaces the silent-spinner-then-nothing UX called out by the
 * dogfood Finding #14: claude -p died at 3:35 with no UI feedback.
 *
 * State machine:
 *   idle      → nothing rendered (caller may show its empty state)
 *   running   → spinner + elapsed counter + Cancel button
 *   succeeded → green check + brief detail; usually transient (caller
 *               typically swaps in the artifact card on success)
 *   failed    → red border + reason + Retry button
 *   timeout   → orange border + "Timed out after Xm" + Retry button
 *   cancelled → grey + "Cancelled by you" + Retry button
 */

export type RunState =
  | "idle"
  | "running"
  | "succeeded"
  | "failed"
  | "timeout"
  | "cancelled";

export type RunStateCardProps = {
  state: RunState;
  /** When state === running, milliseconds since start (UI shows mm:ss). */
  elapsedMs?: number;
  /** Free-form message — failure-mode reason copy or skill-emitted detail. */
  message?: string;
  /** Skill or operation label, shown in the header (e.g. "council fanout"). */
  label?: string;
  /** When provided, called for state="running" Cancel button. */
  onCancel?: () => void;
  /** When provided, called for failed/timeout/cancelled "Retry" button. */
  onRetry?: () => void;
  /** When provided, called for failed/timeout "Dismiss" button. */
  onDismiss?: () => void;
  /** Shown small under the message — typically the run id for /runs link. */
  runId?: string;
  className?: string;
};

export function RunStateCard({
  state,
  elapsedMs,
  message,
  label,
  onCancel,
  onRetry,
  onDismiss,
  runId,
  className,
}: RunStateCardProps) {
  if (state === "idle") return null;

  const palette = paletteFor(state);
  return (
    <div
      role={state === "failed" || state === "timeout" ? "alert" : "status"}
      aria-live={state === "failed" || state === "timeout" ? "assertive" : "polite"}
      data-run-state={state}
      className={cn(
        "flex items-start gap-3 rounded-md border p-3 text-sm",
        palette.container,
        className,
      )}
    >
      <div className={cn("mt-0.5 size-4 shrink-0", palette.icon)}>
        {state === "running" ? <Spinner /> : <StateGlyph state={state} />}
      </div>
      <div className="min-w-0 flex-1">
        <div className={cn("font-medium", palette.title)}>
          {titleFor(state, label)}
          {state === "running" && elapsedMs != null ? (
            <span className="ml-2 font-mono text-xs text-text-dim">
              {formatElapsed(elapsedMs)}
            </span>
          ) : null}
        </div>
        {message ? (
          <div className={cn("mt-0.5 break-words", palette.body)}>{message}</div>
        ) : null}
        {runId ? (
          <div className="mt-1 font-mono text-[11px] text-text-dim">run · {runId}</div>
        ) : null}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {state === "running" && onCancel ? (
          <button
            type="button"
            onClick={onCancel}
            className="rounded border border-border-dim px-2 py-0.5 text-xs text-text-dim hover:bg-bg-elev"
          >
            Cancel
          </button>
        ) : null}
        {(state === "failed" || state === "timeout" || state === "cancelled") && onRetry ? (
          <button
            type="button"
            onClick={onRetry}
            className="rounded border border-border-dim px-2 py-0.5 text-xs text-text hover:bg-bg-elev"
          >
            Retry
          </button>
        ) : null}
        {(state === "failed" || state === "timeout") && onDismiss ? (
          <button
            type="button"
            onClick={onDismiss}
            className="rounded px-2 py-0.5 text-xs text-text-dim hover:bg-bg-elev"
          >
            Dismiss
          </button>
        ) : null}
      </div>
    </div>
  );
}

function paletteFor(state: RunState) {
  switch (state) {
    case "running":
      return {
        container: "border-border-dim bg-bg-soft",
        icon: "text-text-dim",
        title: "text-text",
        body: "text-text-dim",
      };
    case "succeeded":
      return {
        container: "border-green-500/40 bg-green-500/5",
        icon: "text-green-400",
        title: "text-green-300",
        body: "text-text-dim",
      };
    case "failed":
      return {
        container: "border-red-500/50 bg-red-500/5",
        icon: "text-red-400",
        title: "text-red-300",
        body: "text-red-200/90",
      };
    case "timeout":
      return {
        container: "border-orange-500/50 bg-orange-500/5",
        icon: "text-orange-400",
        title: "text-orange-300",
        body: "text-orange-200/90",
      };
    case "cancelled":
      return {
        container: "border-border-dim bg-bg-soft",
        icon: "text-text-dim",
        title: "text-text",
        body: "text-text-dim",
      };
    default:
      return { container: "", icon: "", title: "", body: "" };
  }
}

function titleFor(state: RunState, label?: string): string {
  const base =
    state === "running" ? "Running" :
    state === "succeeded" ? "Done" :
    state === "failed" ? "Failed" :
    state === "timeout" ? "Timed out" :
    state === "cancelled" ? "Cancelled" : "";
  return label ? `${base} · ${label}` : base;
}

function formatElapsed(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function Spinner() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
         className="animate-spin">
      <circle cx="12" cy="12" r="9" strokeOpacity="0.25" />
      <path d="M21 12a9 9 0 0 0-9-9" strokeLinecap="round" />
    </svg>
  );
}

function StateGlyph({ state }: { state: RunState }) {
  if (state === "succeeded") {
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
        <path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  if (state === "failed" || state === "timeout") {
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
        <path d="M12 9v4M12 17h.01" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="12" cy="12" r="9" strokeOpacity="0.7" />
      </svg>
    );
  }
  if (state === "cancelled") {
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
        <circle cx="12" cy="12" r="9" strokeOpacity="0.7" />
        <path d="M9 9l6 6M15 9l-6 6" strokeLinecap="round" />
      </svg>
    );
  }
  return null;
}
