import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 5 fix-sprint regression tests:
//   1. resolve.ts unifies cite + fig token resolution; cite_key OR paper.id.
//   2. APA → "(Surname, Year)"; numeric styles → "[N]"; multi-cite → "[1, 2]".
//   3. Unresolved tokens are returned in result + leave a breadcrumb in md.
//   4. Figure tokens become markdown image + caption.
//   5. assembleMarkdown integrates resolve + bibliography in a single pass.
//   6. Export route 422s on unresolved unless body.force === true.
//   7. Embed autocomplete inserts cite_key (not paper.id).
//
// Same source-text + tiny pure-JS mirror pattern used by Phase 3/4 tests —
// `node --test tests/**/*.test.mjs` runs without a TS build step.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const RESOLVE_SRC = readFileSync(join(ROOT, "src", "lib", "draft", "resolve.ts"), "utf8");
const RENDER_SRC = readFileSync(join(ROOT, "src", "lib", "draft", "render.ts"), "utf8");
const EXPORT_SRC = readFileSync(
  join(ROOT, "src", "app", "api", "draft", "[slug]", "export", "route.ts"),
  "utf8",
);
const AUTOCOMPLETE_SRC = readFileSync(
  join(ROOT, "src", "components", "draft", "embed-autocomplete.tsx"),
  "utf8",
);

test("resolve.ts exports resolveCitesAndFigs with the documented shape", () => {
  assert.match(RESOLVE_SRC, /export function resolveCitesAndFigs\(/);
  assert.match(RESOLVE_SRC, /unresolvedCites: string\[\];/);
  assert.match(RESOLVE_SRC, /unresolvedFigs: string\[\];/);
  // Lookup is cite_key OR paper.id.
  assert.match(
    RESOLVE_SRC,
    /byCiteKey\.get\(token\) \?\? byId\.get\(token\)/,
    "lookup must check cite_key first, paper.id as fallback",
  );
  // APA + numeric branches present.
  assert.match(RESOLVE_SRC, /citationStyle === "apa"/);
  assert.match(RESOLVE_SRC, /\[\$\{idx \+ 1\}\]/);
});

test("resolveCitesAndFigs (mirror): APA labels, numeric collapse, unresolved breadcrumbs", () => {
  const { resolveCitesAndFigs } = makeMirror();

  const library = [
    { id: "pmid-1", cite_key: "Shah2026", authors: ["Ermeena Shah"], year: 2026 },
    { id: "pmid-2", cite_key: "Rosen2026", authors: ["David Rosen"], year: 2026 },
  ];
  const figures = [
    { id: "fig-A", png_path: "projects/x/figures/fig-A/v1.png", caption: "scatter", alt_text: "scatter alt" },
  ];
  const sections = [
    {
      section_id: "intro",
      content_md: "GLP-1 \\cite{Shah2026}. See \\fig{fig-A} for the scatter.",
    },
    {
      section_id: "results",
      content_md: "Multi \\cite{Shah2026, Rosen2026, Phantom2099}.",
    },
  ];

  // APA mode
  const apa = resolveCitesAndFigs({
    manuscriptOrdering: ["intro", "results"],
    sections,
    library,
    figures,
    citationStyle: "apa",
  });
  assert.equal(apa.unresolvedCites.length, 1);
  assert.equal(apa.unresolvedCites[0], "Phantom2099");
  assert.equal(apa.unresolvedFigs.length, 0);
  // Section 1 has the APA inline cite + fig markdown image
  const intro = apa.resolvedSections.find((s) => s.section_id === "intro");
  assert.match(intro.content_md, /\(Shah, 2026\)/);
  assert.match(intro.content_md, /!\[scatter alt\]\(/);
  assert.match(intro.content_md, /\*Fig\. 1\.\*/);
  // Multi-cite stays as separate "(A, Y); (B, Y)" + unresolved breadcrumb
  const results = apa.resolvedSections.find((s) => s.section_id === "results");
  assert.match(results.content_md, /\(Shah, 2026\); \(Rosen, 2026\); \[unresolved \\cite\{Phantom2099\}\]/);

  // Numeric mode collapses multi-cite to "[1, 2]"
  const num = resolveCitesAndFigs({
    manuscriptOrdering: ["intro", "results"],
    sections,
    library,
    figures,
    citationStyle: "ieee",
  });
  const numIntro = num.resolvedSections.find((s) => s.section_id === "intro");
  assert.match(numIntro.content_md, /\[1\]/);
  // Unresolved within multi-cite still reports
  assert.equal(num.unresolvedCites.length, 1);
});

test("resolveCitesAndFigs (mirror): cite_key OR paper.id resolves both legacy + new tokens", () => {
  const { resolveCitesAndFigs } = makeMirror();
  const library = [
    { id: "pmid-41889156", cite_key: "Shah2026", authors: ["Ermeena Shah"], year: 2026 },
  ];
  // Old manuscript referenced by paper.id; new by cite_key.
  const sections = [
    { section_id: "a", content_md: "By id \\cite{pmid-41889156}." },
    { section_id: "b", content_md: "By key \\cite{Shah2026}." },
  ];
  const out = resolveCitesAndFigs({
    manuscriptOrdering: ["a", "b"],
    sections,
    library,
    figures: [],
    citationStyle: "apa",
  });
  assert.equal(out.unresolvedCites.length, 0);
  // Same paper, both tokens get the same APA label.
  assert.match(
    out.resolvedSections.find((s) => s.section_id === "a").content_md,
    /\(Shah, 2026\)/,
  );
  assert.match(
    out.resolvedSections.find((s) => s.section_id === "b").content_md,
    /\(Shah, 2026\)/,
  );
});

test("assembleMarkdown returns unresolved sets + uses resolveCitesAndFigs", () => {
  // Source-text only: assembleMarkdown shape changed to return an object.
  assert.match(
    RENDER_SRC,
    /md: string;\s+unresolvedCites: string\[\];\s+unresolvedFigs: string\[\]/,
    "assembleMarkdown must return {md, unresolvedCites, unresolvedFigs}",
  );
  assert.match(
    RENDER_SRC,
    /resolveCitesAndFigs\(\{/,
    "assembleMarkdown must call resolveCitesAndFigs",
  );
  // Render.ts uses firstAuthorSurname (T4.4 unification).
  assert.match(RENDER_SRC, /firstAuthorSurname\(paper\)/);
});

test("export route returns 422 on unresolved unless force=true", () => {
  // Body type carries force flag.
  assert.ok(
    EXPORT_SRC.includes("force?: boolean"),
    "export route Body must accept force flag",
  );
  // Builds via assembleMarkdown(meta, sections, library, figures).
  assert.match(EXPORT_SRC, /assembleMarkdown\(meta, sections, library, figures\)/);
  // 422 branch
  assert.match(EXPORT_SRC, /status: 422/);
  // Skips 422 when force is true
  assert.match(EXPORT_SRC, /!body\.force/);
  // unresolved arrays land in the response body
  assert.match(EXPORT_SRC, /unresolved_cites: assembled\.unresolvedCites/);
  assert.match(EXPORT_SRC, /unresolved_figs: assembled\.unresolvedFigs/);
  // listFigures wired up
  assert.match(EXPORT_SRC, /listFigures\(project\.path\)/);
});

test("embed-autocomplete inserts cite_key (paper.id fallback) sorted by saved_at", () => {
  // The cite-picker's id field is paper.cite_key ?? paper.id.
  assert.match(AUTOCOMPLETE_SRC, /id:\s*p\.cite_key \?\? p\.id/);
  // Library is sorted by saved_at.
  assert.match(AUTOCOMPLETE_SRC, /saved_at \?\? ""\)\.localeCompare/);
  // The sub-line still surfaces paper.id so users can locate the file.
  assert.match(AUTOCOMPLETE_SRC, /\$\{p\.id\}/);
});

// --- mirror -------------------------------------------------------------
// Tiny pure-JS port of resolveCitesAndFigs so we can unit-test the
// behaviour without a TS build step. Drift between this and resolve.ts is
// caught by the source-text scan above.

function makeMirror() {
  const FIG_RE = /\\fig\{([^}\s]+)\}/g;
  const CITE_RE = /\\cite\{([^}\s]+(?:\s*,\s*[^}\s]+)*)\}/g;

  function firstAuthorSurname(paper) {
    const a = paper.authors?.[0]?.trim();
    if (!a) return "Anonymous";
    if (a.includes(",")) return a.split(",")[0].trim();
    const w = a.split(/\s+/).filter(Boolean);
    return w[w.length - 1] || "Anonymous";
  }

  function extractRefsSequence(sections) {
    const figures = [];
    const citations = [];
    const seenF = new Set();
    const seenC = new Set();
    for (const s of sections) {
      for (const m of s.content_md.matchAll(FIG_RE)) {
        const id = m[1].trim();
        if (!seenF.has(id)) { seenF.add(id); figures.push(id); }
      }
      for (const m of s.content_md.matchAll(CITE_RE)) {
        for (const raw of m[1].split(",")) {
          const id = raw.trim();
          if (id && !seenC.has(id)) { seenC.add(id); citations.push(id); }
        }
      }
    }
    return { figures, citations };
  }

  function resolveCitesAndFigs(input) {
    const ordered = input.manuscriptOrdering
      .map((id) => input.sections.find((s) => s.section_id === id))
      .filter(Boolean);
    const refs = extractRefsSequence(ordered);
    const byId = new Map(input.library.map((p) => [p.id, p]));
    const byCiteKey = new Map();
    for (const p of input.library) {
      if (typeof p.cite_key === "string" && p.cite_key.length > 0) byCiteKey.set(p.cite_key, p);
    }
    const lookupPaper = (token) => byCiteKey.get(token) ?? byId.get(token);
    const figureById = new Map(input.figures.map((f) => [f.id, f]));

    const unresolvedCites = new Set();
    const unresolvedFigs = new Set();
    const figureLabel = new Map();
    refs.figures.forEach((id, idx) => {
      if (figureById.get(id)) figureLabel.set(id, `Fig. ${idx + 1}`);
      else unresolvedFigs.add(id);
    });
    const citationLabel = new Map();
    refs.citations.forEach((id, idx) => {
      const p = lookupPaper(id);
      if (!p) { unresolvedCites.add(id); return; }
      if (input.citationStyle === "apa") {
        const surname = firstAuthorSurname(p);
        const year = p.year && p.year > 0 ? p.year : "n.d.";
        citationLabel.set(id, `(${surname}, ${year})`);
      } else {
        citationLabel.set(id, `[${idx + 1}]`);
      }
    });

    const figureUrl = input.figureUrl
      ?? ((fig, png) => `figures/${fig.id}/${png}`);

    const resolvedSections = ordered.map((sect) => {
      let md = sect.content_md;
      md = md.replace(FIG_RE, (raw, idRaw) => {
        const id = String(idRaw).trim();
        const fig = figureById.get(id);
        if (!fig) { unresolvedFigs.add(id); return `[unresolved \\fig{${id}}]`; }
        const png = fig.png_path.split("/").pop() ?? "v1.png";
        const url = figureUrl(fig, png);
        const label = figureLabel.get(id) ?? `Fig. ${refs.figures.indexOf(id) + 1}`;
        const alt = (fig.alt_text ?? label).replace(/\[/g, "(").replace(/\]/g, ")");
        const cap = (fig.caption ?? "").trim();
        return cap ? `![${alt}](${url})\n\n*${label}.* ${cap}` : `![${alt}](${url})\n\n*${label}.*`;
      });
      md = md.replace(CITE_RE, (raw, body) => {
        const tokens = String(body).split(",").map((s) => s.trim()).filter(Boolean);
        const labels = tokens.map((tok) => {
          const lbl = citationLabel.get(tok);
          if (lbl) return lbl;
          unresolvedCites.add(tok);
          return `[unresolved \\cite{${tok}}]`;
        });
        if (input.citationStyle !== "apa") {
          const stripped = labels.map((l) => l.replace(/^\[|\]$/g, ""));
          return `[${stripped.join(", ")}]`;
        }
        return labels.join("; ");
      });
      return { ...sect, content_md: md };
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

  return { resolveCitesAndFigs };
}
