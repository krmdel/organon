# Remez exchange — equioscillation / min-max polynomial approximation

## When to use

You want the polynomial of degree ≤ n that best approximates a function `f`
on an interval in the **max-norm**:

    min_{p ∈ P_n} max_{x ∈ [a,b]} | f(x) − p(x) |

Or, more generally, any Chebyshev-style min-max fitting where the
Chebyshev equioscillation theorem applies: the optimal `p` equioscillates
between `n+2` extrema with alternating signs and equal magnitude.

Classic fits:

- Designing filters / transfer functions to hit a tight worst-case error.
- Approximating special functions (exp, log, trig) on fixed ranges for
  library implementations (CORDIC, libm-style).
- Competition problems where the objective is "minimise the max residual
  over a polynomial family."

Skip when:

- You're minimising L² error — use ordinary least squares, far easier.
- Constraints are non-convex in the coefficients (Remez assumes the
  approximation class is linear in parameters).
- You need interval-arithmetic guaranteed bounds — use rigorous Remez
  (e.g., `Sollya`), not this sketch.

## Pseudocode

```
def remez(f, n, interval=(-1, 1), tol=1e-12, max_iter=20):
    a, b = interval
    # Start with Chebyshev nodes — n+2 points on [a, b].
    nodes = chebyshev_nodes(n + 2, a, b)
    for _ in range(max_iter):
        # Solve for (p_0, ..., p_n, E) in n+2 linear equations:
        #    f(x_i) - p(x_i) = (-1)^i * E    for i = 0..n+1
        p_coef, E = solve_linear_system(nodes, f, degree=n)
        # Build residual r(x) = f(x) - p(x) and find its extrema.
        extrema = find_extrema(lambda x: f(x) - poly_eval(p_coef, x), a, b)
        # Exchange: keep n+2 points with alternating-sign extrema, largest |r|.
        new_nodes = exchange_alternating(extrema, n + 2)
        if max_abs_diff(nodes, new_nodes) < tol:
            return p_coef, E
        nodes = new_nodes
    return p_coef, E
```

Convergence is **quadratic** near the optimum once the correct
equioscillation pattern is found.

## Worked example

Approximate `f(x) = e^x` on `[-1, 1]` by a degree-3 polynomial.

- Chebyshev nodes at start: `x ≈ (-0.951, -0.588, 0, 0.588, 0.951)` (n+2=5).
- After 3 Remez exchange iterations, the coefficients converge to:
  `p(x) ≈ 0.99455 + 0.99546·x + 0.54293·x² + 0.17936·x³`,
  `E ≈ 5.52 × 10⁻³`.
- Residual `e^x − p(x)` equioscillates with 5 extrema of magnitude `E`.
- This beats the Taylor-series degree-3 polynomial (max error ≈ 5.2 × 10⁻²,
  an order of magnitude worse) over the interval.

## Gotchas

1. **Finding extrema robustly** is the hard part. Use a dense sampling
   (`N ≈ 1000·n`) followed by local Brent/Newton refinement; naive gradient
   methods miss extrema near the interval boundary.
2. **Exchange rule** must preserve alternating signs — one sloppy swap and
   convergence stalls. If you only have `n+1` alternations, add the largest
   remaining `|r|` extremum wherever it fits the sign pattern.
3. **Ill-conditioning** for high degree: use barycentric or Chebyshev bases
   instead of the monomial basis — `[1, x, x², ...]` has a Vandermonde-like
   matrix that blows up past `n ≈ 20`.
4. **Weighted Remez** (minimise `max w(x)|f(x) − p(x)|`) needs only minor
   changes but the weight must not vanish on the interval.

## References

- Remez, E. Y. "Sur la détermination des polynômes d'approximation de
  degré donnée." *Comm. Soc. Math. Kharkov* 10 (1934), pp. 41–63.
- Cheney, E. W. *Introduction to Approximation Theory*, 2nd ed., Chelsea
  (1982), Chapters 3 and 4.
- Fraser, W., Hart, J. F. "On the computation of rational approximations
  to continuous functions." *Communications of the ACM* 5 (1962),
  pp. 401–403.
- Pachón, R., Trefethen, L. N. "Barycentric-Remez algorithms for best
  polynomial approximation in the chebfun system." *BIT Numer. Math.* 49
  (2009), pp. 721–741.
