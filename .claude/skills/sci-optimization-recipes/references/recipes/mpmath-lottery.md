# mpmath precision lottery — break the float64 floor

## When to use

You're stuck at the float64 precision floor (`~1e-15` relative error) and
rounding error, not model error, is what's blocking progress. `ulp-descent`
gets you the last few double-precision ULPs — mpmath lets you escape
double precision entirely.

Classic fits:

- Evaluating an objective that contains catastrophic cancellation (sums of
  many opposing terms).
- High-degree polynomial roots near the unit circle where float64 loses
  most of the mantissa.
- Competition problems whose verifier evaluates in extended precision —
  once you know the verifier's precision, "overshoot" in arbitrary
  precision and round back.

The "lottery" analogy: you don't know which ULP at double precision will
win once rounded — so generate a cloud of arbitrary-precision candidates
**near** the current best, round each to float64, and keep the best.

Skip when:

- Your verifier evaluates in float64 — mpmath buys nothing.
- Computation is dominated by BLAS-level linear algebra (mpmath is
  Python-loop-slow, ~10³ × slower than numpy).
- Problem is combinatorial, not numerical.

## Pseudocode

```
from mpmath import mp, mpf

def mpmath_lottery(f_mp, f_float, x_best, digits=100, n_samples=1000, radius_ulp=8):
    mp.dps = digits
    best_x, best_val = x_best, f_float(x_best)
    x_mp = [mpf(v) for v in x_best]
    for _ in range(n_samples):
        # Perturb each coordinate in mpmath space by a few-ULP amount in float space.
        eps = [mpf(nextafter_ulps(float(xi), rand_int(-radius_ulp, radius_ulp)) - float(xi))
               for xi in x_mp]
        y_mp = [xi + ei for xi, ei in zip(x_mp, eps)]
        y_float = [float(yi) for yi in y_mp]     # round back to double
        val = f_float(y_float)
        if val < best_val:
            best_val = val
            best_x = y_float
            x_mp = [mpf(v) for v in y_float]
    return best_x, best_val
```

The key insight: `mp → float64` rounding itself can flip outcomes in
your favour on a few coordinates even if the mp-precision candidate looks
identical to the starting point.

## Worked example

Einstein Arena Heilbronn (Option C): after reaching `N=400` digits of
precision on the configuration, rounding the arbitrary-precision solution
back to float64 consistently found `~3 × 10⁻¹⁴` improvements on
sub-samples of coordinates — a win that float-only optimisation could not
reach because the "right" float64 neighbour required arbitrary-precision
arithmetic to identify.

## Gotchas

1. **Convert once, not per-iteration.** `mpf(x)` is expensive; pre-convert
   the whole coordinate vector and mutate in mpmath space.
2. **Radius tuning.** Too narrow (`radius_ulp=1`) and every sample
   collapses back to the same float — you're doing nothing. Too wide
   (`radius_ulp=32`) and you're just random-searching at double precision.
3. **dps (decimal precision) choice.** Set `mp.dps` at 1.5 × your target
   margin. For a 1e-14 goal, `dps=50` is enough; for 1e-50, set
   `dps=150`.
4. **Beware of constants.** Literal `mpf('0.1')` differs from `mpf(0.1)`:
   the string form is exact; the float form is the float64 approximation
   of 0.1. Always use strings for exact constants.

## References

- mpmath — `https://mpmath.org/` — Fredrik Johansson's arbitrary-precision
  arithmetic library for Python.
- Muller, J.-M., et al. *Handbook of Floating-Point Arithmetic*, 2nd ed.,
  Birkhäuser (2018), Chapter 4 on rounding and precision.
- `ops-ulp-polish` for the float64-only cousin.
