import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 57 (v2.1) — A3: hypothesis status state-machine relaxation.
// User-driven `supported ↔ refuted` direct flips and `archived → open`
// un-archive must be allowed without round-tripping through `synthesized`.
// Skill-source remains restricted to `open → synthesized`.
//
// Source-text-scan + inline behavioural replica per the v1.x TDD methodology.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const STORE_SRC = readSrc("src/lib/hypothesis/store.ts");

const VALID_STATUSES = new Set([
  "open",
  "synthesized",
  "supported",
  "refuted",
  "archived",
]);

// Inline replica mirroring src/lib/hypothesis/store.ts after Phase 57.
function isValidTransition(from, to, source) {
  if (!VALID_STATUSES.has(to)) return false;
  if (from === to) return true;
  if (to === "archived") return true;
  if (source === "skill") {
    return from === "open" && to === "synthesized";
  }
  // user
  if (from === "synthesized" && (to === "supported" || to === "refuted")) return true;
  if (from === "supported" || from === "refuted") {
    if (to === "synthesized" || to === "supported" || to === "refuted") return true;
  }
  if (from === "archived" && to === "open") return true;
  return false;
}

test("Phase 57 — supported → refuted is a valid user transition (direct)", () => {
  assert.equal(isValidTransition("supported", "refuted", "user"), true);
  // Implementation must encode the same edge.
  assert.match(
    STORE_SRC,
    /to\s*===\s*"synthesized"\s*\|\|\s*to\s*===\s*"supported"\s*\|\|\s*to\s*===\s*"refuted"/,
    "store.ts must allow supported|refuted → supported|refuted|synthesized for user-source",
  );
});

test("Phase 57 — refuted → supported is a valid user transition (direct)", () => {
  assert.equal(isValidTransition("refuted", "supported", "user"), true);
});

test("Phase 57 — archived → open lets the user un-archive", () => {
  assert.equal(isValidTransition("archived", "open", "user"), true);
  assert.match(
    STORE_SRC,
    /from\s*===\s*"archived"\s*&&\s*to\s*===\s*"open"/,
    "store.ts must encode archived → open un-archive for user-source",
  );
});

test("Phase 57 — skill-source still restricted to open → synthesized", () => {
  // Skill-source must remain locked. sci-council can only ratify.
  assert.equal(isValidTransition("supported", "refuted", "skill"), false);
  assert.equal(isValidTransition("refuted", "supported", "skill"), false);
  assert.equal(isValidTransition("archived", "open", "skill"), false);
  assert.equal(isValidTransition("open", "synthesized", "skill"), true);

  // Pre-existing legitimate user paths still pass.
  assert.equal(isValidTransition("synthesized", "supported", "user"), true);
  assert.equal(isValidTransition("synthesized", "refuted", "user"), true);
  assert.equal(isValidTransition("supported", "synthesized", "user"), true);
  assert.equal(isValidTransition("refuted", "synthesized", "user"), true);

  // No invalid transitions were silently legalised.
  assert.equal(isValidTransition("open", "supported", "user"), false);
  assert.equal(isValidTransition("open", "refuted", "user"), false);

  // Source-text confirms the skill-source branch is the unchanged early return.
  assert.match(
    STORE_SRC,
    /source\s*===\s*"skill"[\s\S]{0,80}from\s*===\s*"open"\s*&&\s*to\s*===\s*"synthesized"/,
    "store.ts skill-source branch must keep open → synthesized only",
  );
});
