import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 14d (v1.0.1) — F-1 project switcher search + grouping + pinned.
//
// Scope (NEXT_SESSION_phase13-16.md §12):
//   F-1 — search input filters across all project groups; group
//         headers click-to-collapse; pinned-favourites at top via
//         workspace-scoped localStorage.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const TOPBAR_SRC = readSrc("src/components/shell/topbar.tsx");
const PINNED_SRC = readSrc("src/lib/state/pinned-projects.ts");

test("Phase 14d — pinned-projects helper round-trips toggle (SSR-safe)", () => {
  // SSR guards on every accessor — the topbar mounts client-side but
  // the helper is imported from a "use client" module that may still
  // be evaluated during prerender on hydration mismatch paths.
  assert.match(PINNED_SRC, /typeof window === "undefined"/);
  // Toggle is idempotent — adding a slug already in the set drops it.
  assert.match(
    PINNED_SRC,
    /export function togglePinned\(slug: string\): string\[\] \{[\s\S]+?cur\.includes\(slug\) \? cur\.filter\(\(s\) => s !== slug\) : \[\.\.\.cur, slug\]/,
  );
  // Quota / private-mode failures degrade silently — never throw.
  assert.match(PINNED_SRC, /catch \{[\s\S]+?\/\* quota/);
  // getPinned + isPinned + togglePinned exported.
  assert.match(PINNED_SRC, /export function getPinned\(\)/);
  assert.match(PINNED_SRC, /export function isPinned\(slug: string\)/);
  // Group-collapse helper sits alongside — same SSR-safe shape.
  assert.match(PINNED_SRC, /export function getCollapsedGroups\(\)/);
  assert.match(PINNED_SRC, /export function toggleGroupCollapsed\(groupId: string\)/);
  // Workspace-scoped (NOT per-tab): single key for the whole workspace.
  assert.match(PINNED_SRC, /const STORAGE_KEY = "organon:topbar:pinned-projects"/);
});

test("Phase 14d — topbar exposes search input + collapse toggles for each group", () => {
  // Search input fires controlled state; data-project-search hooks the
  // surface for click-tests.
  assert.match(TOPBAR_SRC, /data-project-search/);
  assert.match(
    TOPBAR_SRC,
    /onChange=\{\(e\) => setQuery\(e\.target\.value\)\}/,
  );
  // Search filter is case-insensitive substring match on `name`.
  assert.match(
    TOPBAR_SRC,
    /p\.name\.toLowerCase\(\)\.includes\(needle\)/,
  );
  // Group component carries data-project-group + data-collapsed for
  // click-test stability + visual regression hooks.
  assert.match(TOPBAR_SRC, /data-project-group=\{groupId\}/);
  assert.match(TOPBAR_SRC, /data-collapsed=\{collapsed \? "true" : "false"\}/);
  assert.match(TOPBAR_SRC, /data-action="toggle-group"/);
  // Collapsed groups hide their item list — `!collapsed && items.map`.
  assert.match(TOPBAR_SRC, /\{!collapsed &&[\s\S]+?items\.map/);
});

test("Phase 14d — topbar surfaces pinned section above the standard groups", () => {
  // Pinned items derived from the same filtered matches so search
  // narrows the pinned set too — favourites stay first but follow
  // the active filter.
  assert.match(
    TOPBAR_SRC,
    /const pinnedItems = matches\.filter\(\(p\) => pinnedSet\.has\(p\.slug\)\)/,
  );
  // Pinned group renders BEFORE Repo root / Briefs / Projects in the
  // dropdown JSX. The order in source is the render order.
  const pinnedIdx = TOPBAR_SRC.indexOf('label="Pinned"');
  const briefsIdx = TOPBAR_SRC.indexOf('label="Briefs"');
  const projectsIdx = TOPBAR_SRC.indexOf('label="Projects"');
  assert.ok(pinnedIdx > 0, "Pinned group must render");
  assert.ok(briefsIdx > 0, "Briefs group must render");
  assert.ok(projectsIdx > 0, "Projects group must render");
  assert.ok(pinnedIdx < briefsIdx, "Pinned must come before Briefs in JSX");
  assert.ok(pinnedIdx < projectsIdx, "Pinned must come before Projects in JSX");
});

test("Phase 14d — per-row star button toggles pin via the helper", () => {
  // Star button on every project row — data-action="toggle-pin" +
  // data-pinned hook the click-test surface; star vs hollow-star
  // glyph reflects the live state.
  assert.match(TOPBAR_SRC, /data-action="toggle-pin"/);
  assert.match(TOPBAR_SRC, /data-pinned=\{isPinned \? "true" : "false"\}/);
  assert.match(TOPBAR_SRC, /isPinned \? "★" : "☆"/);
  // handlePin delegates to togglePinned (the helper is the single
  // source of truth — never inline localStorage writes in the topbar).
  assert.match(
    TOPBAR_SRC,
    /const handlePin = \(slug: string\) => \{[\s\S]+?setPinned\(togglePinned\(slug\)\)/,
  );
});

test("Phase 14d — empty-results branch surfaces a helpful 'no matches' message", () => {
  // When no group has any items (the search excluded everything), the
  // dropdown shows a clear empty state instead of a blank panel.
  assert.match(
    TOPBAR_SRC,
    /pinnedItems\.length === 0[\s\S]+?briefs\.length === 0[\s\S]+?roots\.length === 0[\s\S]+?synthetic\.length === 0/,
  );
  assert.match(TOPBAR_SRC, /No projects match/);
});
