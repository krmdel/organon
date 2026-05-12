import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 62 (v2.2) — M1: per-row × delete affordance for manuscripts +
// new DELETE /api/draft/[slug] route + deleteManuscript helper. Mirrors
// Phase 58's hypothesis delete substrate.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const ROUTE_SRC = readSrc("src/app/api/draft/[slug]/route.ts");
const STORE_SRC = readSrc("src/lib/draft/store.ts");
const LIST_SRC = readSrc("src/components/draft/draft-list.tsx");

const stripComments = (s) =>
  s
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, "")
    .replace(/^[ \t]*\/\/.*$/gm, "");

test("Phase 62 — DELETE /api/draft/[slug] route exists with DELETE export", () => {
  assert.match(
    ROUTE_SRC,
    /export\s+async\s+function\s+DELETE/,
    "route must export an async DELETE handler",
  );
  // Standard 404 for unknown projects (mirror of Phase 58 wording).
  assert.match(
    ROUTE_SRC,
    /Unknown project/,
    "route must reject missing project with the standard 404 message",
  );
});

test("Phase 62 — deleteManuscript helper resolves to the manuscript dir and uses fs.rmSync", () => {
  // Helper exists by name and is exported.
  assert.match(
    STORE_SRC,
    /export\s+function\s+deleteManuscript\s*\(/,
    "store must export deleteManuscript",
  );
  // Uses fs.rmSync (recursive + force) for idempotent cascade. Reuses the
  // existing manuscriptDir() resolver — no new path concept introduced.
  // Match either inline `rmSync(manuscriptDir(...))` or a hoisted local
  // alias seeded from manuscriptDir() then rmSync'd.
  const helperBody = STORE_SRC.split(/export\s+function\s+deleteManuscript/)[1] ?? "";
  assert.match(
    helperBody,
    /manuscriptDir\s*\(/,
    "deleteManuscript must resolve the target via manuscriptDir(...)",
  );
  assert.match(
    helperBody,
    /rmSync\s*\(/,
    "deleteManuscript must call rmSync on the resolved target",
  );
  assert.match(
    STORE_SRC,
    /recursive:\s*true/,
    "deleteManuscript must call rmSync with { recursive: true }",
  );
  assert.match(
    STORE_SRC,
    /force:\s*true/,
    "deleteManuscript must use force:true so the helper is idempotent",
  );
});

test("Phase 62 — DraftList splits each manuscript row into sibling buttons (selection + delete)", () => {
  // Static scan: every <li> inside the manuscripts list must contain
  // exactly two sibling <button> elements (selection + delete). The
  // creation form's buttons live outside this list.
  const naked = stripComments(LIST_SRC);
  // Find the manuscripts <ul>...</ul> block by anchoring on the
  // ordering map open — manuscripts.map((m) => ( <li ... > ... </li> ))
  const ulMatch = naked.match(
    /\{items\.map\(\(m\)\s*=>[\s\S]*?<li\b[\s\S]*?<\/li>/,
  );
  assert.ok(ulMatch, "DraftList must render the manuscript items via .map → <li>");
  const liBlock = ulMatch[0];
  const buttonOpenings = liBlock.match(/<button\b/g) ?? [];
  assert.equal(
    buttonOpenings.length,
    2,
    `each manuscript <li> must contain 2 sibling buttons (selection + delete) — got ${buttonOpenings.length}`,
  );
});

test("Phase 62 — delete button carries data-manuscript-delete sentinel and stopPropagation", () => {
  assert.match(
    LIST_SRC,
    /data-manuscript-delete=\{m\.slug\}/,
    "DraftList must render data-manuscript-delete={m.slug} on the × button",
  );
  assert.match(
    LIST_SRC,
    /e\.stopPropagation\(\)/,
    "DraftList × handler must call e.stopPropagation()",
  );
  assert.match(
    LIST_SRC,
    /window\.confirm/,
    "DraftList × handler must gate behind window.confirm",
  );
});

test("Phase 62 — DraftList handleDeleteManuscript optimistically prunes + clears active slug", () => {
  // Handler exists by name.
  assert.match(
    LIST_SRC,
    /handleDeleteManuscript/,
    "DraftList must declare handleDeleteManuscript",
  );
  // Optimistic prune from local items state (filter by slug).
  assert.match(
    LIST_SRC,
    /setItems\(\(prev\)\s*=>\s*prev\.filter\(\(m\)\s*=>\s*m\.slug\s*!==\s*slug\)\)/,
    "DraftList must optimistically filter the deleted manuscript out of state",
  );
  // DELETE call against the right path with project query param.
  assert.match(
    LIST_SRC,
    /\/api\/draft\/\$\{encodeURIComponent\(slug\)\}\?project=/,
    "DraftList handler must DELETE /api/draft/${slug}?project=…",
  );
  assert.match(
    LIST_SRC,
    /method:\s*"DELETE"/,
    "DraftList handler must use method: 'DELETE'",
  );
  // Active-slug guard: when the deleted manuscript was the active one,
  // strip the slug query param (mirror of Phase 58's sp.delete("hyp")).
  assert.match(
    LIST_SRC,
    /activeSlug\s*===\s*slug/,
    "DraftList handler must guard the active-slug clear branch on activeSlug === slug",
  );
  assert.match(
    LIST_SRC,
    /sp\.delete\("slug"\)/,
    "DraftList handler must drop ?slug from the URL when clearing the active slug",
  );
});
