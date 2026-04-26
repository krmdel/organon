"""Continuous-attack adapter registry (Upgrade U14).

A problem-class-keyed registry of named optimizer recipes. The orchestrator
classifies an arena problem via :func:`classify_problem`, looks up a recipe
factory in :data:`RECIPE_REGISTRY`, runs the recipe under a
:class:`~arena_framework.primitives.budget.Budget`, and returns an
:class:`AttackResult` that plugs into the submit-gate pipeline.

This module is the U14/1 skeleton: the Protocol, the registry scaffold, and
the classifier. Recipes themselves land in U14/2..U14/6 and register into
:data:`RECIPE_REGISTRY` at import time. The public ``attack()`` API lands in
U14/7.

Invariants (extend the framework's module-design invariants to U14):
  1. No heavy imports at module load — no scipy, no sympy, no mpmath.
     Enforced via the lazy-import subprocess test in
     ``tests/test_continuous_attack_protocol.py``.
  2. Every recipe's ``attack(...)`` respects the passed ``Budget`` and
     returns an ``AttackResult`` validated by :func:`validate_result`.
  3. Recipes compose primitives; the registry composes recipes. Keep the
     level-ordering: primitives → recipes → registry → orchestrator.
"""

from .orchestrator import attack
from .recipe import AttackResult, ContinuousRecipe, validate_result
from .registry import (
    KNOWN_SLUG_SHAPE,
    PROBLEM_CLASSES,
    RECIPE_REGISTRY,
    classify_problem,
    get_recipe,
    register_recipe,
)

__all__ = [
    "AttackResult",
    "ContinuousRecipe",
    "KNOWN_SLUG_SHAPE",
    "PROBLEM_CLASSES",
    "RECIPE_REGISTRY",
    "attack",
    "classify_problem",
    "get_recipe",
    "register_recipe",
    "validate_result",
]
