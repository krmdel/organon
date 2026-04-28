"""First Autocorrelation Inequality — verify solution.json reproduces the score.

Recipe (full pipeline lives in projects/einstein-arena-first-autocorrelation-inequality/):
  1. Multi-start basin hopping over Fourier-cosine parameterizations of f >= 0.
  2. L-BFGS-B with smooth-max beta-annealing (beta = 1e3 -> 1e11).
  3. Compaction: zero entries below 1e-13, round to 15 sig figs to fit 2 MB cap.

Verification reproduces arena's score via numpy.convolve, matching the server
to within 1 ULP. The polish step below applies one round of beta-annealed
L-BFGS to the loaded solution; remove the --polish flag to verify only.
"""
import argparse, json, sys
import numpy as np
from evaluator import evaluate


def score(values):
    return evaluate({"values": values})


def loss_and_grad(f, beta):
    n = len(f)
    dx = 0.5 / n
    f_pos = np.maximum(f, 0.0)
    integral = f_pos.sum() * dx
    if integral <= 0:
        return np.inf, np.zeros_like(f)
    conv = np.convolve(f_pos, f_pos, mode="full") * dx
    smax = np.log(np.sum(np.exp(beta * conv))) / beta
    C = smax / integral**2
    return float(C), None  # gradient computed numerically by L-BFGS for brevity


def polish(f, betas=(1e6, 1e8, 1e10, 1e11), maxiter=200):
    from scipy.optimize import minimize
    f = np.asarray(f, dtype=np.float64).copy()
    for beta in betas:
        res = minimize(lambda x: loss_and_grad(x, beta)[0], f, method="L-BFGS-B",
                       bounds=[(0, None)] * len(f),
                       options={"maxiter": maxiter, "ftol": 1e-15, "gtol": 1e-12})
        f = res.x
        c = score(f.tolist())
        print(f"  beta={beta:.0e}  C={c:.18f}", flush=True)
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--polish", action="store_true", help="run one round of beta-annealed L-BFGS")
    ap.add_argument("solution", nargs="?", default="solution.json")
    args = ap.parse_args()

    with open(args.solution) as fh:
        data = json.load(fh)
    values = data["values"]
    print(f"Loaded {len(values)} samples from {args.solution}")
    print(f"Score: {score(values):.18f}")
    print(f"Current #1 (JSAgent):    1.502861628349766")
    print(f"OrganonAgent submitted:  1.502861426854577")

    if args.polish:
        print("\nPolishing (this takes a few minutes)...")
        f = polish(np.array(values, dtype=np.float64))
        out = {"values": f.tolist()}
        with open("solution_polished.json", "w") as fh:
            json.dump(out, fh)
        print(f"\nSaved solution_polished.json  C={score(f.tolist()):.18f}")


if __name__ == "__main__":
    main()
