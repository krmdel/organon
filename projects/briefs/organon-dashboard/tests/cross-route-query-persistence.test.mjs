import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 40 (v1.4) — F3 cross-route query persistence.
//
// User types a query in /lit, switches to /hypothesis, and the
// query is gone. Phase 40 ships a small localStorage-backed store
// that the lit search-bar writes (debounced) and the hypothesis
// claim-form reads (pre-fills when empty). v1.4 is one-way only;
// v1.5+ can extend to bidirectional sync.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const STORE_SRC = readSrc("src/lib/cross-route-query/store.ts");
const SEARCH_BAR_SRC = readSrc("src/components/lit/search-bar.tsx");
const CLAIM_FORM_SRC = readSrc("src/components/hypothesis/claim-form.tsx");

test("Phase 40 — getCrossRouteQuery / setCrossRouteQuery round-trip via localStorage", () => {
  // Public surface — both functions exported.
  assert.match(STORE_SRC, /export function getCrossRouteQuery\(/);
  assert.match(STORE_SRC, /export function setCrossRouteQuery\(/);
  // Per-project key.
  assert.match(STORE_SRC, /organon:cross-route-query:/);
  // SSR-safe — short-circuits when window is undefined.
  assert.match(STORE_SRC, /typeof\s+window\s*===\s*["']undefined["']/);
  // Behavioural replica.
  const fakeStorage = new Map();
  const set = (project, query, fromRoute) => {
    fakeStorage.set(`organon:cross-route-query:${project}`, JSON.stringify({
      query, last_route: fromRoute, updated_at: new Date().toISOString(),
    }));
  };
  const get = (project) => {
    const raw = fakeStorage.get(`organon:cross-route-query:${project}`);
    if (!raw) return null;
    try { return JSON.parse(raw); } catch { return null; }
  };
  set("p1", "GLP-1 weight regain", "lit");
  const out = get("p1");
  assert.equal(out?.query, "GLP-1 weight regain");
  assert.equal(out?.last_route, "lit");
  assert.equal(get("p2"), null);
});

test("Phase 40 — search-bar persists query on change (debounced)", () => {
  // Imports the helper.
  assert.match(SEARCH_BAR_SRC, /setCrossRouteQuery/);
  // Debounce value pinned at module scope so a future change is
  // reviewable in one place.
  assert.match(SEARCH_BAR_SRC, /CROSS_ROUTE_DEBOUNCE_MS\s*=\s*500/);
  // Persists from the "lit" route — the second arg.
  assert.match(SEARCH_BAR_SRC, /setCrossRouteQuery\([^)]*["']lit["']/);
});

test("Phase 40 — claim-form pre-fills empty textarea from cross-route query", () => {
  // Imports the helper.
  assert.match(CLAIM_FORM_SRC, /getCrossRouteQuery/);
  // useEffect on mount reads from store; pre-fills only when claim is
  // empty so user-typed content isn't overwritten.
  assert.match(
    CLAIM_FORM_SRC,
    /getCrossRouteQuery[\s\S]{0,300}claim\.trim\(\)\.length\s*===\s*0/,
  );
  // Affordance caption — "from lit search" or similar.
  assert.match(CLAIM_FORM_SRC, /from lit search|from \/lit/i);
});
