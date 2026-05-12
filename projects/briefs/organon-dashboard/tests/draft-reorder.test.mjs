import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 7 (fix-sprint) T6.4 + T6.5 — drag-and-drop section reorder +
// keystroke-throttled live preview. Both are React UI changes; structural
// tests assert the wiring + that the existing PATCH contract is preserved.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const SECTION_LIST_SRC = readSrc("src/components/draft/section-list.tsx");
const LIVE_PREVIEW_SRC = readSrc("src/components/draft/live-preview.tsx");
const DRAFT_SLUG_ROUTE = readSrc("src/app/api/draft/[slug]/route.ts");

// ---- T6.4 drag-and-drop ----------------------------------------------

test("T6.4 — section-list wires HTML5 drag events", () => {
  for (const handler of ["onDragStart", "onDragOver", "onDragLeave", "onDrop", "onDragEnd"]) {
    assert.ok(SECTION_LIST_SRC.includes(handler),
      `section-list.tsx must declare ${handler} handler`);
  }
  assert.match(SECTION_LIST_SRC, /draggable/,
    "li elements must be marked draggable");
  assert.match(SECTION_LIST_SRC, /e\.dataTransfer\.setData/,
    "onDragStart must populate dataTransfer");
  assert.match(SECTION_LIST_SRC, /e\.dataTransfer\.getData\("text\/plain"\)/,
    "onDrop must read dataTransfer payload");
});

test("T6.4 — keyboard ▲▼ buttons remain as accessibility fallback", () => {
  assert.ok(SECTION_LIST_SRC.includes("Move up"),
    "▲ Move up button must remain");
  assert.ok(SECTION_LIST_SRC.includes("Move down"),
    "▼ Move down button must remain");
});

test("T6.4 — drag pipeline calls the same onReorder callback as ▲▼", () => {
  // Both paths must funnel through props.onReorder (no separate API call).
  assert.match(SECTION_LIST_SRC, /onReorder\(next\)/,
    "section-list must invoke props.onReorder with the new ordering");
  // reorderTo helper computes the new ordering and calls onReorder.
  assert.ok(SECTION_LIST_SRC.includes("reorderTo"),
    "drag-drop reorder must funnel through reorderTo helper");
});

test("T6.4 — visual cues: dragging opacity + drop-target border", () => {
  assert.match(SECTION_LIST_SRC, /isDragging/,
    "dragged item must be flagged for opacity treatment");
  assert.match(SECTION_LIST_SRC, /isOver/,
    "drop target must be flagged for border treatment");
  assert.ok(SECTION_LIST_SRC.includes("opacity-40"),
    "dragging item should fade via opacity-40");
  assert.ok(SECTION_LIST_SRC.includes("border-t-2 border-accent"),
    "drop target should show accent top-border");
});

test("T6.4 — PATCH /api/draft/[slug] still accepts ordering[] (no API change)", () => {
  // Phase 5 contract: reorder fires PATCH with body.ordering. T6.4 must
  // not change the wire shape.
  assert.match(DRAFT_SLUG_ROUTE, /Array\.isArray\(body\.ordering\)/,
    "draft PATCH must continue accepting ordering[]");
  assert.match(DRAFT_SLUG_ROUTE, /allowed\.ordering\s*=/,
    "draft PATCH must whitelist ordering");
});

// ---- T6.5 keystroke throttling ---------------------------------------

test("T6.5 — live-preview debounces section updates", () => {
  assert.match(LIVE_PREVIEW_SRC, /useDebouncedValue/,
    "live-preview must declare a useDebouncedValue helper");
  assert.match(LIVE_PREVIEW_SRC, /debouncedSections/,
    "live-preview must consume debouncedSections in useMemo");
  assert.match(LIVE_PREVIEW_SRC, /PREVIEW_DEBOUNCE_MS/,
    "live-preview must declare a debounce-ms constant");
});

test("T6.5 — debounce uses setTimeout (no lodash dep)", () => {
  assert.match(LIVE_PREVIEW_SRC, /setTimeout\(\(\)\s*=>\s*setDebounced/,
    "useDebouncedValue must use setTimeout, not a lib");
  assert.match(LIVE_PREVIEW_SRC, /clearTimeout\(timer\)/,
    "useDebouncedValue must clean up its timer");
});

test("T6.5 — useMemo dep list points to debounced sections, not raw props", () => {
  // The dep array of the html useMemo should mention debouncedSections.
  assert.match(LIVE_PREVIEW_SRC, /\[props\.manuscript,\s*debouncedSections,/,
    "html useMemo deps must reference debouncedSections, not props.sections");
});
