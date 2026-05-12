/**
 * PHASE_5_TASKS.md T10 — figure + citation auto-numbering.
 * Pure mapping: ref id → display label. Used by render.ts at preview time
 * AND by the export pipeline.
 */

import type { CitationStyle } from "./store";

export type NumberingMaps = {
  figureLabel: Map<string, string>;
  citationLabel: Map<string, string>;
  /** Order of citations as they appear; used by bibliography assembly. */
  citationOrder: string[];
};

/** Build numbering for a manuscript given seen-in-order ref lists. */
export function buildNumbering(
  refs: { figures: string[]; citations: string[] },
  citation_style: CitationStyle,
  bibAuthorYear?: Map<string, { author: string; year: number }>,
): NumberingMaps {
  const figureLabel = new Map<string, string>();
  refs.figures.forEach((id, idx) => {
    figureLabel.set(id, `Fig. ${idx + 1}`);
  });

  const citationLabel = new Map<string, string>();
  if (citation_style === "apa") {
    // (Author, Year) — fall back to [#] when metadata is missing
    refs.citations.forEach((id, idx) => {
      const meta = bibAuthorYear?.get(id);
      const label = meta ? `(${meta.author}, ${meta.year})` : `[${idx + 1}]`;
      citationLabel.set(id, label);
    });
  } else {
    // Numeric styles — Nature / IEEE / Vancouver all use [#] inline.
    refs.citations.forEach((id, idx) => {
      citationLabel.set(id, `[${idx + 1}]`);
    });
  }

  return { figureLabel, citationLabel, citationOrder: refs.citations };
}
