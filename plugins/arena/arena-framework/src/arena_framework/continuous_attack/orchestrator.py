"""Top-level ``attack()`` composer for the continuous-attack registry (U14/7).

Wires together:
  * :func:`arena_framework.continuous_attack.classify_problem` — maps a
    problem dict + optional top-K to a fine problem class.
  * :data:`arena_framework.continuous_attack.RECIPE_REGISTRY` — returns a
    recipe factory for a given class.
  * :func:`arena_framework.recon.default_evaluator_registry` — provides
    the arena + rigorous evaluators when the caller doesn't supply them.

This module is what end users (or the broader arena orchestrator) call
instead of touching the registry directly. Lazy imports keep the
continuous_attack package's heavy-deps invariant intact.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from arena_framework.primitives.budget import Budget

from .recipe import AttackResult, validate_result
from .registry import (
    PROBLEM_CLASSES,
    RECIPE_REGISTRY,
    classify_problem,
    get_recipe,
)


def _ensure_recipes_loaded(needed_class: str) -> None:
    """Lazy-import all recipe modules if the needed class isn't registered.

    Importing ``continuous_attack`` itself doesn't pull scipy / numpy —
    only calling :func:`attack` does. Recipes register themselves via
    ``register_recipe`` at module-import time, so a single
    :func:`load_all_recipes` call populates :data:`RECIPE_REGISTRY`.
    """
    if needed_class in RECIPE_REGISTRY:
        return
    from .recipes import load_all_recipes

    load_all_recipes()


def _lookup_evaluators(
    slug: str,
    evaluator: Optional[Callable[[Any], float]],
    rigorous_evaluator: Optional[
        Callable[[Any], tuple[float, dict[str, Any]]]
    ],
) -> tuple[
    Callable[[Any], float],
    Optional[Callable[[Any], tuple[float, dict[str, Any]]]],
]:
    """Return ``(evaluator, rigorous_evaluator)``, falling back to
    :func:`arena_framework.recon.default_evaluator_registry` when the
    caller leaves either slot as ``None`` and the problem has a slug."""
    if evaluator is not None and rigorous_evaluator is not None:
        return evaluator, rigorous_evaluator
    if not slug:
        if evaluator is None:
            raise ValueError(
                "attack() requires either an explicit ``evaluator=`` callable "
                "or a ``problem['slug']`` that exists in the default "
                "evaluator registry."
            )
        return evaluator, rigorous_evaluator

    # Lazy-import recon to avoid pulling sympy at continuous_attack import time.
    from arena_framework.recon import default_evaluator_registry

    reg = default_evaluator_registry()
    entry = reg.get(slug)
    if entry is None:
        if evaluator is None:
            raise ValueError(
                f"No evaluator registered for slug {slug!r}; pass "
                f"``evaluator=`` explicitly or register the problem."
            )
        return evaluator, rigorous_evaluator
    if evaluator is None:
        evaluator = entry["arena_evaluator"]
    if rigorous_evaluator is None:
        rigorous_evaluator = entry["rigorous_evaluator"]
    return evaluator, rigorous_evaluator


def _resolve_recipe_class(
    problem: dict[str, Any],
    top_solutions: Optional[list[dict[str, Any]]],
    recipe_name: Optional[str],
) -> tuple[str, dict[str, Any]]:
    """Determine the problem class we'll dispatch on.

    When ``recipe_name`` is set, it must name one of
    :data:`PROBLEM_CLASSES` and becomes the class outright. Otherwise
    we classify and surface diagnostics for logging.
    """
    if recipe_name is not None:
        if recipe_name not in PROBLEM_CLASSES:
            raise ValueError(
                f"recipe_name={recipe_name!r} is not a valid problem class; "
                f"must be one of {PROBLEM_CLASSES}"
            )
        return recipe_name, {
            "reasons": [f"caller override recipe_name={recipe_name!r}"],
            "overridden": True,
        }
    cls, diag = classify_problem(problem, top_solutions)
    return cls, diag


def attack(
    problem: dict[str, Any],
    *,
    budget: Budget,
    evaluator: Optional[Callable[[Any], float]] = None,
    rigorous_evaluator: Optional[
        Callable[[Any], tuple[float, dict[str, Any]]]
    ] = None,
    top_solutions: Optional[list[dict[str, Any]]] = None,
    start_candidate: Any | None = None,
    recipe_name: Optional[str] = None,
    config: Optional[dict[str, Any]] = None,
    validate: bool = True,
) -> AttackResult:
    """Top-level continuous-attack entrypoint.

    Parameters
    ----------
    problem
        The arena problem dict (same shape recon loads from
        ``problem.json``). Must include at least ``scoring`` and
        ``solutionSchema``; include ``slug`` to enable evaluator auto-lookup
        and pinned classification.
    budget
        Wall / iteration / evaluation cap.
    evaluator
        Arena-score callable. When omitted we look up the slug in
        :func:`arena_framework.recon.default_evaluator_registry`.
    rigorous_evaluator
        Optional companion for rigor checks; auto-resolved the same way.
    top_solutions
        Optional top-K competitor solutions; fed to classify_problem for
        warm-start fallback routing.
    start_candidate
        Optional warm start handed to the recipe.
    recipe_name
        Override the classifier. Must be one of
        :data:`PROBLEM_CLASSES`. Useful for rerunning a specific recipe
        against a problem whose natural class doesn't have one registered yet.
    config
        Recipe-specific overrides passed through unchanged.
    validate
        When True (default), call :func:`validate_result` on the recipe's
        output before returning — catches contract violations at the call
        site. Set False for speed in hot loops.

    Returns
    -------
    AttackResult
        Extended with ``primitive_metadata["problem_class"]`` and
        ``primitive_metadata["classification_reasons"]`` so downstream
        logging can explain *why* a recipe was picked.
    """
    problem_class, diag = _resolve_recipe_class(
        problem, top_solutions, recipe_name
    )
    slug = str(problem.get("slug", "") or "")
    evaluator_resolved, rigorous_resolved = _lookup_evaluators(
        slug, evaluator, rigorous_evaluator
    )

    _ensure_recipes_loaded(problem_class)
    recipe = get_recipe(problem_class)
    if recipe is None:
        # Graceful fallback: warmstart polish if we have a warm start or top-K
        if start_candidate is not None or top_solutions:
            _ensure_recipes_loaded("warmstart_polish_only")
            recipe = get_recipe("warmstart_polish_only")
        if recipe is None:
            raise RuntimeError(
                f"No recipe registered for problem_class={problem_class!r}; "
                f"register one via register_recipe() or call load_all_recipes(). "
                f"Classification reasons: {diag.get('reasons')}"
            )
        fallback_class = "warmstart_polish_only"
    else:
        fallback_class = problem_class

    result = recipe.attack(
        evaluator=evaluator_resolved,
        rigorous_evaluator=rigorous_resolved,
        start_candidate=start_candidate,
        solution_schema=problem.get("solutionSchema", {}) or {},
        scoring=str(problem.get("scoring", "minimize")),
        budget=budget,
        config=config,
    )

    # Annotate with orchestrator-level metadata before validating.
    if result.primitive_metadata is None:  # pragma: no cover - defaulted to {}
        result.primitive_metadata = {}
    result.primitive_metadata.setdefault("classified_as", problem_class)
    result.primitive_metadata.setdefault("dispatched_to", fallback_class)
    result.primitive_metadata.setdefault(
        "classification_reasons", list(diag.get("reasons", []))
    )

    if validate:
        validate_result(result, budget=budget)
    return result
