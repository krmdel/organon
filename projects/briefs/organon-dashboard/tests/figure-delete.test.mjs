import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 63 (v2.2) — M2: per-figure × delete affordance + new collection-
// level DELETE route + deleteFigure helper. Mirrors Phase 62.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const ROUTE_SRC = readSrc("src/app/api/figures/[fig_id]/route.ts");
const STORE_SRC = readSrc("src/lib/figures/store.ts");
const WORKSPACE_SRC = readSrc("src/components/figures/figures-workspace.tsx");

const stripComments = (s) =>
  s
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, "")
    .replace(/^[ \t]*\/\/.*$/gm, "");

test("Phase 63 — DELETE /api/figures/[fig_id]/route.ts exists with DELETE export", () => {
  assert.match(
    ROUTE_SRC,
    /export\s+async\s+function\s+DELETE/,
    "route must export an async DELETE handler",
  );
  assert.match(
    ROUTE_SRC,
    /Unknown project/,
    "route must reject missing project with the standard 404 message",
  );
});

test("Phase 63 — deleteFigure helper resolves to figureDir and uses fs.rmSync recursive force", () => {
  assert.match(
    STORE_SRC,
    /export\s+function\s+deleteFigure\s*\(/,
    "store must export deleteFigure",
  );
  const helperBody = STORE_SRC.split(/export\s+function\s+deleteFigure/)[1] ?? "";
  assert.match(
    helperBody,
    /figureDir\s*\(/,
    "deleteFigure must resolve the target via figureDir(...)",
  );
  assert.match(
    helperBody,
    /rmSync\s*\(/,
    "deleteFigure must call rmSync on the resolved figureDir",
  );
  assert.match(
    helperBody,
    /recursive:\s*true/,
    "deleteFigure must call rmSync with { recursive: true } so mask + iteration files cascade",
  );
  assert.match(
    helperBody,
    /force:\s*true/,
    "deleteFigure must use force:true so the helper is idempotent",
  );
});

test("Phase 63 — figure card splits into sibling selection + delete buttons", () => {
  const naked = stripComments(WORKSPACE_SRC);
  // Anchor on the figures.map((f) => ...) block in the figures aside.
  const liMatch = naked.match(
    /\{figures\.map\(\(f\)\s*=>[\s\S]*?<li\b[\s\S]*?<\/li>/,
  );
  assert.ok(liMatch, "figures-workspace must render figures via .map → <li>");
  const liBlock = liMatch[0];
  const buttonOpenings = liBlock.match(/<button\b/g) ?? [];
  assert.equal(
    buttonOpenings.length,
    2,
    `each figure <li> must contain 2 sibling buttons (selection + delete) — got ${buttonOpenings.length}`,
  );
});

test("Phase 63 — delete button carries data-figure-delete sentinel and stopPropagation", () => {
  assert.match(
    WORKSPACE_SRC,
    /data-figure-delete=\{f\.id\}/,
    "figures-workspace must render data-figure-delete={f.id} on the × button",
  );
  assert.match(
    WORKSPACE_SRC,
    /e\.stopPropagation\(\)/,
    "figures-workspace × handler must call e.stopPropagation()",
  );
  assert.match(
    WORKSPACE_SRC,
    /window\.confirm/,
    "figures-workspace × handler must gate behind window.confirm",
  );
});

test("Phase 63 — workspace handleDeleteFigure clears active fig_id when deleting active figure", () => {
  assert.match(
    WORKSPACE_SRC,
    /handleDeleteFigure/,
    "figures-workspace must declare handleDeleteFigure",
  );
  assert.match(
    WORKSPACE_SRC,
    /setFigures\(\(prev\)\s*=>\s*prev\.filter\(\(f\)\s*=>\s*f\.id\s*!==\s*fig_id\)\)/,
    "figures-workspace must optimistically filter the deleted figure out of state",
  );
  assert.match(
    WORKSPACE_SRC,
    /\/api\/figures\/\$\{encodeURIComponent\(fig_id\)\}\?project=/,
    "figures-workspace handler must DELETE /api/figures/${fig_id}?project=…",
  );
  assert.match(
    WORKSPACE_SRC,
    /method:\s*"DELETE"/,
    "figures-workspace handler must use method: 'DELETE'",
  );
  assert.match(
    WORKSPACE_SRC,
    /activeFigId\s*===\s*fig_id/,
    "figures-workspace handler must guard the active-fig clear branch on activeFigId === fig_id",
  );
  assert.match(
    WORKSPACE_SRC,
    /setActiveFigId\(null\)/,
    "figures-workspace handler must call setActiveFigId(null) when the active figure was deleted",
  );
});
