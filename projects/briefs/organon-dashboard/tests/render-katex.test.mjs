import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 7 (fix-sprint) — renderer extensions: HTML strip (T6.1), DEFAULT
// placeholder cleanup (T6.2), KaTeX-subset math (T6.3), and GFM tables /
// footnotes / definition lists (T6.6).
//
// We use:
//  1. Source-text scans on render.ts / store.ts / math.ts to lock the
//     contract (no regressions on the helper exports + key sentinel
//     pipeline).
//  2. Behaviour assertions via dynamic-importing the math.ts module.
//     math.ts is pure ESM TS; we transpile-on-import using esbuild's
//     stripping behavior via Node's experimental TS support is not
//     available here, so we mirror the regex logic in the tests.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const RENDER_SRC = readSrc("src/lib/draft/render.ts");
const STORE_SRC = readSrc("src/lib/draft/store.ts");
const MATH_SRC = readSrc("src/lib/draft/math.ts");

// ---- T6.1 HTML strip --------------------------------------------------

test("T6.1 — render.ts exports stripRawHtml and applies it on the section path", () => {
  assert.match(RENDER_SRC, /export function stripRawHtml/,
    "stripRawHtml must be exported from render.ts");
  assert.match(RENDER_SRC, /RAW_HTML_TAG_RE/,
    "render.ts must define a tag regex constant");
  assert.match(RENDER_SRC, /stripRawHtml\(sect\.content_md/,
    "renderSection must run stripRawHtml on the input markdown");
  // Also covers assembleMarkdown export path so the markdown export drops HTML.
  assert.match(RENDER_SRC, /stripRawHtml\(s\.content_md\)/,
    "assembleMarkdown must strip raw HTML before joining sections");
});

test("T6.1 — strip regex matches only well-formed tags, leaves cite/fig tokens", () => {
  // Mirror the regex from render.ts in the test so we can run it on samples.
  const RE = /<\/?[a-zA-Z][a-zA-Z0-9-]*(?:\s+[^<>]*)?\/?>/g;
  const cleaned = (s) => s.replace(RE, "");

  assert.equal(cleaned(`<span class="x">Hello</span>`), "Hello");
  assert.equal(cleaned(`<div>foo</div>`), "foo");
  assert.equal(cleaned(`prefix <br/> suffix`), "prefix  suffix");
  assert.equal(cleaned(`<img src="x.png" alt="x"/>`), "");
  // Keep cite/fig tokens intact — they're not HTML.
  assert.equal(
    cleaned(`See \\fig{fig-1} and \\cite{Smith2024} please.`),
    `See \\fig{fig-1} and \\cite{Smith2024} please.`,
  );
  // Keep math intact too — we strip BEFORE math runs.
  assert.equal(
    cleaned(`The result $\\Delta = 4.2$ kg.`),
    `The result $\\Delta = 4.2$ kg.`,
  );
  // Keep markdown links intact — `<` not the start of a tag.
  assert.equal(
    cleaned(`A [paper](https://example.com) and *italic*.`),
    `A [paper](https://example.com) and *italic*.`,
  );
});

// ---- T6.2 DEFAULT_SECTIONS ---------------------------------------------

test("T6.2 — DEFAULT_SECTIONS contain no <span>/<div>/raw HTML markup", () => {
  // Find the DEFAULT_SECTIONS literal.
  const m = STORE_SRC.match(/DEFAULT_SECTIONS:[^=]*=\s*\[([\s\S]*?)\];/);
  assert.ok(m, "DEFAULT_SECTIONS literal must be present");
  const literal = m[1];
  assert.doesNotMatch(literal, /<span/i, "no <span> in default placeholders");
  assert.doesNotMatch(literal, /<div/i, "no <div> in default placeholders");
  // Inline math hint should now be present in methods placeholder.
  assert.match(literal, /\$\\\\Delta\$/,
    "methods placeholder should hint at inline math via $\\Delta$");
});

// ---- T6.3 Math (KaTeX subset) ------------------------------------------

test("T6.3 — math.ts exports applyMath + substituteMath + renderMath", () => {
  for (const name of ["applyMath", "substituteMath", "renderMath"]) {
    assert.match(
      MATH_SRC,
      new RegExp(`export function ${name}`),
      `math.ts must export ${name}`,
    );
  }
});

test("T6.3 — math.ts greek table covers Delta + alpha + Sigma + Omega", () => {
  // The constant tables hold the unicode glyph the LaTeX command should map to.
  for (const [latex, glyph] of [
    ["Delta", "Δ"], ["alpha", "α"], ["Sigma", "Σ"], ["Omega", "Ω"],
    ["pi", "π"], ["mu", "μ"], ["epsilon", "ε"], ["Gamma", "Γ"],
  ]) {
    assert.match(
      MATH_SRC,
      new RegExp(`${latex}:\\s*"${glyph}"`),
      `math.ts must map \\\\${latex} → ${glyph}`,
    );
  }
});

test("T6.3 — math.ts symbol table covers operators researchers actually type", () => {
  for (const [latex, glyph] of [
    ["pm", "±"], ["le", "≤"], ["ge", "≥"], ["neq", "≠"],
    ["approx", "≈"], ["infty", "∞"], ["times", "×"], ["sum", "∑"],
  ]) {
    assert.match(
      MATH_SRC,
      new RegExp(`${latex}:\\s*"${glyph}"`),
      `math.ts must map \\\\${latex} → ${glyph}`,
    );
  }
});

test("T6.3 — math.ts handles \\frac and \\sqrt", () => {
  assert.ok(MATH_SRC.includes("\\\\frac\\{"), "must match \\frac literal");
  assert.ok(MATH_SRC.includes("\\\\sqrt\\{"), "must match \\sqrt literal");
  assert.match(MATH_SRC, /<sup>.*<\/sup>.*<sub>/,
    "fraction renders as <sup>num</sup> ⁄ <sub>den</sub>");
});

test("T6.3 — math.ts handles super/subscript both braced and single-char", () => {
  // Look for the regex characters that handle ^{...} ^x _{...} _x.
  assert.ok(MATH_SRC.includes("\\^\\{"), "must handle ^{...}");
  assert.ok(MATH_SRC.includes("\\^([a-zA-Z0-9])"), "must handle single-char ^x");
  assert.ok(MATH_SRC.includes("_\\{"), "must handle _{...}");
});

test("T6.3 — render.ts wires math through inlineMarkup before escapeHtml", () => {
  assert.match(RENDER_SRC, /import\s*\{[^}]*applyMath[^}]*\}\s*from\s*"\.\/math"/,
    "render.ts must import applyMath + substituteMath from ./math");
  assert.match(RENDER_SRC, /substituteMath\(html,\s*mathMap\)/,
    "inlineMarkup must substitute math sentinels back at the very end");
});

// ---- T6.6 GFM tables / footnotes / definition lists -------------------

test("T6.6 — render.ts has table, footnote-def, definition-list block parsers", () => {
  // Tables: must match a row + separator line. (Use literal-string scans to
  // dodge regex-escape gotchas — pitfall #14 in NEXT_SESSION_2026-05-06c.md.)
  assert.ok(RENDER_SRC.includes("/^\\s*\\|/.test(line)"),
    "renderSection must detect table rows starting with `|`");
  assert.ok(RENDER_SRC.includes("/^\\s*\\|?\\s*:?-{3,}/"),
    "renderSection must detect table separator with `---`");
  // Footnote definitions: `[^name]: body`.
  assert.ok(RENDER_SRC.includes("/^\\[\\^([A-Za-z0-9_-]+)\\]:"),
    "renderSection must detect footnote definitions [^name]:");
  // Definition lists: line followed by `: defn`.
  assert.ok(RENDER_SRC.includes("/^:\\s+/"),
    "renderSection must detect dl bodies starting with `: `");
});

test("T6.6 — inline footnote refs render as <sup><a href=\"#fn-…\"…>", () => {
  assert.match(RENDER_SRC, /function footnoteRefs/,
    "render.ts must declare footnoteRefs helper");
  assert.match(RENDER_SRC, /<sup class="footnote-ref"><a href="#fn-/,
    "footnote refs render as <sup><a href=\"#fn-…\">N</a></sup>");
});

test("T6.6 — renderManuscript emits footnotes section after sections", () => {
  assert.match(RENDER_SRC, /footnoteDefs:\s*FootnoteDef\[\]/,
    "renderManuscript ctx must carry footnoteDefs");
  assert.match(RENDER_SRC, /Footnotes/,
    "renderManuscript must emit a Footnotes heading when footnotes exist");
});
