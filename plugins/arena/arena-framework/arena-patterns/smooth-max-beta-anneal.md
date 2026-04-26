# smooth-max-beta-anneal

## Trigger

Objective is a max (or min) over a discrete set of smooth components —
autocorrelation peak, minimax design, Chebyshev fit. Non-smooth max
breaks L-BFGS and other gradient methods; at finite β the log-sum-exp
approximation is smooth and converges to the true max.

## Recipe

1. Replace `max_i c_i(x)` with `(1/β) log Σ_i exp(β c_i(x))`.
2. Anneal β through an ascending cascade: `[1e2, 1e3, 1e4, 1e5, 1e6, 1e7]`
   (optionally higher up to 1e10 for final precision).
3. Warm-start each level from the previous level's minimum.
4. Inner solver: L-BFGS-B with analytic gradient via
   `softmax_i = exp(β c_i) / Σ_j exp(β c_j)` and the chain rule.
5. Use the max-subtraction trick in both `smooth_max` and its gradient to
   stay numerically stable at β ≥ 1e8.

## Observed in

- **first-autocorrelation-inequality**: JSAgent's published β=1e6 endpoint
  left an unexploited tight-gradient direction. Continuing through β=1e7 →
  3e7 → 1e8 → 3e8 → 1e9 → 3e9 → 1e10 extracted an additional ~2e-7
  improvement. Active-constraint count exploded from 445 (β=1e6) to
  26,556 (β=1e10) within 1e-8 tolerance — equioscillation plateau.

## Test

`tests/test_smooth_max_beta.py` — `test_annealing_reaches_minimax_on_parabolas`,
`test_annealing_minimises_small_autocorrelation_peak`.

## Primitive

`arena_framework.primitives.smooth_max_beta.smooth_max_beta_anneal(components_fn, x0, jacobian_fn=..., beta_schedule=[...])`
