"""Problem-class registry + classifier for the continuous-attack adapter.

``PROBLEM_CLASSES`` enumerates the fine sub-classes the U14 recipes
recognise. The router (``arena_framework.router``) still emits coarse
Class A / B; this module produces the finer class keyed against specific
recipe families.

The classifier reads schema text, scoring direction, description and
verifier source in that priority order, falling through to ``unknown``
if no pattern matches. It is deliberately conservative — a slug can
pin its class via :data:`KNOWN_SLUG_SHAPE` to skip the heuristic path.
"""

from __future__ import annotations

from typing import Any, Callable, Optional


# ---------------------------------------------------------------------------
# Problem-class taxonomy
# ---------------------------------------------------------------------------

#: Canonical set of fine problem classes the registry recognises.
#:
#: * ``sphere_minimize`` — minimise an objective over points on S^(d-1)
#:   (Thomson, any future sphere-min problem).
#: * ``sphere_maximize_mindist`` — maximise min pairwise distance on
#:   S^(d-1) (Tammes, potentially kissing variants).
#: * ``nonneg_function_maximize`` — maximise a ratio/functional of a
#:   non-negative 1D function (C1/C2/C3 autocorrelation inequalities).
#: * ``plane_minimize_distance_ratio`` — minimise d_max / d_min on 2D
#:   point set (min-distance-ratio-2d).
#: * ``plane_maximize_radius`` — maximise packing radius on 2D set
#:   (circle-packing, hexagon-packing, circles-rectangle).
#: * ``warmstart_polish_only`` — no shape match, but top-K competitor
#:   solutions are available; polish the best.
#: * ``discrete_pm1_coefficients`` — ±1 coefficient optimisation
#:   (flat-polynomials).
#: * ``unknown`` — no pattern matched and no warm start available.
PROBLEM_CLASSES: tuple[str, ...] = (
    "sphere_minimize",
    "sphere_maximize_mindist",
    "nonneg_function_maximize",
    "plane_minimize_distance_ratio",
    "plane_maximize_radius",
    "warmstart_polish_only",
    "discrete_pm1_coefficients",
    "unknown",
)


#: Fast-path slug pins for problems whose class is already known. The
#: classifier consults this first — heuristics only fire when the slug is
#: missing or absent from this dict. Add new slugs here as new problems
#: become attackable.
KNOWN_SLUG_SHAPE: dict[str, str] = {
    "thomson-problem": "sphere_minimize",
    "tammes-problem": "sphere_maximize_mindist",
    "first-autocorrelation-inequality": "nonneg_function_maximize",
    "second-autocorrelation-inequality": "nonneg_function_maximize",
    "third-autocorrelation-inequality": "nonneg_function_maximize",
    "min-distance-ratio-2d": "plane_minimize_distance_ratio",
    "circle-packing": "plane_maximize_radius",
    "hexagon-packing": "plane_maximize_radius",
    "circles-rectangle": "plane_maximize_radius",
    "flat-polynomials": "discrete_pm1_coefficients",
}


# ---------------------------------------------------------------------------
# Recipe factory registry
# ---------------------------------------------------------------------------

#: Mapping from problem class → recipe-factory callable. Recipe modules
#: populate this at import time via :func:`register_recipe`. Empty at
#: U14/1; recipes land in U14/2..U14/6.
#:
#: Callable returns a fresh recipe instance per call — recipes may carry
#: per-call mutable state, so the orchestrator gets its own instance.
RECIPE_REGISTRY: dict[str, Callable[[], Any]] = {}


def register_recipe(problem_class: str, factory: Callable[[], Any]) -> None:
    """Register a recipe factory for ``problem_class``.

    Raises ``ValueError`` if ``problem_class`` is not in
    :data:`PROBLEM_CLASSES`. Re-registering is allowed — later registration
    wins, which lets a specialised recipe shadow a fallback.
    """
    if problem_class not in PROBLEM_CLASSES:
        raise ValueError(
            f"unknown problem_class {problem_class!r}; "
            f"must be one of {PROBLEM_CLASSES}"
        )
    RECIPE_REGISTRY[problem_class] = factory


def get_recipe(problem_class: str) -> Optional[Any]:
    """Return a fresh recipe instance for ``problem_class``, or ``None``.

    Callers should fall back to ``warmstart_polish_only`` (when top-K
    solutions are available) or raise when both return ``None``.
    """
    factory = RECIPE_REGISTRY.get(problem_class)
    if factory is None:
        return None
    return factory()


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------


def classify_problem(
    problem: dict[str, Any],
    top_solutions: Optional[list[dict[str, Any]]] = None,
) -> tuple[str, dict[str, Any]]:
    """Infer the fine problem class for a recipe dispatch.

    Returns ``(class, diagnostics)`` where ``class`` is one of
    :data:`PROBLEM_CLASSES` and ``diagnostics`` records the matched
    rule(s) plus inferred schema signals. Rule order:

    1. :data:`KNOWN_SLUG_SHAPE` slug pin.
    2. Schema-text pattern: ``"+1 or -1"``, ``"[x, y, z]"``, ``"[x, y]"``,
       ``"non-negative"``.
    3. Description/verifier keyword ensemble (packing / ratio /
       autocorrelation / ±1 coefficients).
    4. Warm-start fallback when ``top_solutions`` is non-empty.
    5. ``unknown``.

    The classifier never imports heavy deps. It operates on the
    ``problem`` dict only — the same dict recon.py loads from
    ``problem.json``.
    """
    slug = problem.get("slug", "")
    diagnostics: dict[str, Any] = {"reasons": []}

    if slug in KNOWN_SLUG_SHAPE:
        cls = KNOWN_SLUG_SHAPE[slug]
        diagnostics["reasons"].append(f"pinned by slug: {slug}")
        return cls, diagnostics

    scoring = str(problem.get("scoring", "minimize")).lower()
    schema = problem.get("solutionSchema", {}) or {}
    schema_str = " ".join(str(v) for v in schema.values()).lower()
    verifier = problem.get("verifier", "") or ""
    desc = (problem.get("description", "") or "").lower()
    diagnostics["scoring_direction"] = scoring
    diagnostics["schema_text"] = schema_str[:200]

    # Rule 2a — ±1 coefficient integer problems
    if (
        "+1 or -1" in schema_str
        or "-1 or +1" in schema_str
        or "c in (-1, 1)" in verifier
        or "c in (1, -1)" in verifier
        or "{-1, 1}" in verifier
        or "{1, -1}" in verifier
    ):
        diagnostics["reasons"].append("±1 coefficient pattern in schema/verifier")
        return "discrete_pm1_coefficients", diagnostics

    # Rule 2b — 3D sphere coordinates
    if "[x, y, z]" in schema_str:
        if scoring == "minimize":
            diagnostics["reasons"].append(
                "3D coordinate schema + minimize → sphere_minimize"
            )
            return "sphere_minimize", diagnostics
        if scoring == "maximize":
            # Prefer the explicit min-pairwise-distance signal; otherwise
            # default to sphere_maximize_mindist as the most common maximise
            # pattern on a sphere.
            if ("min" in desc and "distance" in desc) or "minimum pairwise" in desc:
                diagnostics["reasons"].append(
                    "3D + maximize + min pairwise distance → sphere_maximize_mindist"
                )
            else:
                diagnostics["reasons"].append(
                    "3D + maximize → sphere_maximize_mindist (default)"
                )
            return "sphere_maximize_mindist", diagnostics

    # Rule 2c — 2D plane coordinates
    if "[x, y]" in schema_str:
        if "ratio" in desc or (
            "max" in desc and "min" in desc and "distance" in desc
        ):
            diagnostics["reasons"].append(
                "2D coordinate schema + distance ratio → plane_minimize_distance_ratio"
            )
            return "plane_minimize_distance_ratio", diagnostics
        if "pack" in desc or "radius" in desc:
            diagnostics["reasons"].append(
                "2D coordinate schema + pack/radius → plane_maximize_radius"
            )
            return "plane_maximize_radius", diagnostics
        if scoring == "minimize":
            diagnostics["reasons"].append(
                "2D coordinate schema + minimize (default) → plane_minimize_distance_ratio"
            )
            return "plane_minimize_distance_ratio", diagnostics
        diagnostics["reasons"].append(
            "2D coordinate schema + maximize (default) → plane_maximize_radius"
        )
        return "plane_maximize_radius", diagnostics

    # Rule 2d — non-negative function values
    if "non-negative" in schema_str and scoring == "maximize":
        diagnostics["reasons"].append(
            "non-negative schema + maximize → nonneg_function_maximize"
        )
        return "nonneg_function_maximize", diagnostics

    # Rule 3 — description-level autocorrelation / autoconvolution
    if (
        "autocorrelation" in desc
        or "autoconvolution" in desc
        or "autoconvolve" in desc
        or "oaconvolve" in verifier
        or "np.convolve" in verifier
    ):
        if scoring == "maximize":
            diagnostics["reasons"].append(
                "autocorrelation/autoconvolution + maximize → nonneg_function_maximize"
            )
            return "nonneg_function_maximize", diagnostics

    # Rule 4 — warm-start fallback
    if top_solutions:
        diagnostics["reasons"].append(
            "no shape pattern matched; top solutions available → warmstart_polish_only"
        )
        return "warmstart_polish_only", diagnostics

    diagnostics["reasons"].append("no pattern matched; unknown")
    return "unknown", diagnostics
