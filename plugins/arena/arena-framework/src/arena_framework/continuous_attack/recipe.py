"""Recipe protocol + ``AttackResult`` dataclass + contract validator.

A ``ContinuousRecipe`` is the level-above-primitive unit: it composes
primitives (L-BFGS, basin-hopping, soft-min, ULP polish, etc.) into a
problem-class-shaped workflow. One recipe handles every arena problem that
shares a class — so ``SphereLBFGSRecipe`` attacks Thomson *and* any future
"minimise a sphere objective" problem with zero new code.

Contract:

* Each recipe carries ``name`` and ``problem_classes`` as attributes.
* Each recipe implements ``attack(*, evaluator, rigorous_evaluator,
  start_candidate, solution_schema, scoring, budget, config) -> AttackResult``.
* Every call must respect the ``Budget`` (wall-clock / iterations /
  evaluations) — ``validate_result`` allows a 20%% slack by default so
  recipes can finish an in-flight L-BFGS step.
* ``AttackResult.best_state`` is whatever the arena verifier consumes
  (list, dict, ndarray.tolist()); callers serialise it to JSON for
  submit-gate review.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Protocol, runtime_checkable

from arena_framework.primitives.budget import Budget, PrimitiveResult


@dataclass
class AttackResult(PrimitiveResult):
    """Extends ``PrimitiveResult`` with recipe-specific metadata.

    ``PrimitiveResult`` carries (best_score, best_state, n_iterations,
    n_evaluations, wall_time_s, trace, primitive_metadata). ``AttackResult``
    adds:

    * ``recipe_name`` — the recipe that produced this result.
    * ``problem_class`` — the fine class (``"sphere_minimize"``, etc.) the
      recipe was dispatched against.
    * ``n_restarts`` / ``n_basin_hops`` — structured counters that most
      continuous recipes already track; surfaced so the submit gate and
      orchestrator can display them without reaching into ``trace``.
    * ``phase_history`` — per-phase rollup (phase name → best score, wall-
      time, accepted count) for the post-hoc dashboards.
    """

    recipe_name: str = ""
    problem_class: str = ""
    n_restarts: int = 0
    n_basin_hops: int = 0
    phase_history: list[dict[str, Any]] = field(default_factory=list)


@runtime_checkable
class ContinuousRecipe(Protocol):
    """Structural protocol for a continuous-attack recipe.

    ``runtime_checkable`` so tests (and the orchestrator's boot sanity
    check) can assert ``isinstance(instance, ContinuousRecipe)`` without
    importing the concrete recipe class. Concrete recipes do NOT need to
    subclass this Protocol — they only need the attributes + method.
    """

    name: str
    problem_classes: tuple[str, ...]

    def attack(
        self,
        *,
        evaluator: Callable[[Any], float],
        rigorous_evaluator: Optional[
            Callable[[Any], tuple[float, dict[str, Any]]]
        ] = None,
        start_candidate: Any | None = None,
        solution_schema: dict[str, Any],
        scoring: str,
        budget: Budget,
        config: dict[str, Any] | None = None,
    ) -> AttackResult: ...


def validate_result(
    result: AttackResult,
    *,
    budget: Budget,
    slack: float = 0.2,
) -> None:
    """Raise if ``result`` violates the recipe contract.

    Checks:
      * Must be an ``AttackResult`` instance (ducktyping not enough — we
        want the extra counters).
      * ``recipe_name`` and ``problem_class`` must be non-empty strings.
      * Wall-clock must be within ``(1 + slack)`` of ``budget.wall_clock_s``
        when the budget sets one. Slack of 20%% lets an L-BFGS step finish.
      * Iteration / evaluation caps — same slack policy.
      * ``best_score`` must be a finite float unless ``best_state`` is None
        (pure failure mode allowed).

    Called by the orchestrator post-``attack()`` and by tests.
    """
    import math

    if not isinstance(result, AttackResult):
        raise TypeError(
            f"expected AttackResult, got {type(result).__name__}; "
            f"recipes must return the extended dataclass"
        )
    if not result.recipe_name:
        raise ValueError("AttackResult.recipe_name must be a non-empty string")
    if not result.problem_class:
        raise ValueError("AttackResult.problem_class must be a non-empty string")

    if result.best_state is not None and not math.isfinite(result.best_score):
        raise ValueError(
            f"AttackResult.best_score must be finite when best_state is set; "
            f"got {result.best_score!r}"
        )

    if budget.wall_clock_s is not None:
        cap = budget.wall_clock_s * (1.0 + slack)
        if result.wall_time_s > cap:
            raise ValueError(
                f"budget overrun: wall_time_s={result.wall_time_s:.2f} > "
                f"{cap:.2f} (budget {budget.wall_clock_s:.2f}s + "
                f"{int(slack * 100)}% slack)"
            )
    if budget.max_iterations is not None:
        cap_iter = int(budget.max_iterations * (1.0 + slack)) + 1
        if result.n_iterations > cap_iter:
            raise ValueError(
                f"iteration overrun: n_iterations={result.n_iterations} > "
                f"{cap_iter} (budget {budget.max_iterations} + "
                f"{int(slack * 100)}% slack)"
            )
    if budget.max_evaluations is not None:
        cap_eval = int(budget.max_evaluations * (1.0 + slack)) + 1
        if result.n_evaluations > cap_eval:
            raise ValueError(
                f"evaluation overrun: n_evaluations={result.n_evaluations} > "
                f"{cap_eval} (budget {budget.max_evaluations} + "
                f"{int(slack * 100)}% slack)"
            )
