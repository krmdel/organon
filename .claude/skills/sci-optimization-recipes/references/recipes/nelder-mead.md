# Nelder-Mead / L-BFGS / hill-climbing — sequential CPU fallbacks

## When to use

A gradient-based solver has failed or isn't usable, and you need a robust
CPU baseline. Each method plays a different role in the fallback ladder:

- **L-BFGS-B** — smooth objective, have gradient (or can finite-diff),
  constraints are simple box bounds. Fastest converger for smooth
  convex-ish problems.
- **Nelder-Mead** — gradient unavailable or unreliable, small `n` (≤ 20).
  Derivative-free simplex search; slow but steady. Good last resort.
- **Hill climbing** — discrete or combinatorial neighbourhoods, or when
  you just want "best of N trials, with 1-swap local fix".

The three together cover the non-global-search side of the toolkit.
Pair them with `k-climbing` for exploration and `ulp-descent` for polish.

Skip when:

- `n > 100` and the objective is smooth — plain L-BFGS will still work
  but you'll want a proper conjugate-gradient or stochastic method.
- You have a real global structure (LP, SDP, MIP) — use those instead.
- The objective is extremely expensive to evaluate — use a surrogate /
  Bayesian optimiser.

## Pseudocode

```
def fallback_ladder(f, x0, bounds=None, grad=None):
    # (1) L-BFGS-B if we have gradient and smooth objective.
    if grad is not None:
        result = scipy.optimize.minimize(
            f, x0, jac=grad, bounds=bounds, method='L-BFGS-B'
        )
        if result.success:
            return result.x

    # (2) Nelder-Mead for small derivative-free problems.
    if len(x0) <= 20:
        result = scipy.optimize.minimize(
            f, x0, method='Nelder-Mead',
            options={'xatol': 1e-8, 'fatol': 1e-10, 'maxiter': 10_000}
        )
        if result.fun < f(x0):
            return result.x

    # (3) Hill climb with random 1-coord perturbations (last resort).
    x, val = x0.copy(), f(x0)
    for _ in range(5000):
        i = np.random.randint(len(x))
        x_try = x.copy()
        x_try[i] += np.random.randn() * 0.01
        if f(x_try) < val:
            x, val = x_try, f(x_try)
    return x
```

Each rung falls through on failure. In practice, tuning the stopping
tolerances per rung matters more than the algorithm choice.

## Worked example

Einstein Arena Heilbronn — the N=200 pipeline worked as follows:

1. Warm-started from `cross-resolution` output.
2. L-BFGS-B with analytic gradient for 500 iterations (converges to
   smooth local optimum).
3. Nelder-Mead polish with `xatol=1e-12`, `maxiter=5000` to reach the
   basin floor before ULP polish.
4. Hand-off to `ops-ulp-polish` for the last 2 orders of magnitude.

No single rung was enough. The ladder together beat gradient-only and
Nelder-Mead-only variants by ~4×.

## Gotchas

1. **Nelder-Mead does not scale.** Past `n ≈ 20` dimensions, the simplex
   has too many vertices; one iteration per vertex per step blows up.
2. **L-BFGS-B tolerance is per-machine-epsilon.** Default `ftol=2.22e-9`
   is too lax for competition work. Tighten with
   `options={'ftol': 1e-14, 'gtol': 1e-12}`.
3. **Hill climb needs exponential restarts to escape.** Use it as a last
   rung, not a primary method.
4. **Don't mix scales.** If coords differ by 10⁶ in magnitude, rescale
   before L-BFGS or Nelder-Mead; otherwise the step sizes are wrong for
   most coords.

## References

- Nelder, J. A., Mead, R. "A simplex method for function minimization."
  *Computer Journal* 7 (1965), pp. 308–313.
- Byrd, R. H., Lu, P., Nocedal, J., Zhu, C. "A limited-memory algorithm
  for bound-constrained optimization." *SIAM J. Sci. Comput.* 16 (1995),
  pp. 1190–1208.
- Nocedal, J., Wright, S. J. *Numerical Optimization*, 2nd ed., Springer
  (2006), Chapters 7 and 9.
