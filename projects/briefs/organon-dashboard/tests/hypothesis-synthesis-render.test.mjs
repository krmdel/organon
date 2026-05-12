import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 13c (v1.0.1) — synthesis structured render + APPLY route.
//
// Scope (NEXT_SESSION_phase13-16.md §9):
//   H-6 — synthesis-card parses synthesis_text as JSON (permissive),
//         renders proposed_experiment.stages as a collapsible numbered
//         list, falls back to raw render when JSON parse fails.
//   H-7 — when papers_to_drop_from_linked_set OR
//         papers_to_retain_as_evidence are present, an APPLY button
//         confirms then POSTs to /api/hypothesis/[hyp_id]/apply-
//         recommendation; route is destructive of paper_ids; atomic
//         write via patchHypothesis; refuses on archived hypotheses
//         and unknown ids (422).

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const CARD_SRC = readSrc("src/components/hypothesis/synthesis-card.tsx");
const ROUTE_SRC = readSrc(
  "src/app/api/hypothesis/[hyp_id]/apply-recommendation/route.ts",
);
const WORKSPACE_SRC = readSrc(
  "src/components/hypothesis/hypothesis-workspace.tsx",
);

test("Phase 13c — synthesis-card parses synthesis_text as JSON permissively", () => {
  // The parseSynthesis helper must reject non-object roots and malformed
  // JSON without throwing — the card falls back to the raw text render
  // when JSON parse fails.
  assert.match(CARD_SRC, /function parseSynthesis\(text: string \| null \| undefined\)/);
  // Permissive guard: only treat root strings starting with `{` or `[`
  // as JSON candidates so plain prose never enters JSON.parse.
  assert.match(
    CARD_SRC,
    /if \(!trimmed\.startsWith\("\{"\) && !trimmed\.startsWith\("\["\)\) return null/,
  );
  // Try/catch around JSON.parse — must NEVER throw to render.
  assert.match(CARD_SRC, /try \{[\s\S]+?JSON\.parse\(trimmed\)[\s\S]+?\} catch \{[\s\S]+?return null/);
  // Reject array roots — synthesis is always an object.
  assert.match(CARD_SRC, /Array\.isArray\(obj\)\) return null/);
});

test("Phase 13c — proposed_experiment.stages render as collapsible numbered list", () => {
  // Stages list uses semantic <ol> with list-decimal so the number
  // markers come from CSS, not the data — keeps the DOM clean.
  assert.match(CARD_SRC, /list-decimal pl-5/);
  // The stages section is a collapsible block — toggle persists in
  // local state, default open on mount.
  assert.match(CARD_SRC, /const \[stagesOpen, setStagesOpen\] = useState\(true\)/);
  assert.match(CARD_SRC, /data-action="toggle-stages"/);
  assert.match(CARD_SRC, /data-stages-list/);
  // Each stage carries data-stage-index for click-test stability —
  // 1-indexed to match the visible numbering.
  assert.match(CARD_SRC, /data-stage-index=\{i \+ 1\}/);
  // Section gets a stable hook for the proposed-experiment region.
  assert.match(CARD_SRC, /data-section="proposed-experiment"/);
});

test("Phase 13c — APPLY button surfaces only when drop/retain present, disabled when both empty", () => {
  // The APPLY section only renders when at least one of drop/retain
  // is non-empty — empty recommendations don't pollute the card.
  assert.match(CARD_SRC, /\(drop\.length > 0 \|\| retain\.length > 0\)/);
  // The button itself is disabled when both arrays are empty (defensive
  // — the section already gates rendering).
  assert.match(CARD_SRC, /const applyDisabled = drop\.length === 0 && retain\.length === 0/);
  assert.match(CARD_SRC, /data-action="apply-recommendation"/);
  // Confirm modal before destructive POST — Phase 13c lock.
  assert.match(CARD_SRC, /window\.confirm\([\s\S]+?Apply: drop \$\{drop\.length\}, retain \$\{retain\.length\}/);
});

test("Phase 13c — apply-recommendation route validates ids + refuses archived + atomic write", () => {
  // POST handler with the standard project resolution.
  assert.match(ROUTE_SRC, /export async function POST/);
  assert.match(ROUTE_SRC, /resolveProjectFromRequest\(request, body\.project\)/);
  // Refuses archived hypotheses with 409 — matches the brief's guard.
  assert.match(
    ROUTE_SRC,
    /current\.status === "archived"[\s\S]+?status: 409/,
  );
  // Drop ids must be a subset of current paper_ids — unknowns → 422.
  assert.match(ROUTE_SRC, /unknownDrops[\s\S]+?status: 422/);
  // Retain ids must exist in the project's library — unknowns → 422.
  assert.match(ROUTE_SRC, /unknownRetains[\s\S]+?status: 422/);
  // Bare empty bodies → 400 (no-op POST is a contract violation).
  assert.match(
    ROUTE_SRC,
    /drop\.length === 0 && retain\.length === 0[\s\S]+?status: 400/,
  );
  // Atomic write — delegates to patchHypothesis which already does
  // tmp+rename via saveHypothesis. Don't reinvent the write path here.
  assert.match(ROUTE_SRC, /patchHypothesis\(project\.path, hyp_id, \{ paper_ids: after \}\)/);
});

test("Phase 13c — workspace owns the apply POST + optimistic state update", () => {
  // The applyRecommendation callback fires the POST, optimistically
  // updates paper_ids in state, and reverts on error.
  assert.match(
    WORKSPACE_SRC,
    /const applyRecommendation = useCallback\([\s\S]+?async \(drop: string\[\], retain: string\[\]\)/,
  );
  // POST target carries the ?project= query param (Phase 8 strict mode).
  assert.match(
    WORKSPACE_SRC,
    /apply-recommendation\?project=\$\{encodeURIComponent\(project\)\}/,
  );
  // Method + body shape pin the route contract.
  assert.match(WORKSPACE_SRC, /method: "POST"/);
  assert.match(WORKSPACE_SRC, /body: JSON\.stringify\(\{ project, drop, retain \}\)/);
  // Optimistic update applies the same drop/retain math the route
  // does — the card sees a fresh paper_ids list before the round-trip
  // returns.
  assert.match(WORKSPACE_SRC, /const dropSet = new Set\(drop\)/);
  // SynthesisCard receives the callback through ActiveHypothesis.
  assert.match(WORKSPACE_SRC, /onApplyRecommendation=\{applyRecommendation\}/);
});
