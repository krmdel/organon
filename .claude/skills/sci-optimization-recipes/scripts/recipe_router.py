"""sci-optimization-recipes router + loader.

A minimal keyword-match router over a fixed catalog of named optimisation
recipes. Given a user problem description, pick the recipe slug whose
keyword set has the most hits; ties break alphabetically.

Public API:
    RECIPES          -- dict[slug, {"keywords": [...], "title": str}]
    route(problem)   -- str slug (raises NoRecipeMatch / ValueError)
    load_recipe(slug)-- str markdown body (raises ValueError on bad slug)
    NoRecipeMatch    -- exception class for "nothing in the catalog fits"
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

# ---------------------------------------------------------------------------
# Public exceptions
# ---------------------------------------------------------------------------


class NoRecipeMatch(Exception):
    """Raised when a non-empty problem matches zero recipe keywords."""


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

RECIPES: Dict[str, Dict[str, object]] = {
    "dinkelbach": {
        "keywords": [
            "dinkelbach",
            "ratio",
            "fractional program",
            "minimize ratio",
            "n(x)/d(x)",
            "ratio of two linear",
        ],
        "title": "Dinkelbach",
    },
    "k-climbing": {
        "keywords": [
            "k-climb",
            "variable neighborhood",
            "deceptive landscape",
            "multi-start",
            "vns",
        ],
        "title": "k-Climbing / VNS",
    },
    "remez": {
        "keywords": [
            "remez",
            "equioscillation",
            "min-max",
            "minimax polynomial",
            "chebyshev",
        ],
        "title": "Remez exchange",
    },
    "cross-resolution": {
        "keywords": [
            "cross-resolution",
            "warm-start",
            "basin transfer",
            "low-res",
            "upsample",
        ],
        "title": "Cross-resolution transfer",
    },
    "square-param": {
        "keywords": [
            "square param",
            "peak-lock",
            "x=s^2",
            "non-negative variable",
        ],
        "title": "Square parameterization",
    },
    "ulp-descent": {
        "keywords": [
            "ulp",
            "float64 floor",
            "precision polish",
            "1e-12",
            "1e-13",
            "gradient stalled",
        ],
        "title": "ULP descent",
    },
    "mpmath-lottery": {
        "keywords": [
            "mpmath",
            "precision lottery",
            "arbitrary precision",
            "round to float64",
        ],
        "title": "mpmath lottery",
    },
    "lp-reformulation": {
        "keywords": [
            "lp reform",
            "linear program",
            "max objective",
            "epigraph",
        ],
        "title": "LP reformulation",
    },
    "nelder-mead": {
        "keywords": [
            "nelder-mead",
            "l-bfgs",
            "hill climb",
            "simplex method",
        ],
        "title": "Nelder-Mead / L-BFGS",
    },
    "sigmoid-bound": {
        "keywords": [
            "sigmoid bound",
            "ratio objective",
            "bounded ratio",
        ],
        "title": "Sigmoid bounding",
    },
    "incremental-loss": {
        "keywords": [
            "incremental loss",
            "o(n) update",
            "n-body",
            "pairwise update",
        ],
        "title": "Incremental O(n) loss",
    },
}


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_RECIPES_DIR = (
    Path(__file__).resolve().parent.parent / "references" / "recipes"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _count_hits(problem_lc: str, keywords: List[str]) -> int:
    """Count how many distinct keywords appear in the lowercased problem."""
    return sum(1 for kw in keywords if kw.lower() in problem_lc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def route(problem: str) -> str:
    """Return the slug of the best-matching recipe.

    Raises
    ------
    ValueError
        If `problem` is empty or whitespace only.
    NoRecipeMatch
        If no recipe has even one keyword hit in the problem text.
    """
    if not isinstance(problem, str):
        raise ValueError("problem must be a string")
    if not problem.strip():
        raise ValueError("problem string must be non-empty")

    problem_lc = problem.lower()

    # Score every recipe.
    scores: List[tuple[int, str]] = []
    for slug, entry in RECIPES.items():
        hits = _count_hits(problem_lc, entry["keywords"])  # type: ignore[arg-type]
        if hits > 0:
            scores.append((hits, slug))

    if not scores:
        raise NoRecipeMatch(
            f"No recipe keywords matched problem: {problem!r}"
        )

    # Sort: most hits first, tie-break alphabetically on slug.
    scores.sort(key=lambda x: (-x[0], x[1]))
    return scores[0][1]


def load_recipe(slug: str) -> str:
    """Return the raw markdown body of a recipe file.

    Raises
    ------
    ValueError
        If `slug` is not in RECIPES or the file is missing on disk.
    """
    if slug not in RECIPES:
        raise ValueError(f"Unknown recipe slug: {slug!r}")
    path = _RECIPES_DIR / f"{slug}.md"
    if not path.exists():
        raise ValueError(f"Recipe file missing on disk: {path}")
    return path.read_text()
