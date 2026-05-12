import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 58 (v2.1) — B1: × delete affordance per row in History sidebar.
// DELETE /api/hypothesis/[hyp_id] already exists; this phase wires the UI.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const HISTORY_SRC = readSrc("src/components/hypothesis/hypothesis-history.tsx");
const WORKSPACE_SRC = readSrc("src/components/hypothesis/hypothesis-workspace.tsx");
const ROUTE_SRC = readSrc("src/app/api/hypothesis/[hyp_id]/route.ts");

test("Phase 58 — hypothesis-history renders × button per row with data-hypothesis-delete sentinel", () => {
  // Sentinel attribute lets the browser E2E walk + future automation pin
  // the affordance reliably.
  assert.match(
    HISTORY_SRC,
    /data-hypothesis-delete=\{h\.id\}/,
    "history must render data-hypothesis-delete={h.id} on the × button",
  );
  // The visible glyph is "×".
  assert.match(
    HISTORY_SRC,
    /×/,
    "history must render the × glyph for delete",
  );
  // Confirm prop is wired (not hardcoded). The button only renders when
  // onDelete is provided so consumers without the prop still see read-only.
  assert.match(
    HISTORY_SRC,
    /onDelete\?:\s*\(hyp_id:\s*string\)\s*=>\s*void/,
    "history must declare an optional onDelete prop",
  );
  assert.match(
    HISTORY_SRC,
    /\{onDelete\s*&&/,
    "history must render the × button only when onDelete is supplied",
  );
});

test("Phase 58 — workspace declares handleDeleteHypothesis + threads it as prop", () => {
  assert.match(
    WORKSPACE_SRC,
    /handleDeleteHypothesis/,
    "workspace must declare handleDeleteHypothesis",
  );
  // Threaded onto HypothesisHistory.
  assert.match(
    WORKSPACE_SRC,
    /onDelete=\{handleDeleteHypothesis\}/,
    "workspace must thread handleDeleteHypothesis onto <HypothesisHistory onDelete={…}>",
  );
});

test("Phase 58 — handler hits DELETE /api/hypothesis/[hyp_id]", () => {
  // The route handler must exist on disk.
  assert.match(
    ROUTE_SRC,
    /export\s+async\s+function\s+DELETE/,
    "DELETE handler must exist at /api/hypothesis/[hyp_id]",
  );
  // The workspace handler must use method: "DELETE" against the right path.
  assert.match(
    WORKSPACE_SRC,
    /\/api\/hypothesis\/\$\{encodeURIComponent\(hyp_id\)\}/,
    "workspace must DELETE via /api/hypothesis/${encodeURIComponent(hyp_id)}",
  );
  assert.match(
    WORKSPACE_SRC,
    /method:\s*"DELETE"/,
    "workspace handler must use method: 'DELETE'",
  );
});

test("Phase 58 — workspace clears activeId when the deleted hypothesis was active", () => {
  // The optimistic prune must include an activeId === hyp_id branch
  // that clears activeId + the URL hyp param so the user lands on the
  // new-claim form.
  assert.match(
    WORKSPACE_SRC,
    /setHypotheses\(\(prev\)\s*=>\s*prev\.filter\(\(h\)\s*=>\s*h\.id\s*!==\s*hyp_id\)\)/,
    "workspace must optimistically filter the deleted hypothesis out of state",
  );
  assert.match(
    WORKSPACE_SRC,
    /if\s*\(activeId\s*===\s*hyp_id\)/,
    "workspace must guard the activeId-clear branch on activeId === hyp_id",
  );
  assert.match(
    WORKSPACE_SRC,
    /setActiveId\(null\)/,
    "workspace must call setActiveId(null) when the deleted hypothesis was active",
  );
  assert.match(
    WORKSPACE_SRC,
    /sp\.delete\("hyp"\)/,
    "workspace must drop ?hyp from the URL when clearing activeId",
  );
});

test("Phase 58 — × button uses window.confirm before firing DELETE", () => {
  // The user-visible confirm gate. Same pattern as Phase 38 batch-delete.
  assert.match(
    HISTORY_SRC,
    /window\.confirm/,
    "history must call window.confirm before invoking onDelete",
  );
  // And must stop the click from bubbling into the row's onSelect.
  assert.match(
    HISTORY_SRC,
    /e\.stopPropagation\(\)/,
    "history must stopPropagation so the × click doesn't bubble into onSelect",
  );
});
