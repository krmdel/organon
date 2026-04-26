# Square parameterization — break peak-locking on non-negative variables

## When to use

You have a variable `x ≥ 0` and the unconstrained solver keeps pushing it
toward exactly zero and locking there — even when the true optimum wants
a tiny positive value. Or the variable is already stuck at a boundary
peak and gradient descent can't escape because the gradient is zero on
the inequality wall.

Classic fits:

- Weights in a mixture model `w_i ≥ 0, Σw_i = 1`.
- Entries of a Gram matrix, covariance matrix, or PSD parameterisation.
- Non-negative penalty / slack variables in convex reformulations.
- Competition problems where a "peak locking" pathology shows up: many
  variables all hit the boundary and the solver stalls.

Skip when:

- Variables can be negative — square parameterisation kills a sign degree
  of freedom.
- You need exact zeros (the `x = s²` map only gives zero as a limit of
  `s → 0`, never hits it in finite iterations).

## Pseudocode

```
# Original: minimise f(x) subject to x >= 0.
# Reparameterise: x = s**2, s unconstrained. Optimise f(s**2) freely.

def square_param_min(f, n, x0=None):
    # Initial guess: pick sqrt of current x0, or random s ~ N(0, 1).
    if x0 is None:
        s = np.random.randn(n)
    else:
        s = np.sqrt(np.maximum(x0, 1e-12))
    # Wrap the objective in the reparameterisation.
    def g(s):  return f(s**2)
    def dg(s): return 2.0 * s * grad_f(s**2)   # chain rule
    s_opt = unconstrained_minimise(g, s, gradient=dg)
    return s_opt**2                             # map back to x-space
```

The trick: `∂x/∂s = 2s`. When `s = 0`, the gradient of the reparameterised
objective also vanishes — so zero is a saddle/fixed point, not a wall.
Gradient descent on `s` leaves zero voluntarily, whereas gradient descent
on `x ≥ 0` can't.

## Worked example

Non-negative least squares: fit `y ≈ A w`, `w ≥ 0`.

- Direct approach: projected gradient or active-set NNLS. Works but clips
  many `w_i` to exactly zero and gets stuck there.
- Square parameterisation: let `w_i = s_i²`, solve
  `min_s ‖A s² − y‖²` unconstrained with L-BFGS.
- For near-collinear columns where true optimum has small-positive entries
  (e.g. `w_i* = 0.001`), the squared form routinely finds those small
  values; the projected method pins them at 0.

## Gotchas

1. **Convexity is not preserved.** Even if `f(x)` is convex, `f(s²)` is
   generally not. Expect local minima. Pair with multi-start or
   `k-climbing` if the landscape is nasty.
2. **Scaling becomes odd.** Gradients near `s ≈ 0` are tiny (factor `2s`),
   so an optimiser with bad step-size heuristics may stall. Use L-BFGS
   with curvature estimate, not vanilla SGD.
3. **Sign ambiguity.** `s` and `-s` map to the same `x`. Fine for the
   solution but may confuse identifiability analysis downstream.
4. **For sum-to-one simplex constraints**, pair with a softmax:
   `w = softmax(s)` simultaneously enforces `w ≥ 0` and `Σw = 1`.

## References

- Chen, Y., Ye, Y. "Projection onto a simplex." *arXiv:1101.6081* (2011)
  — survey of boundary-handling reparameterisations.
- Kim, D., Sra, S., Dhillon, I. S. "A non-monotonic method for large-scale
  non-negative least squares." *Optimization Methods and Software* 28
  (2013), pp. 1012–1039.
- Burer, S., Monteiro, R. D. C. "A nonlinear programming algorithm for
  solving semidefinite programs via low-rank factorization." *Math.
  Program.* 95 (2003), pp. 329–357. (`X = Y Yᵀ` is the matrix analogue.)
