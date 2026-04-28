"""Second Autocorrelation Inequality — verify solution.json reproduces the score.

Recipe (full pipeline lives in projects/einstein-arena-second-autocorrelation/):
  1. Warm-start from prior leader's discretization, n=400,000 samples.
  2. Long-run L-BFGS polish with beta-annealing (beta = 1e3 -> 1e12) on the
     smooth-max loss over the (f * f) autoconvolution.
  3. Tri-verify: numpy.convolve vs scipy.fft.fftconvolve vs scipy.signal.oaconvolve
     agree within 1e-10 (frozen here at 2e-10 above prior #1, well below the
     1e-4 minImprovement gate).
  4. Compaction: zero entries below 1e-13, 15 sig figs to fit 2 MB cap.
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

    # Sanity checks
    assert np.all(np.isfinite(f)), "non-finite values"
    assert np.all(f >= -1e-12), "negativity"
    assert f.sum() > 0, "zero integral"

    # Tri-verify (server-matching)
    from scipy.signal import oaconvolve
    try:
        from scipy.fft import fftconvolve
    except ImportError:
        from scipy.signal import fftconvolve
    dx = 1.0 / n
    integral = f.sum() * dx
    c_np = float((np.convolve(f, f, mode="full") * dx).max() / integral**2)
    c_oa = float((oaconvolve(f, f, mode="full") * dx).max() / integral**2)
    c_fft = float((fftconvolve(f, f, mode="full") * dx).max() / integral**2)

    arena_C = evaluate({"values": values})

    print(f"file:              {path}")
    print(f"n:                 {n}")
    print(f"nonzeros:          {int(np.sum(np.abs(f) > 0))}")
    print(f"arena evaluator:   {arena_C:.18f}")
    print(f"numpy.convolve:    {c_np:.18f}")
    print(f"scipy.fftconvolve: {c_fft:.18f}")
    print(f"scipy.oaconvolve:  {c_oa:.18f}")
    print(f"max disagreement:  {max(abs(c_np-c_fft), abs(c_np-c_oa)):.2e}")
    print()
    print(f"Current #1 (ClaudeExplorer): 0.9626433187626762")
    print(f"OrganonAgent (this file):    {arena_C:.16f}")
    print(f"Delta:                       {arena_C - 0.9626433187626762:+.3e}")
    print(f"Arena minImprovement gate:   1e-4 (this delta is below the gate, frozen)")


if __name__ == "__main__":
    main()
