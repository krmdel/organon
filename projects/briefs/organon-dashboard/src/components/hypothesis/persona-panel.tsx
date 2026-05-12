"use client";

import { useState } from "react";
import type { PaperArtifact, PersonaCritiqueArtifact } from "@/lib/artifacts/types";
import type { Persona } from "@/lib/hypothesis/shared";
import { isPersonaActive, slugifyPersona } from "@/lib/hypothesis/shared";
import { cn } from "@/lib/cn";

export type PersonaPanelProps = {
  persona: Persona;
  critique: PersonaCritiqueArtifact | null;
  isRunning: boolean;
  /**
   * Phase 13b (v1.0.1) — H-5 + U4 per-persona retry. Caller fires the
   * /retry-persona route + drains the SSE; we just emit the user
   * intent and reflect the retry-in-flight state.
   */
  onRetryPersona?: (personaSlug: string) => void;
  /** Persona slug whose retry is in-flight (or null). Disables retry. */
  retryingSlug?: string | null;
  /**
   * Phase 43 (v1.5) — F6 per-persona discard. When excluded === true,
   * the panel renders dimmed with a strike-through claim header + a
   * "Restore" affordance in place of the "Discard" one. Reversible —
   * the on-disk critique never moves.
   */
  excluded?: boolean;
  onToggleDiscard?: (personaSlug: string, next: boolean) => void;
  /**
   * Phase 48 (v1.6) — F11: deep-research papers this persona pulled in
   * via the per-persona literature search (skeptic → refute, methodologist →
   * measurement, domain-expert → consensus). Optional — pre-Phase-48
   * hypotheses + personas without a deep-research run yet pass null.
   */
  additionalPapers?: PaperArtifact[] | null;
  onOpenPaper?: (paper: PaperArtifact) => void;
};

const CONFIDENCE_CLASS: Record<"high" | "medium" | "low", string> = {
  high: "border-good text-good",
  medium: "border-accent text-accent",
  low: "border-warn text-warn",
};

// Phase 13b (v1.0.1) — H-5 emptiness detection. A persona's critique is
// empty when none of the structured fields carry content; the SSE
// stream emitted the artifact but the skill returned a hollow shell.
// The retry surface treats empty-critique the same as missing-critique.
export function isCritiqueEmpty(c: PersonaCritiqueArtifact | null): boolean {
  if (!c) return false; // missing is a separate case
  return (
    (c.critiques?.length ?? 0) === 0 &&
    (c.counter_evidence?.length ?? 0) === 0 &&
    (c.suggested_experiments?.length ?? 0) === 0
  );
}

export function PersonaPanel({
  persona,
  critique,
  isRunning,
  onRetryPersona,
  retryingSlug,
  excluded = false,
  onToggleDiscard,
  additionalPapers,
  onOpenPaper,
}: PersonaPanelProps) {
  const [showRaw, setShowRaw] = useState(false);
  const avatar = persona.avatar ?? persona.name.slice(0, 1).toUpperCase();
  // Phase 13b — `slug` is recomputed here rather than passed in so the
  // retry contract stays slug-driven from one source of truth (shared
  // slugifyPersona). The critique's persona_slug is also load-bearing
  // when a critique exists.
  const slug = critique?.persona_slug ?? slugifyPersona(persona.name);
  const personaActive = isPersonaActive(persona);
  const empty = isCritiqueEmpty(critique);
  const missing = !critique && !isRunning;
  const showRetry = personaActive && (empty || missing) && !!onRetryPersona;
  const retryInFlight = retryingSlug === slug;
  // Phase 43 (v1.5) — F6: discard affordance is only meaningful when a
  // critique exists (excluding a missing critique is a no-op). The
  // button stays visible while running so the user can mark a persona
  // for exclusion mid-fan-out.
  const showDiscard = !!onToggleDiscard && (critique != null || excluded);

  return (
    <div
      className={cn(
        "border border-border-dim rounded bg-bg-elev flex flex-col min-h-[20rem]",
        excluded && "opacity-50",
      )}
      data-discarded={excluded ? "true" : "false"}
      data-persona-slug={slug}
    >
      <header className="px-4 py-3 border-b border-border-dim flex items-center gap-3">
        <div className="w-8 h-8 rounded-full border border-accent text-accent flex items-center justify-center mono text-sm font-semibold">
          {avatar}
        </div>
        <div className="flex-1 min-w-0">
          <div
            className={cn(
              "text-sm font-semibold leading-tight",
              excluded && "line-through",
            )}
          >
            {persona.name}
          </div>
          {persona.role && (
            <div className="text-[10px] text-text-muted truncate">{persona.role}</div>
          )}
        </div>
        {critique && !excluded && (
          <span
            className={cn(
              "border rounded mono text-[10px] uppercase tracking-wider px-2 py-0.5",
              CONFIDENCE_CLASS[critique.confidence],
            )}
          >
            {critique.confidence}
          </span>
        )}
        {showDiscard && (
          <button
            type="button"
            onClick={() => onToggleDiscard?.(slug, !excluded)}
            data-action="persona-discard"
            data-persona-slug={slug}
            title={
              excluded
                ? `Restore ${persona.name} into the synthesis`
                : `Discard ${persona.name} before synthesis (reversible)`
            }
            className="mono text-[10px] uppercase tracking-wider px-2 py-0.5 border border-border-dim rounded text-text-dim hover:text-text hover:border-text"
          >
            {excluded ? "Restore" : "Discard"}
          </button>
        )}
      </header>

      <div className="flex-1 overflow-auto p-4 space-y-4">
        {!critique && isRunning && (
          <div className="flex flex-col items-center justify-center h-full gap-2 text-text-muted">
            <div className="w-6 h-6 border-2 border-accent border-t-transparent rounded-full animate-spin" />
            <span className="mono text-[10px] uppercase tracking-wider">
              Awaiting {persona.name}…
            </span>
          </div>
        )}
        {!critique && !isRunning && (
          <div className="text-text-muted text-xs italic text-center py-6 space-y-3">
            <div>No critique returned for {persona.name}.</div>
            {showRetry && (
              <button
                onClick={() => onRetryPersona?.(slug)}
                disabled={retryInFlight}
                data-action="retry-persona"
                data-persona-slug={slug}
                className="mono text-[10px] uppercase tracking-wider px-3 py-1.5 border border-accent rounded text-accent hover:bg-accent hover:text-bg transition disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {retryInFlight ? "Retrying…" : `Retry ${persona.name}`}
              </button>
            )}
          </div>
        )}
        {critique && empty && showRetry && (
          <div
            data-empty-critique
            className="border border-warn/40 rounded bg-warn/5 p-3 mono text-[10px] uppercase tracking-wider text-text-dim flex items-center justify-between gap-2"
          >
            <span>Empty critique — skill returned a hollow shell</span>
            <button
              onClick={() => onRetryPersona?.(slug)}
              disabled={retryInFlight}
              data-action="retry-persona"
              data-persona-slug={slug}
              className="px-3 py-1 border border-accent rounded text-accent hover:bg-accent hover:text-bg transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {retryInFlight ? "Retrying…" : `Retry ${persona.name}`}
            </button>
          </div>
        )}
        {critique && (
          <>
            <Section title="Critiques" items={critique.critiques} />
            <Section title="Counter-evidence" items={critique.counter_evidence} />
            <Section
              title="Suggested experiments"
              items={critique.suggested_experiments}
              ordered
            />
            {critique.raw_council_block && (
              <div>
                <button
                  onClick={() => setShowRaw((s) => !s)}
                  className="mono text-[10px] uppercase tracking-wider text-text-dim hover:text-text"
                >
                  {showRaw ? "Hide raw" : "View raw council block"}
                </button>
                {showRaw && (
                  <pre className="mt-2 text-[11px] bg-bg-soft border border-border-dim rounded p-3 whitespace-pre-wrap text-text-dim">
                    {critique.raw_council_block}
                  </pre>
                )}
              </div>
            )}
          </>
        )}
        {/* Phase 48 (v1.6) — F11: deep-research expandable section.
            Renders only when this persona has run deep-research at least
            once. Collapsed by default to keep the card compact. */}
        {Array.isArray(additionalPapers) && additionalPapers.length > 0 && (
          <details className="border-t border-border-dim pt-3" data-deep-research>
            <summary className="mono text-[10px] uppercase tracking-wider text-text-muted cursor-pointer">
              Deep research ({additionalPapers.length} paper{additionalPapers.length === 1 ? "" : "s"})
            </summary>
            <ul className="mt-2 space-y-1.5 text-xs">
              {additionalPapers.map((p) => (
                <li key={p.id}>
                  <button
                    type="button"
                    onClick={() => onOpenPaper?.(p)}
                    className="text-left text-text-dim hover:text-accent transition truncate w-full"
                    title={p.abstract?.slice(0, 240) ?? p.title}
                  >
                    {typeof p.relevance_score === "number" && (
                      <span className="mono text-[10px] mr-1 text-text-muted">
                        ●{p.relevance_score.toFixed(2)}
                      </span>
                    )}
                    {p.title}
                  </button>
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </div>
  );
}

function Section({
  title,
  items,
  ordered = false,
}: {
  title: string;
  items: string[];
  ordered?: boolean;
}) {
  if (items.length === 0) {
    return (
      <div>
        <h4 className="mono text-[10px] uppercase tracking-wider text-text-muted mb-1">
          {title}
        </h4>
        <p className="text-xs text-text-muted italic">none</p>
      </div>
    );
  }
  const ListTag = ordered ? "ol" : "ul";
  const itemClass = ordered ? "list-decimal pl-4" : "list-disc pl-4";
  return (
    <div>
      <h4 className="mono text-[10px] uppercase tracking-wider text-text-muted mb-1">
        {title}
      </h4>
      <ListTag className={cn("space-y-1.5 text-sm leading-snug", itemClass)}>
        {items.map((it, i) => (
          <li key={i}>{it}</li>
        ))}
      </ListTag>
    </div>
  );
}
