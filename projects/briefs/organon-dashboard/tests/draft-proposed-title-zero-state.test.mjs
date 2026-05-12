import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 49 (v1.6) — F12: proposed-title from zero state.
// Tests are pure source-text-scans; no real claude-runner spawns.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const DRAFT_LIST_SRC = readSrc("src/components/draft/draft-list.tsx");
const MANUSCRIPT_WORKSPACE_SRC = readSrc("src/components/draft/manuscript-workspace.tsx");
const ROUTE_SRC = readSrc("src/app/api/draft/[slug]/generate-title/route.ts");

// ---- UI: zero-section gate must NOT exist --------------------------

test("Phase 49 — manuscript-workspace allows proposed-title click with zero sections drafted", () => {
  // The propose-title surface must NOT gate on `section_count > 0` or
  // `sections.length > 0` or "you must draft a section first".
  // (Phase 49 verifies the absence of the gate; the propose-title
  // button itself lives in draft-list.tsx in v1.6, not manuscript-
  // workspace, but the gate check applies to both files.)
  for (const src of [DRAFT_LIST_SRC, MANUSCRIPT_WORKSPACE_SRC]) {
    assert.ok(
      !/section_count\s*[><=]\s*0|sections\.length\s*[><=]\s*0\s*&&\s*[^|]*propos/i.test(src),
      "no surface may gate Propose Title on section_count > 0",
    );
    assert.ok(
      !/draft\s+(?:a|the)\s+section\s+(?:first|before)/i.test(src),
      "no surface may show a 'draft a section first' message before propose-title",
    );
  }
});

// ---- route: empty corpus tolerance ---------------------------------

test("Phase 49 — generate-title route handles empty library + empty stat-results gracefully", () => {
  // The route already pulls listLibrary + listResults; both can be
  // empty arrays without crashing. Test ensures the prompt builder
  // doesn't gate on `linkedPapers.length > 0`.
  assert.ok(
    !/linkedPapers\.length\s*===?\s*0\s*&&\s*throw/.test(ROUTE_SRC),
    "route must not throw when linkedPapers is empty",
  );
  assert.ok(
    !/linkedStatResults\.length\s*===?\s*0\s*&&\s*throw/.test(ROUTE_SRC),
    "route must not throw when linkedStatResults is empty",
  );
  // Prompt must include both arrays even when they're [].
  assert.match(
    ROUTE_SRC,
    /linked_papers=\$\{JSON\.stringify\(linkedPapers\)\}/,
    "route must always emit linked_papers in the prompt",
  );
  assert.match(
    ROUTE_SRC,
    /linked_stat_results=\$\{JSON\.stringify\(linkedStatResults\)\}/,
    "route must always emit linked_stat_results in the prompt",
  );
});

test("Phase 49 — generate-title falls back to manuscript.title + linked hypotheses when corpus is empty", () => {
  // When linkedPapers + linkedStatResults are BOTH empty, the route
  // must inject a zero-state-fallback section into the prompt so
  // sci-writing has at least the manuscript title + linked
  // hypothesis ids[] (Phase 41 substrate) to anchor on.
  assert.match(
    ROUTE_SRC,
    /zero[\s_-]?state|empty[\s_-]?corpus|linked_hypothesis_ids/i,
    "route must surface a zero-state / empty-corpus / linked-hypothesis fallback",
  );
  // Hypothesis-id context must be threaded from manuscript metadata.
  assert.match(
    ROUTE_SRC,
    /linked_hypothesis_ids/,
    "route must include manuscript.linked_hypothesis_ids when falling back",
  );
});
