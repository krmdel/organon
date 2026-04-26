# ULP coordinate descent — precision polish to the float64 floor

## When to use

Continuous gradient descent has stalled at roughly `1e-12` and you need
another 1–2 orders of magnitude of improvement. Classic signs:

- The gradient norm is no longer decreasing; rounding error dominates the
  true descent direction.
- You've hit the "precision floor" of double-precision arithmetic
  (~1e-13 to 1e-15 depending on conditioning).
- A competition leaderboard rewards the last few digits and every other
  method saturates.

**This recipe delegates execution to the sibling skill `ops-ulp-polish`.**
Use this entry as the routing marker — the actual implementation lives
there with full tests, a CLI, and a progress dashboard.

Skip when:

- You're still in the coarse regime (f > 1e-9). Gradient descent is
  faster; don't burn cycles on 4-ulp trials at that range.
- The objective is discrete or has wide staircase plateaus — ULP moves
  are invisible because every float64 neighbour gives the identical
  rounded value.
- You need bit-exact reproducibility across platforms — float64 results
  can differ across CPUs, even at the same ULP.

## Pseudocode

```
def ulp_descent(f, x0, steps=10_000, window=(-4, 4)):
    x, best = x0.copy(), f(x0)
    while True:
        # Priority: rank coordinates by contribution-weighted badness.
        order = priority_order(x, f)
        improved = False
        for i in order:
            base = x[i]
            for delta_ulp in [d for d in window if d != 0]:
                candidate = nextafter_n(base, delta_ulp)
                x[i] = candidate
                val = f(x)
                if val < best:
                    best = val
                    improved = True
                    break
                x[i] = base       # revert
            if improved:
                break
        if not improved:
            break
    return x, best
```

`nextafter_n(x, n)` walks `|n|` ULPs in the sign direction — use
`math.nextafter` iteratively or bit-cast via `numpy.float64.view('int64')`
for speed.

## Worked example

Einstein Arena PNT (score saturating near 0.9948): ULP coordinate descent
with `window=(-4, 4)` improved the final submission from 0.99473 to
0.99490 over ~3000 accepted ULP moves in about 40 minutes wall-clock.

The `ops-ulp-polish` skill wraps this with a progress dashboard,
resumable state, and 4-way / 8-way tie-break heuristics. Invoke it with:

```bash
python3 .claude/skills/ops-ulp-polish/scripts/polish.py \
    --objective my_objective.py \
    --input current.json \
    --window -4 4 \
    --output polished.json
```

## Gotchas

1. **Don't compute the gradient.** ULP moves are discrete; finite
   differences at the precision floor are pure noise. Use only
   `f(x_candidate) < f(x)`.
2. **Order matters.** A blind round-robin pass over coordinates is ~10×
   slower than priority ordering by contribution-weighted badness.
3. **Window size tuning.** Start `window=(-1, 1)`; widen only when the
   narrow window stops improving. `(-4, 4)` is practical maximum —
   beyond that you'd be better off with a continuous solver.
4. **Reject NaN / Inf candidates silently.** Boundary variables near
   underflow produce `inf` objectives on perturbation; treat them as
   rejection, don't crash.

## References

- Goldberg, D. "What every computer scientist should know about
  floating-point arithmetic." *ACM Computing Surveys* 23 (1991),
  pp. 5–48. (ULPs and nextafter defined.)
- Kahan, W. "A survey of error analysis." *IFIP Congress Proceedings*
  (1972).
- `ops-ulp-polish` skill — internal Organon sibling with full
  implementation, CLI, progress tracking, and resumable state.
