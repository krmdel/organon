import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// Phase 12b (v1.0.1) — D-9 regression assumption diagnostics regression contract.
//
// Scope (V1_0_1_PLAN.md §7.2 + NEXT_SESSION_phase12.md §5):
//   D-9 — Linear regression must emit four assumption diagnostics in the
//         result's assumption_checks list, mirroring the ANOVA pattern:
//           1. Breusch-Pagan      → homoscedasticity (p > 0.05 → pass)
//           2. Shapiro-Wilk       → residual normality (p > 0.05 → pass)
//           3. Durbin-Watson      → no autocorrelation (1.5 ≤ DW ≤ 2.5 → pass)
//           4. VIF (max)          → no multicollinearity (< 10 → pass)
//
// Implemented in pure scipy + numpy because statsmodels is intentionally
// NOT in the dashboard's venv (run_stat_test.py:26 documents the exclusion).
//
// Source-text-scan pattern matches the rest of the suite — we cannot
// execute Python from a node test, so we pin the structural contract on
// the source. Behavioural verification was done manually during
// implementation across well-behaved / single-predictor / heteroscedastic /
// collinear fixtures (logged in commit message).

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const PY_SRC = readSrc("scripts/run_stat_test.py");
const CARD_SRC = readSrc("src/components/data/stat-result-card.tsx");

test("run_stat_test.py emits all four diagnostics from the linear-regression branch", () => {
  // Helper exists with the right shape — single entry point so the four
  // diagnostics are tested as a unit.
  assert.match(PY_SRC, /def _regression_diagnostics\(/);
  // run_linear_regression actually wires the diagnostics into the
  // assumption_checks list — without this line the helper exists but is
  // never called, which is the regression we're guarding against.
  assert.match(PY_SRC, /diagnostics = _regression_diagnostics\(/);
  assert.match(PY_SRC, /"assumption_checks": diagnostics/);
  // Each of the four diagnostics is named, with the canonical verb-name
  // pattern that the assumption strip already renders.
  assert.match(PY_SRC, /"homoscedasticity_breusch_pagan"/);
  assert.match(PY_SRC, /"residual_normality_shapiro"/);
  assert.match(PY_SRC, /"no_autocorrelation_durbin_watson"/);
  assert.match(PY_SRC, /"no_multicollinearity_vif"/);
});

test("Diagnostics implementation guards the documented edge cases", () => {
  // Single-predictor → VIF emits the canonical note instead of crashing.
  assert.match(PY_SRC, /"single predictor"/);
  // n < k+2 is a degenerate case — Breusch-Pagan emits warn with note.
  assert.match(PY_SRC, /insufficient n/);
  // Perfect collinearity → VIF=inf, surfaced explicitly so the user sees
  // *why* the test failed rather than a generic warn.
  assert.match(PY_SRC, /perfect collinearity detected/);
  // Durbin-Watson uses the closed-form formula on np.diff — no statsmodels.
  assert.match(PY_SRC, /np\.diff\(resid\)/);
  // Breusch-Pagan derives p from chi²(k) on the auxiliary R² — pure scipy.
  assert.match(PY_SRC, /stats\.chi2\.cdf\(lm_stat, k\)/);
  // VIF auxiliary regression goes through the same _ols_r2 helper used by
  // Breusch-Pagan — single OLS path so the two diagnostics agree on
  // ill-conditioned design matrices.
  assert.match(PY_SRC, /def _ols_r2\(/);
});

test("StatResultCard's existing assumption strip renders the four diagnostics generically", () => {
  // The card already iterates over result.assumption_checks — no change
  // needed for 12b BUT we pin that the strip exists, so a future refactor
  // that drops the strip (and silently breaks D-9's surface) regresses.
  assert.match(CARD_SRC, /Assumption checks/);
  assert.match(CARD_SRC, /result\.assumption_checks\.map/);
  // Verdict-tone palette covers pass / warn / fail (the only three
  // verdicts the diagnostics emit).
  assert.match(CARD_SRC, /pass: "text-good"/);
  assert.match(CARD_SRC, /warn: "text-text-dim"/);
  assert.match(CARD_SRC, /fail: "text-danger"/);
  // p-value rendering — Breusch-Pagan + Shapiro both emit p; the card
  // surfaces it via fmtP. Pin so a future "tidy up the chip" PR can't
  // accidentally hide the p-values D-9 promises.
  assert.match(CARD_SRC, /a\.p_value !== undefined/);
});
