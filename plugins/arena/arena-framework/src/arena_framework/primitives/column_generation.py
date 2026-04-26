"""Column generation LP primitive.

Solve a large (possibly exponentially sized) LP by:
1. Start with a small "restricted master problem" (RMP) over an initial
   set of columns.
2. Solve the RMP to get primal x* and dual y*.
3. For each candidate column c not in the RMP, compute reduced cost
   ``reduced_cost = price_fn(c, y*)``. If any candidate has reduced cost
   that would improve the RMP, add it.
4. Repeat until no candidate has improving reduced cost (proved optimal
   over the candidate universe) or the budget is exhausted.

Caller supplies:
- ``lp_solver(columns) -> (primal, dual, value)``
- ``candidate_iterator`` yielding candidate columns
- ``price_fn(candidate, dual) -> reduced_cost``

Used for our PNT attack: N=3500 column set selected via this exact pattern.
Returns ``n_columns_added``, the full pricing trajectory, and the final
primal/dual solution for downstream analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Iterator, Optional

from .budget import Budget, PrimitiveResult


@dataclass
class ColumnGenerationResult(PrimitiveResult):
    final_columns: list[Any] = field(default_factory=list)
    primal: Any = None
    dual: Any = None
    n_rounds: int = 0
    n_columns_added: int = 0
    best_reduced_costs_per_round: list[float] = field(default_factory=list)
    converged: bool = False


def column_generation_lp(
    initial_columns: list[Any],
    candidate_iterator_factory: Callable[[], Iterator[Any]],
    lp_solver: Callable[[list[Any]], tuple[Any, Any, float]],
    price_fn: Callable[[Any, Any], float],
    *,
    max_rounds: int = 20,
    add_per_round: int = 10,
    improving_threshold: float = -1e-9,
    sense: str = "minimize",
    budget: Optional[Budget] = None,
    verbose: bool = False,
) -> ColumnGenerationResult:
    """Run column generation.

    Parameters
    ----------
    initial_columns
        Seed columns for the RMP. Must be non-empty.
    candidate_iterator_factory
        Zero-arg callable returning a fresh iterator over candidate columns.
        Called once per pricing round (so each round sees all candidates).
    lp_solver
        ``columns -> (primal, dual, objective_value)``. Caller must know
        which sense (min/max) the LP is.
    price_fn
        ``(candidate, dual) -> reduced_cost``. For a minimization LP a
        candidate with reduced_cost < 0 would improve the objective; we add
        columns whose reduced_cost is <= ``improving_threshold``.
    max_rounds, add_per_round
        Per-round caps.
    improving_threshold
        Column is added only if its reduced_cost beats this threshold.
        Default -1e-9 treats strict negativity as improvement (minimization).
        For maximization set it to e.g. +1e-9 and reverse the comparison
        via ``sense="maximize"``.
    sense
        "minimize" or "maximize". Affects the comparison direction.
    budget
        Optional wall-clock / round cap.
    """
    if not initial_columns:
        raise ValueError("initial_columns must be non-empty")
    if sense not in ("minimize", "maximize"):
        raise ValueError(f"sense must be minimize/maximize, got {sense}")

    clock = (budget or Budget()).started()
    columns = list(initial_columns)

    primal, dual, value = lp_solver(columns)
    clock.tick_evaluation()

    trace: list[dict] = [
        {"round": 0, "n_columns": len(columns), "value": value}
    ]
    best_rc_per_round: list[float] = []
    converged = False
    n_added_total = 0

    for rnd in range(1, max_rounds + 1):
        if clock.exhausted():
            break

        # Evaluate reduced cost on every candidate
        rcs: list[tuple[float, Any]] = []
        for cand in candidate_iterator_factory():
            rc = float(price_fn(cand, dual))
            rcs.append((rc, cand))

        if not rcs:
            converged = True
            break

        # Rank by improving-ness
        if sense == "minimize":
            rcs.sort(key=lambda p: p[0])  # most negative first
            improving = [(rc, c) for rc, c in rcs if rc < improving_threshold]
            best_rc = rcs[0][0]
        else:
            rcs.sort(key=lambda p: -p[0])  # most positive first
            improving = [(rc, c) for rc, c in rcs if rc > improving_threshold]
            best_rc = rcs[0][0]

        best_rc_per_round.append(best_rc)

        if not improving:
            converged = True
            trace.append(
                {"round": rnd, "best_rc": best_rc, "added": 0, "value": value}
            )
            break

        to_add = [c for _rc, c in improving[:add_per_round]]
        columns.extend(to_add)
        n_added_total += len(to_add)

        primal, dual, value = lp_solver(columns)
        clock.tick_evaluation()
        clock.tick_iteration()
        trace.append(
            {
                "round": rnd,
                "n_columns": len(columns),
                "value": value,
                "best_rc": best_rc,
                "added": len(to_add),
            }
        )
        if verbose:
            print(
                f"[colgen] round={rnd} cols={len(columns)} value={value:.6e} "
                f"best_rc={best_rc:.3e} added={len(to_add)}"
            )

    return ColumnGenerationResult(
        best_score=float(value),
        best_state=primal,
        n_iterations=clock.iterations,
        n_evaluations=clock.evaluations,
        wall_time_s=clock.elapsed_s(),
        trace=trace,
        primitive_metadata={
            "primitive": "ColumnGenerationLP",
            "sense": sense,
            "max_rounds": max_rounds,
        },
        final_columns=columns,
        primal=primal,
        dual=dual,
        n_rounds=len(trace) - 1,
        n_columns_added=n_added_total,
        best_reduced_costs_per_round=best_rc_per_round,
        converged=converged,
    )
