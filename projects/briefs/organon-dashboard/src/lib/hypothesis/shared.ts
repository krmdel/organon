/**
 * Pure, client-safe helpers for the hypothesis workspace. NO node:* imports.
 * Server-only file/crypto helpers live in personas.ts / store.ts / critiques.ts / id.ts.
 */

export type Persona = {
  name: string;
  role?: string;
  avatar?: string;
  /**
   * Phase 13a (v1.0.1) — H-4: when false, the persona is preserved in
   * personas.json (history + restoration) but excluded from the next
   * council fanout. Default true via read-time backfill in
   * normalisePersona — pre-Phase-13a personas.json files do not carry
   * the field and must keep firing every persona.
   */
  active?: boolean;
};

export const MAX_PERSONAS = 5;

export function getDefaultPersonas(): Persona[] {
  return [
    { name: "Skeptic", role: "challenges every claim", avatar: "S", active: true },
    { name: "Methodologist", role: "checks study design", avatar: "M", active: true },
    { name: "Domain-expert", role: "field-specific knowledge", avatar: "D", active: true },
  ];
}

export function getMathTemplatePersonas(): Persona[] {
  return [
    { name: "Gauss", role: "algebraic / number-theoretic", avatar: "G", active: true },
    { name: "Erdős", role: "probabilistic / extremal", avatar: "E", active: true },
    { name: "Tao", role: "harmonic / arithmetic-combinatorics", avatar: "T", active: true },
  ];
}

/**
 * Phase 13a — single source of truth for "is this persona active?"
 * The bare-truthy check (`!== false`) defends against:
 *   - older personas.json without the field at all
 *   - parsed JSON returning undefined / null instead of a boolean
 * Both cases must default to active so historic projects do not
 * silently drop personas after upgrading.
 */
export function isPersonaActive(p: Persona): boolean {
  return p.active !== false;
}

/**
 * Slugify a persona name for use as the critique sidecar filename.
 *   "Erdős" → "erdos"
 *   "Domain-expert" → "domain-expert"
 *
 * Strips Unicode combining diacritics post-NFD normalisation.
 */
export function slugifyPersona(name: string): string {
  return name
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}
