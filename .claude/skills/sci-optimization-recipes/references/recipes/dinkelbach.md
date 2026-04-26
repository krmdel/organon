# Dinkelbach algorithm — fractional programs

## When to use

Your objective is a **ratio** of two functions with the same variable `x`:

    min  f(x) = N(x) / D(x)    subject to  x ∈ X,   D(x) > 0 on X

Classic fits:

- Linear-fractional programs: `(cᵀx + c₀) / (dᵀx + d₀)`.
- Rayleigh-quotient style objectives (numerator and denominator both convex,
  denominator positive).
- Competition objectives where a ratio hides a cleaner parametric form.
- Any time you find yourself computing `N/D` inside a black-box solver and
  the solver stalls — Dinkelbach separates the fractional layer from the
  underlying geometry.

Skip when:

- N or D is **not** continuous / computable independently (you only get
  `f(x)` from a black box).
- D(x) can cross zero over the feasible set (denominator handling needed).
- The ratio is actually a **max** of several ratios — that's min-max, use
  `remez` or `lp-reformulation`.

## Pseudocode

```
def dinkelbach(N, D, X, tol=1e-12, max_iter=50):
    # Pick any feasible starting point.
    x = any_feasible(X)
    lam = N(x) / D(x)
    for k in range(max_iter):
        # Solve the parametric subproblem: min_x { N(x) - lam * D(x) }.
        x_new = solve_subproblem(lambda y: N(y) - lam * D(y), X)
        F = N(x_new) - lam * D(x_new)   # optimal value of subproblem
        if abs(F) < tol:
            return x_new, lam
        lam = N(x_new) / D(x_new)       # update parameter
        x = x_new
    return x, lam
```

Convergence is **superlinear** when the subproblem is solved to optimality
and D(x) is bounded away from zero on X.

## Worked example

Minimise `(x + 2) / (x² + 1)` on `x ∈ [0, 5]`.

- Iteration 0: `x=0`, `λ₀ = 2/1 = 2.0`.
- Iteration 1: `min_x (x + 2) − 2(x² + 1) = −2x² + x` → `x=0.25`, new
  `λ₁ = 2.25 / 1.0625 ≈ 2.1176`.
- Iteration 2: `min_x (x + 2) − 2.1176(x² + 1) → x ≈ 0.2361`.
- `F(x₂) ≈ −0.000_012` → converged.

Closed-form optimum is at `x* = √2 − 1 ≈ 0.4142`, confirming the solver.

## Gotchas

1. **Denominator positivity.** If `D(x)` can be zero or negative inside X,
   Dinkelbach breaks. Check `D > 0` before each subproblem, or add a slack
   constraint `D(x) ≥ ε`.
2. **Subproblem must be solvable.** For linear-fractional programs the
   subproblem is an LP — easy. For non-convex N/D the subproblem is as hard
   as the original, so Dinkelbach buys you nothing.
3. **λ can oscillate** if the subproblem is only approximately solved — use
   the damped update `λ_{k+1} = λ_k + α · (N(x)/D(x) − λ_k)` with
   `α ∈ (0, 1]` to stabilise.
4. **Competition tip.** When you're already inside an LP/SDP pipeline, the
   Dinkelbach subproblem is often one extra linear term — cheap compared
   to the outer solver.

## References

- Dinkelbach, W. "On nonlinear fractional programming." *Management
  Science* 13 (1967), pp. 492–498.
- Schaible, S. "Fractional programming." *Handbook of Global
  Optimization* (1995), Kluwer.
- Crouzeix, J.-P., Ferland, J. "Algorithms for generalized fractional
  programming." *Mathematical Programming* 52 (1991), pp. 191–207.
