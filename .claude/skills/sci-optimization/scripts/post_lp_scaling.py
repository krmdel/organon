#!/usr/bin/env python3
"""Post-LP scaling to exploit evaluator tolerance.

After solving the LP, the solution often has slack in the constraint.
Scaling all values by a factor slightly > 1 can improve the objective
without violating constraints.

Usage:
    from post_lp_scaling import optimal_scale, non_uniform_scale
    scale, score = optimal_scale(solution, evaluator_fn)
"""

from typing import Callable, Dict, Tuple

import numpy as np


def optimal_scale(
    solution: Dict[str, float],
    evaluator_fn: Callable,
    lo: float = 1.0,
    hi: float = 1.001,
    n_iters: int = 30,
    verbose: bool = True,
) -> Tuple[float, float, Dict[str, float]]:
    """Binary search for maximum scale factor that passes evaluator.

    Args:
        solution: Dict mapping string keys to float values.
        evaluator_fn: callable({"partial_function": solution}) -> float.
        lo: Lower bound for scale factor.
        hi: Upper bound for scale factor.
        n_iters: Number of binary search iterations.

    Returns:
        (best_scale, best_score, scaled_solution).
    """
    base_score = evaluator_fn({"partial_function": solution})
    best_score = base_score
    best_scale = 1.0

    for i in range(n_iters):
        mid = (lo + hi) / 2
        scaled = {k: v * mid for k, v in solution.items()}
        score = evaluator_fn({"partial_function": scaled})

        if score > float("-inf"):
            if score > best_score:
                best_score = score
                best_scale = mid
            lo = mid
        else:
            hi = mid

    if verbose:
        gain = best_score - base_score
        print(f"  Scale: {best_scale:.10f}, score: {best_score:.15f} "
              f"(+{gain:.2e})")

    best_solution = {k: v * best_scale for k, v in solution.items()}
    return best_scale, best_score, best_solution


def non_uniform_scale(
    solution: Dict[str, float],
    evaluator_fn: Callable,
    groups: int = 10,
    n_iters: int = 20,
    verbose: bool = True,
) -> Tuple[float, Dict[str, float]]:
    """Per-group scaling optimization.

    Divides keys into groups by magnitude and optimizes scale per group.
    More granular than uniform scaling.

    Args:
        solution: Dict mapping string keys to float values.
        evaluator_fn: callable({"partial_function": solution}) -> float.
        groups: Number of key groups to scale independently.
        n_iters: Binary search iterations per group.

    Returns:
        (best_score, scaled_solution).
    """
    keys = sorted(solution.keys(), key=lambda k: int(k))
    n = len(keys)
    group_size = max(1, n // groups)

    current = dict(solution)
    current_score = evaluator_fn({"partial_function": current})

    for g in range(groups):
        start = g * group_size
        end = min(start + group_size, n) if g < groups - 1 else n
        group_keys = keys[start:end]

        lo, hi = 1.0, 1.002
        best_group_scale = 1.0
        best_group_score = current_score

        for _ in range(n_iters):
            mid = (lo + hi) / 2
            test = dict(current)
            for k in group_keys:
                test[k] = current[k] * mid

            score = evaluator_fn({"partial_function": test})
            if score > float("-inf"):
                if score > best_group_score:
                    best_group_score = score
                    best_group_scale = mid
                lo = mid
            else:
                hi = mid

        if best_group_scale > 1.0:
            for k in group_keys:
                current[k] = current[k] * best_group_scale
            current_score = best_group_score

    if verbose:
        base_score = evaluator_fn({"partial_function": solution})
        print(f"  Non-uniform scale: {current_score:.15f} "
              f"(+{current_score - base_score:.2e})")

    return current_score, current
