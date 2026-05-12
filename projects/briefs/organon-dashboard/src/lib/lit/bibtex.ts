import type { PaperArtifact } from "../artifacts/types";

/**
 * Produce a BibTeX entry from a PaperArtifact.
 * Uses an AuthorYear key (first-author last name + year). Falls back to the
 * paper id when the author is missing.
 */
export function paperToBibtex(paper: PaperArtifact): string {
  const key = bibtexKey(paper);
  const fields: [string, string][] = [];

  if (paper.title) fields.push(["title", `{${escapeBibtex(paper.title)}}`]);
  if (paper.authors.length > 0) {
    fields.push(["author", `{${paper.authors.map(escapeBibtex).join(" and ")}}`]);
  }
  if (paper.journal) fields.push(["journal", `{${escapeBibtex(paper.journal)}}`]);
  if (paper.year && paper.year > 0) fields.push(["year", `{${paper.year}}`]);
  if (paper.source_ids.doi) fields.push(["doi", `{${paper.source_ids.doi}}`]);
  if (paper.url) fields.push(["url", `{${paper.url}}`]);

  const body = fields.map(([k, v]) => `  ${k} = ${v}`).join(",\n");
  return `@article{${key},\n${body}\n}`;
}

export function libraryToBibtex(papers: PaperArtifact[]): string {
  const seen = new Set<string>();
  const entries: string[] = [];
  for (const p of papers) {
    let key = bibtexKey(p);
    let suffix = "";
    let n = 1;
    while (seen.has(key + suffix)) {
      n += 1;
      suffix = String.fromCharCode(96 + n); // 'b', 'c', ...
    }
    seen.add(key + suffix);
    if (suffix) {
      entries.push(paperToBibtex(p).replace(`{${key},`, `{${key}${suffix},`));
    } else {
      entries.push(paperToBibtex(p));
    }
  }
  return entries.join("\n\n") + "\n";
}

function bibtexKey(paper: PaperArtifact): string {
  // Phase 3 (fix-sprint): prefer the persisted cite_key (surname-based,
  // disambiguation suffix already applied). Falls back to the legacy
  // first-token derivation only for pre-Phase-3 papers that haven't been
  // re-keyed by the backfill script.
  if (paper.cite_key) return paper.cite_key;
  const firstAuthor = paper.authors[0] ?? "";
  // Legacy: take the first space-separated token. Buggy on PubMed authors
  // (which arrive as "First Last" → first-name key) but kept until backfill.
  const lastName = firstAuthor.split(/\s+/)[0]?.replace(/[.,;{}]/g, "") || "Unknown";
  const year = paper.year && paper.year > 0 ? String(paper.year) : "n.d.";
  const slug = lastName.replace(/[^A-Za-z0-9]/g, "");
  return `${slug || "Unknown"}${year}`;
}

function escapeBibtex(s: string): string {
  return s
    .replace(/\\/g, "\\textbackslash{}")
    .replace(/[&%$#_^~]/g, (c) => `\\${c}`)
    .replace(/[{}]/g, (c) => `\\${c}`);
}
