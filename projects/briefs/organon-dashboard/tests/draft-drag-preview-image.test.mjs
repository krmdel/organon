import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 23 (v1.2) — Custom drag-preview images for figure placement (DR-7+).
//
// Closes the v1.1 "no drag preview customisation" deferred item. The
// figure-drag-source rows currently fall back to the browser-default
// drag image (a translucent copy of the row). Phase 23 mounts a hidden
// per-row <img> at the same thumbnail URL and calls
// e.dataTransfer.setDragImage(imgEl, w/2, h/2) on dragstart so the
// cursor sits in the middle of a clean thumbnail-only drag preview.
//
// Source-text scan pattern (Phases 9–22).

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const DRAG_SRC_SRC = readFileSync(
  join(ROOT, "src", "components", "draft", "figure-drag-source.tsx"),
  "utf8",
);

test("Phase 23 — figure-drag-source calls setDragImage with the row thumbnail", () => {
  // setDragImage is invoked inside the onDragStart handler.
  assert.match(
    DRAG_SRC_SRC,
    /setDragImage\s*\(/,
    "onDragStart wires setDragImage onto the dataTransfer",
  );
  // A ref (or refs) is used to read the per-row image element. The
  // hidden image needs an attachable ref so the drag handler can read
  // .current on dragstart.
  assert.match(
    DRAG_SRC_SRC,
    /useRef|createRef|refCallback|imgRef/,
    "drag handler reads a ref to the per-row hidden image",
  );
});

test("Phase 23 — drag preview img is mounted hidden, not display:none", () => {
  // display:none images don't render and setDragImage captures a blank
  // surface. The brief mandates the hidden image stays painted via
  // off-screen positioning so the browser can capture it.
  assert.doesNotMatch(
    DRAG_SRC_SRC,
    /drag-preview[^>]*display:\s*none/i,
    "hidden drag preview is NOT display:none (would capture blank)",
  );
  // Off-screen positioning marker. We accept either the literal
  // -9999px sentinel or a tailwind-style absolute+far-left equivalent.
  assert.match(
    DRAG_SRC_SRC,
    /-9999px|left:\s*-?9999|absolute.*left/,
    "hidden drag preview uses off-screen positioning to stay painted",
  );
  // The hidden image is tagged so the drag handler can find it /
  // tests can identify it.
  assert.match(
    DRAG_SRC_SRC,
    /data-drag-preview/,
    "hidden image carries data-drag-preview marker",
  );
});

test("Phase 23 — setDragImage offsets centre the cursor on the thumbnail", () => {
  // Centred offsets: setDragImage(img, w/2, h/2) — the brief mandates
  // centre, not top-left. We accept either explicit /2 division or
  // width/height halves (e.g. naturalWidth/2). Both cover the contract.
  const setDragImageCalls =
    DRAG_SRC_SRC.match(/setDragImage\s*\([^)]+\)/g) ?? [];
  assert.ok(
    setDragImageCalls.length >= 1,
    "at least one setDragImage call exists",
  );
  const callBlob = setDragImageCalls.join(" ");
  assert.match(
    callBlob,
    /\/\s*2|width.*\/\s*2|height.*\/\s*2/,
    "setDragImage offsets centre the cursor on the thumbnail (w/2, h/2)",
  );
});
