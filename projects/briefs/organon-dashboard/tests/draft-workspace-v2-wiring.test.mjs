import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 50–54 (v2.0) — workspace wiring regression guards.
//
// The lib helpers, routes, and UI primitives shipped behind opt-in
// callback props. These tests pin that the workspace actually wires
// the callbacks so the buttons render and the routes get hit.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const WORKSPACE_SRC = readSrc("src/components/draft/manuscript-workspace.tsx");
const MODAL_SRC = readSrc("src/components/draft/section-overrides-modal.tsx");

test("Phase 52 wiring — manuscript-workspace passes onImportNotebook to SectionList", () => {
  // The handler must be defined and the prop must be threaded through
  // the SectionList component instance.
  assert.match(WORKSPACE_SRC, /handleImportNotebook/);
  assert.match(WORKSPACE_SRC, /onImportNotebook=\{handleImportNotebook\}/);
  // The handler POSTs to the import-notebook route.
  assert.match(WORKSPACE_SRC, /\/import-notebook/);
});

test("Phase 51 wiring — manuscript-workspace passes onEditSectionOverrides + mounts the modal", () => {
  assert.match(WORKSPACE_SRC, /handleEditSectionOverrides/);
  assert.match(WORKSPACE_SRC, /onEditSectionOverrides=\{handleEditSectionOverrides\}/);
  // Modal mounted via gating state.
  assert.match(WORKSPACE_SRC, /editingOverridesForSection/);
  assert.match(WORKSPACE_SRC, /SectionOverridesModal/);
});

test("Phase 51 wiring — modal exists with the data sentinel + 4 tabs", () => {
  assert.match(MODAL_SRC, /export function SectionOverridesModal\(/);
  assert.match(MODAL_SRC, /data-section-overrides-modal/);
  // Four tab keys.
  assert.match(MODAL_SRC, /['"]papers['"]/);
  assert.match(MODAL_SRC, /['"]figures['"]/);
  assert.match(MODAL_SRC, /['"]hypotheses['"]/);
  assert.match(MODAL_SRC, /['"]datasets['"]/);
  // Save handler PATCHes via parent callback (onSave receives the
  // override_* arrays).
  assert.match(MODAL_SRC, /override_linked_paper_ids/);
  assert.match(MODAL_SRC, /override_linked_figure_ids/);
  assert.match(MODAL_SRC, /override_linked_hypothesis_ids/);
  assert.match(MODAL_SRC, /override_linked_dataset_ids/);
});

test("Phase 51 wiring — workspace POST hits /sections/[section_id] with override_* keys", () => {
  // The save handler must PATCH the section route with the override keys.
  assert.match(WORKSPACE_SRC, /handleSaveSectionOverrides/);
  assert.match(WORKSPACE_SRC, /\/sections\/\$\{[^}]+\}/);
  assert.match(WORKSPACE_SRC, /method:\s*['"]PATCH['"]/);
});
