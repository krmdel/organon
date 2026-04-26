"""E.4 — sci-optimization-recipes end-to-end tests.

Per context/memory/organon_upgrade_final_handoff.md §3.4. Unit tests cover
_count_hits / RECIPES shape in isolation; these tests confirm the router
resolves realistic problem descriptions to the right slug AND every recipe
file loads + parses under the 5-section schema.
"""
from __future__ import annotations

import re

import pytest

from recipe_router import RECIPES, NoRecipeMatch, load_recipe, route


# Each tuple: (problem-description, expected-slug). Problem strings are crafted
# to include unambiguous recipe-specific keywords — validates the composed
# router returns the right slug for realistic user phrasing.
ROUTE_CASES = [
    ("sigmoid bound on a bounded ratio: ratio objective C = max(conv(f,f))/(sum(f))^2",
     "sigmoid-bound"),
    ("stuck at 1e-12 precision polish on float64 floor — gradient stalled",
     "ulp-descent"),
    ("autocorrelation evaluator is O(n²), need incremental loss with O(n) update for n-body pairwise",
     "incremental-loss"),
    ("find best 10th-degree polynomial using remez equioscillation chebyshev minimax polynomial",
     "remez"),
    ("LP reform with max objective using epigraph trick on a linear program",
     "lp-reformulation"),
    ("dinkelbach fractional program N(x)/D(x) — minimize ratio of two linear forms",
     "dinkelbach"),
    ("cross-resolution warm-start: basin transfer via low-res upsample",
     "cross-resolution"),
    ("square param x=s^2 to break peak-lock using a non-negative variable",
     "square-param"),
    ("mpmath precision lottery — arbitrary precision round to float64",
     "mpmath-lottery"),
    ("nelder-mead simplex method fallback — hill climb when no gradient",
     "nelder-mead"),
    ("k-climb / variable neighborhood search for deceptive landscape — multi-start VNS",
     "k-climbing"),
]


# ---------------------------------------------------------------------------
# E.4.1–E.4.11 — real problem descriptions → expected slug
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("problem,expected", ROUTE_CASES,
                         ids=[c[1] for c in ROUTE_CASES])
def test_e4_router_dispatches_correctly(problem, expected):
    assert route(problem) == expected


# ---------------------------------------------------------------------------
# E.4.12 — route("") raises ValueError
# ---------------------------------------------------------------------------

def test_e4_12_empty_raises():
    with pytest.raises(ValueError):
        route("")
    with pytest.raises(ValueError):
        route("   \n\t")


# ---------------------------------------------------------------------------
# E.4.13 — totally-unmatched input raises NoRecipeMatch (documented contract)
# ---------------------------------------------------------------------------

def test_e4_13_unmatched_raises():
    with pytest.raises(NoRecipeMatch):
        route("apple pie and banana bread recipe")


# ---------------------------------------------------------------------------
# E.4.14 — All 11 recipe files loadable + schema-valid
# ---------------------------------------------------------------------------

SCHEMA_SECTIONS = [
    r"^##\s+When to use",
    r"^##\s+Pseudocode",
    r"^##\s+Worked example",
    r"^##\s+Gotchas",
    r"^##\s+References",
]


@pytest.mark.parametrize("slug", sorted(RECIPES.keys()))
def test_e4_14_every_recipe_loads_and_has_five_sections(slug):
    body = load_recipe(slug)
    assert body.strip(), f"{slug} is empty"
    for pattern in SCHEMA_SECTIONS:
        assert re.search(pattern, body, re.MULTILINE), (
            f"{slug}.md missing section matching {pattern!r}"
        )


# ---------------------------------------------------------------------------
# E.4.15 — Router tie-break determinism (100 repeated calls, same result)
# ---------------------------------------------------------------------------

def test_e4_15_router_tie_break_determinism():
    # "ratio" hits both dinkelbach (exact "ratio" keyword) and sigmoid-bound
    # ("ratio objective"). The sort key (-hits, slug) must produce a single
    # deterministic winner regardless of dict iteration order.
    ambiguous = "I have a ratio problem"
    first = route(ambiguous)
    for _ in range(99):
        assert route(ambiguous) == first


# ---------------------------------------------------------------------------
# Bonus — load_recipe raises on unknown slug
# ---------------------------------------------------------------------------

def test_e4_load_recipe_rejects_unknown_slug():
    with pytest.raises(ValueError):
        load_recipe("not-a-real-recipe-slug")
