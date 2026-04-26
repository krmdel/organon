"""Smooth-max β-cascade optimization primitive.

Replace a non-differentiable ``max(c_1(x), …, c_m(x))`` objective with the
differentiable log-sum-exp approximation

    f_β(x) = (1/β) · log( Σ_i exp(β · c_i(x)) )

As β → ∞, f_β → max_i c_i. At finite β the function is smooth so L-BFGS works.
β is annealed from a small value (well-smoothed, easy landscape) through a
cascade up to very large values (sharp, near-true max). Each level warm-starts
from the previous level's minimum.

This primitive formalizes the pattern our First Autocorrelation (C1) attack
used to push from JSAgent's published β=1e6 endpoint through β=1e10. The
same pattern applies to minimax design, Chebyshev fits, and any objective
that's a max over finitely many smooth components.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import numpy as np
from scipy.optimize import minimize

from .budget import Budget, PrimitiveResult


@dataclass
class SmoothMaxResult(PrimitiveResult):
    """Extends PrimitiveResult with β-cascade diagnostics."""

    beta_trajectory: list[float] = field(default_factory=list)
    score_per_beta: list[float] = field(default_factory=list)
    hard_max_per_beta: list[float] = field(default_factory=list)


def smooth_max(values: np.ndarray, beta: float) -> float:
    """Numerically-stable log-sum-exp approximation to max(values).

    log-sum-exp with the max-subtraction trick avoids overflow at large β.
    """
    m = float(np.max(values))
    return m + float(np.log(np.exp(beta * (values - m)).sum()) / beta)


def smooth_max_grad(
    values: np.ndarray, jacobian: np.ndarray, beta: float
) -> np.ndarray:
    """Gradient of smooth_max wrt x, given dvalues/dx in ``jacobian`` of shape
    (m, n) where m = number of components, n = dimension of x.

    d(smooth_max)/dx_k = Σ_i softmax_i · dc_i/dx_k
    where softmax_i = exp(β c_i) / Σ_j exp(β c_j), numerically stable with
    the max-subtraction trick.
    """
    m = float(np.max(values))
    w = np.exp(beta * (values - m))
    w = w / w.sum()
    return w @ jacobian


def smooth_max_beta_anneal(
    components_fn: Callable[[np.ndarray], np.ndarray],
    x0: np.ndarray,
    *,
    jacobian_fn: Optional[Callable[[np.ndarray], np.ndarray]] = None,
    beta_schedule: Optional[list[float]] = None,
    budget: Optional[Budget] = None,
    inner_tol: float = 1e-12,
    inner_maxiter: int = 500,
    verbose: bool = False,
) -> SmoothMaxResult:
    """Minimise max_i components_fn(x)[i] via log-sum-exp β-annealing.

    Parameters
    ----------
    components_fn
        ``x -> ndarray(m,)`` returning the m component values whose max we
        want to minimise.
    x0
        Warm-start input of shape (n,).
    jacobian_fn
        Optional ``x -> ndarray(m, n)`` returning d components / dx. If
        ``None``, scipy approximates gradients numerically (slower, less
        stable at large β).
    beta_schedule
        Ascending β values. Each level warm-starts from the previous
        minimum. If ``None``, defaults to a 6-step cascade 1e2..1e7.
    budget
        Optional wall-clock / iteration limit. Checked between β levels.
    inner_tol, inner_maxiter
        Passed to scipy.optimize.minimize for each L-BFGS-B inner solve.
    """
    if beta_schedule is None:
        beta_schedule = [1e2, 1e3, 1e4, 1e5, 1e6, 1e7]
    clock = (budget or Budget()).started()

    x = np.asarray(x0, dtype=np.float64).ravel().copy()
    trace: list[dict] = []
    score_per_beta: list[float] = []
    hard_max_per_beta: list[float] = []
    betas_run: list[float] = []

    best_hard_max = float("inf")
    best_x = x.copy()

    for beta in beta_schedule:
        if clock.exhausted():
            break

        def objective(xv: np.ndarray) -> tuple[float, np.ndarray]:
            vals = components_fn(xv)
            clock.tick_evaluation()
            if jacobian_fn is None:
                return smooth_max(vals, beta), None  # type: ignore
            jac = jacobian_fn(xv)
            return smooth_max(vals, beta), smooth_max_grad(vals, jac, beta)

        if jacobian_fn is not None:
            result = minimize(
                lambda xv: objective(xv),
                x,
                jac=True,
                method="L-BFGS-B",
                options={"gtol": inner_tol, "ftol": inner_tol, "maxiter": inner_maxiter},
            )
        else:
            def obj_only(xv: np.ndarray) -> float:
                return objective(xv)[0]
            result = minimize(
                obj_only,
                x,
                method="L-BFGS-B",
                options={"gtol": inner_tol, "ftol": inner_tol, "maxiter": inner_maxiter},
            )

        x = result.x
        vals = components_fn(x)
        clock.tick_evaluation()
        hard_max = float(vals.max())
        smooth = smooth_max(vals, beta)
        betas_run.append(beta)
        score_per_beta.append(smooth)
        hard_max_per_beta.append(hard_max)
        trace.append(
            {
                "beta": beta,
                "smooth_max": smooth,
                "hard_max": hard_max,
                "inner_iters": int(result.nit),
                "inner_success": bool(result.success),
                "elapsed_s": clock.elapsed_s(),
            }
        )
        if hard_max < best_hard_max:
            best_hard_max = hard_max
            best_x = x.copy()
        if verbose:
            print(
                f"[smooth-max] β={beta:.2e}  smooth={smooth:.6e}  hard_max={hard_max:.6e}"
                f"  iters={result.nit}"
            )
        clock.tick_iteration()

    return SmoothMaxResult(
        best_score=best_hard_max,
        best_state=best_x,
        n_iterations=clock.iterations,
        n_evaluations=clock.evaluations,
        wall_time_s=clock.elapsed_s(),
        trace=trace,
        primitive_metadata={
            "primitive": "SmoothMaxBetaAnneal",
            "beta_schedule": list(beta_schedule),
        },
        beta_trajectory=betas_run,
        score_per_beta=score_per_beta,
        hard_max_per_beta=hard_max_per_beta,
    )
