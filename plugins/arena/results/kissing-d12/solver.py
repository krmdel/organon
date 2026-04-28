"""Kissing-d12 — verify solution.npy reproduces the locally-verified score.

Construction (full notes in projects/einstein-arena-kissing-d12/):
  Arena target: 841 unit vectors in R^12 minimizing pairwise overlap.
  Score 0 would be a world record (beats the 840-vector D12 lattice from 1971).
  We submit V[226] duplicated for the 841st vector -- one duplicate pair
  contributes the score of 2.0; all other 840 vectors are the standard D12
  shell with cosine == 0.5 pairs (kissing config).

  Integer-coordinate ILP certificates rule out any rigorous 841-config under
  cosine <= 0.5 that beats 2.0; this solution is a tied-floor submission.
"""
import json, sys
from pathlib import Path
import numpy as np
from evaluator import evaluate


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("solution.npy")
    V = np.load(path)
    assert V.shape == (841, 12), f"expected (841, 12), got {V.shape}"
    V = V / np.linalg.norm(V, axis=1, keepdims=True)
    score = evaluate({"vectors": V.tolist()})

    C = V @ V.T
    np.fill_diagonal(C, -np.inf)
    print(f"file:              {path}")
    print(f"shape:             {V.shape}")
    print(f"max cosine:        {C.max():.10f}")
    print(f"# pairs cos>0.5:   {int((C > 0.5).sum()) // 2}")
    print(f"arena score:       {score:.12f}  (lower is better; 0 = world record)")
    print()
    print("Notes:")
    print("  Score 2.0 = one duplicate pair, all other 840 distinct cos == 0.5 pairs.")
    print("  Integer 841-config under strict cos <= 0.5 proven impossible (ILP cert).")


if __name__ == "__main__":
    main()
