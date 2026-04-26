#!/usr/bin/env python3
"""Column generation: find optimal variable sets via reduced cost pricing.

Uses dual variables from a solved LP to evaluate candidate variables
without re-solving the full LP each time.

Usage:
    from column_generation import ColumnGenerator
    cg = ColumnGenerator(lp_result, constraint_fn)
    rc = cg.price_candidates(candidates, constraint_points)
    new_keys = cg.iterative_generation(initial_keys, candidates, budget=2000)
"""

import gc
import time
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
from scipy.optimize import linprog


class ColumnGenerator:
    """Find optimal variable set via reduced cost pricing."""

    def __init__(self, duals: np.ndarray, constraint_fn: Callable,
                 objective_fn: Callable):
        """Initialize from dual variables of a solved LP.

        Args:
            duals: Dual variables (shadow prices) from LP solve.
            constraint_fn: callable(keys_float, x_points) -> constraint rows.
            objective_fn: callable(keys_float) -> cost coefficients.
        """
        self.duals = duals
        self.constraint_fn = constraint_fn
        self.objective_fn = objective_fn

    def price_candidates(
        self,
        candidates: np.ndarray,
        constraint_points: np.ndarray,
    ) -> Dict[int, float]:
        """Compute reduced cost for each candidate variable.

        Reduced cost = c_j + duals @ A_col_j
        Negative RC means the variable can improve the LP.

        Returns:
            Dict mapping candidate key -> reduced cost.
        """
        candidates_f = np.asarray(candidates, dtype=np.float64)
        c_candidates = self.objective_fn(candidates_f)

        # Build constraint columns for all candidates at once
        A_cols = self.constraint_fn(candidates_f, constraint_points)
        # A_cols shape: (n_constraints, n_candidates)

        # Truncate duals to match constraint count
        n_constraints = A_cols.shape[0]
        duals = self.duals[:n_constraints] if len(self.duals) > n_constraints else self.duals

        # RC = c_j + duals @ A_col_j
        rc = c_candidates + duals @ A_cols

        return {int(candidates[i]): float(rc[i]) for i in range(len(candidates))}

    def price_candidates_batched(
        self,
        candidates: np.ndarray,
        constraint_points: np.ndarray,
        current_set: set,
        batch_size: int = 1000,
    ) -> List[Tuple[float, int]]:
        """Price candidates in batches. Returns sorted list of (rc, key) with rc < 0."""
        improving = []
        candidates_f = np.asarray(candidates, dtype=np.float64)
        n_constraints = len(constraint_points)
        duals = self.duals[:n_constraints] if len(self.duals) > n_constraints else self.duals

        for i in range(0, len(candidates), batch_size):
            batch = candidates_f[i:i + batch_size]
            batch_keys = candidates[i:i + batch_size]

            c_batch = self.objective_fn(batch)
            A_cols = self.constraint_fn(batch, constraint_points)
            rc_batch = c_batch + duals @ A_cols

            for j, k in enumerate(batch_keys):
                if int(k) not in current_set and rc_batch[j] < -1e-10:
                    improving.append((float(rc_batch[j]), int(k)))

        improving.sort()
        return improving

    def find_best_swap(
        self,
        current_keys: np.ndarray,
        current_values: np.ndarray,
        candidates: np.ndarray,
        constraint_points: np.ndarray,
        budget: int,
    ) -> Optional[Tuple[int, int, float]]:
        """Find the single swap that most improves the LP.

        Returns (remove_key, add_key, estimated_improvement) or None.
        """
        current_set = set(int(k) for k in current_keys)

        # Price candidates
        improving = self.price_candidates_batched(
            candidates, constraint_points, current_set
        )
        if not improving:
            return None

        best_add_rc, best_add_key = improving[0]

        # Find worst current key (highest positive reduced cost = least useful)
        current_rc = {}
        current_f = current_keys.astype(np.float64)
        c_current = self.objective_fn(current_f)
        A_current = self.constraint_fn(current_f, constraint_points)
        n_constraints = A_current.shape[0]
        duals = self.duals[:n_constraints] if len(self.duals) > n_constraints else self.duals
        rc_current = c_current + duals @ A_current

        # Worst = highest RC (most positive = least improving)
        worst_idx = np.argmax(rc_current)
        worst_key = int(current_keys[worst_idx])
        worst_rc = float(rc_current[worst_idx])

        estimated_improvement = worst_rc - best_add_rc
        if estimated_improvement <= 0:
            return None

        return (worst_key, best_add_key, estimated_improvement)

    def prove_optimality(
        self,
        current_keys: np.ndarray,
        candidate_range: Tuple[int, int],
        constraint_points: np.ndarray,
    ) -> Tuple[bool, int]:
        """Check if any candidate in range has negative reduced cost.

        Returns (is_optimal, n_improving_candidates).
        """
        current_set = set(int(k) for k in current_keys)
        candidates = np.array([
            k for k in range(candidate_range[0], candidate_range[1] + 1)
            if k not in current_set
        ])

        if len(candidates) == 0:
            return True, 0

        improving = self.price_candidates_batched(
            candidates, constraint_points, current_set
        )
        return len(improving) == 0, len(improving)

    def iterative_generation(
        self,
        initial_keys: np.ndarray,
        candidates: np.ndarray,
        budget: int,
        objective_fn: Callable,
        constraint_fn: Callable,
        bounds: Tuple[float, float] = (-10, 10),
        rhs: float = 1.0,
        max_rounds: int = 10,
    ) -> Tuple[np.ndarray, float]:
        """Full column generation loop: price, swap, re-solve, repeat.

        Returns (optimal_keys, final_score).
        """
        from .lp_solver import LPSolver

        current_keys = np.array(sorted(initial_keys))
        best_score = float("-inf")

        for round_num in range(max_rounds):
            print(f"\n  CG Round {round_num + 1}/{max_rounds}")

            # Solve LP with current keys
            solver = LPSolver(current_keys, objective_fn, constraint_fn,
                              bounds=bounds, rhs=rhs)
            result = solver.solve_full()

            if not result.success:
                print(f"  LP failed: {result.message}")
                break

            print(f"  Score: {result.score:.15f}")

            if result.score <= best_score + 1e-12:
                print(f"  No improvement. Stopping.")
                break
            best_score = result.score

            if result.duals is None:
                print(f"  No duals available. Stopping.")
                break

            # Update duals and find swap
            self.duals = result.duals
            x_range = int(10 * current_keys[-1])
            constraint_points = np.arange(1, x_range + 1, dtype=np.float64)

            swap = self.find_best_swap(
                current_keys, result.x, candidates,
                constraint_points, budget
            )

            if swap is None:
                print(f"  No improving swap found. OPTIMAL.")
                break

            remove_key, add_key, est_improvement = swap
            print(f"  Swap: remove k={remove_key}, add k={add_key}, "
                  f"est_improvement={est_improvement:.2e}")

            # Apply swap
            current_keys = np.array(sorted(
                [k for k in current_keys if k != remove_key] + [add_key]
            ))

        return current_keys, best_score
