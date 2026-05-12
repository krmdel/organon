import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 14c (v1.0.1) — F-3 figure version history strip.
//
// Scope (NEXT_SESSION_phase13-16.md §14):
//   F-3 — every APPLY EDIT bumps version; version selector strip in
//         the workspace; original (v1) always retrievable; older
//         versions are read-only (canvas locked, editing tools hidden).
//   Read-time backfill: pre-Phase-14c figures default to a single v1
//         via the existing loadVersions fallback path.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const STRIP_SRC = readSrc("src/components/figures/version-strip.tsx");
const WORKSPACE_SRC = readSrc("src/components/figures/figures-workspace.tsx");

test("Phase 14c — version-strip sorts ascending so original is always leftmost", () => {
  // The caller may pass versions in any order; the strip owns the
  // display order so "original is on the left" stays a contract.
  assert.match(
    STRIP_SRC,
    /const sorted = \[\.\.\.versions\]\.sort\(\(a, b\) => a\.version - b\.version\)/,
  );
  // Latest version derived from the highest version number after sort
  // — used to tag the rightmost chip "latest".
  assert.match(STRIP_SRC, /const latestVersion = sorted\[sorted\.length - 1\]\?\.version \?\? 1/);
});

test("Phase 14c — version-strip tags v1 'orig' and the latest 'latest'", () => {
  // The labels are visual hooks the user sees AND data-attributes that
  // click-tests can assert against without depending on copy.
  assert.match(STRIP_SRC, /const isOriginal = v\.version === 1/);
  assert.match(STRIP_SRC, /const isLatest = v\.version === latestVersion/);
  assert.match(STRIP_SRC, /data-original=\{isOriginal \? "true" : "false"\}/);
  assert.match(STRIP_SRC, /data-latest=\{isLatest \? "true" : "false"\}/);
  assert.match(STRIP_SRC, /isOriginal \? "orig" : "latest"/);
});

test("Phase 14c — workspace derives latestVersion + isViewingHistorical", () => {
  // latestVersion derived from the highest .version in the array;
  // single-version figures default to 1 via the fallback.
  assert.match(
    WORKSPACE_SRC,
    /const latestVersion = useMemo\([\s\S]+?Math\.max\(\.\.\.versions\.map\(\(v\) => v\.version\)\)/,
  );
  // isViewingHistorical = the user picked a non-latest version.
  assert.match(
    WORKSPACE_SRC,
    /const isViewingHistorical =\s*!!activeFigure && activeFigure\.version < latestVersion/,
  );
});

test("Phase 14c — historical view locks the canvas + hides editing tools + surfaces a banner", () => {
  // Banner shows the version + a "Go to v{latest}" jump button.
  assert.match(WORKSPACE_SRC, /data-historical-banner/);
  assert.match(WORKSPACE_SRC, /data-action="goto-latest"/);
  assert.match(
    WORKSPACE_SRC,
    /onClick=\{\(\) => setActiveVersion\(latestVersion\)\}/,
  );
  // ImageCanvas + AnnotationLayer both receive `tool="none"` when
  // historical — pointer events on the active surface are no-ops.
  assert.match(
    WORKSPACE_SRC,
    /tool=\{isViewingHistorical \? "none" : tool\}/,
  );
  assert.match(
    WORKSPACE_SRC,
    /tool=\{isViewingHistorical \? "none" : annotateTool\}/,
  );
  // Edit prompt textarea hidden when historical, even if the mask
  // tool was active before the user switched versions.
  assert.match(
    WORKSPACE_SRC,
    /\{!isViewingHistorical && figureMode === "edit-with-ai" && tool !== "none"/,
  );
  // Toolbar shows a clear read-only message instead of the active tools.
  assert.match(
    WORKSPACE_SRC,
    /Read-only view — editing tools hidden/,
  );
});

test("Phase 14c — version strip renders for any figure with ≥ 1 version (original always retrievable)", () => {
  // The strip used to gate on `versions.length > 1` so single-version
  // figures didn't show the strip at all. After Phase 14c the user
  // ALWAYS sees v1 — even before any AI edit — so the original is
  // explicit + retrievable from day one.
  assert.match(WORKSPACE_SRC, /versions\.length >= 1/);
});
