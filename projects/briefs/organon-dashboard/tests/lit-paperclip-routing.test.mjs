import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 45 (v1.6) — F8: paperclip-as-default for biomedical queries.
// Tests are pure source-text-scans + inline behavioural replicas; no live
// MCP / HTTP calls per the established TDD methodology.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const SEARCH_SRC = readSrc("src/lib/lit/search.ts");
const PAPERCLIP_SRC = readSrc("src/lib/lit/paperclip-search.ts");
const ROUTE_SRC = readSrc("src/app/api/lit/search/route.ts");
const SEARCHBAR_SRC = readSrc("src/components/lit/search-bar.tsx");
const ARTIFACT_TYPES = readSrc("src/lib/artifacts/types.ts");

// ---- routing layer ----------------------------------------------------

test("Phase 45 — searchPapers routes biomedical queries to paperclip primary", () => {
  // The routing layer must call paperclip first for biomedical queries
  // when sources are not pinned.
  assert.match(
    SEARCH_SRC,
    /searchPaperclip/,
    "search.ts must import or reference searchPaperclip",
  );
  assert.match(
    SEARCH_SRC,
    /PAPERCLIP_FALLBACK_THRESHOLD/,
    "search.ts must declare a fallback threshold constant for shortfall fanout",
  );
  // Auto-routing must guard on (a) biomedical AND (b) caller didn't pin sources.
  assert.match(
    SEARCH_SRC,
    /opts\.sources\s*&&\s*opts\.sources\.length\s*>\s*0/,
    "search.ts must check that sources is unpinned before auto-routing",
  );
});

test("Phase 45 — paperclip primary returns ≥ N results → API tier is skipped", () => {
  // Inline replica of the routing decision: when paperclip returns enough,
  // skip the API tier.
  const N = 8;
  const decideRoute = (paperclipCount, threshold) => {
    if (paperclipCount >= threshold) return "skip-fallback";
    return "fanout-fallback";
  };
  assert.equal(decideRoute(10, N), "skip-fallback");
  assert.equal(decideRoute(8, N), "skip-fallback");
  assert.equal(decideRoute(7, N), "fanout-fallback");
  assert.equal(decideRoute(0, N), "fanout-fallback");

  // The implementation must encode the same gate.
  assert.match(
    SEARCH_SRC,
    /paperclipResults\.length\s*>=\s*PAPERCLIP_FALLBACK_THRESHOLD/,
    "search.ts must encode the ≥ threshold short-circuit",
  );
});

test("Phase 45 — paperclip primary returns < N → API tier fanout merges in", () => {
  // The shortfall path must run the API tier and merge into one ranked list.
  // The merged result preserves the dedupeByDoi contract — paperclip-only
  // entries with no DOI cohabit with API-tier ones, and DOI matches union.
  assert.match(
    SEARCH_SRC,
    /paperclipResults\.length\s*<\s*PAPERCLIP_FALLBACK_THRESHOLD/,
    "search.ts must check the shortfall branch",
  );
  // The fallback branch must still call dedupeByDoi via the existing pipeline.
  assert.match(
    SEARCH_SRC,
    /dedupeByDoi\(/,
    "search.ts must keep dedupeByDoi in the merged path",
  );
});

test("Phase 45 — non-biomedical queries skip paperclip and hit API tier directly", () => {
  // Inline replica: when biomedical=false AND sources unpinned, route is API-only.
  const route = (biomedical, pinned) => {
    if (pinned) return "honour-explicit";
    if (biomedical) return "paperclip-primary";
    return "api-tier";
  };
  assert.equal(route(false, false), "api-tier");
  assert.equal(route(true, false), "paperclip-primary");
  assert.equal(route(true, true), "honour-explicit");
  assert.equal(route(false, true), "honour-explicit");

  // Routing decision must consult `biomedical` (already classified) before
  // calling paperclip.
  assert.match(
    SEARCH_SRC,
    /if\s*\(\s*biomedical\s*&&[^)]*paperclipEnabled/,
    "search.ts must gate paperclip-primary on biomedical && unpinned sources",
  );
});

test("Phase 45 — explicit sources override disables auto-routing", () => {
  // When the caller pins sources (e.g. paperclip absent, only ['arxiv']), the
  // router honours the choice and never auto-routes to paperclip.
  assert.match(
    SEARCH_SRC,
    /paperclipEnabled\s*=\s*[^;]*sources\.includes\("paperclip"\)/,
    "search.ts must derive paperclipEnabled from the explicit sources list",
  );
});

test("Phase 45 — search-bar shows the biomedical caption when classifier fires", () => {
  // search-bar.tsx must surface a "🩺 biomedical detected" hint when the
  // classifier auto-toggles paperclip on.
  assert.match(
    SEARCHBAR_SRC,
    /biomedical[Cc]aption|biomedical-detected|biomedical detected/,
    "search-bar.tsx must render a biomedical-detected caption",
  );
  // Paperclip must appear in ALL_SOURCES.
  assert.match(
    SEARCHBAR_SRC,
    /"paperclip"/,
    "search-bar.tsx must include paperclip in the source toggles",
  );
});

// ---- wrapper module shape --------------------------------------------

test("Phase 45 — paperclip-search.ts exports searchPaperclip with PaperResult shape", () => {
  assert.match(
    PAPERCLIP_SRC,
    /export\s+(?:async\s+)?function\s+searchPaperclip/,
    "paperclip-search.ts must export searchPaperclip",
  );
  // Must return PaperResult[] (the same shape as pubmed/arxiv handlers).
  assert.match(
    PAPERCLIP_SRC,
    /Promise<PaperResult\[\]>/,
    "searchPaperclip must return Promise<PaperResult[]>",
  );
  // Must stamp source: "paperclip" on each result.
  assert.match(
    PAPERCLIP_SRC,
    /source:\s*"paperclip"/,
    "paperclip wrapper must stamp source: \"paperclip\" on each result",
  );
});

test("Phase 45 — PaperResult source union includes \"paperclip\"", () => {
  // The pubmed.ts shared PaperResult type must allow "paperclip" as a source.
  // The wrapper imports PaperResult; if the type doesn't accept it the
  // wrapper would fail typecheck.
  const PUBMED_SRC = readSrc("src/lib/paper-search/pubmed.ts");
  assert.match(
    PUBMED_SRC,
    /"paperclip"/,
    "PaperResult source union must include \"paperclip\"",
  );
});

// ---- artifact + route surface ---------------------------------------

test("Phase 45 — PaperArtifact.sources allows paperclip (already in v1.5)", () => {
  // Already shipped in v1.5 — sentinel ensures the path is preserved.
  assert.match(
    ARTIFACT_TYPES,
    /"paperclip"/,
    "PaperArtifact.sources union must include paperclip",
  );
});

test("Phase 45 — /api/lit/search VALID_SOURCES includes paperclip", () => {
  assert.match(
    ROUTE_SRC,
    /VALID_SOURCES:\s*SearchSource\[\]\s*=\s*\[[^\]]*"paperclip"[^\]]*\]/,
    "VALID_SOURCES must include paperclip after Phase 45",
  );
});

test("Phase 45 — SearchSource union includes paperclip", () => {
  assert.match(
    SEARCH_SRC,
    /export\s+type\s+SearchSource\s*=\s*[^;]*"paperclip"/,
    "SearchSource type union must include \"paperclip\"",
  );
});
