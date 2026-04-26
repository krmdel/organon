#!/usr/bin/env python3
"""Constraint matrix construction for floor/ceil optimization problems.

Builds the constraint matrix A for problems of the form:
    sum_k f(k) * (floor(x/k) - x/k) <= rhs  for all x in [1, x_max]

This is the standard form for PNT-type problems on Einstein Arena.

Usage:
    from constraint_builder import build_floor_constraints, pnt_constraint_fn, pnt_objective_fn
"""

import gc
from typing import Callable, Tuple

import numpy as np


def build_floor_constraints(
    keys: np.ndarray,
    x_range: int,
    chunk_size: int = 5000,
) -> Tuple[np.ndarray, np.ndarray]:
    """Build full constraint matrix for floor-fractional problems.

    Constraint: sum_k f(k) * (floor(x/k) - x/k) <= 1  for all x

    Args:
        keys: Array of integer keys (variable indices).
        x_range: Maximum x value for constraints.
        chunk_size: Rows per chunk for memory management.

    Returns:
        (A_ub, b_ub) ready for scipy.optimize.linprog.
    """
    keys_f = keys.astype(np.float64)
    chunks = []
    for s in range(1, x_range + 1, chunk_size):
        e = min(s + chunk_size, x_range + 1)
        x_points = np.arange(s, e, dtype=np.float64)
        # floor(x/k) - x/k is always in [-1, 0)
        chunk = np.floor(x_points[:, None] / keys_f[None, :]) - \
                x_points[:, None] / keys_f[None, :]
        chunks.append(chunk)

    A_ub = np.vstack(chunks)
    b_ub = np.full(A_ub.shape[0], 1.0)
    del chunks
    gc.collect()

    return A_ub, b_ub


def pnt_constraint_fn(keys_f: np.ndarray, x_points: np.ndarray) -> np.ndarray:
    """Constraint function for Prime Number Theorem problem.

    A[i, j] = floor(x_i / k_j) - x_i / k_j

    This is the standard constraint for PNT-type Selberg sieve problems.
    """
    return np.floor(x_points[:, None] / keys_f[None, :]) - \
           x_points[:, None] / keys_f[None, :]


def pnt_objective_fn(keys_f: np.ndarray) -> np.ndarray:
    """Objective function for PNT problem.

    c_j = log(k_j) / k_j

    Minimizing c'x is equivalent to maximizing sum(f(k) * log(k) / k).
    """
    return np.log(keys_f) / keys_f


def get_squarefree_integers(n_max: int) -> np.ndarray:
    """Generate all squarefree integers in [2, n_max]."""
    is_squarefree = np.ones(n_max + 1, dtype=bool)
    for p in range(2, int(n_max**0.5) + 1):
        p2 = p * p
        for mult in range(p2, n_max + 1, p2):
            is_squarefree[mult] = False
    return np.array([k for k in range(2, n_max + 1) if is_squarefree[k]])


def check_constraints(
    keys: np.ndarray,
    values: np.ndarray,
    x_range: int,
    rhs: float = 1.0,
    chunk_size: int = 10000,
) -> Tuple[float, int, np.ndarray]:
    """Check constraint satisfaction across full range.

    Returns:
        (max_constraint_value, n_violated, violated_x_points).
    """
    keys_f = keys.astype(np.float64)
    max_cv = float("-inf")
    violated = []

    for s in range(1, x_range + 1, chunk_size):
        e = min(s + chunk_size, x_range + 1)
        x_points = np.arange(s, e, dtype=np.float64)
        A_chunk = pnt_constraint_fn(keys_f, x_points)
        cv = A_chunk @ values

        chunk_max = float(np.max(cv))
        if chunk_max > max_cv:
            max_cv = chunk_max

        violated_mask = cv > rhs
        if np.any(violated_mask):
            violated.extend(x_points[violated_mask].astype(int).tolist())

    return max_cv, len(violated), np.array(violated)
