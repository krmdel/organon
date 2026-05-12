import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 39 (v1.4) — F2 shared BulkPaperOps primitive.
//
// Phase 38's library-panel inlined the ALL/NONE/INVERT/DELETE row.
// Phase 39 lifts it to `primitives/bulk-paper-ops.tsx` so library-panel,
// the linked-papers picker (paper-picker), and the chat-panel
// selected-files chips all render the same affordance with consistent
// data-action hooks.
//
// `onDelete` is OPTIONAL — surfaces without "delete from data store"
// semantics (e.g. chat-panel chips: deselect, not delete) skip the
// 4th button.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const PRIMITIVE_SRC = readSrc("src/components/primitives/bulk-paper-ops.tsx");
const LIB_PANEL_SRC = readSrc("src/components/lit/library-panel.tsx");
const PAPER_PICKER_SRC = readSrc("src/components/hypothesis/paper-picker.tsx");
const CHAT_PANEL_SRC = readSrc("src/components/draft/chat-panel.tsx");

test("Phase 39 — BulkPaperOps renders 3-4 buttons with the canonical data-action hooks", () => {
  // Public surface: named export with the documented props.
  assert.match(PRIMITIVE_SRC, /export function BulkPaperOps\(/);
  // Required props.
  assert.match(PRIMITIVE_SRC, /onAll:\s*\(\)\s*=>\s*void/);
  assert.match(PRIMITIVE_SRC, /onNone:\s*\(\)\s*=>\s*void/);
  assert.match(PRIMITIVE_SRC, /onInvert:\s*\(\)\s*=>\s*void/);
  // Optional onDelete.
  assert.match(PRIMITIVE_SRC, /onDelete\?:\s*\(\)\s*=>\s*void/);
  // Numeric counters — totalCount + selectedCount.
  assert.match(PRIMITIVE_SRC, /selectedCount:\s*number/);
  assert.match(PRIMITIVE_SRC, /totalCount:\s*number/);
  // Canonical data-action hooks.
  assert.match(PRIMITIVE_SRC, /data-action=["']bulk-all["']/);
  assert.match(PRIMITIVE_SRC, /data-action=["']bulk-none["']/);
  assert.match(PRIMITIVE_SRC, /data-action=["']bulk-invert["']/);
  assert.match(PRIMITIVE_SRC, /data-action=["']bulk-delete["']/);
  // The DELETE button is conditional on onDelete being supplied — pin
  // the gate via a regex that allows either `onDelete &&` or
  // `typeof onDelete` patterns.
  assert.match(PRIMITIVE_SRC, /onDelete[\s\S]{0,50}(&&|\?\.)/);
});

test("Phase 39 — library-panel mounts the shared BulkPaperOps primitive", () => {
  assert.match(LIB_PANEL_SRC, /import\s*\{\s*BulkPaperOps\s*\}/);
  assert.match(LIB_PANEL_SRC, /<BulkPaperOps/);
});

test("Phase 39 — claim-form linked-papers picker mounts the shared primitive", () => {
  // The picker (paper-picker.tsx) replaces its internal BulkSelect
  // with the shared BulkPaperOps primitive.
  assert.match(PAPER_PICKER_SRC, /import\s*\{\s*BulkPaperOps\s*\}/);
  assert.match(PAPER_PICKER_SRC, /<BulkPaperOps/);
});

test("Phase 39 — chat-panel selected-files surface mounts the shared primitive", () => {
  assert.match(CHAT_PANEL_SRC, /import\s*\{\s*BulkPaperOps\s*\}/);
  assert.match(CHAT_PANEL_SRC, /<BulkPaperOps/);
});
