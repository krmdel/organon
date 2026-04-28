# Third Autocorrelation Inequality — Einstein Arena

**Problem:** Cubic version of the autocorrelation family. Minimize
`C(f) = max(f * f * f) / (integral f)^3` for non-negative `f: [0, 1] -> R+`,
discretized to `n` samples. Arena evaluates via `numpy.convolve` (twice, for the
triple convolution).

**Status:** **NOT YET SUBMITTED.** Beats JSAgent's posted #1 by `2.17x` the arena's
`1e-4` minImprovement threshold — a clean #1 if submitted.

| | Score | Notes |
|---|---|---|
| **OrganonAgent (this folder)** | **1.45230433318** | `solution.json`, n=100,000, round 5 polish |
| Current #1 (JSAgent)           | 1.45252115505 | tied with alpha_omega_agents |
| AlphaEvolve (historical)       | 1.4557        | predecessor frontier |

## Recipe

Recursive basin-escape — a unique structural finding for this problem. Starting from
JSAgent's published configuration, applying a small noise perturbation and re-polishing
finds a *different* basin every round, with diminishing returns. Five rounds reach
`2.17x` the gate; further rounds have decaying yield (geometric ratio ~0.7-0.8).

```
round 0  JSAgent public #1                          C = 1.452521155
round 1  + 1% noise (seed 42), 15-stage beta-cascade   1.452377144  (-1.44e-4)
round 2  + 1% noise (seed 101)                          1.452338214  (-1.83e-4)
round 3  8 seeds, all converge                          1.452321192  (-2.00e-4)
round 4  6 seeds, all converge                          1.452311414  (-2.10e-4)
round 5  6 seeds, all converge                          1.452304333  (-2.17e-4)
```

Five independent structural signatures confirm each round lands in a genuinely
distinct critical point (not float-precision drift):

- Autoconv peak location migrates between rounds.
- Amplitude envelope grows (round 5: |f| reaches noticeably larger extrema).
- Active-set fingerprint at 1e-9 tolerance: 14,847 active peaks (JSAgent) vs
  61,528 (round 5) — wider Chebyshev-like equioscillation.
- β-push within a round extracts only ~3e-11; gains come from basin changes,
  not local polish.

## Reproduce

```bash
# Verify the included solution.json (loads 100k samples, evaluates triple conv)
python3 solver.py
```

The full 5-round basin-escape pipeline lives in
`projects/einstein-arena-third-autocorrelation/` (gitignored; ~12 hours wall clock).

## Files

| | |
|---|---|
| `solution.json` | Round-5 polished, n=100,000. |
| `solver.py`     | Verifier — loads, runs `numpy.convolve` twice, prints score + delta. |
| `evaluator.py`  | Arena server-matching evaluator. |
