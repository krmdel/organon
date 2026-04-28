# Arena Results

Reproducibility bundles for the Einstein Arena problems OrganonAgent attacked.
Each subfolder is self-contained:

```
{problem}/
  README.md     -- problem statement, score, recipe, reproduce command
  solution.json -- the submission (or submission-ready candidate)
  solver.py     -- verifier and/or recipe driver
  evaluator.py  -- arena server-matching evaluator
```

## Standings

| Problem | Best score | Leaderboard standing | Status |
|---|---:|---|---|
| [Prime Number Theorem](prime-number-theorem/)              | 0.99490198825        | beats prior #1 by 7.6e-5                | **submitted and accepted** |
| [First Autocorrelation](first-autocorrelation-inequality/) | 1.50286090736        | #1 on live leaderboard                  | **submitted and accepted** |
| [Second Autocorrelation](second-autocorrelation/)          | 0.96264331885        | +8.7e-11 over #1 (below 1e-4 gate)      | submitted, not accepted/scored due to arena evaluator |
| [Third Autocorrelation](third-autocorrelation/)            | 1.45230433318        | #1 on live leaderboard (2.17x the gate) | **submitted and accepted** |
| [Erdős Minimum Overlap](erdos-min-overlap/)                | 0.38087031047        | -1.16e-10 vs #1 (effective tie)         | submitted, not accepted/scored due to arena evaluator |
| [Kissing Number d=12](kissing-d12/)                        | 2.000000000006       | #2 on live leaderboard                  | **submitted and accepted** |
| [Thomson N=282](thomson-problem/)                          | 37147.29441846225    | tied #1 (3-way)                         | submitted, not accepted/scored due to arena evaluator |
| [Hexagon Packing](hexagon-packing/)                        | 3.94164212           | -1e-5 vs tied #1 (below 1e-4 gate)      | submitted, not accepted/scored due to arena evaluator |

Lower-is-better for: Erdős, Kissing, Thomson, Hexagon, all three autocorrelations.
Higher-is-better for: Prime Number Theorem.

## How to reproduce

Each folder verifies in seconds via:

```bash
cd plugins/arena/results/{problem}
python3 solver.py
```

The PNT and Erdős solvers are full recipes that re-derive the solution from
scratch (~75 min and ~30 min wall clock respectively). All others are verifiers
that check the bundled `solution.json` reproduces the claimed score; the full
attack pipelines that produced them live in `projects/einstein-arena-*/`
(gitignored — running multi-hour campaigns is what the arena plugin's
`tool-arena-attack-problem` skill is for).

## Why some scores aren't on the leaderboard

Three reasons that a "best score" here might not be the live leaderboard rank:

1. **Not submitted.** Standing rule across the campaign: no submission without
   explicit user approval. Several improvements sit submission-ready waiting on
   the call to push.
2. **Below the minImprovement gate.** Arena enforces a per-problem improvement
   threshold (typically 1e-4 or 1e-5 or 1e-6). A mathematically better solution
   that's below the gate can't claim #1 even though the score is genuinely lower.
3. **Leaderboard snapshot drift.** The recorded `leaderboard.json` for each
   project was fetched on a specific date; the live arena may have moved.

## See also

- [`plugins/arena/`](..) — the arena framework (skills, agents, attack patterns) that produced these.
- [`plugins/arena/arena-framework/arena-patterns/`](../arena-framework/arena-patterns/) — the reusable attack patterns referenced in each recipe.
