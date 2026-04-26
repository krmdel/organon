---
name: ops-parallel-tempering-sa
description: 'Parallel-tempering simulated annealing for rugged multi-modal landscapes where local SA stalls. N replicas at a geometric temperature ladder with periodic adjacent-pair exchanges (Metropolis-Hastings). Contribution-weighted coordinate sampling + O(n) incremental delta evaluators. Triggers: "parallel tempering", "simulated annealing", "PT-SA", "replica exchange", "temperature ladder", "MCMC optimization". Not for: gradient descent, convex optimization, linear programming.'
---

# ops-parallel-tempering-sa — parallel-tempering simulated annealing

## When to use

You have a rugged, multi-modal loss landscape and plain SA or gradient descent
keeps getting trapped in the same metastable basin. Replicas swim at different
temperatures — the hot ones explore freely, the cold ones exploit. Periodic
replica exchanges let a good discovery made at high temperature propagate down
the ladder to the cold replicas without the cold replicas having to re-find it.

Canonical triggers:
- Kissing-number / spherical code optimization near an extremal bound.
- Graph layout where local moves get stuck in folded crossings.
- Lattice packings with many nearly-degenerate global minima.
- Combinatorial problems with a discrete state space and cheap local moves.
- Any objective that is a SUM of per-element contributions — contribution-weighted
  sampling wins.

Skip PT-SA for: convex problems (gradient descent / LP works), unimodal
landscapes (plain SA wins), smooth continuous problems (Newton / LBFGS wins),
or anything where you can't write a cheap local move proposer.

## Methodology

1. **Temperature ladder** — geometric schedule `T_i = t_min * (t_max/t_min)^(i/(n-1))`.
   Geometric ladders keep pairwise exchange acceptance roughly uniform
   (Hukushima-Nemoto 1996 / Kofke 2002). Hot end explores; cold end exploits.
2. **Per-replica Metropolis step** — at each iteration each replica proposes a
   local move via user-supplied `propose_move_fn(state, rng, idx=None)` and
   accepts with probability `min(1, exp(-beta_r * dE))`.
3. **Contribution-weighted coordinate sampling** — if the user supplies
   `contribution_fn(state) -> ndarray[n]`, the driver samples which coordinate
   to perturb with probability proportional to its contribution to the loss
   (the kissing-number insight: high-overlap rows benefit most from movement).
4. **Incremental delta evaluator** — if the user supplies
   `delta_fn(state, change) -> delta_loss`, the driver uses it for acceptance,
   bypassing the full O(n) loss recompute. This is the jmsung/einstein pattern
   that gave a 730x speedup vs greedy-perturbation on the kissing problem.
5. **Replica exchange** — every `exchange_every` iterations, alternate
   even/odd adjacent pairs attempt a swap under the Metropolis-Hastings
   criterion `p(i <-> j) = min(1, exp((beta_i - beta_j) * (E_j - E_i)))`.
6. **Best-ever tracking** — each replica tracks its own best state; the final
   result is the minimum across replicas.

## API

```python
from pt_sa import parallel_tempering_sa

result = parallel_tempering_sa(
    initial_state,                 # ndarray or list
    loss_fn,                       # state -> float
    propose_move_fn,               # (state, rng, idx=None) -> (new_state, change)
    delta_fn=None,                 # (state, change) -> float   (optional)
    contribution_fn=None,          # state -> ndarray[n]         (optional)
    n_replicas=8,
    t_min=1e-12,
    t_max=1e-4,
    max_steps=10_000,
    exchange_every=10,
    seed=None,
    verbose=False,
)
# result: {"best_state", "best_loss", "replicas", "temperatures",
#          "history", "exchange_attempts", "exchange_accepts"}
```

Helpers exported: `temperature_schedule(t_min, t_max, n)`,
`attempt_exchange(E_A, E_B, beta_A, beta_B, rng) -> bool`,
`weighted_choice(weights, rng) -> int`.

### Move proposer contract

`propose_move_fn(state, rng, idx=None)` returns `(new_state, change)`:
- `new_state` is a fresh ndarray (do NOT mutate `state` in place).
- `change` is an arbitrary dict describing what changed — passed back to
  `delta_fn` if you supplied one. Include enough info for delta_fn to compute
  `loss(new_state) - loss(state)` without re-summing the whole state.
- If `contribution_fn` is provided, the driver picks an `idx` and passes it;
  your move should use this `idx` to decide what to perturb.

### NaN guard

A move whose evaluated energy is NaN is silently rejected (the replica stays
at its current state and the step still counts toward `max_steps`). This is
safer than raising since stochastic proposers occasionally hand the evaluator
a pathological state.

## Dependencies

| Dependency | Required | Provides | Fallback |
|---|---|---|---|
| `numpy` | Yes | RNG, arrays, vectorised math | None |
| User `loss_fn` | Yes | Scalar objective | None |
| User `propose_move_fn` | Yes | Local move generator | None |
| User `delta_fn` | Optional | O(n) incremental energy | Fall back to full `loss_fn` |
| User `contribution_fn` | Optional | Per-element contribution weights | Uniform coord pick inside proposer |

## References

- `references/pt-sa-theory.md` — PT-SA theory, Hukushima-Nemoto exchange
  criterion, geometric ladders, contribution-weighted sampling, incremental
  delta pattern, when NOT to use PT-SA, and literature citations.

## Tests

- `tests/test_pt_sa.py` — 24 unit tests covering temperature schedule
  (geometric, singleton, invalid params), exchange criterion (acceptance,
  analytic probability, deterministic rejection), weighted choice
  (preference + all-zero uniform fallback), happy-path quadratic
  minimization, delta_fn bypass vs full-loss fallback, reproducibility,
  empty/singleton state, n_replicas=1 and n_replicas=8, temperature
  enforcement, budget enforcement (±1 step), NaN-move rejection,
  monotonicity, contribution_fn end-to-end, and invalid parameter guards.

Run: `python3 -m pytest .claude/skills/ops-parallel-tempering-sa/tests/ -v`

Coverage on `pt_sa.py`: 94% (gate: ≥90%).
