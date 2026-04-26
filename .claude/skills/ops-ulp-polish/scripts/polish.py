#!/usr/bin/env python3
"""Generic ULP coordinate-descent polisher for float64 optimization problems.

Usage:
  polish.py --config <warm_start.npy>
            --evaluator <python.module:function>
            [--max-ulps 4] [--max-sweeps 20] [--budget-sec 3600]
            [--out <out.npy>]

The evaluator must be callable as `eval_fn(V: np.ndarray) -> float`.
Lower scores are better. Optimization stops when score == 0 or no improving
ulp move is found in a complete sweep.

Key ideas:
  - Priority order rows/variables by `badness` (per-row loss contribution).
  - For each coordinate, try ±1, ±2, ±4, ..., ±max_ulps ulps.
  - Accept any strict improvement.
  - Repeat sweeps until converged or budget exhausted.
"""
import argparse
import importlib
import json
import sys
import time
from pathlib import Path

import numpy as np


def next_ulp(x: float, k: int) -> float:
    """Move x by k ulps (signed)."""
    y = x
    if k > 0:
        for _ in range(k):
            y = float(np.nextafter(y, np.inf))
    elif k < 0:
        for _ in range(-k):
            y = float(np.nextafter(y, -np.inf))
    return y


def load_config(path: str) -> np.ndarray:
    if path.endswith(".npy"):
        return np.load(path).astype(np.float64)
    if path.endswith(".json"):
        with open(path) as f:
            data = json.load(f)
        if "vectors" in data:
            return np.array(data["vectors"], dtype=np.float64)
        if "data" in data and "vectors" in data["data"]:
            return np.array(data["data"]["vectors"], dtype=np.float64)
        raise ValueError(f"cannot find 'vectors' in {path}")
    raise ValueError(f"unsupported format: {path}")


def resolve_evaluator(spec: str):
    mod_path, fn = spec.rsplit(":", 1)
    mod = importlib.import_module(mod_path)
    return getattr(mod, fn)


def row_badness_default(V: np.ndarray, i: int, target_sq: float) -> float:
    """Default badness: sum of (sqrt(target_sq) - dist(V[i], V[j])) over j with sq_dist<target.
    This is a generic hinge-sum contribution of row i."""
    d2 = ((V - V[i]) ** 2).sum(axis=1)
    d2[i] = np.inf
    mask = d2 < target_sq
    if not mask.any():
        return 0.0
    return float((np.sqrt(target_sq) - np.sqrt(d2[mask])).sum())


def polish(V: np.ndarray, eval_fn, *, max_ulps: int = 4, max_sweeps: int = 20,
           budget_sec: float = 3600.0, freeze_indices=None, verbose: bool = True,
           target_sq: float | None = None) -> tuple[np.ndarray, float]:
    """Return (best_V, best_score) after polishing."""
    V = V.copy()
    score = float(eval_fn(V))
    n, d = V.shape
    if target_sq is None:
        target_sq = float((V ** 2).sum(axis=1).max())
    if verbose:
        print(f"[ulp-polish] init score={score:.6e}  target_sq={target_sq:.6f}")
    if score == 0.0:
        return V, score

    t0 = time.time()
    best_score = score

    for sweep in range(max_sweeps):
        if time.time() - t0 > budget_sec:
            if verbose: print("[ulp-polish] budget exhausted")
            break

        badness = np.array([row_badness_default(V, i, target_sq) for i in range(n)])
        order = np.argsort(-badness)
        sweep_accepts = 0

        for rank, i in enumerate(order):
            if freeze_indices is not None and i in freeze_indices:
                continue
            if time.time() - t0 > budget_sec:
                break
            if badness[i] == 0 and rank > 30:
                continue

            for k in range(d):
                cur = float(V[i, k])
                best_step = 0
                best_impr = 0.0
                best_new = cur
                for s in range(1, max_ulps + 1):
                    for sign in (+1, -1):
                        trial = next_ulp(cur, s * sign)
                        V[i, k] = trial
                        new_score = float(eval_fn(V))
                        impr = score - new_score
                        if impr > best_impr + 1e-25:
                            best_impr = impr; best_step = s * sign; best_new = trial
                if best_impr > 1e-25:
                    V[i, k] = best_new
                    score -= best_impr
                    sweep_accepts += 1
                else:
                    V[i, k] = cur

        if verbose:
            dt = time.time() - t0
            print(f"[ulp-polish] sweep {sweep+1}: score={score:.6e} "
                  f"(Δ={best_score-score:.3e})  accepts={sweep_accepts}  dt={dt:.0f}s",
                  flush=True)
        if score < best_score:
            best_score = score
        if score == 0.0:
            if verbose: print("[ulp-polish] reached 0")
            break
        if sweep_accepts == 0:
            if verbose: print("[ulp-polish] converged (no improving move)")
            break

    return V, score


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="warm-start .npy or .json")
    ap.add_argument("--evaluator", required=True,
                    help="module.path:function — must accept V ndarray and return float")
    ap.add_argument("--max-ulps", type=int, default=4)
    ap.add_argument("--max-sweeps", type=int, default=20)
    ap.add_argument("--budget-sec", type=float, default=3600.0)
    ap.add_argument("--out", type=str, default=None)
    args = ap.parse_args()

    V = load_config(args.config)
    eval_fn = resolve_evaluator(args.evaluator)

    V_out, final = polish(V, eval_fn,
                          max_ulps=args.max_ulps,
                          max_sweeps=args.max_sweeps,
                          budget_sec=args.budget_sec)
    print(f"final score = {final:.6e}")
    out = Path(args.out or args.config).with_suffix(".polished.npy")
    np.save(out, V_out)
    print(f"saved {out}")


if __name__ == "__main__":
    main()
