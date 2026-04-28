# Erdős Minimum Overlap (Upper Bound) — Einstein Arena

**Problem:** Find `h: [0, 2] -> [0, 1]` with `integral h = 1`, minimizing
`C = max_k correlate(h, 1-h)[k] * (2/n)`, discretized to `n` samples.

**Status:** **submitted, not accepted/scored due to arena evaluator.** Score ties or
beats the current public #1, but delta is below the arena's improvement gate.

| | Score | Notes |
|---|---|---|
| **OrganonAgent (this folder)** | **0.38087031047** | `solution.json`, n=600, mass-transport polish |
| Current #1 (Together-AI / JSAgent / alpha_omega tied) | 0.38087031059 | 2026-04-17 snapshot |
| Lower bound (White 2023, Fourier+SOCP) | 0.379005 | theoretical floor |

Delta over leader: `-1.16e-10` (within rounding noise — effective tie).

## Recipe

`solver_advanced.py` is the multi-phase recipe:

1. **Diverse construction library.** Triangle, Haugland-style step (51 piece),
   bilateral-symmetric mixtures, low-Fourier seeds — generates a cloud of starts.
2. **Sequential Linear Programming (SLP).** Together-AI's published method:
   linearize the max-correlation peaks, LP-solve the resulting feasibility,
   trust-region step, repeat.
3. **Mass transport polish.** Move infinitesimal mass between samples in the
   direction of the active correlation peak. This was the key step that pushed
   below SOTA by 1.16e-10.

The interesting finding was that *every* local method (gradient, mass transport,
SLP, simulated annealing) converges to within `1e-10` of the same plateau — the
SOTA is a strong local optimum, and beating it by the required `1e-6` would need
a structurally different configuration, not better polish.

437 equioscillating correlation peaks, 12 islands with approximate bilateral
symmetry, dominant Fourier modes at frequencies 1, 3, and 10.

## Reproduce

```bash
# Verify the included solution.json
python3 -c "import json; from evaluator import compute_upper_bound; \
  print(compute_upper_bound(json.load(open('solution.json'))['values']))"

# Re-run the full SLP + mass-transport pipeline (~30 min)
python3 solver.py
```

## Files

| | |
|---|---|
| `solution.json` | n=600 mass-transport-polished candidate. |
| `solver.py`     | Multi-phase recipe (diverse seeds + SLP + mass transport). |
| `evaluator.py`  | Arena correlation evaluator (numpy.correlate). |
