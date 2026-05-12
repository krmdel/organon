import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 41 (v1.5) — F4 source-linkage-panel.
//
// NEW src/components/draft/source-linkage-panel.tsx renders four
// sections (Hypotheses · Papers · Figures · Datasets), each with a
// count + edit affordance + an expandable list. The "edit" action
// PATCHes /api/draft/[slug] with the updated linkage array. The
// manuscript-workspace mounts the panel by default (no explicit
// toggle to suppress).

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const PANEL_SRC = readSrc("src/components/draft/source-linkage-panel.tsx");
const WORKSPACE_SRC = readSrc("src/components/draft/manuscript-workspace.tsx");

test("Phase 41 — source-linkage-panel renders four sections (Hypotheses / Papers / Figures / Datasets)", () => {
  // Component exports a named function (PascalCase).
  assert.match(PANEL_SRC, /export function SourceLinkagePanel/);
  // Each section heading appears verbatim somewhere in the JSX.
  assert.match(PANEL_SRC, /Hypotheses/);
  assert.match(PANEL_SRC, /Papers/);
  assert.match(PANEL_SRC, /Figures/);
  assert.match(PANEL_SRC, /Datasets/);
});

test("Phase 41 — each section has a count + edit affordance", () => {
  // Each section row surfaces a count + edit button via stable
  // data attributes. The component renders sections from a map(), so
  // the data-attrs use a key expression (`data-linkage-section={s.key}`)
  // rather than literal strings.
  assert.match(PANEL_SRC, /data-linkage-section=/);
  assert.match(PANEL_SRC, /data-linkage-edit=/);
  // The four keys must appear as JS string literals anywhere in the
  // source (either as the section dispatch table or as default props).
  assert.match(PANEL_SRC, /["']hypotheses["']/);
  assert.match(PANEL_SRC, /["']papers["']/);
  assert.match(PANEL_SRC, /["']figures["']/);
  assert.match(PANEL_SRC, /["']datasets["']/);
  // Edit affordance is a button (not a link) — keeps the surface
  // accessible without dragging in next/link semantics.
  assert.match(PANEL_SRC, /<button[\s\S]{0,200}data-linkage-edit/);
});

test("Phase 41 — adding a paper from the modal picker calls PATCH /api/draft/[slug]", () => {
  // The save handler issues a PATCH against /api/draft/{slug} with
  // the updated linkage array.
  assert.match(PANEL_SRC, /method:\s*"PATCH"/);
  assert.match(PANEL_SRC, /\/api\/draft\//);
  // The handler signature accepts a LinkageField + the array of ids;
  // the body sends them via JSON.stringify with a computed key so the
  // surface stays DRY across the four linkage shapes.
  assert.match(PANEL_SRC, /LinkageField/);
  assert.match(PANEL_SRC, /JSON\.stringify\(\s*\{\s*\[field\]\s*:\s*ids\s*\}\s*\)/);
  // The four linkage field names appear in the LinkageField type union.
  assert.match(PANEL_SRC, /linked_hypothesis_ids/);
  assert.match(PANEL_SRC, /linked_paper_ids/);
  assert.match(PANEL_SRC, /linked_figure_ids/);
  assert.match(PANEL_SRC, /linked_dataset_ids/);
});

test("Phase 41 — workspace mounts the source-linkage-panel by default", () => {
  // ManuscriptWorkspace imports + renders <SourceLinkagePanel /> without
  // a hidden-by-default toggle. The panel's props include the manuscript
  // meta + the four lists.
  assert.match(
    WORKSPACE_SRC,
    /import\s*\{[^}]*SourceLinkagePanel[^}]*\}\s*from\s*["']\.\/source-linkage-panel["']/,
  );
  assert.match(WORKSPACE_SRC, /<SourceLinkagePanel/);
});
