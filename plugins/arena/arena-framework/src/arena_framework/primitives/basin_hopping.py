"""Basin-hopping L-BFGS wrapper.

Thin adapter around ``scipy.optimize.basinhopping`` conforming to the arena
framework's primitive contract. Basin-hopping performs L-BFGS-B local
minimization from many random-perturbation restarts, which is usually the
right move on moderately-sized continuous nonconvex problems where you
have a gradient but the landscape has multiple local minima.

Used for: Thomson-style sphere packing, Erdős-family smooth QCQP attacks,
general small-to-medium continuous optimization warm-starts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import numpy as np
from scipy.optimize import basinhopping

from .budget import Budget, PrimitiveResult


@dataclass
class BasinHoppingResult(PrimitiveResult):
    n_basin_hops: int = 0
    minima_scores: list[float] = field(default_factory=list)
    accept_count: int = 0


class PerturbStep:
    """Gaussian perturbation step that respects an optional bounds mask.
    scipy passes a per-iteration ``take_step`` callable; this class is
    callable and tracks its own RNG so the framework stays deterministic."""

    def __init__(self, sigma: float, seed: Optional[int] = None) -> None:
        self.sigma = sigma
        self.rng = np.random.default_rng(seed)

    def __call__(self, x: np.ndarray) -> np.ndarray:
        return x + self.rng.normal(0.0, self.sigma, size=x.shape)


def basin_hopping_lbfgs(
    loss_fn: Callable[[np.ndarray], float],
    x0: np.ndarray,
    *,
    gradient_fn: Optional[Callable[[np.ndarray], np.ndarray]] = None,
    n_hops: int = 20,
    step_sigma: float = 0.5,
    temperature: float = 1.0,
    seed: Optional[int] = None,
    local_maxiter: int = 200,
    local_tol: float = 1e-10,
    budget: Optional[Budget] = None,
    bounds: Optional[list[tuple[float, float]]] = None,
) -> BasinHoppingResult:
    """Minimize ``loss_fn`` via basin-hopping + L-BFGS-B local descent.

    Parameters
    ----------
    loss_fn, gradient_fn
        Scalar objective and optional analytic gradient. If gradient_fn is
        None, scipy estimates gradient numerically.
    x0
        Initial point.
    n_hops
        Number of basin-hopping outer iterations.
    step_sigma, temperature
        Metropolis acceptance uses ``temperature``; step size uses ``step_sigma``.
    seed
        Deterministic RNG for perturbation.
    local_maxiter, local_tol
        Passed to the inner L-BFGS-B minimizer.
    budget
        Wall-clock cap. basinhopping doesn't natively expose per-iter
        checkpoints, so we translate wall_clock_s into a callback that halts
        the outer loop.
    bounds
        Optional list of (low, high) per dimension.
    """
    clock = (budget or Budget()).started()

    minimizer_kwargs: dict[str, Any] = {
        "method": "L-BFGS-B",
        "options": {"maxiter": local_maxiter, "gtol": local_tol, "ftol": local_tol},
    }
    if gradient_fn is not None:
        minimizer_kwargs["jac"] = gradient_fn
    if bounds is not None:
        minimizer_kwargs["bounds"] = bounds

    minima_scores: list[float] = []
    accept_count_box: list[int] = [0]

    def callback(x, f, accept):  # scipy basinhopping callback
        minima_scores.append(float(f))
        if accept:
            accept_count_box[0] += 1
        clock.tick_iteration()
        if clock.exhausted():
            return True  # tells basinhopping to stop
        return None

    result = basinhopping(
        func=loss_fn,
        x0=np.asarray(x0, dtype=np.float64),
        minimizer_kwargs=minimizer_kwargs,
        niter=n_hops,
        T=temperature,
        take_step=PerturbStep(step_sigma, seed=seed),
        callback=callback,
        seed=seed,
    )

    return BasinHoppingResult(
        best_score=float(result.fun),
        best_state=result.x,
        n_iterations=clock.iterations,
        n_evaluations=int(result.nfev) if hasattr(result, "nfev") else 0,
        wall_time_s=clock.elapsed_s(),
        trace=[{"hop": i, "score": s} for i, s in enumerate(minima_scores)],
        primitive_metadata={
            "primitive": "BasinHoppingLBFGS",
            "n_hops": n_hops,
            "step_sigma": step_sigma,
            "temperature": temperature,
        },
        n_basin_hops=len(minima_scores),
        minima_scores=minima_scores,
        accept_count=accept_count_box[0],
    )
