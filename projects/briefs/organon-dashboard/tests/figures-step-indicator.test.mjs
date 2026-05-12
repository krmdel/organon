import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 14a (v1.0.1) — F-4 figures guided-flow step indicator.
//
// Scope (NEXT_SESSION_phase13-16.md §11):
//   F-4 — top-of-page step indicator with five canonical labels:
//         Generate · Mask · Edit prompt · Apply edit · Lock + caption
//   Each step lights up complete (✓) / available / locked based on
//   workspace state — no router state, derived live.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const COMP_SRC = readSrc("src/components/figures/step-indicator.tsx");
const WORKSPACE_SRC = readSrc("src/components/figures/figures-workspace.tsx");

test("Phase 14a — step-indicator exposes the canonical 5 labels constant", () => {
  // FIGURE_STEP_LABELS is the single source of truth — workspace + tests
  // BOTH read from it so a label rename never drifts.
  assert.match(
    COMP_SRC,
    /export const FIGURE_STEP_LABELS = \[[\s\S]+?"Generate",[\s\S]+?"Mask",[\s\S]+?"Edit prompt",[\s\S]+?"Apply edit",[\s\S]+?"Lock \+ caption",[\s\S]+?\] as const/,
  );
  // Step type carries the three load-bearing flags only — keeping the
  // surface narrow so unrelated state never leaks in.
  assert.match(
    COMP_SRC,
    /export type Step = \{[\s\S]+?label: string;[\s\S]+?complete: boolean;[\s\S]+?available: boolean;[\s\S]+?\}/,
  );
});

test("Phase 14a — step-indicator renders 3 states (complete / available / locked) with data hooks", () => {
  // The state classification + data-step-state attribute make a click-
  // test possible without depending on the visible chip styling.
  assert.match(COMP_SRC, /data-step-indicator/);
  assert.match(COMP_SRC, /data-step-index=\{idx\}/);
  assert.match(COMP_SRC, /data-step-state=\{state\}/);
  assert.match(COMP_SRC, /data-step-focused/);
  // Three distinct states; the chip renders ✓ for complete and the
  // 1-indexed step number for available / locked.
  assert.match(COMP_SRC, /step\.complete[\s\S]+?"complete"/);
  assert.match(COMP_SRC, /step\.available[\s\S]+?"available"[\s\S]+?: "locked"/);
  assert.match(COMP_SRC, /step\.complete \? "✓" : idx/);
  // Focused step inferred when the caller doesn't pin one — first
  // available-but-not-complete; falls back to last complete; default 1.
  assert.match(COMP_SRC, /steps\.findIndex\(\(s\) => s\.available && !s\.complete\)/);
});

test("Phase 14a — figures-workspace mounts the step indicator + derives state live", () => {
  // Indicator imported and mounted at the top of <main>.
  assert.match(
    WORKSPACE_SRC,
    /import \{ StepIndicator, FIGURE_STEP_LABELS, type Step \} from "\.\/step-indicator"/,
  );
  assert.match(WORKSPACE_SRC, /<StepIndicator steps=\{figureSteps\} \/>/);
  // figureSteps derived from workspace state — useMemo over
  // {activeFigure, maskBlob, editPrompt} so SSE-driven updates flow
  // through to the indicator without a re-fetch.
  assert.match(
    WORKSPACE_SRC,
    /const figureSteps = useMemo<Step\[\]>\([\s\S]+?\[activeFigure, maskBlob, editPrompt\]/,
  );
  // Step state derivations — pin the load-bearing rules so a refactor
  // doesn't accidentally regress step semantics.
  assert.match(WORKSPACE_SRC, /const hasFigure = !!activeFigure/);
  assert.match(WORKSPACE_SRC, /const hasMask = !!maskBlob/);
  assert.match(WORKSPACE_SRC, /const hasEditPrompt = editPrompt\.trim\(\)\.length > 0/);
  // "Apply edit" is complete once a v2+ exists — version >= 2 means an
  // FAL fill landed at least once on this figure.
  assert.match(
    WORKSPACE_SRC,
    /const hasNewerVersion = \(activeFigure\?\.version \?\? 1\) >= 2/,
  );
  // "Lock + caption" is available as soon as a figure exists; the user
  // can lock the v1 directly without doing an edit pass.
  assert.match(
    WORKSPACE_SRC,
    /\{ label: FIGURE_STEP_LABELS\[4\], complete: isLocked, available: hasFigure \}/,
  );
});
