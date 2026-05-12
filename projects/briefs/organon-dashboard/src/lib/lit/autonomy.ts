/**
 * Phase 46 (v1.6) — F9: full-autonomy literature mode.
 *
 * Takes { keywords, research_question, threshold } and returns a curated
 * set partitioned into accepted (≥ threshold) and borderline (< threshold).
 *
 * The expansion is deterministic — no LLM in v1.6 (per brief decision Q4).
 * v1.7+ can swap in an LLM expansion behind the same `expandQueries`
 * interface. Threshold default 0.6 matches the relevance scorer (Phase 47);
 * autonomy can run before Phase 47 ships and just sees relevance_score = 0
 * on every paper, in which case everything lands in "borderline" — the UI
 * handles that gracefully.
 *
 * SERVER-ONLY — imports searchPapers which talks to the network.
 */

import { searchPapers } from "./search";
import type { PaperArtifact } from "../artifacts/types";

export interface AutonomyOptions {
  keywords: string[];
  research_question: string;
  threshold?: number;
  /** Project slug — controls library_path on returned artifacts. */
  projectSlug: string;
  /** Optional brief metadata. Same field passed to searchPapers. */
  field?: string | null;
  /** Per-query result cap. Default 5; total ≤ 4×5 = 20 before dedupe. */
  perQueryMax?: number;
}

export interface AutonomyResult {
  accepted: PaperArtifact[];
  borderline: PaperArtifact[];
  errors: string[];
  soft_errors: string[];
  /** The exact set of expansion variants that were searched. */
  variants: string[];
}

const DEFAULT_THRESHOLD = 0.6;
const DEFAULT_PER_QUERY = 5;

/**
 * Deterministic expansion. v1.7+ may delegate to an LLM; the surface stays
 * stable — input keywords + question, output unique query variants.
 */
export function expandQueries(keywords: string[], research_question: string): string[] {
  const kws = keywords.map((s) => s.trim()).filter((s) => s.length > 0);
  const variants: string[] = [];
  const q = research_question.trim();
  if (q.length > 0) variants.push(q);
  if (kws.length === 1) variants.push(kws[0]);
  if (kws.length >= 2) {
    variants.push(kws.join(" AND "));
    variants.push(kws.join(" OR "));
    variants.push(kws.join(" "));
  }
  return Array.from(new Set(variants));
}

/**
 * DOI normaliser mirroring search.ts. Inlined so the orchestrator can run
 * on PaperArtifact (post-search) shape rather than the per-source
 * PaperResult shape.
 */
function normalizeDoi(doiUrl: string | null | undefined): string | null {
  if (!doiUrl) return null;
  return doiUrl
    .toLowerCase()
    .replace(/^https?:\/\/(dx\.)?doi\.org\//, "")
    .replace(/^doi:/, "")
    .trim();
}

function dedupeByDoi(papers: PaperArtifact[]): PaperArtifact[] {
  const byKey = new Map<string, PaperArtifact>();
  const noDoi: PaperArtifact[] = [];
  for (const p of papers) {
    // Prefer source_ids.doi (already normalised at search time); fall back to doi_url.
    const key = p.source_ids?.doi ?? normalizeDoi(p.doi_url);
    if (!key) {
      // Fall back to id-keyed dedupe so the same paperclip-only paper
      // doesn't appear twice when two query variants both retrieve it.
      const idKey = `id:${p.id}`;
      if (!byKey.has(idKey)) byKey.set(idKey, p);
      continue;
    }
    if (!byKey.has(key)) byKey.set(key, p);
  }
  return [...byKey.values(), ...noDoi];
}

/**
 * Run the autonomy orchestrator. Each variant fans out via searchPapers
 * (which itself does paperclip-primary routing for biomedical queries
 * via Phase 45). Results merge + dedupe by DOI. Partition by relevance
 * threshold; the relevance score is read off `(p as any).relevance_score`
 * — Phase 47 will populate it; before that ships, everything is 0 and
 * lands in borderline.
 */
export async function runAutonomy(opts: AutonomyOptions): Promise<AutonomyResult> {
  const threshold = opts.threshold ?? DEFAULT_THRESHOLD;
  const perQueryMax = opts.perQueryMax ?? DEFAULT_PER_QUERY;
  const variants = expandQueries(opts.keywords, opts.research_question);

  const errors: string[] = [];
  const soft_errors: string[] = [];
  const merged: PaperArtifact[] = [];

  await Promise.all(
    variants.map(async (variant) => {
      try {
        const r = await searchPapers({
          query: variant,
          maxResults: perQueryMax,
          projectSlug: opts.projectSlug,
          field: opts.field,
        });
        merged.push(...r.results);
        for (const e of r.errors) errors.push(`[${variant}] ${e}`);
        for (const e of r.soft_errors) soft_errors.push(`[${variant}] ${e}`);
      } catch (e) {
        errors.push(`[${variant}] ${e instanceof Error ? e.message : String(e)}`);
      }
    }),
  );

  const deduped = dedupeByDoi(merged);

  const accepted: PaperArtifact[] = [];
  const borderline: PaperArtifact[] = [];
  for (const p of deduped) {
    // relevance_score is attached by Phase 47's scorer, optional until then.
    const score = (p as PaperArtifact & { relevance_score?: number }).relevance_score ?? 0;
    if (score >= threshold) accepted.push(p);
    else borderline.push(p);
  }

  return { accepted, borderline, errors, soft_errors, variants };
}
