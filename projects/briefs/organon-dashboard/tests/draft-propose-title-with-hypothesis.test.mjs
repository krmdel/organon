import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 60 (v2.1) — A5: propose-title threads linked hypotheses with
// claim_short + status + council_confidence (not just IDs) so the
// skill has real evidence to anchor candidate framings on, even when
// the manuscript has linked papers (so Phase 49's zero-state gate
// doesn't fire).

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const ROUTE_SRC = readSrc("src/app/api/draft/[slug]/generate-title/route.ts");

test("Phase 60 — generate-title route threads linked_hypothesis_ids[] into the prompt", () => {
  // Pre-Phase-60: only the IDs were threaded. Phase 60 keeps the IDs AND
  // adds the rich `linked_hypotheses=...` block.
  assert.match(
    ROUTE_SRC,
    /linked_hypothesis_ids=/,
    "route must keep threading linked_hypothesis_ids=...",
  );
});

test("Phase 60 — route resolves IDs to claim_short + status + council_confidence", () => {
  // The route must call into the hypothesis store + materialise a
  // rich block per linked hypothesis.
  assert.match(
    ROUTE_SRC,
    /import\s*\{\s*listHypotheses\s*\}\s*from\s*"@\/lib\/hypothesis\/store"/,
    "route must import listHypotheses from the hypothesis store",
  );
  assert.match(
    ROUTE_SRC,
    /listHypotheses\(project\.path\)/,
    "route must call listHypotheses(project.path)",
  );
  // Each entry must include the three fields the skill needs.
  for (const field of ["claim_short", "status", "council_confidence"]) {
    assert.match(
      ROUTE_SRC,
      new RegExp(`${field}\\s*:`),
      `linked_hypotheses block must include ${field}`,
    );
  }
  // And the rich block must be threaded into the prompt.
  assert.match(
    ROUTE_SRC,
    /linked_hypotheses=\$\{JSON\.stringify\(linkedHypotheses\)\}/,
    "prompt must thread linked_hypotheses=${JSON.stringify(linkedHypotheses)}",
  );
});

test("Phase 60 — generate-title route emits parse-debug SSE event when no candidates returned", () => {
  // The diagnostic event was added pre-Phase-60 (Phase 35 carried over).
  // The contract pinned here: the route must yield a parse-debug event
  // when the run completes but no title-candidates artifact arrived.
  assert.match(
    ROUTE_SRC,
    /diagnoseUnparsedArtifact/,
    "route must call diagnoseUnparsedArtifact when no artifact parsed",
  );
  assert.match(
    ROUTE_SRC,
    /type:\s*"parse-debug"/,
    "route must yield a parse-debug event with the diagnostic payload",
  );
  assert.match(
    ROUTE_SRC,
    /anyTitleArtifactParsed/,
    "route must track whether a title-candidates artifact was successfully parsed",
  );
});

test("Phase 60 — Phase 49 zero-state fallback still fires when both linked_papers + stat_results are empty", () => {
  // The zero-state gate must not be loosened. Both buckets must remain
  // empty for the fallback branch to fire.
  assert.match(
    ROUTE_SRC,
    /isZeroState\s*=\s*\n?\s*linkedPapers\.length\s*===\s*0\s*&&\s*linkedStatResults\.length\s*===\s*0/,
    "route must keep the AND gate for the zero-state fallback (no loosening)",
  );
  assert.match(
    ROUTE_SRC,
    /zero_state_fallback=true/,
    "route must still emit the zero_state_fallback=true line when the gate fires",
  );
});

test("Phase 60 — when linked hypotheses are present, the route passes claim_short + council_confidence to the skill", () => {
  // Inline replica of the resolution.
  const allHypotheses = [
    { id: "h1", claim: "long claim text".repeat(20), claim_short: "GLP-1 reduces appetite", status: "supported", council_confidence: "high" },
    { id: "h2", claim: "another long claim text", claim_short: "Insulin sensitivity drops", status: "refuted", council_confidence: "low" },
    { id: "h3", claim: "irrelevant", claim_short: "Tirzepatide is novel", status: "open", council_confidence: null },
  ];
  const linkedIds = ["h1", "h2"];
  const set = new Set(linkedIds);
  const linkedHypotheses = allHypotheses
    .filter((h) => set.has(h.id))
    .map((h) => ({
      id: h.id,
      claim_short: h.claim_short ?? h.claim.slice(0, 120),
      status: h.status,
      council_confidence: h.council_confidence ?? null,
    }));
  assert.equal(linkedHypotheses.length, 2);
  assert.equal(linkedHypotheses[0].claim_short, "GLP-1 reduces appetite");
  assert.equal(linkedHypotheses[0].council_confidence, "high");
  assert.equal(linkedHypotheses[1].council_confidence, "low");
  // h3 must NOT leak through (not in linked_ids).
  assert.ok(!linkedHypotheses.some((h) => h.id === "h3"));

  // And the route must instruct sci-writing to anchor candidates on
  // hypothesis claims when present, not just papers/stats.
  assert.match(
    ROUTE_SRC,
    /linked_hypotheses is non-empty/i,
    "prompt must direct sci-writing to anchor candidates on linked_hypotheses when present",
  );
});

test("Phase 60 — sci-writing's generate-title mode (Step 7.8) handles hypothesis-only context per its updated prompt", () => {
  // The dashboard-side contract: regardless of whether the skill SKILL.md
  // gets updated in the same commit, the prompt must thread enough
  // hypothesis context that the skill CAN compose a title from claim_short
  // alone. We assert on the route's prompt copy.
  assert.match(
    ROUTE_SRC,
    /first-class title evidence/i,
    "route must label hypotheses as first-class title evidence in the prompt",
  );
  assert.match(
    ROUTE_SRC,
    /regardless of whether papers/i,
    "route must explicitly tell the skill to use hypotheses regardless of papers/stats",
  );
});
