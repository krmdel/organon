# k-Climbing / Variable Neighborhood Search

## When to use

The landscape is **deceptive**: greedy local search traps you in shallow
basins, and random restarts take forever to find the good ones. Signs:

- Best-so-far stalls after a few hundred gradient steps, but you suspect
  much better exists.
- Small perturbations go nowhere; larger perturbations kick you to a worse
  basin; somewhere in between there's a sweet spot.
- The feasible set is combinatorial or has many "walls" where a 1-variable
  move helps but a 2-variable move is needed to escape.

Classic fits: competition math arenas with discrete jumps, integer-like
continuous problems, MINLP relaxations, bin packing, scheduling, and any
"hill with hidden shoulders" landscape.

Skip when:

- Landscape is smooth and unimodal — plain L-BFGS is faster.
- You already know the basin from warm start (use `cross-resolution`).
- Problem is a ratio or min-max in disguise (use `dinkelbach` / `remez`).

## Pseudocode

```
def k_climbing(f, x0, k_max=4, restarts=100, eps=1e-9):
    best_x, best_f = x0, f(x0)
    for r in range(restarts):
        x = random_start_near(best_x)            # perturbation amplitude tuned per restart
        k = 1
        while k <= k_max:
            # k-opt move: flip / perturb exactly k coordinates.
            candidate = local_search_k_opt(f, x, k)
            if f(candidate) < f(x) - eps:
                x = candidate
                k = 1                             # good move — shrink back
            else:
                k += 1                            # widen neighbourhood
        if f(x) < best_f:
            best_x, best_f = x, f(x)
    return best_x, best_f
```

k controls the **radius** of combinatorial exploration. `k=1` is steepest
descent; `k=4` often covers the useful horizon for competition problems.

## Worked example

Einstein Arena First Autocorrelation (C1) — the β-anneal breakthrough came
from a VNS variant:

1. Start at a known-good basin (score ≈ 1.40).
2. At each step: try `k=1` coord moves; if none improve, widen to `k=2`;
   anneal β (temperature) from high (exploration) to low (exploitation).
3. After ≈ 300 iterations, score jumped to 1.50286 — a cliff, not a slope,
   that `k=1` alone missed.

## Gotchas

1. **k_max too small** → traps you in the same basin you started from.
2. **k_max too large** → combinatorial explosion (`C(n, k)` candidates).
   Practical upper bound is 4 for n ≤ 100 variables.
3. **Random restart distribution** is crucial. Gaussian noise near the
   best-so-far is usually too tight; sample from a heavier-tailed
   distribution (Laplace, Cauchy) for escape.
4. **Don't forget to reset `k=1`** after any improvement — otherwise you
   waste time in wide neighbourhoods on already-good points.

## References

- Hansen, P., Mladenović, N. "Variable neighborhood search: principles and
  applications." *European Journal of Operational Research* 130 (2001),
  pp. 449–467.
- Mladenović, N., Hansen, P. "Variable neighborhood search." *Computers &
  Operations Research* 24 (1997), pp. 1097–1100.
- Lin, S., Kernighan, B. W. "An effective heuristic algorithm for the
  traveling-salesman problem." *Operations Research* 21 (1973), pp.
  498–516. (Origin of k-opt.)
