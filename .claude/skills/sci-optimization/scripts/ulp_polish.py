#!/usr/bin/env python3
"""Float64 ULP (Unit in Last Place) stepping descent.

After LP solving and scaling, this squeezes the last bits of score by
testing tiny float64 perturbations at the ULP level.

Usage:
    from ulp_polish import ulp_step_descent, ulp_of
    polished = ulp_step_descent(solution, evaluator_fn, max_rounds=5)
"""

from typing import Callable, Dict, List, Tuple

import numpy as np


def ulp_of(x: float) -> float:
    """Return the ULP (smallest representable difference) at value x."""
    return float(np.nextafter(x, np.inf) - x)


def ulp_step_descent(
    solution: Dict[str, float],
    evaluator_fn: Callable,
    max_rounds: int = 5,
    offsets: Tuple[int, ...] = (1, 2, 4),
    verbose: bool = True,
) -> Dict[str, float]:
    """Discrete descent at ULP granularity.

    For each variable, tests +/- {1,2,4} ULP offsets.
    Accepts any change that improves the score.
    Alternates single-coordinate and 2-coordinate sweeps.

    Args:
        solution: Dict mapping string keys to float values.
        evaluator_fn: callable({"partial_function": solution}) -> float.
        max_rounds: Number of full sweep rounds.
        offsets: ULP multipliers to test (e.g., (1, 2, 4)).
        verbose: Print progress.

    Returns:
        Polished solution dict (same format as input).
    """
    current = dict(solution)
    keys = list(current.keys())
    base_score = evaluator_fn({"partial_function": current})

    if verbose:
        print(f"  ULP polish: {len(keys)} variables, base score={base_score:.15f}")

    total_improvements = 0

    for round_num in range(max_rounds):
        improved_this_round = 0

        # Single-coordinate sweep
        for key in keys:
            val = current[key]
            u = ulp_of(abs(val)) if val != 0 else ulp_of(1e-300)

            best_val = val
            best_score = base_score

            for off in offsets:
                for direction in (+1, -1):
                    new_val = np.nextafter(val, direction * np.inf)
                    # Step `off` ULPs
                    for _ in range(off - 1):
                        new_val = np.nextafter(new_val, direction * np.inf)

                    current[key] = new_val
                    score = evaluator_fn({"partial_function": current})

                    if score > best_score:
                        best_score = score
                        best_val = new_val

            if best_val != val:
                current[key] = best_val
                base_score = best_score
                improved_this_round += 1
            else:
                current[key] = val

        # 2-coordinate sweep (pairs of adjacent keys)
        for i in range(0, len(keys) - 1, 2):
            k1, k2 = keys[i], keys[i + 1]
            v1, v2 = current[k1], current[k2]

            best_v1, best_v2 = v1, v2
            best_score_pair = base_score

            for off in offsets[:2]:  # smaller offset set for pairs
                for d1 in (+1, -1):
                    nv1 = v1
                    for _ in range(off):
                        nv1 = np.nextafter(nv1, d1 * np.inf)

                    for d2 in (+1, -1):
                        nv2 = v2
                        for _ in range(off):
                            nv2 = np.nextafter(nv2, d2 * np.inf)

                        current[k1] = nv1
                        current[k2] = nv2
                        score = evaluator_fn({"partial_function": current})

                        if score > best_score_pair:
                            best_score_pair = score
                            best_v1, best_v2 = nv1, nv2

            if best_v1 != v1 or best_v2 != v2:
                current[k1] = best_v1
                current[k2] = best_v2
                base_score = best_score_pair
                improved_this_round += 1
            else:
                current[k1] = v1
                current[k2] = v2

        total_improvements += improved_this_round

        if verbose:
            print(f"  Round {round_num + 1}: {improved_this_round} improvements, "
                  f"score={base_score:.15f}")

        if improved_this_round == 0:
            if verbose:
                print(f"  No improvements. Stopping.")
            break

    if verbose:
        print(f"  ULP polish complete: {total_improvements} total improvements")

    return current


def batch_ulp_polish(
    solutions: List[Dict[str, float]],
    evaluator_fn: Callable,
    max_rounds: int = 3,
) -> Tuple[Dict[str, float], float]:
    """Polish multiple solutions and return the best one."""
    best_solution = None
    best_score = float("-inf")

    for i, sol in enumerate(solutions):
        print(f"\n  Polishing solution {i + 1}/{len(solutions)}...")
        polished = ulp_step_descent(sol, evaluator_fn, max_rounds=max_rounds)
        score = evaluator_fn({"partial_function": polished})
        if score > best_score:
            best_score = score
            best_solution = polished

    return best_solution, best_score
