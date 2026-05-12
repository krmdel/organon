/**
 * Phase 48 (v1.6) — F11: per-persona deep-research query templates.
 *
 * Each council persona has a query template family that biases its
 * literature search toward the kind of evidence it's best at consuming:
 *
 *   - Skeptic        → refute / limitation / failed-replication evidence
 *   - Methodologist  → measurement / validation / reliability evidence
 *   - Domain-expert  → consensus / review / meta-analysis evidence
 *
 * Templates substitute the hypothesis claim into a `{claim}` placeholder.
 * The function returns 3 query variants per persona; the orchestrator
 * fires searchPapers on each variant (default 5 results) and merges.
 *
 * Templates are static, NOT LLM-generated, per brief decision Q5:
 * deterministic + debuggable + fast. v1.7+ may swap in dynamic templates.
 *
 * Pure data — no node:* imports, importable from anywhere server-side.
 */

import { slugifyPersona } from "./shared";

const TEMPLATES: Record<string, string[]> = {
  // Phase 48 — skeptic biases toward refutation. Searches for studies
  // that limit, refute, or fail-to-replicate the claim.
  skeptic: [
    "refute {claim}",
    "limitations of {claim}",
    "failed to replicate {claim}",
  ],
  // Phase 48 — methodologist biases toward measurement validity. Searches
  // for the operational + reliability literature behind the claim's
  // observable variables.
  methodologist: [
    "measurement of {claim}",
    "validation of {claim}",
    "reliability of {claim}",
  ],
  // Phase 48 — domain-expert biases toward field consensus. Searches for
  // reviews, meta-analyses, and consensus statements.
  "domain-expert": [
    "consensus on {claim}",
    "review of {claim}",
    "meta-analysis of {claim}",
  ],
};

// Phase 48 — fallback template for custom personas (e.g. math-template's
// Gauss/Erdős/Tao, or user-defined ones). Three generic angles so every
// persona gets some targeted search rather than nothing.
const FALLBACK_TEMPLATE: string[] = [
  "evidence for {claim}",
  "background on {claim}",
  "open questions about {claim}",
];

/**
 * Substitute the hypothesis claim into one template string. Both
 * `{claim}` and `{X}` placeholders are accepted (the brief uses both
 * forms interchangeably).
 */
function substituteClaim(template: string, claim: string): string {
  return template.replace(/\{claim\}|\{X\}/gi, claim);
}

/**
 * Return 3 query variants for a persona. Match order:
 *   1. Direct slug match (e.g. "skeptic", "methodologist", "domain-expert")
 *   2. Slug-prefix match (e.g. "skeptical-reviewer" → "skeptic")
 *   3. Fallback generic-angle template
 */
export function getPersonaQueries(personaName: string, claim: string): string[] {
  const slug = slugifyPersona(personaName);
  const direct = TEMPLATES[slug];
  if (direct) return direct.map((t) => substituteClaim(t, claim));
  for (const key of Object.keys(TEMPLATES)) {
    if (slug.startsWith(key) || key.startsWith(slug)) {
      return TEMPLATES[key].map((t) => substituteClaim(t, claim));
    }
  }
  return FALLBACK_TEMPLATE.map((t) => substituteClaim(t, claim));
}
