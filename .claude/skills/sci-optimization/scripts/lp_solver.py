#!/usr/bin/env python3
"""LP solving engine with full-constraint and cutting-plane modes.

Uses scipy's HiGHS backend (IPM or dual simplex). Manages memory for large
constraint matrices and extracts dual variables for column generation.

Usage:
    from lp_solver import LPSolver, LPResult

    solver = LPSolver(
        keys=np.array([2, 3, 5, 6, 7, ...]),
        objective_fn=lambda k: np.log(k) / k,
        constraint_fn=lambda k, x: np.floor(x[:, None] / k[None, :]) - x[:, None] / k[None, :],
        bounds=(-10, 10),
        rhs=1.0,
    )
    result = solver.solve_full(time_limit=7200)
    result = solver.solve_cutting_plane(n_init=3000, max_iters=50)
"""

import gc
import time
from dataclasses import dataclass, field
from typing import Callable, Optional, Tuple

import numpy as np
from scipy.optimize import linprog


@dataclass
class LPResult:
    """LP solution with metadata."""
    x: np.ndarray
    score: float
    duals: Optional[np.ndarray] = None
    max_constraint: float = 0.0
    solve_time: float = 0.0
    n_active: int = 0
    n_constraints: int = 0
    n_variables: int = 0
    method: str = ""
    success: bool = True
    message: str = ""


class LPSolver:
    """Flexible LP solver with multiple strategies.

    Solves: min c'x  s.t.  Ax <= b,  lb <= x <= ub

    Args:
        keys: Array of variable indices (e.g. squarefree integers).
        objective_fn: callable(keys_float) -> cost vector c.
        constraint_fn: callable(keys_float, x_points) -> constraint matrix rows.
            Must return shape (len(x_points), len(keys)).
        bounds: (lower, upper) bounds per variable.
        rhs: Right-hand side scalar for Ax <= rhs.
    """

    def __init__(
        self,
        keys: np.ndarray,
        objective_fn: Callable,
        constraint_fn: Callable,
        bounds: Tuple[float, float] = (-10, 10),
        rhs: float = 1.0,
    ):
        self.keys = np.asarray(keys)
        self.keys_f = self.keys.astype(np.float64)
        self.n_vars = len(self.keys)
        self.objective_fn = objective_fn
        self.constraint_fn = constraint_fn
        self.bounds = bounds
        self.rhs = rhs

        self.c = self.objective_fn(self.keys_f)
        self._last_result: Optional[LPResult] = None

    def _build_constraints(
        self, x_range: int, chunk_size: int = 5000
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Build full constraint matrix in chunks to manage memory."""
        chunks = []
        for s in range(1, x_range + 1, chunk_size):
            e = min(s + chunk_size, x_range + 1)
            x_points = np.arange(s, e, dtype=np.float64)
            chunks.append(self.constraint_fn(self.keys_f, x_points))
        A_ub = np.vstack(chunks)
        b_ub = np.full(A_ub.shape[0], self.rhs)
        del chunks
        gc.collect()
        return A_ub, b_ub

    def solve_full(
        self,
        x_range: Optional[int] = None,
        time_limit: int = 7200,
        method: str = "highs-ipm",
        chunk_size: int = 5000,
    ) -> LPResult:
        """Build complete constraint matrix and solve with IPM.

        Args:
            x_range: Maximum x value for constraints. Default: 10 * max(keys).
            time_limit: Solver time limit in seconds.
            method: scipy linprog method ('highs-ipm', 'highs-ds', 'highs').
            chunk_size: Rows per chunk when building constraint matrix.
        """
        if x_range is None:
            x_range = int(10 * self.keys_f[-1])

        print(f"  Building constraints: {self.n_vars} vars, x_range={x_range}")
        t0 = time.time()
        A_ub, b_ub = self._build_constraints(x_range, chunk_size)
        build_time = time.time() - t0
        print(f"  Matrix: {A_ub.shape}, {A_ub.nbytes / 1e6:.0f}MB, "
              f"built in {build_time:.1f}s")

        t0 = time.time()
        result = linprog(
            self.c, A_ub=A_ub, b_ub=b_ub,
            bounds=[self.bounds] * self.n_vars,
            method=method,
            options={"maxiter": 1000000, "presolve": True, "time_limit": time_limit},
        )
        solve_time = time.time() - t0

        # Extract duals
        duals = None
        if hasattr(result, "ineqlin") and hasattr(result.ineqlin, "marginals"):
            duals = result.ineqlin.marginals

        # Compute max constraint value
        max_cv = 0.0
        if result.success:
            cv = A_ub @ result.x
            max_cv = float(np.max(cv))
            n_active = int(np.sum(cv > self.rhs - 1e-8))
        else:
            n_active = 0

        del A_ub, b_ub
        gc.collect()

        lp_result = LPResult(
            x=result.x if result.success else np.zeros(self.n_vars),
            score=float(-result.fun) if result.success else float("-inf"),
            duals=duals,
            max_constraint=max_cv,
            solve_time=solve_time,
            n_active=n_active,
            n_constraints=x_range,
            n_variables=self.n_vars,
            method=method,
            success=result.success,
            message=result.message,
        )

        print(f"  LP: {solve_time:.1f}s, score={lp_result.score:.15f}, "
              f"active={n_active}, max_cv={max_cv:.8f}")

        self._last_result = lp_result
        return lp_result

    def solve_cutting_plane(
        self,
        x_range: Optional[int] = None,
        n_init: int = 3000,
        max_iters: int = 50,
        adaptive_margin: bool = True,
        tol: float = 1e-8,
    ) -> LPResult:
        """Iterative cutting-plane with violation detection.

        Starts with a subset of constraints, solves, finds violations,
        adds them, re-solves. More memory-efficient than full LP for
        large constraint ranges.

        Args:
            x_range: Maximum x value. Default: 10 * max(keys).
            n_init: Initial number of evenly-spaced constraint points.
            max_iters: Maximum cutting-plane iterations.
            adaptive_margin: Increase rhs margin when stalled.
            tol: Convergence tolerance for max violation.
        """
        if x_range is None:
            x_range = int(10 * self.keys_f[-1])

        # Initial constraint set: evenly spaced
        x_init = np.linspace(1, x_range, n_init).astype(np.float64)
        A_active = self.constraint_fn(self.keys_f, x_init)
        b_active = np.full(A_active.shape[0], self.rhs)

        margin = 0.0
        stall_count = 0
        best_score = float("-inf")

        t0_total = time.time()

        for iteration in range(max_iters):
            t0 = time.time()
            result = linprog(
                self.c, A_ub=A_active, b_ub=b_active + margin,
                bounds=[self.bounds] * self.n_vars,
                method="highs-ipm",
                options={"maxiter": 500000, "presolve": True, "time_limit": 600},
            )
            elapsed = time.time() - t0

            if not result.success:
                print(f"  Iter {iteration}: FAILED ({result.message})")
                break

            score = float(-result.fun)
            print(f"  Iter {iteration}: score={score:.15f}, "
                  f"constraints={A_active.shape[0]}, {elapsed:.1f}s")

            # Check ALL constraints for violations
            all_x = np.arange(1, x_range + 1, dtype=np.float64)
            all_cv = np.zeros(x_range)

            for s in range(0, x_range, 5000):
                e = min(s + 5000, x_range)
                chunk_x = all_x[s:e]
                chunk_A = self.constraint_fn(self.keys_f, chunk_x)
                all_cv[s:e] = chunk_A @ result.x

            max_violation = float(np.max(all_cv))
            n_violated = int(np.sum(all_cv > self.rhs + tol))

            print(f"    max_cv={max_violation:.8f}, violations={n_violated}")

            if n_violated == 0:
                print(f"  Converged! No violations.")
                break

            # Add violated constraints
            violated_idx = np.where(all_cv > self.rhs + tol)[0]
            violated_x = all_x[violated_idx]
            new_A = self.constraint_fn(self.keys_f, violated_x)
            new_b = np.full(new_A.shape[0], self.rhs)

            A_active = np.vstack([A_active, new_A])
            b_active = np.concatenate([b_active, new_b])

            # Adaptive margin
            if adaptive_margin and abs(score - best_score) < 1e-12:
                stall_count += 1
                if stall_count >= 3:
                    margin += 1e-5
                    print(f"    Stalled. Margin increased to {margin:.2e}")
            else:
                stall_count = 0
            best_score = max(best_score, score)

        total_time = time.time() - t0_total

        # Extract duals from final solve
        duals = None
        if hasattr(result, "ineqlin") and hasattr(result.ineqlin, "marginals"):
            duals = result.ineqlin.marginals

        lp_result = LPResult(
            x=result.x if result.success else np.zeros(self.n_vars),
            score=float(-result.fun) if result.success else float("-inf"),
            duals=duals,
            max_constraint=max_violation if result.success else 0.0,
            solve_time=total_time,
            n_active=A_active.shape[0],
            n_constraints=x_range,
            n_variables=self.n_vars,
            method="cutting-plane",
            success=result.success,
            message=f"{iteration + 1} iterations",
        )

        self._last_result = lp_result
        return lp_result

    def extract_duals(self) -> Optional[np.ndarray]:
        """Get dual variables (shadow prices) from last solve."""
        if self._last_result and self._last_result.duals is not None:
            return self._last_result.duals
        return None

    @property
    def last_result(self) -> Optional[LPResult]:
        return self._last_result
