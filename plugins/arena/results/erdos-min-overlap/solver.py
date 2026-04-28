#!/usr/bin/env python3
"""
Advanced solver for Erdos Minimum Overlap.

Strategy: Multi-scale + structured construction + SLP refinement.

Phase 1: Small-n global search (n=50-200) with DE/basin-hopping
Phase 2: Upsample best small-n solutions to n=600
Phase 3: SLP refinement at n=600
Phase 4: Exact sum-preserving mass transport polish

Key insight from research:
- Together-AI used SLP from TTT-Discover -> converged to same optimum
- AlphaEvolve used n=95 and got 0.38092 (close!)
- The SOTA appears to be a LOCAL optimum, not global
- White's lower bound 0.379005 leaves room for 0.00187 improvement
- The problem is a QCQP; need global search to escape basin
"""

import json
import numpy as np
from scipy.optimize import (minimize, differential_evolution,
                             dual_annealing, linprog, shgo, direct)
from scipy.signal import fftconvolve
import time
import sys

# Load best solutions
with open("best_solutions.json") as f:
    sols = json.load(f)

h_sota = np.array(sols[0]["data"]["values"], dtype=np.float64)
SOTA_SCORE = 0.3808703105862199


def evaluate(h):
    """Official evaluator (exact copy of server logic)."""
    h = np.array(h, dtype=np.float64)
    n = len(h)
    if np.isnan(h).any():
        return float('inf')
    if np.any(h < 0) or np.any(h > 1):
        return float('inf')
    target = n / 2.0
    s = float(np.sum(h))
    if s != target:
        if s == 0:
            return float('inf')
        h = h * (target / s)
    if np.any(h < 0) or np.any(h > 1):
        return float('inf')
    corr = np.correlate(h, 1 - h, mode='full')
    return float(np.max(corr)) / n * 2


def evaluate_fast(h):
    """FFT-based evaluation (faster for large n)."""
    n = len(h)
    g = 1 - h
    # Zero-pad for linear (not circular) correlation
    N = 2 * n - 1
    H = np.fft.rfft(h, N)
    G = np.fft.rfft(g[::-1], N)
    corr = np.fft.irfft(H * G, N)
    return float(np.max(corr)) * 2.0 / n


# ============================================================
# CONSTRUCTION METHODS
# ============================================================

def haugland_construction(n, breakpoints, values):
    """Haugland-style piecewise constant construction.

    breakpoints: positions in [0, 2] where function changes
    values: function value in each interval

    This is how Haugland (2016) achieved 0.380926 with 51 pieces.
    """
    h = np.zeros(n)
    x = np.linspace(0, 2, n, endpoint=False) + 1.0 / n  # bin centers
    bp = np.array([0] + list(breakpoints) + [2])
    vals = np.array(values)

    for i in range(len(vals)):
        mask = (x >= bp[i]) & (x < bp[i + 1])
        h[mask] = vals[i]

    # Normalize sum
    target = n / 2.0
    if np.sum(h) > 0:
        h *= target / np.sum(h)
    h = np.clip(h, 0, 1)
    return h


def parametric_construction(params, n):
    """Flexible parametric construction.

    params encodes:
    - n_pieces: number of piecewise segments
    - For each segment: (start_frac, end_frac, value)

    Or more simply: a set of "island" parameters.
    """
    n_islands = len(params) // 3
    h = np.zeros(n)
    x = np.arange(n) / n * 2  # [0, 2)

    for i in range(n_islands):
        center = params[3 * i] * 2  # center in [0, 2]
        width = params[3 * i + 1] * 0.5  # half-width
        height = params[3 * i + 2]  # value [0, 1]

        # Smooth island (raised cosine)
        mask = np.abs(x - center) < width
        if width > 0:
            t = (x[mask] - center) / width
            h[mask] += height * 0.5 * (1 + np.cos(np.pi * t))

    h = np.clip(h, 0, 1)
    # Normalize
    target = n / 2.0
    if np.sum(h) > 0:
        h *= target / np.sum(h)
    h = np.clip(h, 0, 1)
    return h


def island_objective(params, n):
    """Objective for island-parametric search."""
    try:
        h = parametric_construction(params, n)
        return evaluate(h)
    except:
        return 1.0


# ============================================================
# PHASE 1: SMALL-N GLOBAL SEARCH
# ============================================================

def global_search_small_n(n, max_time=120):
    """Global search at small n using differential evolution."""
    print(f"\n{'='*60}")
    print(f"Phase 1: Global Search at n={n}")
    print(f"{'='*60}")

    start = time.time()

    def obj(h):
        h = np.array(h)
        h = np.clip(h, 0, 1)
        target = n / 2.0
        s = np.sum(h)
        if s > 0:
            h = h * (target / s)
        h = np.clip(h, 0, 1)
        return evaluate(h)

    bounds = [(0, 1)] * n

    # Seed population with known good constructions
    x0_list = []

    # 1. Interpolated SOTA
    x_orig = np.linspace(0, 2, len(h_sota), endpoint=False)
    x_new = np.linspace(0, 2, n, endpoint=False)
    h_interp = np.interp(x_new, x_orig, h_sota)
    h_interp = np.clip(h_interp, 0, 1)
    h_interp *= (n / 2.0) / np.sum(h_interp)
    h_interp = np.clip(h_interp, 0, 1)
    x0_list.append(h_interp)

    # 2. Symmetric version
    h_sym = (h_interp + h_interp[::-1]) / 2.0
    h_sym *= (n / 2.0) / np.sum(h_sym)
    h_sym = np.clip(h_sym, 0, 1)
    x0_list.append(h_sym)

    # 3. Parabolic
    x = np.linspace(0, 2, n, endpoint=False)
    h_para = 1 - (x - 1)**2
    h_para = np.clip(h_para, 0, 1)
    h_para *= (n / 2.0) / np.sum(h_para)
    h_para = np.clip(h_para, 0, 1)
    x0_list.append(h_para)

    # Also try different power-tent shapes
    for alpha in [0.5, 0.8, 1.0, 1.2, 1.5, 2.0, 3.0]:
        h_tent = np.maximum(0, 1 - np.abs(x - 1)**alpha)
        h_tent *= (n / 2.0) / np.sum(h_tent)
        h_tent = np.clip(h_tent, 0, 1)
        x0_list.append(h_tent)

    # Multi-start L-BFGS-B from various constructions
    best_score = float('inf')
    best_h = None

    for i, h0 in enumerate(x0_list):
        score0 = evaluate(h0)

        # Smooth objective for gradient optimization
        def smooth_obj(h_flat, temperature=50.0):
            h = np.array(h_flat)
            h = np.clip(h, 0, 1)
            n_loc = len(h)
            target = n_loc / 2.0
            s = np.sum(h)
            if s > 0:
                h = h * (target / s)
            h = np.clip(h, 0, 1)
            corr = np.correlate(h, 1 - h, mode='full')
            max_c = np.max(corr)
            # Log-sum-exp smoothing
            shifted = temperature * (corr - max_c)
            lse = max_c + np.log(np.sum(np.exp(shifted))) / temperature
            return lse * 2.0 / n_loc

        result = minimize(smooth_obj, h0, method='L-BFGS-B',
                         bounds=[(0, 1)] * n,
                         options={'maxiter': 3000, 'ftol': 1e-18})

        h_opt = np.array(result.x)
        h_opt = np.clip(h_opt, 0, 1)
        h_opt *= (n / 2.0) / np.sum(h_opt)
        h_opt = np.clip(h_opt, 0, 1)
        score = evaluate(h_opt)

        if score < best_score:
            best_score = score
            best_h = np.copy(h_opt)
            print(f"  Start {i}: {score0:.10f} -> {score:.10f} ({'*' if score < SOTA_SCORE else ' '})")
        elif i < 3:
            print(f"  Start {i}: {score0:.10f} -> {score:.10f}")

        if time.time() - start > max_time:
            break

    # Now try DE on the best
    print(f"\n  Running DE from best start (score={best_score:.10f})...")

    try:
        result_de = differential_evolution(
            obj, bounds, seed=42, maxiter=500, tol=1e-14,
            mutation=(0.5, 1.5), recombination=0.9,
            popsize=15, x0=best_h,
            maxfun=50000
        )
        h_de = np.array(result_de.x)
        h_de = np.clip(h_de, 0, 1)
        h_de *= (n / 2.0) / np.sum(h_de)
        h_de = np.clip(h_de, 0, 1)
        score_de = evaluate(h_de)
        print(f"  DE result: {score_de:.10f}")

        if score_de < best_score:
            best_score = score_de
            best_h = np.copy(h_de)
    except Exception as e:
        print(f"  DE failed: {e}")

    print(f"\n  Best at n={n}: {best_score:.16f}")
    return best_h, best_score


# ============================================================
# PHASE 2: UPSAMPLING
# ============================================================

def upsample_careful(h_small, target_n):
    """Carefully upsample h from small n to target_n."""
    n_small = len(h_small)
    x_small = np.linspace(0, 2, n_small, endpoint=False) + 1.0 / n_small
    x_target = np.linspace(0, 2, target_n, endpoint=False) + 1.0 / target_n

    # Cubic interpolation
    from scipy.interpolate import interp1d
    f = interp1d(x_small, h_small, kind='cubic', fill_value='extrapolate')
    h_target = f(x_target)

    # Enforce constraints
    h_target = np.clip(h_target, 0, 1)

    # Fix sum iteratively
    target_sum = target_n / 2.0
    for _ in range(100):
        h_target = np.clip(h_target, 0, 1)
        s = np.sum(h_target)
        if abs(s - target_sum) < 1e-12:
            break
        excess = s - target_sum
        free = (h_target > 1e-10) & (h_target < 1 - 1e-10)
        if np.sum(free) > 0:
            h_target[free] -= excess / np.sum(free)

    h_target = np.clip(h_target, 0, 1)
    return h_target


# ============================================================
# PHASE 3: SLP REFINEMENT
# ============================================================

def slp_refine(h_init, max_iter=100, trust_init=0.01, n_active=200, verbose=True):
    """SLP refinement with proper gradient computation."""
    h = np.copy(h_init)
    n = len(h)
    trust = trust_init
    best_score = evaluate(h)
    best_h = np.copy(h)

    if verbose:
        print(f"  SLP refine start: score={best_score:.16f}")

    for it in range(max_iter):
        corr = np.correlate(h, 1 - h, mode='full')
        max_corr = np.max(corr)

        # Top n_active constraints
        top_idx = np.argsort(corr)[-n_active:][::-1]

        # Build LP: minimize t s.t. C_k + grad_k.delta <= t
        n_vars = n + 1  # delta + t
        n_cons = len(top_idx)

        c_obj = np.zeros(n_vars)
        c_obj[-1] = 1.0

        A_ub = np.zeros((n_cons, n_vars))
        b_ub = np.zeros(n_cons)

        for ci, m_idx in enumerate(top_idx):
            k = m_idx - (n - 1)
            # Gradient of C_k w.r.t. h
            grad = np.zeros(n)
            for j in range(n):
                jk = j + k
                if 0 <= jk < n:
                    grad[j] += (1 - h[jk])
                jmk = j - k
                if 0 <= jmk < n:
                    grad[j] -= h[jmk]

            A_ub[ci, :n] = grad
            A_ub[ci, -1] = -1.0
            b_ub[ci] = -corr[m_idx]

        # Sum constraint: sum(delta) = 0
        A_eq = np.zeros((1, n_vars))
        A_eq[0, :n] = 1.0
        b_eq = np.array([0.0])

        # Bounds
        bounds = []
        for i in range(n):
            lb = max(-trust, -h[i])
            ub = min(trust, 1 - h[i])
            bounds.append((lb, ub))
        bounds.append((None, None))

        result = linprog(c_obj, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
                        bounds=bounds, method='highs')

        if not result.success:
            trust *= 0.5
            if trust < 1e-10:
                break
            continue

        delta = result.x[:n]
        h_new = h + delta
        h_new = np.clip(h_new, 0, 1)

        # Fix sum
        target = n / 2.0
        excess = np.sum(h_new) - target
        free = (h_new > 1e-10) & (h_new < 1 - 1e-10)
        if np.sum(free) > 0:
            h_new[free] -= excess / np.sum(free)
        h_new = np.clip(h_new, 0, 1)

        score = evaluate(h_new)
        if score < best_score - 1e-16:
            imp = best_score - score
            best_score = score
            best_h = np.copy(h_new)
            h = h_new
            trust = min(trust * 1.5, 0.05)
            if verbose and (it < 5 or it % 10 == 0):
                print(f"    iter {it}: score={score:.16f} (improved {imp:.2e})")
        else:
            trust *= 0.6
            if trust < 1e-10:
                break

    if verbose:
        print(f"  SLP refine end: score={best_score:.16f}")
    return best_h, best_score


# ============================================================
# PHASE 4: EXACT SUM MASS TRANSPORT POLISH
# ============================================================

def mass_transport_polish(h_init, n_rounds=100000, step=2**-32):
    """Dyadic exact-sum mass transport polish."""
    h = np.copy(h_init)
    n = len(h)

    # Quantize to dyadic grid
    h = np.round(h / step) * step
    target = n / 2.0
    excess = np.sum(h) - target
    n_adj = int(round(abs(excess) / step))

    if excess > 0:
        cands = np.where(h > step)[0]
        for i in range(min(n_adj, len(cands))):
            h[cands[i]] -= step
    elif excess < 0:
        cands = np.where(h < 1 - step)[0]
        for i in range(min(n_adj, len(cands))):
            h[cands[i]] += step

    best_score = evaluate(h)
    improved = 0

    for r in range(n_rounds):
        # 2-point mass transport
        i, j = np.random.randint(0, n, size=2)
        if i == j:
            continue

        if h[i] + step <= 1.0 and h[j] - step >= 0.0:
            h[i] += step
            h[j] -= step
            score = evaluate(h)
            if score < best_score:
                best_score = score
                improved += 1
            else:
                h[i] -= step
                h[j] += step

        if r % 50000 == 0 and r > 0:
            print(f"    mass transport round {r}: best={best_score:.16f}, improved={improved}")

    return h, best_score


# ============================================================
# MAIN PIPELINE
# ============================================================

def main():
    print("=" * 70)
    print("ADVANCED ERDOS MINIMUM OVERLAP SOLVER")
    print("=" * 70)
    print(f"SOTA: {SOTA_SCORE:.16f}")
    print(f"Target: < {SOTA_SCORE - 1e-6:.16f}")
    print(f"Lower bound (White 2023): 0.379005")
    print(f"Gap to close: {SOTA_SCORE - 0.379005:.6f}")

    best_overall_score = SOTA_SCORE
    best_overall_h = np.copy(h_sota)

    # Phase 1: Multi-scale global search
    print("\n\n" + "=" * 70)
    print("PHASE 1: MULTI-SCALE GLOBAL SEARCH")
    print("=" * 70)

    small_n_results = []
    for n in [50, 80, 95, 100, 128, 150, 200, 256, 300]:
        h_small, score_small = global_search_small_n(n, max_time=60)
        small_n_results.append((score_small, h_small, n))
        print(f"\n  => Best at n={n}: {score_small:.16f}")

    # Sort by score
    small_n_results.sort(key=lambda x: x[0])

    print("\n\nPhase 1 Results (sorted):")
    for score, h, n in small_n_results[:5]:
        print(f"  n={n}: {score:.16f}")

    # Phase 2: Upsample top candidates to n=600
    print("\n\n" + "=" * 70)
    print("PHASE 2: UPSAMPLE TO n=600")
    print("=" * 70)

    upsampled = []
    for score_small, h_small, n_small in small_n_results[:5]:
        h_600 = upsample_careful(h_small, 600)
        score_600 = evaluate(h_600)
        print(f"  n={n_small} (score={score_small:.10f}) -> n=600: {score_600:.16f}")
        upsampled.append((score_600, h_600))

        if score_600 < best_overall_score:
            best_overall_score = score_600
            best_overall_h = np.copy(h_600)
            print(f"    *** NEW BEST! ***")

    # Phase 3: SLP refinement on upsampled candidates + SOTA
    print("\n\n" + "=" * 70)
    print("PHASE 3: SLP REFINEMENT")
    print("=" * 70)

    candidates = [(SOTA_SCORE, np.copy(h_sota))] + upsampled[:5]

    for i, (score_init, h_init) in enumerate(candidates):
        print(f"\n  Candidate {i} (initial: {score_init:.16f}):")
        h_refined, score_refined = slp_refine(h_init, max_iter=150,
                                               trust_init=0.02, n_active=300)
        if score_refined < best_overall_score:
            best_overall_score = score_refined
            best_overall_h = np.copy(h_refined)
            print(f"    *** NEW OVERALL BEST: {score_refined:.16f} ***")

    # Phase 4: Mass transport polish
    print("\n\n" + "=" * 70)
    print("PHASE 4: MASS TRANSPORT POLISH")
    print("=" * 70)

    h_polished, score_polished = mass_transport_polish(
        best_overall_h, n_rounds=200000, step=2**-32)
    if score_polished < best_overall_score:
        best_overall_score = score_polished
        best_overall_h = np.copy(h_polished)

    # FINAL RESULTS
    print("\n\n" + "=" * 70)
    print("FINAL RESULTS")
    print("=" * 70)
    print(f"SOTA:           {SOTA_SCORE:.16f}")
    print(f"Our best:       {best_overall_score:.16f}")
    print(f"Improvement:    {SOTA_SCORE - best_overall_score:.6e}")

    if best_overall_score < SOTA_SCORE - 1e-6:
        print("\n*** BEATS THE LEADERBOARD BY > 1e-6! ***")
        print("Ready to submit!")
    elif best_overall_score < SOTA_SCORE:
        print(f"\nImproved but not enough (need 1e-6, got {SOTA_SCORE - best_overall_score:.6e})")
    else:
        print("\nNo improvement found. Need a fundamentally new approach.")

    # Save
    solution = {"values": best_overall_h.tolist()}
    with open("solution_advanced.json", "w") as f:
        json.dump(solution, f)
    print(f"Saved to solution_advanced.json")

    return best_overall_h, best_overall_score


if __name__ == "__main__":
    main()
