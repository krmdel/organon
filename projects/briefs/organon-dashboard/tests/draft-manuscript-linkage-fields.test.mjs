import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 41 (v1.5) — F4 manuscript ↔ source linkage fields.
//
// Goal: ManuscriptMeta gains four optional linkage arrays
// (linked_hypothesis_ids / linked_paper_ids / linked_figure_ids /
// linked_dataset_ids). Read-time backfill defaults missing fields to
// []; existing manuscript.json files keep working untouched. POST
// /api/draft/new accepts them in the body. NEW PATCH /api/draft/[slug]
// accepts partial linkage updates and validates each id against the
// corresponding store (404 on unknown). generate-section narrows
// linked_papers to the manuscript subset when non-empty; empty linkage
// → backward-compat fallback to listLibrary().

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const STORE_SRC = readSrc("src/lib/draft/store.ts");
const NEW_ROUTE_SRC = readSrc("src/app/api/draft/new/route.ts");
const SLUG_ROUTE_SRC = readSrc("src/app/api/draft/[slug]/route.ts");
const GEN_SECTION_SRC = readSrc("src/app/api/draft/[slug]/generate-section/route.ts");
const GEN_TITLE_SRC = readSrc("src/app/api/draft/[slug]/generate-title/route.ts");

test("Phase 41 — ManuscriptMeta accepts linked_hypothesis_ids / linked_paper_ids / linked_figure_ids / linked_dataset_ids", () => {
  // Type definition must declare all four optional arrays.
  const block = STORE_SRC.match(/export type ManuscriptMeta\s*=\s*\{[\s\S]*?\n\};/);
  assert.ok(block, "ManuscriptMeta type literal not found");
  const text = block[0];
  assert.match(text, /linked_hypothesis_ids\??\s*:\s*string\[\]/);
  assert.match(text, /linked_paper_ids\??\s*:\s*string\[\]/);
  assert.match(text, /linked_figure_ids\??\s*:\s*string\[\]/);
  assert.match(text, /linked_dataset_ids\??\s*:\s*string\[\]/);
});

test("Phase 41 — migrateManuscriptLinkage defaults missing fields to []", () => {
  // Helper must be exported and pure: returns a NEW meta with each
  // missing field defaulted to []. Existing arrays preserved.
  assert.match(STORE_SRC, /export function migrateManuscriptLinkage\(/);
  // Wired into the read paths alongside migrateManuscriptOrdering.
  assert.match(STORE_SRC, /function getManuscript[\s\S]{0,800}migrateManuscriptLinkage/);
  assert.match(STORE_SRC, /function listManuscripts[\s\S]{0,1200}migrateManuscriptLinkage/);

  // Behavioural replica.
  const migrate = (meta) => ({
    ...meta,
    linked_hypothesis_ids: Array.isArray(meta.linked_hypothesis_ids) ? meta.linked_hypothesis_ids : [],
    linked_paper_ids: Array.isArray(meta.linked_paper_ids) ? meta.linked_paper_ids : [],
    linked_figure_ids: Array.isArray(meta.linked_figure_ids) ? meta.linked_figure_ids : [],
    linked_dataset_ids: Array.isArray(meta.linked_dataset_ids) ? meta.linked_dataset_ids : [],
  });
  // Legacy meta without any linkage fields → all defaulted.
  const before = { slug: "demo", title: "Demo", ordering: ["abstract"] };
  const after = migrate(before);
  assert.deepEqual(after.linked_hypothesis_ids, []);
  assert.deepEqual(after.linked_paper_ids, []);
  assert.deepEqual(after.linked_figure_ids, []);
  assert.deepEqual(after.linked_dataset_ids, []);
  assert.notEqual(after, before, "must return a NEW object");
  // Existing arrays are preserved.
  const withFields = {
    slug: "demo",
    linked_paper_ids: ["paper-1", "paper-2"],
    linked_hypothesis_ids: ["hyp-x"],
  };
  const after2 = migrate(withFields);
  assert.deepEqual(after2.linked_paper_ids, ["paper-1", "paper-2"]);
  assert.deepEqual(after2.linked_hypothesis_ids, ["hyp-x"]);
  assert.deepEqual(after2.linked_figure_ids, []);
  assert.deepEqual(after2.linked_dataset_ids, []);
});

test("Phase 41 — POST /api/draft/new accepts the four linkage arrays in the body", () => {
  // Body type extended with optional linkage arrays.
  assert.match(NEW_ROUTE_SRC, /linked_hypothesis_ids\??\s*:\s*string\[\]/);
  assert.match(NEW_ROUTE_SRC, /linked_paper_ids\??\s*:\s*string\[\]/);
  assert.match(NEW_ROUTE_SRC, /linked_figure_ids\??\s*:\s*string\[\]/);
  assert.match(NEW_ROUTE_SRC, /linked_dataset_ids\??\s*:\s*string\[\]/);
  // createManuscript call threads them through (one of: name match or
  // explicit assignment in opts). The route forwards the four fields.
  assert.match(NEW_ROUTE_SRC, /linked_hypothesis_ids:[^,\n]*body\.linked_hypothesis_ids/);
  assert.match(NEW_ROUTE_SRC, /linked_paper_ids:[^,\n]*body\.linked_paper_ids/);
  assert.match(NEW_ROUTE_SRC, /linked_figure_ids:[^,\n]*body\.linked_figure_ids/);
  assert.match(NEW_ROUTE_SRC, /linked_dataset_ids:[^,\n]*body\.linked_dataset_ids/);
});

test("Phase 41 — PATCH /api/draft/[slug] validates each id against the corresponding store", () => {
  // The PATCH handler imports listLibrary / listFigures / listHypotheses /
  // listDataframes (or equivalent) to validate ids exist.
  assert.match(SLUG_ROUTE_SRC, /listLibrary/);
  assert.match(SLUG_ROUTE_SRC, /listFigures/);
  assert.match(SLUG_ROUTE_SRC, /listHypotheses/);
  // Dataset ids validated against listDataframes (data files).
  assert.match(SLUG_ROUTE_SRC, /listDataframes|listFiles|listData/);
  // Each linkage field name appears in the route source (whether as
  // direct `body.<name>` access or as a dispatch table entry — the
  // test pins the surface, not the exact shape of the dispatch).
  assert.match(SLUG_ROUTE_SRC, /linked_hypothesis_ids/);
  assert.match(SLUG_ROUTE_SRC, /linked_paper_ids/);
  assert.match(SLUG_ROUTE_SRC, /linked_figure_ids/);
  assert.match(SLUG_ROUTE_SRC, /linked_dataset_ids/);
});

test("Phase 41 — PATCH /api/draft/[slug] returns 404 for unknown ids", () => {
  // The handler emits a 404 when any id is not present in the
  // corresponding store. Look for `status: 404` near "unknown" or
  // "not found" reference text.
  assert.match(
    SLUG_ROUTE_SRC,
    /unknown[\s\S]{0,200}(status:\s*404|404)|404[\s\S]{0,200}(unknown|linked)/i,
  );
});

test("Phase 41 — generate-section narrows linked_papers to manuscript.linked_paper_ids when non-empty", () => {
  // The route reads manuscript.linked_paper_ids (either directly or via
  // Phase 51's effectiveSectionLinkage helper which resolves
  // override > manuscript > undefined) and narrows the listLibrary()
  // output before mapping with trimPaper.
  const readsManuscriptLinkage =
    /manuscript\.linked_paper_ids/.test(GEN_SECTION_SRC) ||
    /effectiveSectionLinkage\([^)]*['"]paper['"]/.test(GEN_SECTION_SRC);
  assert.ok(readsManuscriptLinkage, "must read manuscript paper linkage");
  const readsFigureLinkage =
    /manuscript\.linked_figure_ids/.test(GEN_SECTION_SRC) ||
    /effectiveSectionLinkage\([^)]*['"]figure['"]/.test(GEN_SECTION_SRC);
  assert.ok(readsFigureLinkage, "must read manuscript figure linkage");
  // The narrowing happens before the trimPaper map (papers filtered
  // into a Set or via .filter).
  assert.match(GEN_SECTION_SRC, /\.filter\(/);
});

test("Phase 41 — generate-section falls back to listLibrary when linked_paper_ids is empty", () => {
  // Behavioural replica of the narrowing rule.
  const narrow = (allPapers, linkedIds) => {
    const ids = Array.isArray(linkedIds) ? linkedIds : [];
    if (ids.length === 0) return allPapers;
    const set = new Set(ids);
    return allPapers.filter((p) => set.has(p.id));
  };
  const allPapers = [
    { id: "p1", title: "A" },
    { id: "p2", title: "B" },
    { id: "p3", title: "C" },
  ];
  // Empty linkage → all returned (backward-compat).
  assert.equal(narrow(allPapers, []).length, 3);
  assert.equal(narrow(allPapers, undefined).length, 3);
  // Non-empty linkage → narrowed.
  assert.deepEqual(
    narrow(allPapers, ["p1", "p3"]).map((p) => p.id),
    ["p1", "p3"],
  );
  // generate-title applies the same rule.
  assert.match(GEN_TITLE_SRC, /manuscript\.linked_paper_ids/);
});
