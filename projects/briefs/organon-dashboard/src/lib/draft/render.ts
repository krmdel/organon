/**
 * PHASE_5_TASKS.md T09 — minimal markdown renderer with custom plugins for
 * `\fig{fig-id}` (figure embed with auto-numbered caption) and
 * `\cite{paper-id, paper-id-2}` (inline citation label).
 *
 * Hand-rolled to avoid the markdown-it npm dep (npm install is denied in this
 * sandbox). Covers: ATX headings, paragraphs, fenced code blocks, inline
 * code, **bold**, *italic*, [link](url), - / 1. lists, blockquotes, hr.
 *
 * Phase 7 (fix-sprint) extensions:
 *   - T6.1 stripRawHtml — drop raw `<...>` from user input so the export
 *     and preview no longer ship literal `<span class="…">…</span>` markup.
 *   - T6.3 KaTeX-subset math via `./math` (handles `$…$`, `$$…$$`,
 *     greek/operators/super-sub-script/\frac/\sqrt for the biomedical 95%).
 *   - T6.6 GFM tables, footnote refs (`[^name]` + `[^name]: text`), and
 *     definition lists (`Term\n: defn`).
 */

import type { FigureArtifact, PaperArtifact } from "../artifacts/types";
import type { ManuscriptMeta } from "./store";
import type { SectionDraftArtifact } from "../artifacts/types";
import { extractRefsSequence } from "./parse";
import { compileBibliography, firstAuthorSurname } from "./bib";
import { buildNumbering } from "./numbering";
import { resolveCitesAndFigs } from "./resolve";
import { applyMath, substituteMath } from "./math";

export type RenderInput = {
  manuscript: ManuscriptMeta;
  sections: SectionDraftArtifact[];
  figures: FigureArtifact[];
  library: PaperArtifact[];
  /** absolute organon root prefix for figure URLs; defaults to "/api/figures". */
  figureUrlBase?: (figId: string, pngBasename: string) => string;
};

export type RenderOutput = {
  html: string;
  refs: { figures: string[]; citations: string[] };
};

const escapeHtml = (s: string): string =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

const inlineCode = (s: string): string =>
  s.replace(/`([^`]+)`/g, (_, c) => `<code class="text-text bg-bg-soft rounded px-1 py-0.5">${escapeHtml(c)}</code>`);

const bold = (s: string): string =>
  s.replace(/\*\*([^*]+)\*\*/g, (_, c) => `<strong>${c}</strong>`);

const italic = (s: string): string =>
  s.replace(/\*([^*\n]+)\*/g, (_, c) => `<em>${c}</em>`);

const links = (s: string): string =>
  s.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, text, url) =>
    `<a href="${escapeHtml(url)}" class="text-accent underline" target="_blank" rel="noopener">${text}</a>`);

/**
 * Phase 7 T6.1 — drop raw `<...>` HTML tags from user input. Keeps
 * markdown-style cite/fig tokens, math, code fences, etc. intact since
 * they don't use `<` literally. Renderer-emitted HTML (figures, citations,
 * math, formatting) is inserted AFTER this strip so it survives.
 *
 * Also strips paired `</...>` — does NOT strip `<` that's part of valid
 * inline markdown like `<https://example.com>` autolink (that's not
 * supported here anyway). Conservative match on the standard tag grammar.
 */
const RAW_HTML_TAG_RE = /<\/?[a-zA-Z][a-zA-Z0-9-]*(?:\s+[^<>]*)?\/?>/g;
export function stripRawHtml(s: string): string {
  return s.replace(RAW_HTML_TAG_RE, "");
}

/**
 * Phase 7 T6.6 — inline footnote references `[^name]` → numbered super-link.
 * The block-level `[^name]: text` definition is collected separately during
 * the section parse and rendered into a `<section class="footnotes">` block.
 */
function footnoteRefs(
  s: string,
  ctx: { footnoteIndex: Map<string, number>; counter: { next: number } },
): string {
  return s.replace(/\[\^([A-Za-z0-9_-]+)\]/g, (_, name) => {
    const id = String(name);
    let idx = ctx.footnoteIndex.get(id);
    if (idx === undefined) {
      idx = ctx.counter.next++;
      ctx.footnoteIndex.set(id, idx);
    }
    return `<sup class="footnote-ref"><a href="#fn-${escapeHtml(id)}" id="fnref-${escapeHtml(id)}">${idx}</a></sup>`;
  });
}

// Phase 9 hotfix (DR-1) — sentinel for inline-code spans. Distinct from the
// math sentinel (0x01) so the two passes can coexist. Code spans are pulled
// out, pre-rendered as `<code>...</code>`, and re-inserted after the cite/
// fig and other inline passes — so backticked literal-syntax demos like
// `\cite{paper-id}` render as code styling, not as resolved cite spans
// that then get HTML-escaped inside a wrapping `<code>`.
const CODE_SENTINEL_PREFIX = "CODE";
const CODE_SENTINEL_SUFFIX = "";
const INLINE_CODE_SPAN_RE = /`([^`\n]+)`/g;

function inlineMarkup(
  s: string,
  replaceCustom: (raw: string) => string,
  footnoteCtx?: { footnoteIndex: Map<string, number>; counter: { next: number } },
): string {
  // Phase 9 hotfix (DR-1): mask inline-code spans FIRST so anything inside
  // backticks survives the rest of the pipeline verbatim. This is load-
  // bearing for several inline rules at once:
  //   - cite/fig tokens (`\cite{paper-id}` / `\fig{fig-id}` literal demos)
  //   - math (`$\Delta$` as literal-syntax demo must NOT render as math)
  //   - bold / italic / links / footnotes
  // The sentinel uses 0x02 control chars; math uses 0x01; so the two passes
  // can coexist without colliding.
  const codeMap = new Map<string, string>();
  let codeIdx = 0;
  const withCodeMasked = s.replace(INLINE_CODE_SPAN_RE, (_, content) => {
    const sentinel = `${CODE_SENTINEL_PREFIX}${codeIdx++}${CODE_SENTINEL_SUFFIX}`;
    codeMap.set(
      sentinel,
      `<code class="text-text bg-bg-soft rounded px-1 py-0.5">${escapeHtml(String(content))}</code>`,
    );
    return sentinel;
  });

  // Now pull math out of the (code-stripped) prose so escapeHtml + the
  // other inline passes don't mangle `$\Delta$`. Substitute back at the
  // very end. Math inside backticks already survived the mask above, so
  // the demo text "`$\Delta$`" stays as code, never math.
  const { text: withMath, mapping: mathMap } = applyMath(withCodeMasked);
  const withCustom = replaceCustom(escapeHtml(withMath));
  // `inlineCode` was already handled via the sentinel mask above, so it is
  // dropped from the chain here to avoid wrapping the (now non-existent)
  // backticks a second time. bold + italic + links still run.
  let html = links(italic(bold(withCustom)));
  if (footnoteCtx) html = footnoteRefs(html, footnoteCtx);
  html = substituteMath(html, mathMap);

  // Re-insert pre-rendered code spans. `split().join()` instead of `replace`
  // so a sentinel containing regex metacharacters can never confuse the
  // engine, and so duplicate sentinels (shouldn't happen but guard against
  // it) all get replaced.
  for (const [sentinel, rendered] of codeMap) {
    html = html.split(sentinel).join(rendered);
  }
  return html;
}

type FootnoteDef = { name: string; html: string };

function renderSection(
  sect: SectionDraftArtifact,
  ctx: {
    figureLabel: Map<string, string>;
    citationLabel: Map<string, string>;
    figureById: Map<string, FigureArtifact>;
    figureUrlBase: NonNullable<RenderInput["figureUrlBase"]>;
    footnoteIndex: Map<string, number>;
    footnoteCounter: { next: number };
    footnoteDefs: FootnoteDef[];
  },
): string {
  const replaceCustom = (raw: string): string => {
    let out = raw;
    out = out.replace(/\\fig\{([^}\s]+)\}/g, (_, id) => {
      const fig = ctx.figureById.get(id);
      const label = ctx.figureLabel.get(id) ?? "Fig. ?";
      if (!fig) {
        return `<span class="mono text-[11px] text-danger">[unresolved \\fig{${escapeHtml(id)}}]</span>`;
      }
      const png = fig.png_path.split("/").pop() ?? "v1.png";
      const url = ctx.figureUrlBase(fig.id, png);
      const caption = fig.caption ?? "";
      return `<figure class="my-4">
  <img src="${url}" alt="${escapeHtml(fig.alt_text ?? label)}" class="w-full max-w-3xl border border-border-dim rounded" />
  <figcaption class="mt-2 text-xs text-text-muted"><span class="text-text">${label}.</span> ${escapeHtml(caption)}</figcaption>
</figure>`;
    });
    out = out.replace(/\\cite\{([^}\s]+(?:\s*,\s*[^}\s]+)*)\}/g, (_, raw) => {
      const ids = String(raw).split(",").map((s) => s.trim()).filter(Boolean);
      return ids.map((id) => {
        const label = ctx.citationLabel.get(id);
        if (!label) return `<span class="mono text-[11px] text-danger">[unresolved \\cite{${escapeHtml(id)}}]</span>`;
        return `<span class="text-text-dim" title="${escapeHtml(id)}">${escapeHtml(label)}</span>`;
      }).join(" ");
    });
    return out;
  };

  // Phase 7 T6.1 — strip user-typed raw HTML tags (e.g. legacy
  // `<span class="…">…</span>` placeholders) before any further parsing.
  // Renderer-emitted HTML is inserted later via substitution and survives.
  const stripped = stripRawHtml(sect.content_md.replace(/\r\n?/g, "\n"));
  const lines = stripped.split("\n");
  const blocks: string[] = [];
  let i = 0;
  let para: string[] = [];
  // Phase 20 (v1.1+) — DR-7 drag-drop: track the 1-indexed start line
  // of each block as we scan, and emit `data-source-line="{n}"` on
  // every block element. The live-preview's drop handler reads this
  // attribute to map drop position → source line for `\fig{}` insertion.
  let paraStart = -1;
  const inlineCtx = {
    footnoteIndex: ctx.footnoteIndex,
    counter: ctx.footnoteCounter,
  };
  const renderInline = (s: string) => inlineMarkup(s, replaceCustom, inlineCtx);
  const flushPara = () => {
    if (para.length) {
      const joined = para.join(" ").trim();
      if (joined) blocks.push(`<p data-source-line="${paraStart}">${renderInline(joined)}</p>`);
      para = [];
      paraStart = -1;
    }
  };

  while (i < lines.length) {
    const line = lines[i];
    if (/^\s*$/.test(line)) { flushPara(); i += 1; continue; }
    // Fenced code blocks
    if (/^```/.test(line)) {
      flushPara();
      const blockStart = i + 1;
      const closing = lines.indexOf("```", i + 1);
      const end = closing === -1 ? lines.length : closing;
      const code = lines.slice(i + 1, end).join("\n");
      blocks.push(
        `<pre data-source-line="${blockStart}" class="bg-bg-soft border border-border-dim rounded p-3 overflow-auto text-xs"><code>${escapeHtml(code)}</code></pre>`,
      );
      i = end + 1;
      continue;
    }
    // Headings
    const h = line.match(/^(#{1,6})\s+(.+)$/);
    if (h) {
      flushPara();
      const blockStart = i + 1;
      const level = h[1].length;
      const text = renderInline(h[2].trim());
      const sizes = ["text-2xl mt-6 mb-2", "text-xl mt-5 mb-2", "text-lg mt-4 mb-1", "text-base mt-3 mb-1", "text-sm mt-3 mb-1", "text-xs mt-3 mb-1"][level - 1];
      blocks.push(`<h${level} data-source-line="${blockStart}" class="${sizes} text-text font-medium">${text}</h${level}>`);
      i += 1; continue;
    }
    // Horizontal rule
    if (/^---+\s*$/.test(line)) { flushPara(); blocks.push(`<hr data-source-line="${i + 1}" class="my-4 border-border-dim" />`); i += 1; continue; }
    // Phase 7 T6.6 — footnote definitions: `[^name]: body` (multi-line
    // until next blank line). Collected, not rendered inline.
    const fnDef = line.match(/^\[\^([A-Za-z0-9_-]+)\]:\s*(.*)$/);
    if (fnDef) {
      flushPara();
      const name = fnDef[1];
      const bodyParts: string[] = [fnDef[2]];
      i += 1;
      while (i < lines.length && /^(?:\s{2,}|\t)/.test(lines[i])) {
        bodyParts.push(lines[i].replace(/^\s+/, ""));
        i += 1;
      }
      ctx.footnoteDefs.push({
        name,
        html: renderInline(bodyParts.join(" ").trim()),
      });
      continue;
    }
    // Phase 7 T6.6 — GFM tables: header row, separator with `---`, then 1+ data rows.
    if (/^\s*\|/.test(line) && i + 1 < lines.length && /^\s*\|?\s*:?-{3,}/.test(lines[i + 1])) {
      flushPara();
      const blockStart = i + 1;
      const splitRow = (raw: string): string[] =>
        raw.replace(/^\s*\|/, "").replace(/\|\s*$/, "").split("|").map((c) => c.trim());
      const header = splitRow(line);
      const sepCells = splitRow(lines[i + 1]);
      const align = sepCells.map((cell) => {
        const left = cell.startsWith(":");
        const right = cell.endsWith(":");
        if (left && right) return "center";
        if (right) return "right";
        return "left";
      });
      const rows: string[][] = [];
      i += 2;
      while (i < lines.length && /^\s*\|/.test(lines[i])) {
        rows.push(splitRow(lines[i]));
        i += 1;
      }
      const thead = `<thead><tr>${header.map((cell, idx) =>
        `<th class="border border-border-dim px-2 py-1 text-${align[idx] ?? "left"} text-text">${renderInline(cell)}</th>`).join("")}</tr></thead>`;
      const tbody = `<tbody>${rows.map((row) =>
        `<tr>${row.map((cell, idx) =>
          `<td class="border border-border-dim px-2 py-1 text-${align[idx] ?? "left"} text-text-dim">${renderInline(cell)}</td>`).join("")}</tr>`).join("")}</tbody>`;
      blocks.push(`<table data-source-line="${blockStart}" class="my-3 border-collapse text-sm">${thead}${tbody}</table>`);
      continue;
    }
    // Phase 7 T6.6 — definition lists: `Term\n: defn` pattern.
    if (
      i + 1 < lines.length
      && /^[^\s].*$/.test(line)
      && /^:\s+/.test(lines[i + 1])
    ) {
      flushPara();
      const blockStart = i + 1;
      const items: string[] = [];
      while (
        i + 1 < lines.length
        && /^[^\s].*$/.test(lines[i])
        && /^:\s+/.test(lines[i + 1])
        && !/^[-*]\s+/.test(lines[i])
        && !/^\d+\.\s+/.test(lines[i])
        && !/^#{1,6}\s+/.test(lines[i])
        && !/^\s*\|/.test(lines[i])
        && !/^>\s?/.test(lines[i])
      ) {
        const term = lines[i];
        const defLines: string[] = [lines[i + 1].replace(/^:\s+/, "")];
        i += 2;
        while (i < lines.length && /^\s+\S/.test(lines[i])) {
          defLines.push(lines[i].replace(/^\s+/, ""));
          i += 1;
        }
        items.push(
          `<dt class="text-text mt-2">${renderInline(term)}</dt><dd class="text-text-dim ml-4">${renderInline(defLines.join(" "))}</dd>`,
        );
      }
      if (items.length > 0) {
        blocks.push(`<dl data-source-line="${blockStart}" class="my-3">${items.join("")}</dl>`);
        continue;
      }
    }
    // Blockquote
    if (/^>\s?/.test(line)) {
      flushPara();
      const blockStart = i + 1;
      const quoteLines: string[] = [];
      while (i < lines.length && /^>\s?/.test(lines[i])) {
        quoteLines.push(lines[i].replace(/^>\s?/, ""));
        i += 1;
      }
      blocks.push(
        `<blockquote data-source-line="${blockStart}" class="pl-3 border-l-2 border-border-dim text-text-dim italic">${renderInline(quoteLines.join(" "))}</blockquote>`,
      );
      continue;
    }
    // Lists (unordered + ordered, single-level)
    if (/^[-*]\s+/.test(line) || /^\d+\.\s+/.test(line)) {
      flushPara();
      const blockStart = i + 1;
      const ordered = /^\d+\.\s+/.test(line);
      const items: string[] = [];
      const re = ordered ? /^\d+\.\s+(.*)$/ : /^[-*]\s+(.*)$/;
      while (i < lines.length && re.test(lines[i])) {
        const m = lines[i].match(re)!;
        items.push(`<li>${renderInline(m[1])}</li>`);
        i += 1;
      }
      blocks.push(`<${ordered ? "ol" : "ul"} data-source-line="${blockStart}" class="list-${ordered ? "decimal" : "disc"} pl-6 space-y-1">${items.join("")}</${ordered ? "ol" : "ul"}>`);
      continue;
    }
    if (paraStart === -1) paraStart = i + 1;
    para.push(line);
    i += 1;
  }
  flushPara();
  return `<section data-section-id="${escapeHtml(sect.section_id)}" class="mb-6">${blocks.join("")}</section>`;
}

export function renderManuscript(input: RenderInput): RenderOutput {
  const figureUrlBase = input.figureUrlBase ?? ((figId, png) =>
    `/api/figures/${encodeURIComponent(figId)}/${encodeURIComponent(png)}`);
  const orderedSections = input.manuscript.ordering
    .map((id) => input.sections.find((s) => s.section_id === id))
    .filter((s): s is SectionDraftArtifact => !!s);

  const refs = extractRefsSequence(orderedSections);
  // Phase 5 (fix-sprint): the cite-marker → label mapping is the same one
  // resolveCitesAndFigs uses for export. Keeps preview HTML and export
  // markdown numbering identical (closes Finding #24 root-cause). Source
  // of truth for surname extraction is firstAuthorSurname from bib.ts.
  const lookupPaper = (id: string) =>
    input.library.find((p) => p.cite_key === id) ??
    input.library.find((p) => p.id === id);
  const bibAuthorYear = new Map<string, { author: string; year: number }>();
  for (const id of refs.citations) {
    const paper = lookupPaper(id);
    if (paper) {
      bibAuthorYear.set(id, { author: firstAuthorSurname(paper), year: paper.year ?? 0 });
    }
  }
  const numbering = buildNumbering(refs, input.manuscript.citation_style, bibAuthorYear);
  const figureById = new Map(input.figures.map((f) => [f.id, f]));

  // Phase 7 T6.6 — single footnote registry across all sections so
  // numbering survives across the manuscript and definitions render once.
  const footnoteIndex = new Map<string, number>();
  const footnoteCounter = { next: 1 };
  const footnoteDefs: FootnoteDef[] = [];

  const sectionsHtml = orderedSections
    .map((s) => renderSection(s, {
      figureLabel: numbering.figureLabel,
      citationLabel: numbering.citationLabel,
      figureById,
      figureUrlBase,
      footnoteIndex,
      footnoteCounter,
      footnoteDefs,
    }))
    .join("");

  const footnotesHtml = footnoteDefs.length === 0
    ? ""
    : `<section class="mt-6 pt-3 border-t border-border-dim">
  <h2 class="text-sm text-text-muted mb-2 mono uppercase tracking-wider">Footnotes</h2>
  <ol class="space-y-1 text-xs text-text-dim list-decimal pl-5">${
    footnoteDefs
      .filter((d) => footnoteIndex.has(d.name))
      .sort((a, b) => (footnoteIndex.get(a.name)! - footnoteIndex.get(b.name)!))
      .map((d) => `<li id="fn-${escapeHtml(d.name)}">${d.html} <a href="#fnref-${escapeHtml(d.name)}" class="text-accent">↩</a></li>`)
      .join("")
  }</ol>
</section>`;

  const compiled = compileBibliography(refs.citations, input.library, input.manuscript.citation_style);
  const bibHtml = compiled.entries.length === 0
    ? ""
    : `<section class="mt-8 pt-4 border-t border-border-dim">
  <h2 class="text-xl text-text mb-3">References</h2>
  <ol class="space-y-1 text-sm text-text-dim">${
    compiled.entries.map((e) => `<li id="bib-${escapeHtml(e.id)}">${escapeHtml(e.entry)}</li>`).join("")
  }</ol>
</section>`;

  return {
    html: `<article class="prose-organon">${sectionsHtml}${footnotesHtml}${bibHtml}</article>`,
    refs,
  };
}

/**
 * Assemble canonical markdown for export.
 *
 * Phase 5 (fix-sprint): cite + fig tokens are resolved before assembly so
 * Pandoc/Marp/the markdown copy ship the same labels the preview shows.
 * Returns the unresolved sets so the export route can choose to fail with
 * 422 or ship a "Missing from library" footer under `?force=true`.
 *
 * `figureUrl` defaults to a relative `figures/<fig_id>/<png>` path, suitable
 * for Pandoc/Marp to find PNGs sitting next to the exported `.md`.
 */
export function assembleMarkdown(
  manuscript: ManuscriptMeta,
  sections: SectionDraftArtifact[],
  library: PaperArtifact[],
  figures: FigureArtifact[] = [],
  opts?: { figureUrl?: (fig: FigureArtifact, png: string) => string },
): { md: string; unresolvedCites: string[]; unresolvedFigs: string[] } {
  const resolved = resolveCitesAndFigs({
    manuscriptOrdering: manuscript.ordering,
    sections,
    library,
    figures,
    citationStyle: manuscript.citation_style,
    figureUrl: opts?.figureUrl
      ?? ((fig, png) => `figures/${fig.id}/${png}`),
  });

  const compiled = compileBibliography(
    resolved.citationOrder,
    library,
    manuscript.citation_style,
  );

  // Phase 7 T6.1 — strip user-typed raw HTML from the export markdown too.
  // The cite/fig resolution upstream produces only markdown (no `<...>`),
  // so this only affects literal HTML the researcher pasted into the body.
  const body = resolved.resolvedSections
    .map((s) => stripRawHtml(s.content_md).trim())
    .filter(Boolean)
    .join("\n\n");
  const bib = compiled.entries.length === 0
    ? ""
    : "\n" + ["", "## References", "", ...compiled.entries.map((e) => `- ${e.entry}`)].join("\n");
  return {
    md: `${body}${bib}`,
    unresolvedCites: resolved.unresolvedCites,
    unresolvedFigs: resolved.unresolvedFigs,
  };
}
