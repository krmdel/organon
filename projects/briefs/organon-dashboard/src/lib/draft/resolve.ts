/**
 * Phase 5 (fix-sprint) — single pre-resolution pass for `\cite{...}` and
 * `\fig{...}` tokens. Used by both the preview HTML renderer and the
 * markdown/PDF/HTML/DOCX export pipeline so they always agree.
 *
 * Closes dogfood Finding #24: export shipped raw `\cite{}` LaTeX while
 * preview rendered it as `(Author, Year)`. The fix is to factor token
 * resolution into a markdown-in / markdown-out pass that runs BEFORE any
 * downstream formatter (Pandoc, Marp, the hand-rolled HTML renderer).
 *
 * Lookup order (mirrors Phase 3): cite_key first, paper.id as fallback.
 * Unresolved tokens are returned in the result object so the export route
 * can choose to fail with 422 or ship a "Missing from library" footer
 * under `?force=true`.
 */

import type { CitationStyle } from "./store";
import type { FigureArtifact, PaperArtifact, SectionDraftArtifact } from "../artifacts/types";
import { extractRefsSequence } from "./parse";
import { firstAuthorSurname } from "./bib";
import { replaceOutsideCode } from "./code-aware";

export type ResolveInput = {
  manuscriptOrdering: string[];
  sections: SectionDraftArtifact[];
  library: PaperArtifact[];
  figures: FigureArtifact[];
  citationStyle: CitationStyle;
  /** Builder for the figure URL inside markdown image syntax. The default
   *  produces `/api/figures/<fig_id>/<png_basename>` for in-app preview;
   *  exports use the on-disk path so Pandoc/Marp can find the file. */
  figureUrl?: (fig: FigureArtifact, pngBasename: string) => string;
};

export type ResolveOutput = {
  /** Section objects with content_md replaced by token-resolved markdown.
   *  Same length + section_id ordering as the input ordering. */
  resolvedSections: SectionDraftArtifact[];
  /** Citation order across all sections (for bibliography numbering). */
  citationOrder: string[];
  /** Figure order across all sections (for figure numbering). */
  figureOrder: string[];
  /** cite_key/id tokens that didn't match any library paper. */
  unresolvedCites: string[];
  /** fig_ids that didn't match any figure artifact. */
  unresolvedFigs: string[];
  /** id → display label e.g. "(Shah, 2026)" for APA, "[1]" for numeric. */
  citationLabel: Map<string, string>;
  /** id → "Fig. 1" / "Fig. 2" / ... */
  figureLabel: Map<string, string>;
};

const FIG_RE = /\\fig\{([^}\s]+)\}/g;
const CITE_RE = /\\cite\{([^}\s]+(?:\s*,\s*[^}\s]+)*)\}/g;

/**
 * Resolve every `\cite{...}` and `\fig{...}` token in the manuscript's
 * sections, in source order. Returns the rewritten sections + the unresolved
 * sets + the numbering maps so the caller can append a bibliography.
 */
export function resolveCitesAndFigs(input: ResolveInput): ResolveOutput {
  const ordered = input.manuscriptOrdering
    .map((id) => input.sections.find((s) => s.section_id === id))
    .filter((s): s is SectionDraftArtifact => !!s);

  const refs = extractRefsSequence(ordered);

  // Phase 5: lookup is cite_key OR paper.id. Build both indices once.
  const byId = new Map(input.library.map((p) => [p.id, p]));
  const byCiteKey = new Map<string, PaperArtifact>();
  for (const p of input.library) {
    if (typeof p.cite_key === "string" && p.cite_key.length > 0) {
      byCiteKey.set(p.cite_key, p);
    }
  }
  const lookupPaper = (token: string) => byCiteKey.get(token) ?? byId.get(token);
  const figureById = new Map(input.figures.map((f) => [f.id, f]));

  // Track unresolved tokens.
  const unresolvedCites = new Set<string>();
  const unresolvedFigs = new Set<string>();

  // Build numbering. We need it BEFORE the per-section replace so labels
  // are consistent across sections (Fig. 1 in §1 stays Fig. 1 in §3).
  const figureLabel = new Map<string, string>();
  refs.figures.forEach((id, idx) => {
    const fig = figureById.get(id);
    if (fig) figureLabel.set(id, `Fig. ${idx + 1}`);
    else unresolvedFigs.add(id);
  });

  const citationLabel = new Map<string, string>();
  refs.citations.forEach((id, idx) => {
    const paper = lookupPaper(id);
    if (!paper) {
      unresolvedCites.add(id);
      return;
    }
    if (input.citationStyle === "apa") {
      const surname = firstAuthorSurname(paper);
      const year = paper.year && paper.year > 0 ? paper.year : "n.d.";
      citationLabel.set(id, `(${surname}, ${year})`);
    } else {
      citationLabel.set(id, `[${idx + 1}]`);
    }
  });

  const figureUrl = input.figureUrl
    ?? ((fig, png) => `/api/figures/${encodeURIComponent(fig.id)}/${encodeURIComponent(png)}`);

  // Replace tokens in each section. Markdown stays markdown — image refs
  // become `![alt](url)`, citations become inline text.
  //
  // Phase 9 hotfix (DR-1): wrap both replaces in `replaceOutsideCode` so that
  // backticked literal-syntax demos (e.g. the default-section placeholders
  // showing `\cite{paper-id}` to teach the user) survive verbatim and are
  // not flagged as unresolved.
  const resolvedSections = ordered.map((sect) => {
    let md = sect.content_md;
    md = replaceOutsideCode(md, (prose) => prose.replace(FIG_RE, (raw, idRaw) => {
      const id = String(idRaw).trim();
      const fig = figureById.get(id);
      if (!fig) {
        // Leave a visible breadcrumb in the markdown for the export reader,
        // and remember it for the unresolved set.
        unresolvedFigs.add(id);
        return `[unresolved \\fig{${id}}]`;
      }
      const png = fig.png_path.split("/").pop() ?? "v1.png";
      const url = figureUrl(fig, png);
      const label = figureLabel.get(id) ?? `Fig. ${refs.figures.indexOf(id) + 1}`;
      const alt = (fig.alt_text ?? label).replace(/\[/g, "(").replace(/\]/g, ")");
      const caption = (fig.caption ?? "").trim();
      return caption
        ? `![${alt}](${url})\n\n*${label}.* ${caption}`
        : `![${alt}](${url})\n\n*${label}.*`;
    }));
    md = replaceOutsideCode(md, (prose) => prose.replace(CITE_RE, (raw, body) => {
      const tokens = String(body).split(",").map((s) => s.trim()).filter(Boolean);
      const labels = tokens.map((tok) => {
        const lbl = citationLabel.get(tok);
        if (lbl) return lbl;
        unresolvedCites.add(tok);
        return `[unresolved \\cite{${tok}}]`;
      });
      // Numeric-style multi-cite collapses to "[1, 2]"; APA stays "(A, 2026); (B, 2024)".
      if (input.citationStyle !== "apa") {
        const stripped = labels.map((l) => l.replace(/^\[|\]$/g, ""));
        return `[${stripped.join(", ")}]`;
      }
      return labels.join("; ");
    }));
    return { ...sect, content_md: md } as SectionDraftArtifact;
  });

  return {
    resolvedSections,
    citationOrder: refs.citations,
    figureOrder: refs.figures,
    unresolvedCites: Array.from(unresolvedCites),
    unresolvedFigs: Array.from(unresolvedFigs),
    citationLabel,
    figureLabel,
  };
}
