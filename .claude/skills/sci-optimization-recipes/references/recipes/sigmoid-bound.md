# Sigmoid bounding — smooth ratio-objective surrogates

## When to use

You have a ratio objective whose raw form is numerically unbounded — the
denominator can approach zero and the objective can blow up. You want
gradient-based optimisation to behave, and you don't need the last few
digits of accuracy (pair with `dinkelbach` or a polishing stage if you
do).

Classic fits:

- Early-stage exploration of ratio objectives where you'd otherwise hit
  `NaN` or `inf`.
- Training surrogate neural models on ratio losses.
- Competition problems where you want a well-behaved loss surface before
  refining with a sharper method.

Skip when:

- You need the actual optimal ratio value — sigmoid bounds squash the
  tails, so you lose fidelity at both extremes.
- `dinkelbach` applies and gives you the true answer at comparable cost.
- Denominator is guaranteed bounded away from zero; use the raw ratio.

## Pseudocode

```
def sigmoid_bound(f_ratio, scale=1.0):
    # Wrap a ratio f = N/D in a sigmoid so it stays in (0, 1).
    def f_bounded(x):
        r = f_ratio(x)
        # Clamp NaN / inf to large sentinel first.
        if not np.isfinite(r):
            return 1.0
        return 1.0 / (1.0 + np.exp(-scale * r))   # logistic
    return f_bounded

# Analytic gradient via chain rule: g * sigmoid * (1 - sigmoid) * scale.
def sigmoid_bound_grad(f_ratio, grad_ratio, scale=1.0):
    def g(x):
        r = f_ratio(x)
        if not np.isfinite(r):
            return np.zeros_like(x)
        s = 1.0 / (1.0 + np.exp(-scale * r))
        return s * (1.0 - s) * scale * grad_ratio(x)
    return g
```

`scale` controls how "flat" the bounded objective is near the optimum.
Small `scale` (0.1–1.0) gives a gentle surrogate; large `scale` (10–100)
recovers the sharpness of the original near the optimum.

## Worked example

Einstein Arena sigmoid warm-up: a ratio objective `num(x)/den(x)` with
near-singular `den(x)` crashed L-BFGS via `inf` evaluations. Wrapping in
`sigmoid_bound(scale=0.5)`:

1. Gradient descent converged cleanly in 50 iterations to a good
   neighbourhood.
2. Switched to the raw ratio (with Dinkelbach) for the last 2 orders of
   magnitude.
3. Final score ~1.5% better than running Dinkelbach from a random start
   (because the sigmoid stage landed in a better basin).

## Gotchas

1. **The optimum of sigmoid(f) is the optimum of f.** Sigmoid is
   monotonic, so `argmin sigmoid(f) = argmin f`. Reassuring — but only
   when `f` is bounded; if `f` is unbounded below, sigmoid sends you
   toward the tail without a real minimum.
2. **Scale tuning is coupled with `f`'s range.** If `|f|` is ~10⁻⁶
   at the optimum and `scale=1`, the sigmoid is essentially `0.5`
   everywhere — zero gradient. Rescale `f` first.
3. **Numerical overflow** in `exp(-scale * r)` for large positive `r`:
   use `scipy.special.expit` or a branch-aware implementation.
4. **Pair with a polish stage.** Sigmoid alone rarely gets close to the
   true optimum; hand off to Dinkelbach, L-BFGS on raw `f`, or ULP
   descent for the final polish.

## References

- Boyd, S., Vandenberghe, L. *Convex Optimization*, Cambridge (2004),
  §3.6 (log-sum-exp smoothing, a cousin of sigmoid bounding).
- Chapelle, O. "Training a support vector machine in the primal."
  *Neural Computation* 19 (2007) — sigmoid hinge-loss surrogates.
- Nesterov, Y. "Smooth minimization of non-smooth functions." *Math.
  Program. A* 103 (2005), pp. 127–152.
