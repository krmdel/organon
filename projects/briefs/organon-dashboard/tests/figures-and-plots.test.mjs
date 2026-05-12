import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 7 (fix-sprint) T6.7 + T6.8 + T6.9 — scatter Y-default, legacy
// single-version figure fallback, and sub-style validation. All three are
// React/server route changes; these are structural source-text scans.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const PLOT_PICKER_SRC = readSrc("src/components/data/plot-picker.tsx");
const FIGURES_WORKSPACE_SRC = readSrc("src/components/figures/figures-workspace.tsx");
const STYLE_PICKER_SRC = readSrc("src/components/figures/style-picker.tsx");
const PROMPT_FORM_SRC = readSrc("src/components/figures/prompt-form.tsx");
const IMAGES_GENERATE_SRC = readSrc("src/app/api/images/generate/route.ts");

// ---- T6.7 scatter Y default differs from X ---------------------------

test("T6.7 — plot-picker seeds DISTINCT columns for required column fields", () => {
  assert.match(PLOT_PICKER_SRC, /usedColumns/,
    "plot-picker seed loop must track used columns");
  assert.match(PLOT_PICKER_SRC, /candidates\.find\(\(c\)\s*=>\s*!usedColumns\.has\(c\)\)/,
    "plot-picker must prefer un-used candidates for distinct seed");
  assert.match(PLOT_PICKER_SRC, /usedColumns\.add\(pick\)/,
    "plot-picker must remember which columns it consumed");
});

test("T6.7 — distinct-pick logic produces different X and Y for scatter", () => {
  // Mirror the seed loop in JS to verify behavior.
  const dataframeColumns = [
    { name: "treatment_weeks", type: "numeric" },
    { name: "weight_kg", type: "numeric" },
    { name: "drug", type: "categorical" },
  ];
  const colsByType = {};
  for (const c of dataframeColumns) {
    colsByType[c.type] = colsByType[c.type] ? [...colsByType[c.type], c.name] : [c.name];
  }
  const fields = [
    { name: "x_col", type: "column", column_filter: ["numeric"], required: true },
    { name: "y_col", type: "column", column_filter: ["numeric"], required: true },
  ];

  const seed = {};
  const used = new Set();
  for (const f of fields) {
    if (f.required && f.type === "column") {
      const cands = (f.column_filter ?? []).flatMap((t) => colsByType[t] ?? []);
      const distinct = cands.find((c) => !used.has(c));
      const pick = distinct ?? cands[0];
      if (pick !== undefined) { seed[f.name] = pick; used.add(pick); }
    }
  }

  assert.equal(seed.x_col, "treatment_weeks", "X should be the first numeric column");
  assert.equal(seed.y_col, "weight_kg", "Y should be the SECOND numeric column, not equal to X");
  assert.notEqual(seed.x_col, seed.y_col, "X and Y must be distinct");
});

test("T6.7 — single-numeric-column dataframe degrades gracefully", () => {
  const fields = [
    { name: "x_col", type: "column", column_filter: ["numeric"], required: true },
    { name: "y_col", type: "column", column_filter: ["numeric"], required: true },
  ];
  const colsByType = { numeric: ["x"], categorical: [] };

  const seed = {};
  const used = new Set();
  for (const f of fields) {
    const cands = (f.column_filter ?? []).flatMap((t) => colsByType[t] ?? []);
    const distinct = cands.find((c) => !used.has(c));
    const pick = distinct ?? cands[0];
    if (pick !== undefined) { seed[f.name] = pick; used.add(pick); }
  }
  // No second column available — fall back to the only one for both.
  assert.equal(seed.x_col, "x");
  assert.equal(seed.y_col, "x");
});

// ---- T6.8 legacy single-version figures ------------------------------

test("T6.8 — figures-workspace falls back to figures-list metadata", () => {
  assert.match(FIGURES_WORKSPACE_SRC, /figures\.find\(\(f\)\s*=>\s*f\.id\s*===\s*figId\)/,
    "loadVersions must look up the figure in the figures list");
  assert.match(FIGURES_WORKSPACE_SRC, /version:\s*fallback\.version\s*\?\?\s*1/,
    "synthetic version must default to 1 when missing");
  assert.match(FIGURES_WORKSPACE_SRC, /locked:\s*fallback\.locked\s*\?\?\s*true/,
    "synthetic legacy figure should default to locked=true");
});

test("T6.8 — fallback only fires when versions[] is empty (not on real-fail)", () => {
  // The OK-but-empty arm goes to fallback; a hard error shows the dispatch.
  assert.match(
    FIGURES_WORKSPACE_SRC,
    /res\.ok\s*&&\s*Array\.isArray\(json\.versions\)\s*&&\s*json\.versions\.length\s*>\s*0/,
    "loadVersions must check Array.isArray + length > 0 before short-circuiting",
  );
});

// ---- T6.9 sub-style validation ----------------------------------------

test("T6.9 — style-picker exports STYLES_REQUIRING_SUB and styleRequiresSub", () => {
  assert.match(STYLE_PICKER_SRC, /export const STYLES_REQUIRING_SUB/,
    "style-picker must export the required-sub list");
  assert.match(STYLE_PICKER_SRC, /export function styleRequiresSub/,
    "style-picker must export the styleRequiresSub helper");
  // Content of the list — both scientific and technical.
  const m = STYLE_PICKER_SRC.match(/STYLES_REQUIRING_SUB:\s*Style\[\]\s*=\s*\[([^\]]*)\]/);
  assert.ok(m, "STYLES_REQUIRING_SUB literal must be present");
  assert.ok(m[1].includes("scientific"), "scientific must be in STYLES_REQUIRING_SUB");
  assert.ok(m[1].includes("technical"), "technical must be in STYLES_REQUIRING_SUB");
});

test("T6.9 — PromptForm gates Generate on sub-style for those styles", () => {
  assert.match(PROMPT_FORM_SRC, /import\s*\{[^}]*styleRequiresSub[^}]*\}\s*from\s*"\.\/style-picker"/,
    "prompt-form must import styleRequiresSub from style-picker");
  assert.match(PROMPT_FORM_SRC, /styleRequiresSub\(style\)/,
    "prompt-form must consult styleRequiresSub on current style");
  assert.ok(PROMPT_FORM_SRC.includes("subOk"),
    "prompt-form must derive a subOk gate from the rule");
  // canSubmit must include subOk.
  assert.match(PROMPT_FORM_SRC, /canSubmit\s*=\s*[^;]*subOk[^;]*/,
    "canSubmit must AND in the subOk check");
});

test("T6.9 — server-side /api/images/generate returns 400 when sub-style missing", () => {
  assert.match(IMAGES_GENERATE_SRC, /STYLES_REQUIRING_SUB/,
    "generate route must declare/check the same list");
  assert.match(IMAGES_GENERATE_SRC, /STYLES_REQUIRING_SUB\.includes\(style\)\s*&&\s*!body\.sub_style/,
    "generate route must reject when style ∈ list and sub_style absent");
  assert.match(IMAGES_GENERATE_SRC, /\{\s*status:\s*400\s*\}/,
    "generate route must respond 400 on the validation failure");
});

test("T6.9 — sub-style picker renders red asterisk when unset", () => {
  assert.match(STYLE_PICKER_SRC, /text-danger/,
    "sub-style label must show a danger-colored asterisk when missing");
});
