# LP reformulation — epigraph form for max-type objectives

## When to use

You have a non-smooth objective that is actually the **max** (or min) of
a collection of linear / affine terms, and your current solver is
struggling with the non-smoothness. Reformulate to a linear program
(LP) via an auxiliary variable `t` and one linear inequality per term.

Classic fits:

- Min-max / Chebyshev problems: `min_x max_i (a_iᵀ x + b_i)`.
- Piecewise-linear cost functions.
- Many robust-optimisation reformulations (adversarial-worst-case LP).
- Competition objectives framed as "minimise the largest residual" — LP
  gives exact bounds and a dual certificate.

Skip when:

- Terms are non-linear (quadratic / convex): use SOCP or SDP instead.
- The number of terms is exponential in the problem size (e.g. all
  vertices of a polyhedron) — use column generation instead.
- You want to solve approximately fast; the LP solver may be overkill.

## Pseudocode

```
# Original:  min_x  max_i  { a_i^T x + b_i }     (finite i in I)

# Epigraph reformulation:
#   minimise_{x, t}  t
#   s.t.             a_i^T x + b_i <= t    for all i in I
#
# This is a standard LP in variables (x, t).

def lp_reformulate_maxmin(A, b):
    # A: (|I|, n), b: (|I|,). Variables [x; t] of length n + 1.
    n = A.shape[1]
    c = np.concatenate([np.zeros(n), [1.0]])       # minimise t only
    # Inequality:   a_i^T x - t <= -b_i
    G = np.hstack([A, -np.ones((A.shape[0], 1))])
    h = -b
    sol = linprog(c, A_ub=G, b_ub=h, bounds=(None, None), method='highs')
    x_opt, t_opt = sol.x[:n], sol.x[n]
    return x_opt, t_opt
```

Any modern LP solver (HiGHS, Gurobi, CPLEX) handles ~10⁵ constraints
easily. For much larger |I|, go to column generation.

## Worked example

Chebyshev approximation as LP: given points `(x_j, y_j)`, find the
affine function `y = m·x + c` minimising `max_j |m·x_j + c − y_j|`.

- `|·|` is shorthand for `max(·, −·)`, so you have two linear terms per
  data point. Epigraph variable `t` bounds both:
  `m·x_j + c − y_j ≤ t` and `−(m·x_j + c − y_j) ≤ t`.
- Total LP: 2 variables (`m`, `c`) + 1 aux (`t`) + `2J` constraints.
- HiGHS solves a 100-point instance in <10 ms.

## Gotchas

1. **Watch the sign.** `max` wraps negatives away; re-check every
   inequality translates to `≤ t` (not `≥`).
2. **Box / simplex constraints on `x` remain**. Add them as usual
   (`A_eq x = b_eq`, `lb ≤ x ≤ ub`); don't forget them when wiring up
   `linprog`.
3. **Numerical conditioning.** LP solvers handle some scaling, but if
   `|a_i|` entries span 10+ orders of magnitude, pre-scale rows — else
   the solver's tolerance is dominated by the largest row.
4. **Dual gives certificates.** For competition problems, inspect the
   dual variables — they identify *which* constraints bind, i.e. which
   `max` terms are active at the optimum (often the whole point of the
   exercise).

## References

- Dantzig, G. B. *Linear Programming and Extensions*, Princeton (1963),
  Chapters 1–4 (epigraph and min-max formulations).
- Boyd, S., Vandenberghe, L. *Convex Optimization*, Cambridge (2004),
  §4.3 (LP reformulations of piecewise-linear and min-max problems).
- Nemirovski, A. *Interior-Point Polynomial Algorithms in Convex
  Programming*, SIAM (1994). (Polynomial-time LP).
