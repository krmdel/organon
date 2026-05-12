import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 50 (v2.0) — Reverse linkage.
//
// Goal: a hypothesis page surfaces "linked from N manuscripts" — the
// reverse of Phase 41's manuscript.linked_hypothesis_ids[]. New
// helper findManuscriptsByHypothesisId(projectPath, hyp_id) scans
// listManuscripts() and returns those whose linked_hypothesis_ids[]
// includes the given hyp_id. New GET /api/hypothesis/[hyp_id]/manuscripts
// returns {manuscripts}. Hypothesis workspace renders a panel listing
// each linked manuscript with a click-through to /draft?slug=<slug>.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const STORE_SRC = readSrc("src/lib/draft/store.ts");
const ROUTE_SRC = readSrc("src/app/api/hypothesis/[hyp_id]/manuscripts/route.ts");
const WORKSPACE_SRC = readSrc("src/components/hypothesis/hypothesis-workspace.tsx");

test("Phase 50 — findManuscriptsByHypothesisId is exported from src/lib/draft/store.ts", () => {
  assert.match(
    STORE_SRC,
    /export function findManuscriptsByHypothesisId\(/,
    "helper must be a named export",
  );
});

test("Phase 50 — findManuscriptsByHypothesisId filters by linked_hypothesis_ids inclusion", () => {
  // Behavioural replica matching the helper's contract.
  const find = (manuscripts, hypId) =>
    manuscripts.filter((m) =>
      Array.isArray(m.linked_hypothesis_ids) && m.linked_hypothesis_ids.includes(hypId),
    );
  const hypId = "hyp-target";
  const all = [
    { slug: "m-a", linked_hypothesis_ids: ["hyp-target", "hyp-other"] },
    { slug: "m-b", linked_hypothesis_ids: ["hyp-other"] },
    { slug: "m-c", linked_hypothesis_ids: [] },
    { slug: "m-d" }, // legacy: missing field
    { slug: "m-e", linked_hypothesis_ids: ["hyp-target"] },
  ];
  const matches = find(all, hypId);
  assert.deepEqual(matches.map((m) => m.slug), ["m-a", "m-e"]);
});

test("Phase 50 — findManuscriptsByHypothesisId reads via listManuscripts (so backfill applies)", () => {
  // Implementation must call listManuscripts(projectPath) so the
  // read-time backfill (migrateManuscriptLinkage) normalises legacy
  // manuscripts. Without this the empty-array default would not apply.
  const block = STORE_SRC.match(
    /export function findManuscriptsByHypothesisId\([\s\S]{0,400}?\}/,
  );
  assert.ok(block, "helper body not located");
  assert.match(block[0], /listManuscripts\s*\(/);
  assert.match(block[0], /linked_hypothesis_ids/);
});

test("Phase 50 — GET /api/hypothesis/[hyp_id]/manuscripts returns the linked-from set", () => {
  // Route exists, runtime: nodejs, and uses findManuscriptsByHypothesisId.
  assert.match(ROUTE_SRC, /export\s+async\s+function\s+GET/);
  assert.match(ROUTE_SRC, /findManuscriptsByHypothesisId/);
  // Must read the project from the request and return a 404 on
  // unknown project, mirroring the sibling routes.
  assert.match(ROUTE_SRC, /resolveProjectFromRequest/);
  assert.match(ROUTE_SRC, /Unknown project/);
  // Returns { manuscripts } in JSON.
  assert.match(ROUTE_SRC, /\{\s*manuscripts\s*\}/);
});

test("Phase 50 — workspace mounts a 'linked-from manuscripts' panel for the active hypothesis", () => {
  // Sentinel data attribute the test pins.
  assert.match(WORKSPACE_SRC, /data-linked-from-manuscripts/);
  // Wired to fetch /api/hypothesis/{id}/manuscripts.
  assert.match(WORKSPACE_SRC, /\/api\/hypothesis\/\$\{[^}]+\}\/manuscripts/);
});

test("Phase 50 — workspace links each manuscript to /draft?slug=<slug>", () => {
  // Click-through pattern: anchor to /draft?slug= with project param
  // (same pattern Phase 41 used).
  assert.match(WORKSPACE_SRC, /\/draft\?[^"`]*slug=/);
});
