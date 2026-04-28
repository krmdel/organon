# Second Autocorrelation Inequality — Einstein Arena

**Problem:** Same family as C1 but on the unit interval. Minimize `C(f) = max(f * f) / (integral f)^2`
for non-negative `f: [0, 1] -> R+`, discretized to `n` samples. Arena evaluates via
`numpy.convolve` over the full support.

**Status:** **submitted, not accepted/scored due to arena evaluator.** Beats current #1
by `+8.7e-11` — well below the arena's `1e-4` minImprovement gate (450,000x below). The
candidate is preserved here for the day a deeper basin opens.

| | Score | Notes |
|---|---|---|
| **OrganonAgent (this folder)** | **0.96264331885** | `solution.json`, n=400,000, compacted |
| Current #1 (ClaudeExplorer)    | 0.96264331876 | 2026-04-24 snapshot |
| JSAgent / alpha_omega          | 0.96221353659 | tied at 1e-4 below our delta |

## Recipe

Same smooth-max + L-BFGS β-anneal as C1, longer runs and a higher resolution:

1. **Warm-start** from prior leader's discretization, upsample to n=400,000 with
   linear interpolation.
2. **Long-run L-BFGS-B** with `beta` geometrically annealed from `1e3` to `1e12` over
   ~4 hours wall clock. Smooth-max loss with positivity bound `f >= 0`.
3. **Tri-verify**: `numpy.convolve` vs `scipy.fft.fftconvolve` vs `scipy.signal.oaconvolve`
   agree within `1e-15` — confirms the score is not a numerical ghost.
4. **Compaction** to 1.7 MB: zero below 1e-13, 15 sig figs.

The "1e-4 calibrated ceiling" finding here was generalized into a project-wide rule:
on medium-difficulty arena problems, run a 200s Dinkelbach polish first; if delta ≤ 1e-8
the basin is locked and no further compute opens the gate.

## Reproduce

```bash
# Verify (loads 400k samples, runs three convolution paths)
python3 solver.py
```

## Files

| | |
|---|---|
| `solution.json` | Compacted n=400,000 candidate (1.7 MB). |
| `solver.py`     | Verifier with tri-verify (np / fft / oaconv agreement). |
| `evaluator.py`  | Arena server-matching evaluator. |
