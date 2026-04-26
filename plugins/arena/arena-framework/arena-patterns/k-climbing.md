# k-climbing

## Trigger

Problem has a tunable size parameter `k` (Laguerre polynomial degree, LP
key count, kissing vector count, convolution grid size). Climbing `k`
unlocks new basins — but the relationship is usually not monotonic:
above some threshold, `k` ceases to improve the score or flips into
exploit-territory.

## Recipe

1. Run the rigor gate across the full top-K leaderboard. Record score +
   rigor_verdict per k.
2. Identify the **exploit line** — the lowest k value where verdict flips
   to `exploit`.
3. Run attacks at each "rigorous k" value (k ≤ exploit_line) from random
   and competitor-derived starting points.
4. For exploit-allowed submissions, climb k aggressively.
5. Never trust a single competitor's k as the correct choice — different
   basins are often reachable at different k values.

## Observed in

- **uncertainty-principle**: the leaderboard shows k=19 (alpha_omega,
  S=0.26543) dominates k=14 (JSAgent, S=0.31817), but rigor gate shows
  only k≤14 are genuine bounds. Our Path A climbed k=14 → k=19 for
  exploit-score; Path B held at k=14 for rigor.
- **kissing-d11**: public SOTA stopped at 593 (AlphaEvolve); Kawaii's 594
  lives in a different lattice construction. Our d12 PackingStar config
  exists only at specific symmetry-compatible sizes.

## Test

Covered manually in the `test_recon_up_flags_exploit_at_k15` regression —
the recon module's rigor scan produces the per-k table this pattern relies
on.

## Primitive

No dedicated primitive; the pattern drives attack-phase scheduling inside
`arena-attack-problem`.
