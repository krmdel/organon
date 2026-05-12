import type { PaperArtifact } from "../artifacts/types";
import type { CitationStyle } from "./store";

export { paperToBibtex, libraryToBibtex } from "../lit/bibtex";

/** First author surname extraction. Falls back to "Anonymous". */
export function firstAuthorSurname(paper: PaperArtifact): string {
  const a = paper.authors[0];
  if (!a) return "Anonymous";
  const trimmed = a.trim();
  // Already in "Last, First" form?
  if (trimmed.includes(",")) return trimmed.split(",")[0].trim();
  // "First Last" form — take the last word.
  const words = trimmed.split(/\s+/);
  return words[words.length - 1];
}

/** Build inline-citation text per style. */
export function formatCitationInText(
  paper: PaperArtifact,
  style: CitationStyle,
  numericIndex?: number,
): string {
  if (style === "apa") {
    const surname = firstAuthorSurname(paper);
    if (paper.year && paper.year > 0) return `(${surname}, ${paper.year})`;
    return `(${surname})`;
  }
  // Numeric styles — Nature, IEEE, Vancouver — use [n]
  return `[${numericIndex ?? 0}]`;
}

/** Build a one-line bibliography entry per style. */
export function formatBibEntry(
  paper: PaperArtifact,
  style: CitationStyle,
  index: number,
): string {
  const authors = paper.authors.length
    ? paper.authors.join(", ")
    : "Anonymous";
  const year = paper.year || "n.d.";
  const title = paper.title || "(no title)";
  const journal = paper.journal ?? "";
  const doi = paper.source_ids?.doi
    ? ` doi:${paper.source_ids.doi}`
    : paper.url
      ? ` ${paper.url}`
      : "";
  const j = journal ? ` *${journal}*.` : "";
  switch (style) {
    case "apa":
      return `${authors} (${year}). ${title}.${j}${doi}`;
    case "nature":
      return `${index}. ${authors} ${title}.${j} (${year}).${doi}`;
    case "ieee":
      return `[${index}] ${authors}, "${title},"${j} ${year}.${doi}`;
    case "vancouver":
      return `${index}. ${authors}. ${title}.${j} ${year}.${doi}`;
  }
}

export type BibCompiled = {
  /** Inline label per cited paper, in citation order */
  inline: Map<string, string>;
  /** Bibliography entries (one per cited paper, in order) */
  entries: { id: string; label: string; entry: string }[];
};

export function compileBibliography(
  citationOrder: string[],
  library: PaperArtifact[],
  style: CitationStyle,
): BibCompiled {
  // Phase 3 (fix-sprint): build TWO indices so `\cite{<token>}` resolves
  // whether the manuscript references the paper.id (`pmid-41889156`) or
  // the cite_key (`Shah2026`). Closes Finding #24 ("Missing from library"
  // in export). cite_key wins on collision because manuscripts authored
  // with the new persist layer all use cite_keys.
  const byId = new Map(library.map((p) => [p.id, p]));
  const byCiteKey = new Map(
    library
      .filter((p): p is PaperArtifact & { cite_key: string } =>
        typeof p.cite_key === "string" && p.cite_key.length > 0,
      )
      .map((p) => [p.cite_key, p]),
  );
  const lookup = (token: string) => byCiteKey.get(token) ?? byId.get(token);

  const inline = new Map<string, string>();
  const entries: BibCompiled["entries"] = [];
  citationOrder.forEach((id, idx) => {
    const n = idx + 1;
    const paper = lookup(id);
    if (!paper) {
      inline.set(id, style === "apa" ? `(missing: ${id})` : `[${n}?]`);
      entries.push({
        id,
        label: style === "apa" ? id : `[${n}]`,
        entry: `${style === "apa" ? "" : `${n}. `}*Missing from library:* ${id}`,
      });
      return;
    }
    inline.set(id, formatCitationInText(paper, style, n));
    entries.push({
      id,
      label: style === "apa" ? "" : `[${n}]`,
      entry: formatBibEntry(paper, style, n),
    });
  });
  return { inline, entries };
}
