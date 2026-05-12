import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 9 hotfix (DR-1) regression — cite/fig tokens inside markdown code
// regions (fenced ```...``` blocks and inline `...` spans) must not be
// tokenized as references. This pattern is load-bearing because the default
// section templates use `\cite{paper-id}` and `\fig{fig-id}` *as inline-code
// demos* to teach the user the syntax. Pre-hotfix the resolver replaced them
// with `<span class="...">[unresolved \cite{paper-id}]</span>`, the inline-
// code rule then html-escaped the spans inside `<code>`, and the preview
// rendered the literal `<span>` text — confirmed in the v2 dogfood walk.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const PARSE_SRC = readFileSync(join(ROOT, "src", "lib", "draft", "parse.ts"), "utf8");
const RESOLVE_SRC = readFileSync(join(ROOT, "src", "lib", "draft", "resolve.ts"), "utf8");
const RENDER_SRC = readFileSync(join(ROOT, "src", "lib", "draft", "render.ts"), "utf8");
const CODE_AWARE_SRC = readFileSync(join(ROOT, "src", "lib", "draft", "code-aware.ts"), "utf8");
const STORE_SRC = readFileSync(join(ROOT, "src", "lib", "draft", "store.ts"), "utf8");

test("code-aware.ts exports the documented helpers", () => {
  assert.match(CODE_AWARE_SRC, /export function splitCodeRegions\(/);
  assert.match(CODE_AWARE_SRC, /export function stripCodeRegions\(/);
  assert.match(CODE_AWARE_SRC, /export function replaceOutsideCode\(/);
});

test("parse.ts strips code regions before scanning for cite/fig tokens", () => {
  assert.match(PARSE_SRC, /import \{ stripCodeRegions \} from "\.\/code-aware"/);
  // Both extractRefs and extractRefsSequence must call stripCodeRegions.
  // Use scanText name to disambiguate from raw content_md scans.
  assert.match(PARSE_SRC, /const scanText = stripCodeRegions\(content\)/);
  assert.match(PARSE_SRC, /const scanText = stripCodeRegions\(s\.content_md\)/);
  // Sanity: token regexes still target scanText, not the raw input.
  assert.ok(
    /scanText\.matchAll\(FIG_RE\)/.test(PARSE_SRC) && /scanText\.matchAll\(CITE_RE\)/.test(PARSE_SRC),
    "extractors must scan stripped text, not raw content_md",
  );
});

test("resolve.ts wraps cite/fig replaces in replaceOutsideCode", () => {
  assert.match(RESOLVE_SRC, /import \{ replaceOutsideCode \} from "\.\/code-aware"/);
  assert.match(RESOLVE_SRC, /replaceOutsideCode\(md, \(prose\) => prose\.replace\(FIG_RE/);
  assert.match(RESOLVE_SRC, /replaceOutsideCode\(md, \(prose\) => prose\.replace\(CITE_RE/);
});

test("render.ts inlineMarkup masks code spans BEFORE applyMath and replaceCustom", () => {
  // Code-span sentinel constants exist (using control char 0x02 to avoid
  // colliding with math's 0x01).
  assert.match(RENDER_SRC, /const CODE_SENTINEL_PREFIX/);
  assert.match(RENDER_SRC, /const INLINE_CODE_SPAN_RE = \/`\(\[\^`\\n\]\+\)`\/g/);
  // The mask must happen BEFORE applyMath, otherwise `$\Delta$` inside
  // backticks gets pulled out of the code span as a math sentinel and
  // substituteMath later can't find it (it lives inside the codeMap value,
  // not in the html string). Strict source-ordering check:
  const maskIdx = RENDER_SRC.indexOf("withCodeMasked = s.replace(INLINE_CODE_SPAN_RE");
  const applyMathIdx = RENDER_SRC.indexOf("applyMath(withCodeMasked)");
  const replaceCustomIdx = RENDER_SRC.indexOf("replaceCustom(escapeHtml(withMath))");
  assert.ok(maskIdx > 0, "code-span mask line must exist");
  assert.ok(applyMathIdx > maskIdx, "applyMath must come AFTER code-span mask");
  assert.ok(replaceCustomIdx > applyMathIdx, "replaceCustom must come after applyMath");
  // inlineCode is dropped from the chain — bold/italic/links still run but
  // not inlineCode (it would try to wrap the now-non-existent backticks again).
  assert.match(RENDER_SRC, /let html = links\(italic\(bold\(withCustom\)\)\);/);
  assert.doesNotMatch(RENDER_SRC, /links\(italic\(bold\(inlineCode\(/);
});

test("default section templates use backticked literal-syntax demos (the case the hotfix protects)", () => {
  // Regression alarm: if these change, the hotfix is still correct but the
  // dogfood evidence shifts. Phase 9's whole point was making these survive.
  assert.match(STORE_SRC, /Cite prior work with `\\\\cite\{paper-id\}`/);
  assert.match(STORE_SRC, /embed plots with `\\\\fig\{fig-id\}`/);
});

// --- behavioural mirror -----------------------------------------------
// Pure-JS port of code-aware + extractRefs + render token-scan path so we
// can unit-test the behaviour without a TS build step. Drift from the real
// helpers is caught by the source-text scans above.

function makeCodeAwareMirror() {
  const FENCED = /```[\s\S]*?```/g;
  const INLINE = /`[^`\n]+`/g;

  function splitCodeRegions(md) {
    const fenced = [];
    let last = 0;
    for (const m of md.matchAll(FENCED)) {
      if (m.index > last) fenced.push({ type: "prose", text: md.slice(last, m.index) });
      fenced.push({ type: "fence", text: m[0] });
      last = m.index + m[0].length;
    }
    if (last < md.length) fenced.push({ type: "prose", text: md.slice(last) });
    const out = [];
    for (const r of fenced) {
      if (r.type !== "prose") { out.push(r); continue; }
      let l = 0;
      for (const m of r.text.matchAll(INLINE)) {
        if (m.index > l) out.push({ type: "prose", text: r.text.slice(l, m.index) });
        out.push({ type: "inline-code", text: m[0] });
        l = m.index + m[0].length;
      }
      if (l < r.text.length) out.push({ type: "prose", text: r.text.slice(l) });
    }
    return out;
  }

  function stripCodeRegions(md) {
    return splitCodeRegions(md).filter((r) => r.type === "prose").map((r) => r.text).join("");
  }

  return { splitCodeRegions, stripCodeRegions };
}

function extractRefsScan(md) {
  const FIG_RE = /\\fig\{([^}\s]+)\}/g;
  const CITE_RE = /\\cite\{([^}\s]+(?:\s*,\s*[^}\s]+)*)\}/g;
  const { stripCodeRegions } = makeCodeAwareMirror();
  const scan = stripCodeRegions(md);
  const figures = new Set();
  const citations = new Set();
  for (const m of scan.matchAll(FIG_RE)) figures.add(m[1].trim());
  for (const m of scan.matchAll(CITE_RE)) {
    for (const id of m[1].split(",")) {
      const t = id.trim();
      if (t) citations.add(t);
    }
  }
  return { figures: [...figures], citations: [...citations] };
}

test("backticked \\cite{X} inside inline code is NOT collected as a citation reference", () => {
  const md = "Cite prior work with `\\cite{paper-id}` to teach the syntax.";
  const { citations, figures } = extractRefsScan(md);
  assert.deepEqual(citations, [], "inline-code cite must not pollute references");
  assert.deepEqual(figures, []);
});

test("backticked \\fig{X} inside inline code is NOT collected as a figure reference", () => {
  const md = "Embed plots with `\\fig{fig-id}` for the figure number.";
  const { citations, figures } = extractRefsScan(md);
  assert.deepEqual(figures, [], "inline-code fig must not pollute references");
  assert.deepEqual(citations, []);
});

test("real cite/fig OUTSIDE code spans are still collected (positive control)", () => {
  const md =
    "Type `\\cite{paper-id}` then for a real cite write \\cite{Shah2026} and embed \\fig{fig-7}.\n" +
    "```\n" +
    "Inside fenced code: \\cite{Codeblock1} and \\fig{Codefig1} should be ignored.\n" +
    "```\n" +
    "Bottom mention: \\cite{Doe2024}.";
  const { citations, figures } = extractRefsScan(md);
  assert.deepEqual(citations, ["Shah2026", "Doe2024"]);
  assert.deepEqual(figures, ["fig-7"]);
});

test("default section templates produce zero unresolvedCites / unresolvedFigs (DR-1 export-clean)", () => {
  // Mirror the v0.9 → v2 default templates from store.ts. With the hotfix,
  // a fresh manuscript with placeholder bodies should export without
  // `force: true` because all the cite/fig demos are inside backticks.
  const sections = [
    { content_md: "## Introduction\n\nMotivate the question. Cite prior work with `\\cite{paper-id}`.\n" },
    { content_md: "## Results\n\nReport findings; embed plots with `\\fig{fig-id}`.\n" },
    { content_md: "## Methods\n\nDescribe materials, procedure, and statistical tests.\n" },
  ];
  const collected = sections.flatMap((s) => {
    const r = extractRefsScan(s.content_md);
    return [...r.citations.map((c) => `cite:${c}`), ...r.figures.map((f) => `fig:${f}`)];
  });
  assert.deepEqual(collected, [],
    "placeholder template must not produce any cite/fig refs after Phase 9 hotfix");
});
