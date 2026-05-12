/**
 * Phase 9 hotfix (DR-1) — code-region-aware helpers used by the cite/fig
 * resolver, the markdown export pipeline, and the live preview renderer.
 *
 * Without this guard, a backticked literal-syntax demo like `\cite{paper-id}`
 * inside a default-section template was tokenized by the resolver, replaced
 * with `<span class="...">[unresolved \cite{paper-id}]</span>`, then wrapped
 * in `<code>` by the inline-code rule which html-escapes its content — so
 * the preview rendered the literal `<span>` text in code styling.
 *
 * Three consumers need to agree on what counts as a "code region":
 *  - parse.ts (extractRefs / extractRefsSequence) — drives linked_paper_ids,
 *    references list, unresolved-cite collector. Tokens inside code regions
 *    must be invisible.
 *  - resolve.ts (resolveCitesAndFigs) — the markdown-in/markdown-out export
 *    pass. Tokens inside code regions stay verbatim.
 *  - render.ts (inlineMarkup) — the live preview. Tokens inside code regions
 *    render as `<code>` styling, not as resolved cite/fig spans.
 *
 * "Code region" = anything inside fenced ```...``` blocks OR inside single-
 * backtick `...` inline spans on the same line. We do NOT strip indented-code
 * blocks (4-space prefix) because the markdown renderer here doesn't honour
 * them either — keeping behaviour consistent.
 */

const FENCED_RE = /```[\s\S]*?```/g;
const INLINE_RE = /`[^`\n]+`/g;

export type MdRunType = "prose" | "fence" | "inline-code";
export type MdRun = { type: MdRunType; text: string };

/**
 * Split markdown into alternating prose / fence / inline-code runs.
 * Order is preserved; concatenating `runs.map((r) => r.text).join("")`
 * reproduces the original input exactly.
 */
export function splitCodeRegions(md: string): MdRun[] {
  // First pass: split on fenced code blocks.
  const fenced: MdRun[] = [];
  let last = 0;
  for (const m of md.matchAll(FENCED_RE)) {
    if (m.index! > last) fenced.push({ type: "prose", text: md.slice(last, m.index!) });
    fenced.push({ type: "fence", text: m[0] });
    last = m.index! + m[0].length;
  }
  if (last < md.length) fenced.push({ type: "prose", text: md.slice(last) });

  // Second pass: split each prose run on inline-code spans.
  const out: MdRun[] = [];
  for (const run of fenced) {
    if (run.type !== "prose") { out.push(run); continue; }
    let l = 0;
    for (const m of run.text.matchAll(INLINE_RE)) {
      if (m.index! > l) out.push({ type: "prose", text: run.text.slice(l, m.index!) });
      out.push({ type: "inline-code", text: m[0] });
      l = m.index! + m[0].length;
    }
    if (l < run.text.length) out.push({ type: "prose", text: run.text.slice(l) });
  }
  return out;
}

/**
 * Return the markdown with all code regions (fenced + inline) removed.
 * Used by parse.ts so cite/fig token scanning ignores demonstrative syntax.
 */
export function stripCodeRegions(md: string): string {
  return splitCodeRegions(md)
    .filter((r) => r.type === "prose")
    .map((r) => r.text)
    .join("");
}

/**
 * Apply a markdown-in / markdown-out replacer ONLY to prose runs; preserve
 * code regions verbatim. Used by resolve.ts so that backticked cite/fig
 * tokens survive the export pass as literal text.
 */
export function replaceOutsideCode(md: string, replacer: (prose: string) => string): string {
  return splitCodeRegions(md)
    .map((r) => (r.type === "prose" ? replacer(r.text) : r.text))
    .join("");
}
