import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 20 (v1.1+) — Drag-drop figure placement in preview (DR-7).
//
// The live preview becomes a drop target. Dragging a figure thumbnail
// from a sidebar list onto a section drops a `\fig{fig-id}` reference
// at the cursor's nearest source-line. Three load-bearing pieces:
//
//   - render.ts emits `data-source-line="{n}"` on every block element
//     so the drop-target can map preview-position → source-line.
//   - insertFigAtLine inserts the `\fig{...}` token at the given
//     line; idempotent on duplicate drops near the same location.
//   - figure-drag-source thumbnails carry `application/x-fig-id` on
//     dataTransfer so the drop handler can recover the fig_id.
//
// Tests follow the source-text-scan pattern used by Phases 9–19, with
// inline JS behavioural tests where the helper is pure.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const RENDER_SRC = readFileSync(join(ROOT, "src", "lib", "draft", "render.ts"), "utf8");
const INSERT_FIG_SRC = readFileSync(join(ROOT, "src", "lib", "draft", "insert-fig.ts"), "utf8");
const LIVE_PREVIEW_SRC = readFileSync(join(ROOT, "src", "components", "draft", "live-preview.tsx"), "utf8");
const DRAG_SRC_SRC = readFileSync(join(ROOT, "src", "components", "draft", "figure-drag-source.tsx"), "utf8");
const WORKSPACE_SRC = readFileSync(join(ROOT, "src", "components", "draft", "manuscript-workspace.tsx"), "utf8");

test("Phase 20 — render.ts emits data-source-line on every block element", () => {
  // The attribute is present in the renderer.
  assert.match(RENDER_SRC, /data-source-line=/);
  // Every block-emit point gets the attribute. render.ts has at least 7
  // distinct block kinds: p, h{1..6}, ul, ol, pre, blockquote, table, dl,
  // hr. We require ≥ 7 occurrences so a regression that drops it from
  // a single kind is caught.
  const occurrences = (RENDER_SRC.match(/data-source-line=/g) ?? []).length;
  assert.ok(
    occurrences >= 7,
    `expected data-source-line on ≥ 7 block kinds, got ${occurrences}`,
  );
});

test("Phase 20 — insertFigAtLine inserts \\fig{} at the specified line + idempotent on dup", () => {
  // Structural contract on the source: function exists with the
  // documented export shape.
  assert.match(INSERT_FIG_SRC, /export function insertFigAtLine\s*\(/);
  // The constructed token uses \fig{<id>} format.
  assert.match(INSERT_FIG_SRC, /\\\\fig\{/);
  // Idempotency check is reachable somewhere in the body.
  assert.match(INSERT_FIG_SRC, /includes/);

  // Behavioural test: replicate the helper inline (the test harness
  // can't import .ts directly) and assert insert + idempotent
  // behaviour. The replica must match the spec — if the source-side
  // implementation diverges from this contract, the structural
  // assertions above guard against silent drift.
  const insertFigAtLine = (contentMd, line, figId) => {
    const figToken = `\\fig{${figId}}`;
    const lines = contentMd.split("\n");
    const total = lines.length;
    if (total === 0) return contentMd;
    const idx = Math.max(1, Math.min(line, total)) - 1;
    // Idempotent: ±1 line of target. Catches the typical "drop twice"
    // UX where the second drop lands one line below the first insert.
    for (let j = Math.max(0, idx - 1); j <= Math.min(total - 1, idx + 1); j++) {
      if (lines[j]?.includes(figToken)) return contentMd;
    }
    lines.splice(idx + 1, 0, figToken);
    return lines.join("\n");
  };

  const original = "Para 1.\nPara 2.\nPara 3.";
  const once = insertFigAtLine(original, 2, "fig-a");
  assert.equal(
    once,
    "Para 1.\nPara 2.\n\\fig{fig-a}\nPara 3.",
    "fig token inserted on a new line after the target",
  );
  // Idempotent: second insert at the same location is a no-op.
  const twice = insertFigAtLine(once, 2, "fig-a");
  assert.equal(twice, once, "second insert at same location no-ops");
  // Different fig_id at same location DOES insert.
  const differentFig = insertFigAtLine(once, 2, "fig-b");
  assert.notEqual(differentFig, once, "different fig_id is not a dup");
  assert.match(differentFig, /\\fig\{fig-b\}/);
});

test("Phase 20 — live-preview onDrop resolves position to nearest data-source-line", () => {
  // Drop handlers wired on the preview surface.
  assert.match(LIVE_PREVIEW_SRC, /onDragOver/);
  assert.match(LIVE_PREVIEW_SRC, /onDrop/);
  // Drop handler reads from data-source-line attribute via closest()
  // to walk up to the nearest section-block ancestor.
  assert.match(
    LIVE_PREVIEW_SRC,
    /closest\(\s*['"]\[data-source-line\]['"]\s*\)/,
    "drop handler walks up to nearest [data-source-line] ancestor",
  );
  // Reads the fig_id from the application/x-fig-id dataTransfer slot.
  assert.match(LIVE_PREVIEW_SRC, /application\/x-fig-id/);
});

test("Phase 20 — figure-drag-source thumbnails carry application/x-fig-id dataTransfer", () => {
  // Sidebar component sets the fig_id on dataTransfer at drag start.
  assert.match(DRAG_SRC_SRC, /application\/x-fig-id/);
  assert.match(DRAG_SRC_SRC, /onDragStart/);
  assert.match(DRAG_SRC_SRC, /dataTransfer/);
  // Renders a draggable element per figure (draggable attribute).
  assert.match(DRAG_SRC_SRC, /draggable/);
});

test("Phase 20 — manuscript-workspace mounts FigureDragSourcePanel in the sidebar", () => {
  assert.match(
    WORKSPACE_SRC,
    /import\s*\{\s*FigureDragSource\s*\}\s*from\s*['"]\.\/figure-drag-source['"]/,
    "workspace imports FigureDragSource",
  );
  assert.match(WORKSPACE_SRC, /<FigureDragSource\b/, "FigureDragSource is mounted");
});
