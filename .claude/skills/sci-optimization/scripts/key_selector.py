#!/usr/bin/env python3
"""Intelligent variable selection strategies for optimization.

Multiple approaches for selecting the best subset of variables
from an overcomplete set.

Usage:
    from key_selector import select_keys_by_lp_importance, select_keys_extended_range
"""

from typing import Callable, List, Tuple

import numpy as np


def select_keys_by_lp_importance(
    all_keys: np.ndarray,
    lp_values: np.ndarray,
    budget: int,
) -> np.ndarray:
    """Select top `budget` keys by |LP value|.

    Simple and effective: solve overcomplete LP, keep keys with
    largest absolute values.
    """
    importance = np.abs(lp_values)
    top_idx = np.argsort(-importance)[:budget]
    return np.sort(all_keys[top_idx])


def select_keys_extended_range(
    base_range: int,
    extended_range: int,
    budget: int,
    key_generator: Callable,
    objective_fn: Callable,
    constraint_fn: Callable,
    bounds: Tuple[float, float] = (-10, 10),
    rhs: float = 1.0,
    time_limit: int = 3600,
) -> Tuple[np.ndarray, float]:
    """Two-phase selection: overcomplete LP on extended_range,
    then select best `budget` keys and re-solve.

    Args:
        base_range: Original key range (e.g. 3289 for 2000 squarefree).
        extended_range: Extended range to search (e.g. 3500).
        budget: Number of keys to select.
        key_generator: callable(n_max) -> array of valid keys.
        objective_fn: callable(keys_float) -> cost vector.
        constraint_fn: callable(keys_float, x_points) -> constraint matrix.

    Returns:
        (selected_keys, final_score).
    """
    from .lp_solver import LPSolver

    # Phase 1: overcomplete LP
    all_keys = key_generator(extended_range)
    print(f"  Phase 1: {len(all_keys)} keys from range [2, {extended_range}]")

    if len(all_keys) <= budget:
        print(f"  All keys fit in budget")
        solver = LPSolver(all_keys, objective_fn, constraint_fn,
                          bounds=bounds, rhs=rhs)
        result = solver.solve_full(time_limit=time_limit)
        return all_keys, result.score

    solver = LPSolver(all_keys, objective_fn, constraint_fn,
                      bounds=bounds, rhs=rhs)
    result = solver.solve_full(time_limit=time_limit)

    if not result.success:
        print(f"  Phase 1 failed: {result.message}")
        return np.array([]), float("-inf")

    # Phase 2: select top keys and re-solve
    selected = select_keys_by_lp_importance(all_keys, result.x, budget)
    print(f"  Phase 2: {len(selected)} keys, max_k={selected[-1]}")

    solver2 = LPSolver(selected, objective_fn, constraint_fn,
                       bounds=bounds, rhs=rhs)
    result2 = solver2.solve_full(time_limit=time_limit)

    return selected, result2.score


def greedy_key_addition(
    current_keys: np.ndarray,
    candidates: np.ndarray,
    lp_solver_fn: Callable,
    budget: int,
    max_additions: int = 10,
) -> Tuple[np.ndarray, float]:
    """Greedily add keys that most improve the LP score.

    Args:
        current_keys: Starting key set.
        candidates: Candidate keys to consider adding.
        lp_solver_fn: callable(keys) -> (score, values). Solves the LP.
        budget: Maximum key count.
        max_additions: Max keys to add.

    Returns:
        (best_keys, best_score).
    """
    best_keys = np.array(sorted(current_keys))
    best_score, _ = lp_solver_fn(best_keys)
    current_set = set(int(k) for k in best_keys)

    for i in range(max_additions):
        if len(best_keys) >= budget:
            break

        best_addition = None
        best_addition_score = best_score

        for k in candidates:
            if int(k) in current_set:
                continue

            trial_keys = np.sort(np.append(best_keys, k))
            score, _ = lp_solver_fn(trial_keys)

            if score > best_addition_score:
                best_addition_score = score
                best_addition = int(k)

        if best_addition is None:
            break

        best_keys = np.sort(np.append(best_keys, best_addition))
        best_score = best_addition_score
        current_set.add(best_addition)
        print(f"  Added k={best_addition}, score={best_score:.15f}")

    return best_keys, best_score
