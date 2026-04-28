"""Hexagon Packing -- verify solution.json reproduces the locally-verified score.

Recipe (full pipeline lives in projects/einstein-arena-hexagon-packing/):
  Pack 12 unit hexagons inside a single outer hexagon, minimize outer side length.
  Standing config (3.9416523, 4-way tied #1) is the Friedman/Schellhorn-style
  arrangement reached by:
    1. SLSQP over (cx, cy, angle) of each inner hex with non-overlap and
       containment constraints (SAT-axis projections).
    2. Soft-mode descent: identify zero-eigenvalues of the constraint Hessian,
       move along soft modes to escape ridge optima.
    3. Aggressive polish at alpha-step shrinking to break through 1e-9 ridge.

  Arena minImprovement = 1e-4. Best-effort polish stalls at delta ~ 1e-8
  below tied #1 -- basin is locked, escape requires a different topology.
"""
import json, sys
from evaluator import evaluate


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "solution.json"
    with open(path) as fh:
        data = json.load(fh)

    print(f"file:              {path}")
    print(f"# inner hexagons:  {len(data['hexagons'])}")
    print(f"outer side length: {data['outer_side_length']:.13f}")
    print(f"outer center:      {tuple(data['outer_center'])}")
    print(f"outer angle deg:   {data['outer_angle_deg']:.6f}")

    score = evaluate(data)
    print(f"arena score:       {score:.10f}")
    print()
    print(f"Current #1 (4-way tie at):   3.9416523")
    print(f"OrganonAgent (this):         {score:.7f}")
    print(f"Delta:                       {score - 3.9416523:+.3e}")
    print(f"Arena minImprovement gate:   1e-4")


if __name__ == "__main__":
    main()
