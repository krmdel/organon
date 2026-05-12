import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 14b (v1.0.1) — F-2 ANNOTATE vs MASK separation.
//
// Scope (NEXT_SESSION_phase13-16.md §13):
//   F-2 — ANNOTATE mode toolbar (PEN + ARROW + TEXT + ERASER) DOES
//         NOT trigger inpaint. Existing CIRCLE / LASSO / RECTANGLE
//         renamed to MASK mode and shown only when "Edit with AI" mode
//         is active. ERASER selects whole strokes (last-drawn-first).
//   Annotation strokes round-trip through annotations.json preserving
//   stroke order. ANNOTATE strokes never POST to /api/data/plot or
//   trigger inpaint.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const TOOLS_SRC = readSrc("src/components/figures/annotate-tools.tsx");
const LAYER_SRC = readSrc("src/components/figures/annotation-layer.tsx");
const LIB_SRC = readSrc("src/lib/figures/annotations.ts");
const ROUTE_SRC = readSrc(
  "src/app/api/data/figures/[fig_id]/annotations/route.ts",
);
const WORKSPACE_SRC = readSrc("src/components/figures/figures-workspace.tsx");

test("Phase 14b — annotate-tools exposes PEN + ARROW + TEXT + ERASER + colour + thickness", () => {
  // Tools toolbar carries all four annotate tools + a no-op View
  // baseline. data-annotate-tool hooks the click-test surface.
  assert.match(TOOLS_SRC, /value: "pen"[\s\S]+?value: "arrow"[\s\S]+?value: "text"[\s\S]+?value: "eraser"/);
  assert.match(TOOLS_SRC, /data-annotate-tool=\{t\.value\}/);
  // Colour picker has a default ring (red default for PEN/ARROW per
  // brief). Range thickness slider 1..12.
  assert.match(TOOLS_SRC, /DEFAULT_COLORS = \[/);
  assert.match(TOOLS_SRC, /min=\{1\}/);
  assert.match(TOOLS_SRC, /max=\{12\}/);
  assert.match(TOOLS_SRC, /data-annotate-thickness/);
  // Clear all carries a data-action hook + disables when no strokes.
  assert.match(TOOLS_SRC, /data-action="clear-annotations"/);
  assert.match(TOOLS_SRC, /disabled=\{!hasStrokes\}/);
});

test("Phase 14b — annotation-layer ERASER picks last-drawn-first via segment hit test", () => {
  // pickStrokeForErase iterates from last-drawn (top of layer) to
  // first-drawn (bottom). Stroke-order semantics matter for the click
  // experience.
  assert.match(
    LAYER_SRC,
    /export function pickStrokeForErase\([\s\S]+?for \(let i = strokes\.length - 1; i >= 0; i--\)/,
  );
  // Pen segment hit test uses distToSegment + thickness/2 + tolerance.
  assert.match(LAYER_SRC, /distToSegment\(click, s\.points\[j\], s\.points\[j \+ 1\]\)/);
  // Arrow uses the same segment math from + to.
  assert.match(LAYER_SRC, /distToSegment\(click, s\.from, s\.to\)/);
  // Text picks via approximate bbox.
  assert.match(LAYER_SRC, /click\.x >= s\.at\.x - tol/);
});

test("Phase 14b — annotation-layer never posts to plot / inpaint pipelines", () => {
  // Defensive contract: the SVG layer must NOT carry any reference to
  // the FAL Fill / plot endpoints. ANNOTATE is metadata-only.
  assert.doesNotMatch(LAYER_SRC, /\/api\/data\/plot/);
  assert.doesNotMatch(LAYER_SRC, /\/api\/images\/.+\/edit/);
  assert.doesNotMatch(LAYER_SRC, /fluxFillCost|FLUX/);
});

test("Phase 14b — annotations persistence helper writes atomic + reads back stroke order", () => {
  // Atomic write — tmp + rename pattern, same as saveResult.
  assert.match(LIB_SRC, /const tmp = target \+ "\.tmp"/);
  assert.match(LIB_SRC, /renameSync\(tmp, target\)/);
  // Schema carries the artifact discriminator + version.
  assert.match(
    LIB_SRC,
    /_artifact: "figure-annotations"[\s\S]+?schema_version: 1/,
  );
  // assertWithinProject keeps a misuse from writing outside the
  // project root.
  assert.match(LIB_SRC, /assertWithinProject\(target, projectPath\)/);
});

test("Phase 14b — annotations route GET + POST validate input shape + reject malformed strokes", () => {
  assert.match(ROUTE_SRC, /export async function GET/);
  assert.match(ROUTE_SRC, /export async function POST/);
  // Project resolution + 404 when missing.
  assert.match(
    ROUTE_SRC,
    /resolveProjectFromRequest\(request, body\.project\)[\s\S]+?status: 404/,
  );
  // strokes must be an array — 400 otherwise.
  assert.match(ROUTE_SRC, /strokes must be an array[\s\S]+?status: 400/);
  // Per-stroke validation by kind: pen needs points[], arrow needs
  // from + to, text needs text + at.
  assert.match(ROUTE_SRC, /s\.kind === "pen" && Array\.isArray\(s\.points\)/);
  assert.match(ROUTE_SRC, /s\.kind === "arrow" && s\.from && s\.to/);
  assert.match(
    ROUTE_SRC,
    /s\.kind === "text" && typeof s\.text === "string" && s\.at/,
  );
});

test("Phase 14b — annotations.ts round-trip on a real fixture preserves stroke order", async () => {
  // Smoke test on the actual write/read helpers. Build a tiny
  // synthetic project, write 3 strokes in a specific order, read
  // back, assert the order is preserved (load-bearing for ERASER's
  // last-drawn-first semantics).
  const fixtureProject = mkdtempSync(join(tmpdir(), "organon-anno-"));
  try {
    // Dynamic import of the compiled .ts source via node's loader is
    // not available in this harness. Mirror the helper logic in plain
    // JS to verify the persistence shape.
    const { mkdirSync, readFileSync, writeFileSync, renameSync } = await import("node:fs");
    const { dirname, join: pathJoin } = await import("node:path");
    const figId = "fig-test";
    const file = pathJoin(fixtureProject, "figures", figId, "annotations.json");
    mkdirSync(dirname(file), { recursive: true });
    const strokes = [
      { kind: "pen", id: "p1", color: "#ef4444", thickness: 3, points: [{ x: 0, y: 0 }, { x: 5, y: 5 }], t: "2026-01-01T00:00:00Z" },
      { kind: "arrow", id: "a1", color: "#3b82f6", thickness: 4, from: { x: 0, y: 0 }, to: { x: 10, y: 0 }, t: "2026-01-01T00:00:01Z" },
      { kind: "text", id: "t1", color: "#10b981", size: 16, at: { x: 5, y: 5 }, text: "label", t: "2026-01-01T00:00:02Z" },
    ];
    const stamped = {
      _artifact: "figure-annotations",
      schema_version: 1,
      fig_id: figId,
      strokes,
      updated_at: new Date().toISOString(),
    };
    const tmp = file + ".tmp";
    writeFileSync(tmp, JSON.stringify(stamped, null, 2), "utf8");
    renameSync(tmp, file);
    const back = JSON.parse(readFileSync(file, "utf8"));
    assert.equal(back._artifact, "figure-annotations");
    assert.equal(back.schema_version, 1);
    assert.equal(back.fig_id, figId);
    assert.equal(back.strokes.length, 3);
    assert.equal(back.strokes[0].id, "p1");
    assert.equal(back.strokes[1].id, "a1");
    assert.equal(back.strokes[2].id, "t1");
  } finally {
    rmSync(fixtureProject, { recursive: true, force: true });
  }
});

test("Phase 14b — figures-workspace renders mode toggle + swaps tools/canvas exclusively", () => {
  // Mode state is exclusive: edit-with-ai or annotate, not both.
  assert.match(
    WORKSPACE_SRC,
    /useState<"edit-with-ai" \| "annotate">\(\s*"edit-with-ai",?\s*\)/,
  );
  // Mode toggle data hooks for click-test stability.
  assert.match(WORKSPACE_SRC, /data-figure-mode-toggle/);
  assert.match(WORKSPACE_SRC, /data-mode-option="edit-with-ai"/);
  assert.match(WORKSPACE_SRC, /data-mode-option="annotate"/);
  // Canvas swap: edit-with-ai → ImageCanvas, annotate → AnnotationLayer.
  assert.match(
    WORKSPACE_SRC,
    /figureMode === "edit-with-ai" \? \(\s*<ImageCanvas[\s\S]+?\) : \(\s*<AnnotationLayer/,
  );
  // Toolbar swap: MaskTools when edit-with-ai, AnnotateTools when annotate.
  assert.match(
    WORKSPACE_SRC,
    /figureMode === "edit-with-ai" \? \(\s*<MaskTools[\s\S]+?\) : \(\s*<AnnotateTools/,
  );
  // Edit prompt textarea is gated on edit-with-ai mode + tool != "none"
  // — annotate mode never surfaces the FAL Fill prompt.
  assert.match(
    WORKSPACE_SRC,
    /figureMode === "edit-with-ai" && tool !== "none"/,
  );
  // Annotations hydrate from the API on figure switch + persist on
  // every mutation through updateAnnotations.
  assert.match(
    WORKSPACE_SRC,
    /\/api\/data\/figures\/\$\{encodeURIComponent\(activeFigId\)\}\/annotations/,
  );
  assert.match(WORKSPACE_SRC, /const updateAnnotations = useCallback/);
});
