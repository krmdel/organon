"use client";

import { useMemo } from "react";
import type { PaperArtifact, PersonaCritiqueArtifact } from "@/lib/artifacts/types";
import { slugifyPersona, type Persona } from "@/lib/hypothesis/shared";
import { PersonaPanel } from "./persona-panel";

export type CouncilFanoutProps = {
  personas: Persona[];
  critiques: PersonaCritiqueArtifact[];
  hypothesisId: string;
  isRunning: boolean;
  /**
   * Phase 13b (v1.0.1) — H-5 + U4 per-persona retry. Caller fires the
   * /retry-persona route + drains SSE; the panel just emits the user
   * intent (slug). Optional so older callers stay compatible.
   */
  onRetryPersona?: (personaSlug: string) => void;
  /** Persona slug whose retry is currently in-flight (or null). */
  retryingSlug?: string | null;
  /**
   * Phase 43 (v1.5) — F6: per-persona discard. Optional so older
   * callers stay compatible.
   */
  excludedPersonaIds?: string[];
  onToggleDiscard?: (personaSlug: string, next: boolean) => void;
  /**
   * Phase 48 (v1.6) — F11: deep-research papers per persona slug.
   * Optional so legacy hypotheses without a deep-research run pass null.
   */
  additionalPapersByPersona?: Record<string, PaperArtifact[]> | null;
  onOpenPaper?: (paper: PaperArtifact) => void;
};

export function CouncilFanout({
  personas,
  critiques,
  isRunning,
  onRetryPersona,
  retryingSlug,
  excludedPersonaIds,
  onToggleDiscard,
  additionalPapersByPersona,
  onOpenPaper,
}: CouncilFanoutProps) {
  const bySlug = useMemo(() => {
    const m = new Map<string, PersonaCritiqueArtifact>();
    for (const c of critiques) m.set(c.persona_slug, c);
    return m;
  }, [critiques]);
  const excludedSet = useMemo(
    () => new Set(excludedPersonaIds ?? []),
    [excludedPersonaIds],
  );

  return (
    <div className="grid gap-4 grid-cols-1 lg:grid-cols-3">
      {personas.map((p) => {
        const slug = slugifyPersona(p.name);
        const critique = bySlug.get(slug) ?? null;
        const additional = additionalPapersByPersona?.[slug] ?? null;
        return (
          <PersonaPanel
            key={p.name}
            persona={p}
            critique={critique}
            isRunning={isRunning}
            onRetryPersona={onRetryPersona}
            retryingSlug={retryingSlug}
            excluded={excludedSet.has(slug)}
            onToggleDiscard={onToggleDiscard}
            additionalPapers={additional}
            onOpenPaper={onOpenPaper}
          />
        );
      })}
    </div>
  );
}
