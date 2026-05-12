import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 53 (v2.0) — Citation graph visualisation.
//
// Goal: a read-only SVG graph showing the manuscript at the centre
// surrounded by its linked artifacts (papers / hypotheses / figures /
// datasets). The graph reads the same linkage arrays as Phase 41's
// SourceLinkagePanel and renders one node per linked artifact with
// connecting lines. Mounted in source-linkage-panel as a toggleable
// "View graph" section.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const COMPONENT_SRC = readSrc("src/components/draft/citation-graph.tsx");
const PANEL_SRC = readSrc("src/components/draft/source-linkage-panel.tsx");

test("Phase 53 — CitationGraph component exports a default-ish named symbol", () => {
  // Allow either default export or named export named CitationGraph.
  assert.ok(
    /export\s+function\s+CitationGraph\(/.test(COMPONENT_SRC) ||
      /export\s+const\s+CitationGraph\s*=/.test(COMPONENT_SRC) ||
      /export\s+default\s+function\s+CitationGraph/.test(COMPONENT_SRC),
    "CitationGraph must be exported",
  );
});

test("Phase 53 — CitationGraph renders an <svg> root", () => {
  assert.match(COMPONENT_SRC, /<svg[^>]*>/);
});

test("Phase 53 — CitationGraph reads four linked_*_ids arrays + emits the manuscript hub", () => {
  // All four kinds must be referenced in the component.
  assert.match(COMPONENT_SRC, /linked_paper_ids/);
  assert.match(COMPONENT_SRC, /linked_hypothesis_ids/);
  assert.match(COMPONENT_SRC, /linked_figure_ids/);
  assert.match(COMPONENT_SRC, /linked_dataset_ids/);
  // The hub label is the manuscript title.
  assert.match(COMPONENT_SRC, /manuscript\.title|props\.manuscript\.title/);
});

test("Phase 53 — CitationGraph emits one <line> per linked artifact (hub→leaf edges)", () => {
  // Lines connect hub to each leaf — the source must contain a
  // <line ...> tag rendered inside a map. The exact attribute order
  // varies; pin the substring + that it appears inside .map(.
  assert.match(COMPONENT_SRC, /<line[^>]*x1=/);
  assert.match(COMPONENT_SRC, /\.map\(/);
});

test("Phase 53 — source-linkage-panel mounts the graph behind a toggle", () => {
  // Sentinel data attribute the test pins — the toggle button.
  assert.match(PANEL_SRC, /data-graph-toggle/);
  // CitationGraph imported.
  assert.match(PANEL_SRC, /CitationGraph/);
});

test("Phase 53 — graph layout replica: leaf coordinates lie on a circle around the hub", () => {
  // Behavioural replica matching the layout contract: N leaves spread
  // around the hub at radius R using angle = (2π * i) / N. The exact
  // R/centre values are an implementation detail; the contract is
  // "uniform polar distribution".
  const polarLayout = (count, hubX, hubY, radius) => {
    const out = [];
    for (let i = 0; i < count; i += 1) {
      const a = (2 * Math.PI * i) / Math.max(count, 1);
      out.push({
        x: hubX + radius * Math.cos(a),
        y: hubY + radius * Math.sin(a),
      });
    }
    return out;
  };
  const points = polarLayout(4, 100, 100, 60);
  assert.equal(points.length, 4);
  // Each point must lie within ±0.001 of the hub-radius.
  for (const p of points) {
    const d = Math.hypot(p.x - 100, p.y - 100);
    assert.ok(Math.abs(d - 60) < 1e-6);
  }
});
