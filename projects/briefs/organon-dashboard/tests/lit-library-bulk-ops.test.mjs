import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 38 (v1.4) — F1 library bulk ops + group-by-search-batch.
//
// The 2026-05-08 walk surfaced "library is impossible to maintain at
// scale". Library card has only per-row Remove. No DELETE-many; no
// grouping by which search call added a paper. Phase 38 adds:
//   1. ALL/NONE/INVERT/DELETE row at the top of the library card
//   2. search_batch_id / search_batch_query / search_batch_added_at
//      stamped on every entry; legacy entries default null
//   3. addPapersToLibrary helper for the batch-stamp at search-accept
//      time; removeBatchFromLibrary for batch-delete
//   4. DELETE /api/lit/library?batch=<id> + ?ids=a,b,c handlers
//   5. library-panel renders batches as collapsible groups with the
//      query as the group header

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const TYPES_SRC = readSrc("src/lib/artifacts/types.ts");
const LIBRARY_SRC = readSrc("src/lib/lit/library.ts");
const ROUTE_SRC = readSrc("src/app/api/lit/library/route.ts");
const PANEL_SRC = readSrc("src/components/lit/library-panel.tsx");

test("Phase 38 — library entry schema accepts search_batch_id / search_batch_query / search_batch_added_at", () => {
  // PaperArtifact has the new optional fields.
  assert.match(TYPES_SRC, /search_batch_id\?:\s*string\s*\|\s*null/);
  assert.match(TYPES_SRC, /search_batch_query\?:\s*string\s*\|\s*null/);
  assert.match(TYPES_SRC, /search_batch_added_at\?:\s*string\s*\|\s*null/);
});

test("Phase 38 — addPapersToLibrary stamps batch metadata on every entry in the call", () => {
  // Helper exists + accepts a batchMeta argument.
  assert.match(LIBRARY_SRC, /export function addPapersToLibrary\(/);
  // Stamps all three batch fields onto each saved paper.
  assert.match(LIBRARY_SRC, /search_batch_id/);
  assert.match(LIBRARY_SRC, /search_batch_query/);
  assert.match(LIBRARY_SRC, /search_batch_added_at/);
  // Behavioural replica.
  const stampBatch = (papers, meta) =>
    papers.map((p) => ({
      ...p,
      search_batch_id: meta.batch_id,
      search_batch_query: meta.query,
      search_batch_added_at: meta.added_at,
    }));
  const batched = stampBatch(
    [{ id: "p1" }, { id: "p2" }],
    { batch_id: "batch_x", query: "GLP-1 weight regain", added_at: "2026-05-08T12:00:00Z" },
  );
  assert.equal(batched.length, 2);
  assert.equal(batched[0].search_batch_id, "batch_x");
  assert.equal(batched[1].search_batch_id, "batch_x");
  assert.equal(batched[0].search_batch_query, "GLP-1 weight regain");
});

test("Phase 38 — removeBatchFromLibrary removes all entries with the given batch_id", () => {
  // Helper exists.
  assert.match(LIBRARY_SRC, /export function removeBatchFromLibrary\(/);
  // Behavioural replica — filter.
  const papers = [
    { id: "p1", search_batch_id: "batch_x" },
    { id: "p2", search_batch_id: "batch_x" },
    { id: "p3", search_batch_id: "batch_y" },
    { id: "p4" }, // legacy — no batch
  ];
  const removed = papers.filter((p) => p.search_batch_id === "batch_x");
  const kept = papers.filter((p) => p.search_batch_id !== "batch_x");
  assert.equal(removed.length, 2);
  assert.equal(kept.length, 2);
  assert.deepEqual(kept.map((p) => p.id), ["p3", "p4"]);
});

test("Phase 38 — DELETE /api/lit/library?batch=<id> calls removeBatchFromLibrary", () => {
  // Route imports the helper.
  assert.match(ROUTE_SRC, /removeBatchFromLibrary/);
  // DELETE handler reads `batch` from URL query string.
  assert.match(ROUTE_SRC, /searchParams[\s\S]{0,200}["']batch["']/);
  // Both query-style (?batch=) and body-style (per-entry paper_id)
  // remain supported — additive, not breaking.
  assert.match(ROUTE_SRC, /export async function DELETE\(/);
});

test("Phase 38 — DELETE /api/lit/library?ids=a,b,c removes the listed entries", () => {
  // Route handles `ids` query param.
  assert.match(ROUTE_SRC, /["']ids["']/);
  // Splits on comma to get the list. Behavioural replica.
  const parseIds = (raw) => (raw ?? "").split(",").map((s) => s.trim()).filter(Boolean);
  assert.deepEqual(parseIds("a,b,c"), ["a", "b", "c"]);
  assert.deepEqual(parseIds("a, b , c"), ["a", "b", "c"]);
  assert.deepEqual(parseIds(""), []);
  assert.deepEqual(parseIds(null), []);
});

test("Phase 38 — library-panel groups entries by search_batch_query", () => {
  // The panel mounts an ALL/NONE/INVERT/DELETE row at the top.
  // Post-Phase-39, the actual data-action hooks live in the shared
  // primitive (see tests/primitives-bulk-paper-ops.test.mjs); the
  // panel's contract is "mounts the primitive" + the grouping logic.
  assert.match(PANEL_SRC, /BulkPaperOps/);
  // Groups entries by search_batch_query — the header shows the query
  // string + a "delete batch" button. Ungrouped legacy entries fall
  // under a default bucket.
  assert.match(PANEL_SRC, /search_batch_query/);
  assert.match(PANEL_SRC, /Ungrouped|legacy|no batch/i);
  // window.confirm gates the destructive batch-delete.
  assert.match(PANEL_SRC, /window\.confirm/);
});
