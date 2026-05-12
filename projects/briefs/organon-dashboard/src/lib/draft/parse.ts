/**
 * PHASE_5_TASKS.md T08 — extract `\fig{...}` and `\cite{...}` references
 * from markdown source. Pure text scan; no AST.
 *
 * Used at preview time (to bind to figures + bibliography), at save time
 * (to update linked_figure_ids + linked_paper_ids), and at export time
 * (numbering across all sections).
 *
 * Phase 9 hotfix (DR-1): tokens inside fenced code blocks or single-backtick
 * inline code spans are demonstrative literal-syntax, not real references.
 * Strip code regions via `stripCodeRegions` before scanning so
 * default-section placeholder templates with `\cite{paper-id}` examples
 * don't pollute linked_paper_ids / unresolved-cite collectors.
 */

import { stripCodeRegions } from "./code-aware";

const FIG_RE = /\\fig\{([^}\s]+)\}/g;
const CITE_RE = /\\cite\{([^}\s]+(?:\s*,\s*[^}\s]+)*)\}/g;

export type ParsedRefs = {
  figures: string[];
  citations: string[];
};

export function extractRefs(content: string): ParsedRefs {
  const figures = new Set<string>();
  const citations = new Set<string>();
  const scanText = stripCodeRegions(content);
  for (const m of scanText.matchAll(FIG_RE)) {
    figures.add(m[1].trim());
  }
  for (const m of scanText.matchAll(CITE_RE)) {
    for (const id of m[1].split(",")) {
      const trimmed = id.trim();
      if (trimmed) citations.add(trimmed);
    }
  }
  return {
    figures: Array.from(figures),
    citations: Array.from(citations),
  };
}

/** Parse refs across multiple sections in source order. Preserves first-seen ordering for numbering. */
export function extractRefsSequence(
  sections: { content_md: string }[],
): ParsedRefs {
  const figures: string[] = [];
  const citations: string[] = [];
  const seenFigs = new Set<string>();
  const seenCites = new Set<string>();
  for (const s of sections) {
    const scanText = stripCodeRegions(s.content_md);
    for (const m of scanText.matchAll(FIG_RE)) {
      const id = m[1].trim();
      if (!seenFigs.has(id)) {
        seenFigs.add(id);
        figures.push(id);
      }
    }
    for (const m of scanText.matchAll(CITE_RE)) {
      for (const raw of m[1].split(",")) {
        const id = raw.trim();
        if (id && !seenCites.has(id)) {
          seenCites.add(id);
          citations.push(id);
        }
      }
    }
  }
  return { figures, citations };
}
