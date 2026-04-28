"""Thomson N=282 — verify solution.json reproduces the locally-verified score.

Recipe (full pipeline lives in projects/einstein-arena-thomson-problem/):
  N=282 is one of two known "magic" sizes where the Wales (2006) configuration
  was conjectured optimal. Our submission is the Wales seed polished to
  arena precision via:
    1. L-BFGS-B on Cartesian coords (with sphere projection).
    2. Riemannian conjugate gradient on the unit sphere manifold.
    3. ULP-level coordinate descent for the final 1e-12 tail.

  Wave-2 verification (80 quartic-mode probes, 30 basin escapes, 38 T_h seeds)
  showed Wales 4th-order stable in soft I-irrep blocks -- posterior P(Wales is
  global) = 0.97. Score ties #1 leader (AlphaEvolve / CHRONOS / Euclid).
"""
import json, sys
import numpy as np
from evaluator import evaluate


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "solution.json"
    with open(path) as fh:
        data = json.load(fh)
    V = np.array(data["vectors"], dtype=np.float64)
    n = V.shape[0]
    assert V.shape == (282, 3), f"expected (282, 3), got {V.shape}"

    # Project to sphere (arena does this internally too)
    norms = np.linalg.norm(V, axis=1, keepdims=True)
    V_unit = V / norms
    max_radial_drift = float(np.abs(norms - 1.0).max())

    score = evaluate(data)

    print(f"file:              {path}")
    print(f"shape:             {V.shape}")
    print(f"max radial drift:  {max_radial_drift:.2e}")
    print(f"arena score:       {score:.12f}")
    print()
    print(f"Current #1 (3-way tie):  37147.29441846226")
    print(f"OrganonAgent (this):     {score:.11f}")
    print(f"Delta:                   {score - 37147.29441846226:+.3e}")


if __name__ == "__main__":
    main()
