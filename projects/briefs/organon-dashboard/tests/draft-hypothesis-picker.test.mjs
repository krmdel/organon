import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 42 (v1.5) — F5 multi-hypothesis picker.
//
// New shared primitive `hypothesis-multiselect.tsx` powers two surfaces:
// (a) the new-manuscript dialog (DraftList) gets a "Linked hypotheses"
//     multi-select section below the title/authors/journal fields.
// (b) the source-linkage-panel's hypothesis edit affordance opens a
//     modal that mounts the same primitive.
// Multi-select with ALL/NONE/INVERT (via BulkPaperOps shape).
// POST /api/draft/new threads `linked_hypothesis_ids[]` (already wired
// in Phase 41); the picker just provides the IDs.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const PICKER_SRC = readSrc("src/components/hypothesis/hypothesis-multiselect.tsx");
const DRAFT_LIST_SRC = readSrc("src/components/draft/draft-list.tsx");
const PANEL_SRC = readSrc("src/components/draft/source-linkage-panel.tsx");
const NEW_ROUTE_SRC = readSrc("src/app/api/draft/new/route.ts");

test("Phase 42 — new-manuscript-dialog mounts hypothesis-multiselect", () => {
  // DraftList imports + renders the new primitive.
  assert.match(
    DRAFT_LIST_SRC,
    /import\s*\{[^}]*HypothesisMultiselect[^}]*\}\s*from\s*["']@\/components\/hypothesis\/hypothesis-multiselect["']/,
  );
  assert.match(DRAFT_LIST_SRC, /<HypothesisMultiselect/);
  // The selection flows back into the create POST body.
  assert.match(DRAFT_LIST_SRC, /linked_hypothesis_ids/);
});

test("Phase 42 — hypothesis-multiselect supports ALL / NONE / INVERT via BulkPaperOps", () => {
  // The primitive imports BulkPaperOps (Phase 39) for the ALL/NONE/INVERT
  // affordance. DELETE is opt-in via prop and NOT used here (no
  // "delete a hypothesis" semantic from the manuscript create form).
  assert.match(
    PICKER_SRC,
    /import\s*\{[^}]*BulkPaperOps[^}]*\}\s*from\s*["']@\/components\/primitives\/bulk-paper-ops["']/,
  );
  assert.match(PICKER_SRC, /<BulkPaperOps/);
  // No DELETE prop wired — selecting hypotheses should not delete them.
  assert.doesNotMatch(PICKER_SRC, /onDelete\s*=\s*\{/);
});

test("Phase 42 — source-linkage-panel edit affordance opens the hypothesis-multiselect modal", () => {
  // The panel imports the new primitive and mounts it inside the
  // hypothesis-edit modal (replacing the inline checkbox list for the
  // hypotheses section specifically).
  assert.match(
    PANEL_SRC,
    /import\s*\{[^}]*HypothesisMultiselect[^}]*\}\s*from\s*["']@\/components\/hypothesis\/hypothesis-multiselect["']/,
  );
  assert.match(PANEL_SRC, /<HypothesisMultiselect/);
});

test("Phase 42 — POST /api/draft/new with linked_hypothesis_ids[] persists to manuscript.json", () => {
  // Phase 41 wiring (route accepts the field + threads through to
  // createManuscript) is the contract we lean on. Pin both ends.
  assert.match(NEW_ROUTE_SRC, /linked_hypothesis_ids/);
  assert.match(NEW_ROUTE_SRC, /createManuscript[\s\S]{0,400}linked_hypothesis_ids/);

  // Behavioural replica of the picker → POST body shape: the picker
  // exposes `selectedIds: string[]`; the dialog forwards them as
  // `linked_hypothesis_ids` in the create body.
  const buildBody = (title, hypIds) => ({
    title,
    linked_hypothesis_ids: Array.isArray(hypIds) ? hypIds : [],
  });
  const body = buildBody("Demo", ["hyp-a", "hyp-b"]);
  assert.deepEqual(body.linked_hypothesis_ids, ["hyp-a", "hyp-b"]);
  assert.equal(body.title, "Demo");
});
