import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 56 (v2.1) — A2: relevance scoring fixes + IDF corpus expansion.
// Source-text-scan + inline behavioural replicas. No live HTTP / scoring calls.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const RELEVANCE_SRC = readSrc("src/lib/lit/relevance.ts");
const OPENALEX_SRC = readSrc("src/lib/paper-search/openalex.ts");
const BUILD_SCRIPT = readSrc("scripts/build-relevance-corpus.mjs");
const FIXTURE = readSrc("tests/fixtures/biomedical-tokens.txt");
const CORPUS = JSON.parse(readSrc("src/lib/lit/relevance-corpus.json"));

// ---- (a) IDF fallback = 1, not 0 ----------------------------------------

test("Phase 56 — DEFAULT_IDF is 1.0 (not 0); unknown tokens still contribute evidence", () => {
  // The static fallback must declare 1.0 so unknown query terms still
  // count for partial overlap. (Was already 1.0 in v1.6 but the brief
  // pinned the contract — keep it locked here.)
  assert.match(
    RELEVANCE_SRC,
    /DEFAULT_IDF\s*=\s*1(\.0)?/,
    "relevance.ts must keep DEFAULT_IDF at 1.0",
  );

  // Inline replica: unknown term contributes its DEFAULT_IDF to both
  // queryWeight and (when matched) sharedWeight.
  const idf = (t, table) => table[t] ?? 1.0;
  const overlap = (q, candidate, table) => {
    if (q.length === 0) return 0;
    let qw = 0;
    let sw = 0;
    for (const t of q) {
      const w = idf(t, table);
      qw += w;
      if (candidate.has(t)) sw += w;
    }
    return qw > 0 ? sw / qw : 0;
  };

  // Query token is unknown to the corpus but PRESENT in candidate set →
  // overlap should be > 0 (would be 0 if DEFAULT_IDF were 0).
  const score = overlap(["zzzunknown"], new Set(["zzzunknown"]), {});
  assert.ok(score > 0, "unknown matched token must score > 0 with IDF fallback = 1");
});

// ---- (b) OpenAlex inverted-abstract decoded at fetch time ---------------

test("Phase 56 — OpenAlex inverted-abstract index decodes to readable abstract", () => {
  // The fetcher must materialise abstract_inverted_index → string at
  // fetch time so downstream consumers (relevance, UI) see normal text.
  assert.match(
    OPENALEX_SRC,
    /abstract_inverted_index/,
    "openalex.ts must reference abstract_inverted_index",
  );
  assert.match(
    OPENALEX_SRC,
    /reconstructAbstract|abstract\s*=\s*reconstruct/,
    "openalex.ts must call reconstructAbstract on the inverted index",
  );

  // Inline replica of the decoder.
  const reconstruct = (idx) => {
    if (!idx) return "";
    const words = [];
    for (const [w, ps] of Object.entries(idx)) {
      for (const p of ps) words.push([p, w]);
    }
    words.sort((a, b) => a[0] - b[0]);
    return words.map(([, w]) => w).join(" ");
  };
  const idx = { sepsis: [0, 4], is: [1], a: [2], leading: [3], cause: [5] };
  assert.equal(reconstruct(idx), "sepsis is a leading sepsis cause");
  assert.equal(reconstruct(null), "");
  assert.equal(reconstruct(undefined), "");
});

// ---- (c) Corpus has ≥ 1500 tokens after rebuild --------------------------

test("Phase 56 — relevance corpus contains ≥ 1500 tokens after rebuild", () => {
  const count = Object.keys(CORPUS.tokens).length;
  assert.ok(
    count >= 1500,
    `corpus must have ≥ 1500 tokens (was ${count}) — rerun scripts/build-relevance-corpus.mjs`,
  );

  // Sanity-check: a few high-leverage biomedical terms must be present.
  for (const t of ["sepsis", "obesity", "metformin", "infection", "cancer"]) {
    assert.ok(
      CORPUS.tokens[t] !== undefined,
      `corpus must contain '${t}' (was missing — rebuild after fixture edit)`,
    );
  }
});

test("Phase 56 — build-relevance-corpus.mjs is idempotent (preserves hand-tuned IDFs)", () => {
  // The build script must NOT clobber existing IDF values; it only fills
  // in new tokens with the default IDF.
  assert.match(
    BUILD_SCRIPT,
    /if\s*\(!\s*\([\w]+\s+in\s+tokens\)\)/,
    "build script must guard token addition with `if (!(t in tokens))`",
  );
  // And the fixture must be a non-empty seed list.
  const fixtureLines = FIXTURE.split(/\r?\n/).filter(
    (l) => l.trim().length > 0 && !l.trim().startsWith("#"),
  );
  assert.ok(
    fixtureLines.length > 1000,
    `fixture must declare > 1000 seed tokens (was ${fixtureLines.length})`,
  );
});

// ---- (d) Real-query smoke check -----------------------------------------

test("Phase 56 — query 'sepsis bacterial infection' against a sepsis paper scores ≥ 0.6", async () => {
  // Dynamic import so the real corpus is consulted.
  const mod = await import(`../src/lib/lit/relevance.ts`);
  const r = mod.scoreRelevance("sepsis bacterial infection guidelines", {
    title: "Surviving Sepsis Campaign: International Guidelines for Management of Severe Sepsis and Septic Shock, 2012",
    abstract:
      "Sepsis is a leading cause of death; bacterial infection requires prompt antibiotic guidelines.",
  });
  assert.ok(
    r.score >= 0.6,
    `real-corpus scoring must clear the 0.6 high-confidence floor (was ${r.score.toFixed(3)})`,
  );
});

// ---- (e) Empty-abstract heuristic relaxed -------------------------------

test("Phase 56 — empty-abstract heuristic relaxed: 80% query coverage on title → score ≥ 0.7", async () => {
  // The relaxed heuristic must fire when titleScore ≥ 0.8 AND abstract
  // is empty. The 100%-match path (allInTitle) still fires earlier.
  assert.match(
    RELEVANCE_SRC,
    /titleScore\s*>=\s*0\.8/,
    "relevance.ts must declare the relaxed 80%-coverage gate (titleScore >= 0.8)",
  );
  assert.match(
    RELEVANCE_SRC,
    /abstractTokens\.size\s*===\s*0/,
    "relevance.ts must guard the relaxed branch on empty abstract",
  );

  // Inline replica covering the new branch.
  const heuristic = (titleScore, abstractEmpty, allInTitle) => {
    if (abstractEmpty) {
      if (allInTitle) return Math.min(1, 0.9 + 0.1 * titleScore);
      if (titleScore >= 0.8) return Math.min(1, 0.7 + 0.2 * titleScore);
    }
    return 0.4 * titleScore + 0.6 * 0;
  };
  // 80% IDF coverage on title, no abstract → ≥ 0.7.
  const partial = heuristic(0.85, true, false);
  assert.ok(partial >= 0.7, `relaxed branch must score ≥ 0.7 (was ${partial})`);
  // Old behaviour for sub-80% coverage stays muted.
  assert.ok(heuristic(0.5, true, false) < 0.7);
  // 100% match still scores ≥ 0.9.
  assert.ok(heuristic(1.0, true, true) >= 0.9);

  // Real-corpus check on a paperclip-style hit (empty abstract).
  const mod = await import(`../src/lib/lit/relevance.ts`);
  const r = mod.scoreRelevance("sepsis guidelines", {
    title: "Surviving Sepsis Campaign Guidelines 2021",
    abstract: "",
  });
  assert.ok(
    r.score >= 0.7,
    `empty-abstract relaxation must surface ≥ 0.7 (was ${r.score.toFixed(3)})`,
  );
});
