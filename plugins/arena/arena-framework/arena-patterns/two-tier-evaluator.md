# two-tier-evaluator

## Trigger

Problem's exact verifier is >5× slower than a correct approximation —
typical for exact-arithmetic sympy verifiers or Decimal-80 kissing checks.

## Recipe

1. **Exact tier**: byte-parity replica of the server's verifier. Slow but
   authoritative. Used only for (a) final submission verification and
   (b) a small top-K regression fixture bank.
2. **Fast tier**: mpmath/numpy approximation whose output matches the
   exact tier to ~1e-12 across a fixture bank of known solutions. Used
   inside every search loop.
3. **Parity test**: assert exact == fast (within tolerance) on every
   fixture in `tests/arena_fixtures/`. Any future change to either tier
   fails CI if the parity breaks — prevents drift where the search uses
   a fast evaluator that silently diverges from the server's exact one.
4. **Rigor gate** (see separate pattern) adds a third tier that
   distinguishes exploits from rigorous bounds.

## Observed in

- **uncertainty-principle**: fast (mpmath dps=100, sympy exact
  construction, numpy sign check) was 5× faster than the server-parity
  exact at k=19. Without the fast tier, the 20+ iterations in H1's snap
  search would have been uneconomical.
- **first-autocorrelation-inequality**: scipy.signal.fftconvolve agrees
  with numpy.convolve to within 1–2 ULPs at float64 and is fast enough
  (~3ms at n=90000) to drive every optimization iteration. Server-side
  numpy.convolve used only for final verification.

## Test

Parity tests against the fixture bank — see `tests/test_arena_fixtures.py`
for the schema, and `tests/test_rigor_gate.py::test_up_path_b_real_evaluator_end_to_end`
for the slow-marked integration that runs the real exact tier.
