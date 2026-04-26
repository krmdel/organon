"""Dinkelbach fractional programming.

Maximise (or minimise) a ratio ``N(x) / D(x)`` with ``D(x) > 0`` by
reducing it to a sequence of parametric problems ``max (N(x) - λ D(x))``.
Each outer iteration updates ``λ`` with the current objective value.
Convergence: when ``N(x*) - λ D(x*) ≈ 0``, ``λ`` equals the optimal ratio.

Caller supplies a ``parametric_solver(lam, warm_start) -> (state, value)``
that maximises ``N(x) - lam*D(x)`` (or minimises; see ``sense`` argument).
Problem-specific structure (LP, SDP, smooth L-BFGS) lives inside the solver;
this primitive just drives the outer λ cascade.

Applies to autocorrelation ratios, ground-state energy quotients, spectral
radius minimisation — any "extremum of a ratio" objective.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Optional

from .budget import Budget, PrimitiveResult


Sense = Literal["maximize", "minimize"]


@dataclass
class DinkelbachResult(PrimitiveResult):
    final_lambda: float = 0.0
    lambda_trajectory: list[float] = field(default_factory=list)
    residual_trajectory: list[float] = field(default_factory=list)
    converged: bool = False


def dinkelbach_fp(
    numerator_fn: Callable[[Any], float],
    denominator_fn: Callable[[Any], float],
    parametric_solver: Callable[[float, Optional[Any]], tuple[Any, float]],
    *,
    initial_state: Optional[Any] = None,
    initial_lambda: Optional[float] = None,
    sense: Sense = "maximize",
    max_outer_iters: int = 50,
    tol: float = 1e-10,
    budget: Optional[Budget] = None,
    verbose: bool = False,
) -> DinkelbachResult:
    """Run Dinkelbach's algorithm.

    Parameters
    ----------
    numerator_fn, denominator_fn
        ``x -> float``. Denominator must be strictly positive.
    parametric_solver
        ``(lambda, warm_start) -> (x_star, value)`` where ``value`` equals
        ``N(x_star) - lambda * D(x_star)`` when maximising (the parametric
        objective the solver reports). For minimisation, the solver should
        return ``lambda * D(x_star) - N(x_star)`` as value.
    initial_state, initial_lambda
        Optional. If ``initial_lambda`` is None, compute from
        ``N(initial_state) / D(initial_state)``. If ``initial_state`` is
        None, first run uses ``lambda=0``.
    sense
        "maximize" or "minimize". Sign of the parametric value convention
        determines convergence direction.
    max_outer_iters, tol
        Stop when residual ``|parametric_value|`` < tol or outer iters
        exceeds cap.
    budget
        Optional wall-clock / iteration limit.
    """
    clock = (budget or Budget()).started()

    if initial_lambda is None:
        if initial_state is None:
            lam = 0.0
        else:
            d = float(denominator_fn(initial_state))
            if d <= 0:
                raise ValueError(f"denominator must be positive; got {d}")
            lam = float(numerator_fn(initial_state)) / d
    else:
        lam = float(initial_lambda)

    state = initial_state
    lambda_traj: list[float] = [lam]
    residual_traj: list[float] = []
    trace: list[dict] = []
    converged = False

    for it in range(max_outer_iters):
        if clock.exhausted():
            break
        state, value = parametric_solver(lam, state)
        clock.tick_iteration()

        num = float(numerator_fn(state))
        den = float(denominator_fn(state))
        if den <= 0:
            raise ValueError(
                f"denominator became non-positive at iter {it}: {den}"
            )

        residual = num - lam * den
        residual_traj.append(residual)

        if sense == "maximize":
            converged_now = residual < tol
            new_lambda = num / den
        else:
            converged_now = residual > -tol
            new_lambda = num / den

        trace.append(
            {
                "iter": it,
                "lambda": lam,
                "N": num,
                "D": den,
                "residual": residual,
                "parametric_value": value,
            }
        )

        if verbose:
            print(
                f"[dinkelbach] iter={it}  λ={lam:.10g}  N/D={new_lambda:.10g}  "
                f"residual={residual:.3e}"
            )

        if abs(new_lambda - lam) < tol and converged_now:
            lam = new_lambda
            lambda_traj.append(lam)
            converged = True
            break

        lam = new_lambda
        lambda_traj.append(lam)

    return DinkelbachResult(
        best_score=lam,
        best_state=state,
        n_iterations=clock.iterations,
        n_evaluations=clock.evaluations,
        wall_time_s=clock.elapsed_s(),
        trace=trace,
        primitive_metadata={"primitive": "DinkelbachFP", "sense": sense},
        final_lambda=lam,
        lambda_trajectory=lambda_traj,
        residual_trajectory=residual_traj,
        converged=converged,
    )
