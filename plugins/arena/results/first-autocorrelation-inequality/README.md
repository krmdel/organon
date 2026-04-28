# First Autocorrelation Inequality — Einstein Arena

**Problem:** Find non-negative `f: [0, 0.5] -> R+` minimizing
`C(f) = max(f * f) / (integral f)^2` (where `*` is convolution and `max` is over the full
support). Discretized to `n` samples; arena evaluates via `numpy.convolve`.

**Status:** **submitted and accepted.** OrganonAgent holds #1 on the live leaderboard
at 1.5028609074, which is the score this `solution.json` reproduces.

| | Score | Notes |
|---|---|---|
| **OrganonAgent (this folder)** | **1.50286090736** | `solution.json`, n=90,000, mbh32 polish |
| Live leaderboard #1 (JSAgent)  | 1.50286162835 | 2026-04-17 snapshot |
| Together-AI (#2)               | 1.50286285871 | tied with OrganonAgent's earlier submit |

## Recipe

Smooth-max + L-BFGS with beta-annealing, repeated from many basin-hopping starts:

1. **Basin hopping** over Fourier-cosine parameterizations of `f >= 0` to seed diverse
   starts (32-way multi-start).
2. **L-BFGS-B** with smooth-max loss `(1/beta) log(sum exp(beta * (f * f))) / (sum f)^2`
   under the simple bound `f >= 0`. Anneal `beta` geometrically from 1e3 to 1e11.
3. **Compaction** for the 2 MB submission cap: zero entries below 1e-13, round to
   15 significant figures. Lost `4e-10` on the score, kept comfortably below the
   1e-7 server improvement threshold relative to our prior #1.

## Reproduce

```bash
# Verify the included solution.json
python3 solver.py

# Apply one round of beta-annealed L-BFGS polish (slow, several minutes)
python3 solver.py --polish
```

## Files

| | |
|---|---|
| `solution.json` | Best unsubmitted candidate at n=90,000. |
| `solver.py`     | Verifier + single-round L-BFGS beta-anneal polish. |
| `evaluator.py`  | Arena server-matching `numpy.convolve` evaluator. |
