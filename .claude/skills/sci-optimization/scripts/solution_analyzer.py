#!/usr/bin/env python3
"""Solution comparison and analysis tools.

Compare solutions, find patterns, decompose scores by key range.

Usage:
    from solution_analyzer import compare_solutions, decompose_score
"""

import json
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np


def load_solution(path: str) -> Dict[str, float]:
    """Load a solution from JSON file."""
    with open(path) as f:
        data = json.load(f)
    return data.get("partial_function", data)


def decompose_score(
    solution: Dict[str, float],
    ranges: Optional[List[Tuple[int, int]]] = None,
) -> Dict[str, float]:
    """Decompose score contribution by key range.

    Score = -sum(f(k) * log(k) / k) for the PNT problem.

    Args:
        solution: Dict mapping string keys to float values.
        ranges: List of (lo, hi) tuples. Default: [(2,10), (10,100), (100,1000), (1000,inf)].

    Returns:
        Dict with range labels as keys and score contributions as values.
    """
    if ranges is None:
        ranges = [(2, 10), (10, 100), (100, 1000), (1000, 10000), (10000, 100000)]

    result = {}
    total = 0.0

    for lo, hi in ranges:
        contrib = 0.0
        count = 0
        for k_str, v in solution.items():
            k = int(k_str)
            if lo <= k < hi:
                contrib += -v * np.log(k) / k
                count += 1
        label = f"[{lo}, {hi})"
        result[label] = {"score": contrib, "n_keys": count}
        total += contrib

    result["total"] = {"score": total, "n_keys": len(solution)}
    return result


def compare_solutions(
    sol_a: Dict[str, float],
    sol_b: Dict[str, float],
    label_a: str = "A",
    label_b: str = "B",
) -> Dict:
    """Compare two solutions in detail."""
    keys_a = set(int(k) for k in sol_a.keys())
    keys_b = set(int(k) for k in sol_b.keys())

    shared = keys_a & keys_b
    only_a = keys_a - keys_b
    only_b = keys_b - keys_a

    # Value differences on shared keys
    value_diffs = []
    for k in sorted(shared):
        va = float(sol_a[str(k)])
        vb = float(sol_b[str(k)])
        if abs(va - vb) > 1e-15:
            value_diffs.append({
                "key": k,
                f"{label_a}": va,
                f"{label_b}": vb,
                "diff": va - vb,
            })

    # Score decomposition
    decomp_a = decompose_score(sol_a)
    decomp_b = decompose_score(sol_b)

    return {
        "key_overlap": {
            "shared": len(shared),
            "only_" + label_a: len(only_a),
            "only_" + label_b: len(only_b),
            "range_only_" + label_a: [min(only_a), max(only_a)] if only_a else [],
            "range_only_" + label_b: [min(only_b), max(only_b)] if only_b else [],
        },
        "key_ranges": {
            label_a: [min(keys_a), max(keys_a)] if keys_a else [],
            label_b: [min(keys_b), max(keys_b)] if keys_b else [],
        },
        "n_keys": {label_a: len(keys_a), label_b: len(keys_b)},
        "value_diffs_count": len(value_diffs),
        "top_value_diffs": value_diffs[:20],
        "decomposition": {label_a: decomp_a, label_b: decomp_b},
    }


def solution_stats(solution: Dict[str, float]) -> Dict:
    """Basic statistics for a solution."""
    keys = sorted(int(k) for k in solution.keys())
    vals = np.array([float(solution[str(k)]) for k in keys])

    return {
        "n_keys": len(keys),
        "key_range": [keys[0], keys[-1]] if keys else [],
        "val_range": [float(vals.min()), float(vals.max())],
        "val_mean": float(vals.mean()),
        "val_std": float(vals.std()),
        "val_positive": int(np.sum(vals > 0)),
        "val_negative": int(np.sum(vals < 0)),
        "val_zero": int(np.sum(np.abs(vals) < 1e-15)),
        "score_estimate": float(-np.sum(vals * np.log(np.array(keys, dtype=float)) /
                                         np.array(keys, dtype=float))),
    }


def find_scaling_factor(
    sol_a: Dict[str, float],
    sol_b: Dict[str, float],
) -> Optional[float]:
    """Check if sol_b = sol_a * scale for some constant scale.

    Returns the scale factor if consistent, None otherwise.
    """
    shared_keys = set(sol_a.keys()) & set(sol_b.keys())
    if not shared_keys:
        return None

    ratios = []
    for k in shared_keys:
        va = float(sol_a[k])
        vb = float(sol_b[k])
        if abs(va) > 1e-15:
            ratios.append(vb / va)

    if not ratios:
        return None

    ratios = np.array(ratios)
    if np.std(ratios) < 1e-10:
        return float(np.mean(ratios))
    return None
