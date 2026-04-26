# dyadic-rational-snap

## Trigger

Evaluator routes floats through `sympy.Rational` (or any exact-arithmetic
conversion). Short-denominator inputs produce structurally shorter
polynomials, changing the numerical tail of downstream exact operations.
This typically rewards snap candidates that a continuous gradient
optimizer can never reach.

## Recipe

1. For each coordinate of a continuous warm-start config, enumerate
   short-denom rational candidates via `Fraction(x).limit_denominator(D)`
   for D ∈ {2, 3, 5, 7, 11, 16, 24, 32, 48, 64, 91, 128}.
2. Also try ±1 numerator nudges around each `limit_denominator` result
   (the rational *neighborhood*, not just the closest).
3. Accept any candidate that strictly improves the arena score.
4. Iterate sweeps until no coordinate improves.

Coordinate-descent logic lives in `DyadicSnapSearch`; candidate generation
in `generate_candidates(value, max_denom, mode)`.

## Observed in

- **uncertainty-principle (H1)**: alpha_omega's k=19 baseline scored 0.26543.
  Single-coord snap `z[1]: 4.7033 → 4.7363 (=431/91)` and
  `z[6]: 39.376 → 39.4 (=197/5)` dropped score to 0.13365. Arena's
  rational-arithmetic polynomial factored more completely with the shorter
  denominators → more numerical sign changes hidden.

## Test

`tests/test_dyadic_snap.py` —
`test_snap_finds_rational_optimum_on_1d_toy`,
`test_snap_on_synthetic_short_denom_reward`.

## Primitive

`arena_framework.primitives.dyadic_snap.dyadic_snap_search(config, loss_fn, max_denom=128, mode="farey")`
