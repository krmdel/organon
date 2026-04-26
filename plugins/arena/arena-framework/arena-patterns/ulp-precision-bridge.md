# ulp-precision-bridge

## Trigger

A continuous gradient-based optimizer has stalled at ~1e-12 residual, but
a high-precision evaluator (mpmath dps≥50 or exact sympy) reports the
true residual is ~1e-13. The gradient direction at float64 grain is no
longer aligned with any better lattice neighbour — L-BFGS can't make
progress, but the float64 lattice still has improving moves.

## Recipe

1. Lock the continuous optimizer's endpoint as warm-start.
2. Run `ulp_polish_incremental(V, loss_fn, max_ulps=4, max_sweeps=20)`
   — per-coordinate ±1/±2/±4 ulp trials, priority-ordered by
   per-row badness contribution. Each improving move accepted.
3. If single-coord converges but residual is still above target, run
   `ulp_polish_2coord` on the top-k contribution-weighted rows — joint
   2-coord moves escape single-coord saddles that coord descent can't.
4. Use `incremental_loss_fn` when the loss structure allows (changing
   one row only touches O(n) pairwise terms, not O(n²)).

## Observed in

- **first-autocorrelation-inequality (C1)**: micro-basin-hopping + ULP
  polish bridged the final ~5e-7 of improvement past JSAgent's β=1e6
  endpoint that continuous methods couldn't cross.
- **kissing-d11**: rank 2–5 on the public leaderboard were all stuck at
  1e-13 precision that only ULP polish could bridge. Only Kawaii crossed
  it (the "extra technique" beyond PT-SA + ULP is still an open
  question).

## Test

`tests/test_ulp_polish.py` — `test_ulp_polish_incremental_reduces_quadratic`,
`test_ulp_polish_d11_fixture_preserves_score_zero`.

## Primitive

`arena_framework.primitives.ulp_polish.ulp_polish_incremental` and
`ulp_polish_2coord` — both respect `Budget`, `freeze_rows`, and return
the full `ULPPolishResult` trace.
