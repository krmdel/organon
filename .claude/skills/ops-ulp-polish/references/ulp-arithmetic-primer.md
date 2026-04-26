# ULP Arithmetic Primer

A concise reference for the IEEE 754 floating-point mechanics underlying `ops-ulp-polish`.

---

## What `np.nextafter` Does

`np.nextafter(x, direction)` returns the next representable float64 in the direction of
`direction`. Internally this maps to a single integer add or subtract on the raw bit
representation of `x`: the mantissa bits are treated as a 52-bit integer and incremented
or decremented by 1. One ULP (Unit in the Last Place) is therefore the smallest possible
change to a float64 value at its current magnitude. Jumping `k` ULPs means calling
`nextafter` k times (or equivalently incrementing the bit pattern by k).

---

## Why ±k-ULP Perturbations Are Safe Under IEEE 754

IEEE 754-2008 mandates that the basic arithmetic operations (+, -, *, /) and `sqrt` be
*correctly rounded*: the result must equal the closest representable float64 to the
mathematical result. As a consequence, when you evaluate `f(x + 1 ULP)` versus `f(x)`,
any difference you observe is a genuine change in the function value, not an artifact
introduced by the perturbation size. There is no cancellation hazard from the step itself
being too small — the arithmetic faithfully rounds each operation independently.

---

## Subnormal-Region Caveats

Near zero (below ~2.2e-308, the smallest normal float64), the exponent is fixed and ULP
spacing collapses to the minimum positive subnormal (~5e-324). A ±1 ULP step is still
well-defined — `nextafter(0.0, 1.0)` returns 5e-324 — but the absolute change is
vanishingly small (~1e-323 per step). The polisher will still make moves in this region;
they are technically correct but may take an enormous number of steps to shift the
coordinate by any macroscopically meaningful amount. Treat this as a **limitation** when
coordinates are expected to be near zero: consider rescaling the problem or clamping the
coordinate range before polishing.

---

## When mpmath Is Necessary

float64 carries ~15.9 decimal digits of precision (52 mantissa bits). If the improvement
from a ULP move is smaller than ~1e-15 * |x|, the sign of the improvement — is the new
point better or worse? — can flip depending on whether you evaluate it in float64 or in
exact arithmetic. For arena problems where the leaderboard threshold gap is below 1e-13,
a float64 comparison `new_score > best_score` may misclassify a genuine improvement as a
regression or vice versa. In that regime, verify candidate moves with `mpmath` (or
Python's `decimal` module at sufficient precision) before accepting them.

---

## Reference Implementation Pseudocode

```python
def ulp_coord_descent(x, eval_fn, max_ulps=3, max_rounds=1000):
    best = x.copy()
    best_score = eval_fn(best)
    for _ in range(max_rounds):
        improved = False
        for i in range(len(best)):
            for direction in (+1, -1):
                for k in range(1, max_ulps + 1):
                    candidate = best.copy()
                    for _ in range(k):
                        candidate[i] = np.nextafter(candidate[i],
                                                    np.inf * direction)
                    score = eval_fn(candidate)
                    if score > best_score:          # strictly better
                        best, best_score = candidate.copy(), score
                        improved = True
                        break
        if not improved:
            break
    return best, best_score
```

---

## Example

```python
import numpy as np
from scripts.polish import polish

x0 = np.array([[1.452304333183158, 0.0]])  # warm-start as (1, d) array
best_x, best_score = polish(x0, eval_fn=my_verifier, max_ulps=2, budget_sec=60)
print(f"Polished score: {best_score:.15f}")
```

---

## Citations

- **jmsung's `polish_ulp_coord.py`** — the inspiration and port source for this skill's
  coordinate-descent loop. The original script demonstrated single-coordinate ULP
  stepping with a badness-ranked traversal order.

- **IEEE Standard for Floating-Point Arithmetic, IEEE Std 754-2008.** Institute of
  Electrical and Electronics Engineers, New York, 2008. Section 4 (Attributes and
  Rounding) and Section 5 (Operations) specify the correctly-rounded guarantee.
