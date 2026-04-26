# Parallel-Tempering Simulated Annealing — Theory

## What it is

Parallel-tempering (PT), also known as replica-exchange Monte Carlo, runs N
independent Markov chains in parallel at N different temperatures and
periodically proposes swaps between neighboring chains. Hot chains explore the
landscape freely; cold chains exploit local minima. Swaps let a good
discovery made at high temperature propagate down the ladder to cold replicas
without the cold replicas having to rediscover it from scratch — this is what
busts metastable traps that ordinary single-chain SA falls into.

The algorithm was introduced by Swendsen & Wang (1986) for spin-glass
simulations and rediscovered / popularized in the form used today by Geyer
(1991) as "Metropolis-coupled MCMC" and by Hukushima & Nemoto (1996) as
"exchange Monte Carlo" / "parallel tempering".

## Detailed balance and the exchange criterion

Let replica `i` hold state `x_i` with energy `E_i = loss(x_i)` at inverse
temperature `beta_i = 1/T_i`. The joint distribution over all replicas is

    P(x_1, ..., x_N) = prod_i (1/Z_i) exp(-beta_i * E_i)

For a proposed swap of states `x_i <-> x_j`, detailed balance on this joint
distribution requires the acceptance probability

    alpha(i <-> j) = min(1, P(swap) / P(no swap))
                   = min(1, exp(-beta_i E_j - beta_j E_i + beta_i E_i + beta_j E_j))
                   = min(1, exp((beta_i - beta_j)(E_j - E_i)))

When the COLD replica has the LOWER energy the expression inside exp is >= 0
and the swap always accepts. When the cold replica has the higher energy the
swap is rejected with probability `1 - exp(delta)` where
`delta = (beta_i - beta_j)(E_j - E_i) <= 0`.

Key property: a sequence of swaps is itself a valid Metropolis chain, so the
stationary distribution over replica configurations is unchanged — PT is an
exact MCMC on the product space, not an approximation.

## Why geometric temperature ladders

Kofke (2002) showed the acceptance rate for adjacent swaps is approximately

    <alpha> ~ 2 * Phi(-sqrt(C_v) * log(T_{i+1}/T_i) / sqrt(2))

where `C_v` is the heat capacity and `Phi` the standard normal CDF. Under a
geometric ladder `T_i = T_min * r^i` with fixed ratio `r`, `log(T_{i+1}/T_i)`
is constant across the ladder, so the acceptance rate between every adjacent
pair is the same. This gives the best-tuned diffusion of states up and down
the ladder with the fewest wasted rejections. Aim for roughly 20-40% pairwise
exchange acceptance; if too low, add replicas; if too high, widen the range.

## Contribution-weighted coordinate sampling

When the objective is a sum of per-element contributions

    loss(x) = sum_i c_i(x)

naive uniform coordinate sampling wastes proposals on elements that already
contribute nothing. Sample the proposed coordinate with probability
proportional to `c_i(x)` and most proposals land on the elements where
improvement is actually possible. This is the trick that powered the
jmsung/einstein kissing-number solver — in that problem, rows whose nearest
neighbor gap is smallest (the "tight" rows) dominate the loss; perturbing
them is the only way to improve. The speedup over uniform sampling was on the
order of 10-100x in wall-clock time to a given solution quality, depending on
how peaked the contribution distribution is.

Caveats:
- You need a `contribution_fn` that is cheap compared to a full loss eval.
- Sampling always keeps a small uniform-like floor via the `+ 1` or softmax so
  a zero-contribution element can still be selected if it would create useful
  structure (the driver in this skill handles the all-zero case by falling
  back to uniform).

## Incremental O(n) delta evaluation

The 730x speedup reported in the jmsung/einstein kissing-number solver came
from bypassing the full O(n^2) pairwise loss recompute on every accepted move.
The observation: if only one row of an `n x d` configuration changes, only the
`n` pairwise distances involving that row change. The contribution of all
other pairs is unchanged. So

    new_loss = old_loss - (old contribution of row i) + (new contribution of row i)

reduces the per-move cost from O(n^2) to O(n). Over 10^7 moves that is four
orders of magnitude saved — more than enough to turn an overnight run into a
minute.

This skill supports that pattern via `delta_fn(state, change) -> delta_loss`.
When provided, `delta_fn` is the sole arbiter of Metropolis acceptance; the
expensive `loss_fn` is called only once per replica at initialization.

## Canonical pseudocode

```
init states x_r <- x_0 for r in 1..N
init energies E_r <- loss(x_r)
temps[1..N] = geometric(t_min, t_max, N)
for step in 1..max_steps:
    for replica r in 1..N:
        idx  <- weighted_choice(contribution_fn(x_r))  # if provided
        x', delta_info <- propose_move(x_r, rng, idx=idx)
        dE   <- delta_fn(x_r, delta_info) or loss(x') - E_r
        if dE < 0 or rng.uniform() < exp(-beta_r * dE):
            x_r <- x'
            E_r <- E_r + dE
    if step mod exchange_every == 0:
        for i in alternating_pairs:
            if rng.uniform() < exp((beta_i - beta_{i+1}) * (E_{i+1} - E_i)):
                swap(x_i, x_{i+1}); swap(E_i, E_{i+1})
return argmin_r best_E_r  # each replica tracked its own best
```

Alternate even/odd pair starts at successive exchange passes — otherwise the
`(1,2), (3,4), ...` pairing never consults `(2,3)` etc., which is bad for
mixing.

## When NOT to use PT-SA

- **Convex problems.** Gradient descent, LP, or QP wins without the overhead.
- **Smooth unimodal problems.** Newton / LBFGS with a decent starting point
  wins.
- **Problems with no cheap local move.** If every proposal requires solving a
  subproblem, Monte Carlo overhead dominates. Use column generation / branch-
  and-bound.
- **Problems dominated by the basin of attraction already.** Plain SA or basin
  hopping with restarts may be enough. PT helps when single-basin escape is
  the bottleneck, not when finding any basin is the problem.

## References

- Swendsen, R. H. & Wang, J.-S. Replica Monte Carlo simulation of spin
  glasses. Phys. Rev. Lett. 57, 2607 (1986).
- Geyer, C. J. Markov chain Monte Carlo maximum likelihood. Proc. 23rd Symp.
  Interface (1991).
- Hukushima, K. & Nemoto, K. Exchange Monte Carlo method and application to
  spin glass simulations. J. Phys. Soc. Jpn. 65, 1604–1608 (1996).
- Kofke, D. A. On the acceptance probability of replica-exchange Monte Carlo
  trials. J. Chem. Phys. 117, 6911 (2002).
- Earl, D. J. & Deem, M. W. Parallel tempering: Theory, applications, and new
  perspectives. Phys. Chem. Chem. Phys. 7, 3910–3916 (2005).
- jmsung/einstein GitHub repo — kissing-number reference implementation whose
  contribution-weighted sampling + O(n) delta pattern inspired this skill.
