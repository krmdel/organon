---
name: ops-ulp-polish
description: 'Discrete float64 ULP coordinate-descent polisher for high-precision optimization. Per-coordinate +/-1/2/4 ulp trials priority-ordered by contribution-weighted badness. Use when gradient methods stall at ~1e-12 but true residual is ~1e-13 (spherical codes, kissing configs, lattice packings). Triggers: "ulp polish", "polish to zero", "precision polish", "bridge precision floor", "float64 coordinate descent", "break through 1e-13".'
---

# ops-ulp-polish — ULP coordinate descent polisher

## When to use

You have a near-optimal float64 configuration. Gradient descent stopped improving
at ~1e-12 but the exact-arithmetic evaluator says the residual is ~1e-13. The
gradient cannot help — at the float64 grain, the gradient direction is no longer
aligned with any better lattice neighbour.

Typical triggers:
- Einstein Arena near-zero solutions
- Spherical codes with min-distance exactly at some fractional limit
- Lattice kissing configurations
- Matrix completion with Frobenius-norm constraints near a machine-precision boundary
- Polynomial root polishing when Newton stalls

## Methodology

1. **Warm-start**: load a candidate vector configuration (or solution file).
2. **Priority order**: rank rows/variables by per-row contribution to the residual
   (`badness` = sum of violations involving that row).
3. **Per-coordinate sweep**: for each coordinate `x[i,k]`, try:
   - `x[i,k] ± 1 ulp, ± 2 ulp, ..., ± max_ulps ulps`
   - For each trial, re-evaluate loss using the FASTEST available evaluator
     (float64 for the fast pass; exact arithmetic only on confirmed improvements).
   - Accept the best improving step.
4. **Iterate** sweeps until no coordinate improves.

Key speed-up (critical): use **incremental evaluation** — when `x[i]` changes,
only distances/residuals involving row `i` need recompute, not the full O(n²)
pairwise sum.

## API

```bash
python3 scripts/polish.py --config <warm-start.json|.npy> \
                          --evaluator <module.fn> \
                          --max-ulps 4 \
                          --max-sweeps 20 \
                          --budget-sec 3600 \
                          --out <out.npy>
```

The `--evaluator` should point to a Python callable `(V) -> float` that returns
the loss; a fast `(V, changed_row_i) -> delta` incremental variant is even
better.

## Dependencies

| Dependency | Required | Provides | Fallback |
|---|---|---|---|
| `numpy` | Yes | ULP arithmetic via `np.nextafter` | None |
| `mpmath` | Optional | Arbitrary-precision cross-verification | Trust the evaluator's output |
| User-provided evaluator | Yes | Problem-specific loss | None |

## References

- `references/ulp-arithmetic-primer.md` — `np.nextafter` semantics, IEEE-754
  subnormal caveats, pseudocode, and when to cross-check with mpmath.

## Tests

- `tests/test_polish.py` — 22 unit tests covering `next_ulp` (IEEE edge cases,
  symmetry, subnormals, near-inf), `load_config` (.npy / .json / rejected
  formats), `polish` (happy path, no-improvement, termination, budget,
  empty / singleton, monotonicity-idempotence, float32 upcast,
  priority ordering), and `row_badness_default`. Run with
  `python3 -m pytest .claude/skills/ops-ulp-polish/tests/ -v`.
