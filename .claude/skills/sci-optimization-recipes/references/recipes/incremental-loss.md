# Incremental O(n) Loss Evaluation

## When to use

You have an n-body objective — loss is a sum over pairs (or triples) of elements, cost is O(n²) per full evaluation. Your solver mutates one element at a time and re-evaluates the full loss at each step. For n ≥ 1000 the full evaluation dominates wall time, even though only n−1 of the n(n−1)/2 pair terms actually changed.

Canonical use cases: kissing-number / spherical-code distance optimisation, lattice packing residual, graph-layout energy (springs or log-barriers between node pairs), difference-basis coverage, any Sidon-like pairwise-constraint objective.

Skip when the objective is genuinely global (e.g. spectral — depends on a matrix factorisation that must be redone on any change), or when n is small enough (≤ 200) that O(n²) is microsecond-scale.

## Pseudocode

```python
# One-time: cache the full pairwise-contribution matrix, shape (n, n).
P = compute_pairwise_table(X)           # P[i,j] = f(X[i], X[j])
loss = P.sum() / 2                       # symmetric → divide by 2

def try_move(i, x_new):
    old_row = P[i, :].copy()
    new_row = np.array([f(x_new, X[j]) for j in range(n) if j != i] + [0.0])
    delta = (new_row - old_row).sum()    # O(n) instead of O(n^2)
    if delta < 0:                        # improving
        P[i, :] = new_row
        P[:, i] = new_row
        X[i] = x_new
        return True, loss + delta
    return False, loss
```

## Worked example

**Kissing-number at n = 594 in d = 11.** Full loss is 176 421 pair-distance terms. A per-coordinate sweep touches 594 × 11 × 8 ulp trials = 52 272 evaluations per sweep.
- **Naive full-eval**: 52 272 × 176 421 = 9.22 × 10⁹ pair operations per sweep.
- **Incremental**: 52 272 × 593 = 3.10 × 10⁷ pair operations per sweep. **297× speed-up**.

This is exactly the jmsung/einstein "O(n) loss" pattern that made 8-replica PT-SA tractable on kissing-d11 — without it, a single replica sweep took minutes; with it, under a second.

## Gotchas

- **Symmetry bookkeeping**: if your pair function is symmetric (`f(a,b) == f(b,a)`) the cache is symmetric too — update BOTH `P[i,:]` and `P[:,i]` or the next try_move on column `j` will read a stale row.
- **Numerical drift**: incrementally accumulated `loss + delta` drifts from the true `P.sum()/2` after many moves (float rounding). Periodically (every 100–1000 moves) recompute `loss = P.sum()/2` from the matrix to resync.
- **Non-pair terms**: if the loss has a self-term `f(X[i], X[i])` (e.g. a regulariser) include it in the row update — easy to forget when refactoring.
- **Higher-arity objectives** (triples, e.g. B₃ difference-basis sums): the cache becomes a 3-tensor, updates touch O(n²) elements. Incremental still helps but only by a constant factor.
- **Acceptance-based staleness**: if a trial is rejected, DO NOT mutate `P` or `X`. The test above returns before mutation on the non-improving branch; refactors sometimes break this invariant.

## References

- Hukushima, K. & Nemoto, K. *Exchange Monte Carlo method and application to spin glass simulations.* J. Phys. Soc. Jpn. 65 (1996), 1604–1608. (Original PT formulation; incremental loss implicit in the spin-flip update.)
- jmsung/einstein repository (GitHub, 2026). `incremental_loss.py` pattern used for kissing-number at d = 11.
- Cohn, H. & Elkies, N. *New upper bounds on sphere packings.* Ann. of Math. 157 (2003). (Motivation for O(n²) pair-sum objectives in packing problems.)
