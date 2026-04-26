# sturm-rigor-gate

## Trigger

Problem's evaluator uses a float sign-change check on a rational-arithmetic
polynomial — e.g. `np.sign(sympy.lambdify(gq)(r ± 1e-6))`. At high enough
polynomial degree, `gq`'s float64 evaluation at moderate-large x has
magnitude far above relative precision and cancellation masks genuine
sign changes. Server records "no sign change" where mathematically there
IS one → exploit surface.

Broader class: any verifier that reduces an exact rational quantity to
float64 comparison.

## Recipe

1. Replicate the exact arena evaluator locally (rebuild the polynomial in
   sympy exactly, match the server's verification byte-for-byte).
2. Build a *rigorous* evaluator alongside: use `sympy.Poly.sqf_list()` to
   decompose into square-free factors. A real root of a factor contributes
   a sign change iff the factor's multiplicity in `sqf_list` is odd.
3. Classify each top-K solution via `rigor_gate()`: verdict is `rigorous`
   when arena and rigorous scores agree within tolerance, `exploit` when
   they diverge (arena << rigorous).
4. Submit gate refuses exploit submissions unless `--allow-exploit` is
   passed explicitly.

## Observed in

- **uncertainty-principle**: k ≥ 15 Laguerre-LP configs on the public
  leaderboard are all exploits (rigorous scores in 20–40 range vs arena
  claims in 0.26–0.30). The exploit line sits exactly at k=15.

## Test

`tests/test_rigor_gate.py` — `test_rigor_gate_up_path_a_classified_as_exploit`
and `test_rigor_gate_up_path_b_classified_as_rigorous`.

## Primitive

`arena_framework.rigor_gate.rigor_gate(config, arena_fn, rigorous_fn)`

Returns `RigorVerdict(verdict, arena_score, rigorous_score, gap, exploit_factor, diagnostics)`.
