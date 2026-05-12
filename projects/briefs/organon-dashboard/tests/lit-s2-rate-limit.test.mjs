import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 37 (v1.4) — B4: Semantic Scholar 429 retry/backoff + soft_errors.
//
// The 2026-05-08 walk surfaced "semanticscholar: API failed: 429" as a
// permanent red error toast. S2's public API is 1 req/s; the dashboard
// fans out per-source in parallel. Phase 37 swaps the retry to 1.5s +
// jitter, classifies the rate-limited case as a typed error, and
// surfaces it via a NEW soft_errors[] response field rendered as a
// yellow info banner instead of red.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const S2_SRC = readSrc("src/lib/paper-search/semanticscholar.ts");
const SEARCH_SRC = readSrc("src/lib/lit/search.ts");
const ROUTE_SRC = readSrc("src/app/api/lit/search/route.ts");
const WORKSPACE_SRC = readSrc("src/components/lit/lit-workspace.tsx");

test("Phase 37 — semanticscholar.ts retries once with backoff on 429", () => {
  // The retry constant lives at module scope so ops can tune it without
  // re-reading the function body.
  assert.match(S2_SRC, /S2_RETRY_BASE_MS\s*=\s*1500/);
  assert.match(S2_SRC, /S2_JITTER_MAX_MS\s*=\s*500/);
  // The retry logic still gates on response.status === 429.
  assert.match(S2_SRC, /response\.status\s*===\s*429/);
  // Exactly one retry attempt — no recursion / loop.
  const retryMatches = S2_SRC.match(/await\s+fetch\(url/g);
  assert.ok(retryMatches && retryMatches.length === 2, "exactly 2 fetch calls (initial + 1 retry)");
});

test("Phase 37 — RateLimitedError is a distinct exported error class", () => {
  // Distinct named class so the search aggregator can branch on it.
  assert.match(S2_SRC, /export class RateLimitedError extends Error/);
  // Carries the source identifier so a future multi-source aggregator
  // can group the soft errors.
  assert.match(S2_SRC, /source[\s\S]{0,40}["']semanticscholar["']/);
  // Thrown after both attempts hit 429.
  assert.match(
    S2_SRC,
    /throw\s+new\s+RateLimitedError/,
  );
});

test("Phase 37 — search.ts surfaces rate-limited cases in soft_errors[], not errors[]", () => {
  // The aggregator imports RateLimitedError so it can branch.
  assert.match(SEARCH_SRC, /RateLimitedError/);
  // SearchResult interface has both fields.
  assert.match(SEARCH_SRC, /errors:\s*string\[\]/);
  assert.match(SEARCH_SRC, /soft_errors:\s*string\[\]/);
  // The aggregator pushes onto soft_errors when the per-source error is
  // a RateLimitedError; otherwise into errors.
  assert.match(
    SEARCH_SRC,
    /instanceof\s+RateLimitedError[\s\S]{0,200}soft_errors/,
  );
  // Route forwards soft_errors[] when non-empty.
  assert.match(ROUTE_SRC, /soft_errors/);
});

test("Phase 37 — lit-workspace renders soft_errors as a yellow info banner", () => {
  // Workspace consumes the new field.
  assert.match(WORKSPACE_SRC, /soft_errors|softErrors/);
  // Distinct yellow / warn styling — distinct from the red `text-danger`
  // toast for hard errors.
  assert.match(
    WORKSPACE_SRC,
    /soft[A-Za-z]*[\s\S]{0,2000}(text-warn|text-yellow|warning|warn-)/i,
  );
  // Hard errors still render as red.
  assert.match(WORKSPACE_SRC, /text-danger/);
});
