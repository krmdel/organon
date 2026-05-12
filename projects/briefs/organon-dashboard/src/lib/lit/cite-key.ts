/**
 * Phase 3 (fix-sprint) — single source of truth for paper cite-keys.
 *
 * Closes dogfood Findings #7 + #25:
 *   - #7: BibTeX cite-keys used the first WORD of the author string
 *         ("Sara2025" instead of "Shah2025") because PubMed returns
 *         "ForeName LastName" and the legacy bibtex.ts:bibtexKey took
 *         token[0] of the split.
 *   - #25: Persisted JSONs had no cite_key field at all, so any consumer
 *         (BibTeX export, manuscript `\cite{...}` resolution, draft
 *         render bibliography) had to re-derive the key on the fly.
 *         Different code paths derived different keys → "Missing from
 *         library" symptom in draft export.
 *
 * The fix is to compute cite_key once, at savePaper time, store it on the
 * artifact, and have every consumer read paper.cite_key first (legacy
 * fallback when the field is absent — backfill removes the gap).
 */

import type { PaperArtifact } from "../artifacts/types";

/**
 * Surname extraction from PubMed/OpenAlex/S2/arXiv author strings.
 *
 * Three input shapes show up in practice:
 *   - "Last, First Middle"   (some bibliographic exports)
 *   - "First Middle Last"    (PubMed default)
 *   - "Last"                 (single token)
 *
 * Heuristic: comma → split, take first part. Otherwise → take last token.
 * Accent + non-ASCII characters are preserved here; the caller strips
 * them before bibkey serialization.
 */
export function firstAuthorSurname(paper: PaperArtifact): string {
  const a = paper.authors[0]?.trim();
  if (!a) return "Anonymous";
  if (a.includes(",")) {
    const last = a.split(",")[0]?.trim();
    return last || "Anonymous";
  }
  const words = a.split(/\s+/).filter(Boolean);
  return words[words.length - 1] || "Anonymous";
}

/**
 * Build a stable cite-key for a paper, deduped against existing keys.
 *
 * Format: `<Surname><Year>` for the primary, `<Surname><Year>b/c/d/...`
 * for collisions (matches BibTeX bibliography conventions).
 *
 * The caller passes a Set of cite-keys already in use in the same library;
 * the function returns a key not in that set. If 26 collisions are
 * exhausted (a/b/.../z) we fall back to suffixing with the paper id —
 * vanishingly unlikely in practice but keeps the function total.
 */
export function paperToCiteKey(
  paper: PaperArtifact,
  existingKeys: ReadonlySet<string>,
): string {
  const surname = firstAuthorSurname(paper).replace(/[^A-Za-z0-9]/g, "");
  const year = paper.year && paper.year > 0 ? String(paper.year) : "n.d.";
  const base = `${surname || "Unknown"}${year}`;
  if (!existingKeys.has(base)) return base;
  for (let i = 1; i < 26; i += 1) {
    // i=1 → 'b', i=2 → 'c', ... (no 'a' suffix; the unsuffixed base wins).
    const candidate = `${base}${String.fromCharCode(97 + i)}`;
    if (!existingKeys.has(candidate)) return candidate;
  }
  // Pathological collision-cluster: salt with the artifact id.
  return `${base}-${paper.id.slice(0, 8)}`;
}
