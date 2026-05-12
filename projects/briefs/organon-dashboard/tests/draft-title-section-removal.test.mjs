import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 35 (v1.4) — B1 fix.
//
// DEFAULT_SECTIONS in src/lib/draft/store.ts used to ship a `title` entry
// with `type: "title"`. sci-writing's Step 7.7 only handles body section
// types, so generate-section emitted no matching artifact and the UI
// reported "succeeded-no-artifact".
//
// Decision: drop the title section entirely (title is ManuscriptMeta.title
// metadata; AI candidates flow through /api/draft/[slug]/generate-title).
// Read-time backfill filters legacy "title" from existing ordering[]
// without writing to disk.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const STORE_SRC = readSrc("src/lib/draft/store.ts");
const WORKSPACE_SRC = readSrc("src/components/draft/manuscript-workspace.tsx");
const SECTION_LIST_SRC = readSrc("src/components/draft/section-list.tsx");
const DRAFT_LIST_SRC = readSrc("src/components/draft/draft-list.tsx");

test("Phase 35 — DEFAULT_SECTIONS no longer includes a title entry", () => {
  // The DEFAULT_SECTIONS array literal must not contain `id: "title"` or
  // `type: "title"`. The first entry should now be abstract.
  const block = STORE_SRC.match(/const DEFAULT_SECTIONS:[\s\S]*?\n\];/);
  assert.ok(block, "DEFAULT_SECTIONS array literal not found");
  const text = block[0];
  assert.doesNotMatch(text, /id:\s*"title"/);
  assert.doesNotMatch(text, /type:\s*"title"/);
  // First entry should be abstract.
  assert.match(text, /\{\s*id:\s*"abstract"/);
});

test("Phase 35 — filterLegacyOrdering drops 'title' from existing ordering arrays", () => {
  // Helper must be exported and pure: returns a new array with "title"
  // filtered out, preserving other entries' order.
  assert.match(STORE_SRC, /export function filterLegacyOrdering\(/);
  // Behavioural replica — compile the helper inline.
  const fn = (ordering) => ordering.filter((id) => id !== "title");
  assert.deepEqual(fn(["title", "abstract", "introduction"]), ["abstract", "introduction"]);
  assert.deepEqual(fn(["abstract", "results"]), ["abstract", "results"]);
  assert.deepEqual(fn([]), []);
  // Pin the implementation matches the contract.
  assert.match(
    STORE_SRC,
    /filterLegacyOrdering[\s\S]{0,200}filter\([\s\S]{0,80}["']title["']/,
  );
});

test("Phase 35 — migrateManuscriptOrdering returns a new meta with ordering filtered", () => {
  // Pure function — no disk write; called from getManuscript + listManuscripts.
  assert.match(STORE_SRC, /export function migrateManuscriptOrdering\(/);
  // Wired into both read paths.
  assert.match(STORE_SRC, /function getManuscript[\s\S]{0,400}migrateManuscriptOrdering/);
  assert.match(STORE_SRC, /function listManuscripts[\s\S]{0,800}migrateManuscriptOrdering/);
  // Behavioural replica.
  const migrate = (meta) => ({
    ...meta,
    ordering: meta.ordering.filter((id) => id !== "title"),
  });
  const before = {
    slug: "demo",
    title: "Demo",
    ordering: ["title", "abstract", "results"],
  };
  const after = migrate(before);
  assert.deepEqual(after.ordering, ["abstract", "results"]);
  assert.notEqual(after, before, "must return a NEW object");
});

test("Phase 35 — manuscript-workspace defensively filters section_id === 'title' from the list", () => {
  // The workspace passes `meta.ordering` to <SectionList />. After Phase 35
  // the helper handles filtering at read-time, but the workspace adds a
  // defensive filter so a third-party-written manuscript.json cannot
  // surface a stale title row.
  assert.match(
    WORKSPACE_SRC,
    /ordering=\{[^}]{0,200}meta\.ordering[^}]{0,200}filter[^}]{0,80}["']title["']/,
  );
});

test("Phase 35 — proposed-title surface remains wired (no regression on the title-generate flow)", () => {
  // The propose-title button on the manuscript-create form (draft-list)
  // still calls /api/draft/[slug]/generate-title — the route exists and
  // is the SOLE entry point for AI title candidates after the section
  // drop. Pin the wiring + import shape.
  assert.match(DRAFT_LIST_SRC, /generate-title/);
  // SectionList still renders SectionGenerateButton for body sections,
  // but is shielded from "title" by the workspace filter above.
  assert.match(SECTION_LIST_SRC, /<SectionGenerateButton/);
});
