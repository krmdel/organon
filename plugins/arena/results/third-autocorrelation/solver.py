"""Third Autocorrelation Inequality — verify solution.json reproduces the score.

Recipe (full pipeline lives in projects/einstein-arena-third-autocorrelation/):
  Five rounds of recursive basin-escape, each round:
    1. Apply 1% relative Gaussian noise to round-N's best (vary seeds).
    2. Run 15-stage L-BFGS beta-cascade: beta = 1e3 -> 1e11 (~20 min/run).
    3. Polish at beta in {1e11, 1e12, 3e12}.
    4. Verify via numpy.convolve (server-matching).
  Per-round delta decays roughly geometrically; 5 rounds reach 2.17x the
  arena's 1e-4 threshold over JSAgent #1.

Diff vs first-autocorrelation: f^3 (cubic autoconvolution) instead of f^2,
so the loss is max(f * f * f) / (sum f)^3 in continuous form. Same beta-anneal
recipe, deeper basins.

This script runs the verifier only; the basin-escape recipe is documented but
not bundled (5 rounds + 6 seeds each takes ~12 hours wall clock).
"""
import json, sys, numpy as np
from evaluator import evaluate


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "solution.json"
    with open(path) as fh:
        data = json.load(fh)
    values = data["values"]
    n = len(values)
    f = np.array(values, dtype=np.float64)

    arena_C = evaluate({"values": values})
    dx = 1.0 / n
    integral = f.sum() * dx
    triple = np.convolve(np.convolve(f, f, mode="full") * dx, f, mode="full") * dx
    c_np = float(triple.max() / integral**3)

    print(f"file:              {path}")
    print(f"n:                 {n}")
    print(f"nonzeros:          {int(np.sum(np.abs(f) > 0))}")
    print(f"arena evaluator:   {arena_C:.18f}")
    print(f"numpy.convolve^3:  {c_np:.18f}")
    print()
    print(f"Current #1 (JSAgent):  1.4525211550468837")
    print(f"OrganonAgent (this):   {arena_C:.16f}")
    print(f"Delta:                 {arena_C - 1.4525211550468837:+.3e}")
    print(f"Arena threshold:       1e-4")
    print(f"Multiplier:            {abs(arena_C - 1.4525211550468837) / 1e-4:.2f}x")


if __name__ == "__main__":
    main()
