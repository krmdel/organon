import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 18 (v1.1+) — Typography / layout preset registry (DR-8).
//
// Named presets bound to pandoc-friendly args. Users pick from a
// dropdown in the export menu. Five canonical presets ship by default
// (default + two-column + nature + science + ieee). Markdown / HTML /
// Substack ignore presets (no pandoc).
//
// Tests follow the source-text-scan pattern used by Phases 9–17:
// plain Node ESM, no TS imports, regex over readFileSync output.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const REGISTRY_SRC = readFileSync(
  join(ROOT, "src", "lib", "draft", "typography-presets.ts"),
  "utf8",
);
const ROUTE_SRC = readFileSync(
  join(ROOT, "src", "app", "api", "draft", "[slug]", "export", "route.ts"),
  "utf8",
);
const MENU_SRC = readFileSync(
  join(ROOT, "src", "components", "draft", "export-menu.tsx"),
  "utf8",
);

test("Phase 18 — typography-presets registry exports 5 canonical preset ids with pandoc args", () => {
  // Required exports.
  assert.match(REGISTRY_SRC, /export function getPreset\b/);
  assert.match(REGISTRY_SRC, /export function listPresets\b/);
  // 5 canonical preset ids must each appear in the source.
  for (const id of ["default", "two-column", "nature", "science", "ieee"]) {
    assert.match(REGISTRY_SRC, new RegExp(`["']${id}["']`), `missing canonical preset id: ${id}`);
  }
  // Each preset carries pandoc-bound args. Accept either `pdfArgs` or
  // `pandocArgs` to leave the implementation room.
  assert.ok(
    /pdfArgs/.test(REGISTRY_SRC) || /pandocArgs/.test(REGISTRY_SRC),
    "presets must carry pandoc-bound args (pdfArgs or pandocArgs)",
  );
});

test("Phase 18 — getPreset(unknown_id) falls back to the default preset, not null", () => {
  // Per brief §6.3: "Unknown id falls back to default, not 404. UX: a
  // stale preset_id from localStorage shouldn't fail export."
  //
  // Acceptable implementation patterns (any one is sufficient):
  //   1) `find(...) ?? <default>`
  //   2) `find(...) || <default>`
  //   3) `if (!found) return <default>`
  //   4) explicit ternary fallback to "default"
  const hasFallback =
    /\.find\([^)]*\)\s*\?\?/s.test(REGISTRY_SRC) ||
    /\.find\([^)]*\)\s*\|\|/s.test(REGISTRY_SRC) ||
    /if\s*\(\s*![\w.]+\s*\)\s*return\s+/.test(REGISTRY_SRC) ||
    /return\s+\w+\s*\?\s*\w+\s*:\s*\w+/.test(REGISTRY_SRC);
  assert.ok(
    hasFallback,
    "getPreset must fall back to the default preset on unknown id",
  );
  // The default id is referenced inside getPreset's reachable code path.
  assert.match(REGISTRY_SRC, /["']default["']/);
});

test("Phase 18 — export-menu renders preset dropdown for PDF + DOCX", () => {
  // Menu reads from the registry.
  assert.match(MENU_SRC, /listPresets\b/, "menu calls listPresets()");
  // A select / dropdown surface with a stable hook for click-tests.
  assert.match(MENU_SRC, /data-preset-picker/, "preset dropdown carries data-preset-picker hook");
  // The dropdown has a label / hint that mentions PDF + DOCX so the
  // user knows the scope.
  assert.match(
    MENU_SRC,
    /PDF[^"]{0,16}(DOCX|\+)|DOCX[^"]{0,16}PDF/i,
    "label mentions PDF + DOCX as the preset scope",
  );
  // workspace-owned state — menu takes presetId + onPresetChange as props.
  assert.match(MENU_SRC, /presetId/, "presetId prop");
  assert.match(MENU_SRC, /onPresetChange/, "onPresetChange callback");
});

test("Phase 18 — export route forwards preset_id to pandoc args", () => {
  // Route accepts preset_id in the body.
  assert.match(ROUTE_SRC, /preset_id/, "body type / parser carries preset_id");
  // Imports the registry helper.
  assert.match(
    ROUTE_SRC,
    /import\s*\{[^}]*\bgetPreset\b[^}]*\}\s*from/,
    "route imports getPreset",
  );
  // The pdf / docx branch spreads / merges preset args into the spawn argv.
  assert.ok(
    /\.\.\.preset\.pdfArgs|\.\.\.preset\.pandocArgs|preset\.pdfArgs\.|preset\.pandocArgs\./.test(ROUTE_SRC),
    "preset args must be spread / merged into the pandoc argv",
  );
});
