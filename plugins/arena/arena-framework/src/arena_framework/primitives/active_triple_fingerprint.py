"""Active-triple fingerprinting for Heilbronn-style min-area problems.

For a point set where the score is `min_{triple} area(triple) / normalizer`,
the optimum typically has many triples simultaneously attaining the minimum
(equioscillation). The *active count* — how many triples sit within eps of
the minimum — is a basin fingerprint: different local minima have
different active counts even when their scores agree to 1e-10.

Why it is useful
----------------
* Distinguishes basins that share a score to machine precision.
* Locates the *stressed* active set needed by an SLSQP / epigraph polisher.
* Flags when a perturbation crossed a basin boundary vs stayed in-basin.

Usage
-----
>>> from arena_framework.primitives.active_triple_fingerprint import fingerprint
>>> fp = fingerprint(points, normalizer="triangle_sqrt3_over_4",
...                  relative_eps=1e-9)
>>> fp.min_area, fp.active_count, fp.top_triples[:5]
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

import numpy as np

try:
    from scipy.spatial import ConvexHull
except ImportError:  # pragma: no cover
    ConvexHull = None


__all__ = ["Fingerprint", "fingerprint", "triangle_areas"]


@dataclass
class Fingerprint:
    min_area: float
    """Smallest normalized triangle area."""

    normalizer: float
    """The divisor used (bounding triangle area, hull area, or 1)."""

    score: float
    """min_area / normalizer."""

    active_count: int
    """Number of triples within relative_eps of the minimum."""

    active_triples: list[tuple[int, int, int]] = field(default_factory=list)
    """Indices of the active triples, sorted by area."""

    top_triples: list[tuple[tuple[int, int, int], float]] = field(default_factory=list)
    """(indices, area) for the smallest K triples (K = max(active_count, 10))."""

    n_points: int = 0
    relative_eps: float = 0.0
    absolute_eps: float = 0.0

    def summary(self) -> str:
        return (
            f"score={self.score:.18f}  min_area={self.min_area:.3e}  "
            f"active={self.active_count}/{self.n_points*(self.n_points-1)*(self.n_points-2)//6}  "
            f"rel_eps={self.relative_eps:.0e}"
        )


def triangle_areas(points: np.ndarray) -> np.ndarray:
    """Return the flat array of signed-abs triangle areas for every (i<j<k).

    Ordering matches ``itertools.combinations(range(n), 3)``.
    """
    n = len(points)
    combos = list(itertools.combinations(range(n), 3))
    out = np.empty(len(combos), dtype=np.float64)
    for idx, (i, j, k) in enumerate(combos):
        p1, p2, p3 = points[i], points[j], points[k]
        out[idx] = abs(
            p1[0] * (p2[1] - p3[1])
            + p2[0] * (p3[1] - p1[1])
            + p3[0] * (p1[1] - p2[1])
        ) / 2.0
    return out


def _resolve_normalizer(points: np.ndarray, normalizer) -> float:
    if isinstance(normalizer, (int, float)):
        return float(normalizer)
    if normalizer == "triangle_sqrt3_over_4":
        return float(np.sqrt(3.0) / 4.0)
    if normalizer == "unit_square":
        return 1.0
    if normalizer == "convex_hull":
        if ConvexHull is None:
            raise RuntimeError("scipy.spatial.ConvexHull unavailable")
        return float(ConvexHull(points).volume)
    if callable(normalizer):
        return float(normalizer(points))
    raise ValueError(f"Unknown normalizer: {normalizer!r}")


def fingerprint(
    points: Sequence[Sequence[float]],
    *,
    normalizer="triangle_sqrt3_over_4",
    relative_eps: float = 1e-9,
    absolute_eps: float = 0.0,
) -> Fingerprint:
    """Compute the active-triple fingerprint of a point set.

    Parameters
    ----------
    points : (n, 2) array-like
    normalizer : str, float, or callable
        ``"triangle_sqrt3_over_4"`` for heilbronn-triangles (n=11 unit eq. tri.),
        ``"convex_hull"`` for heilbronn-convex,
        ``"unit_square"`` for classical Heilbronn unit square,
        a float to divide directly, or a callable(points)->float.
    relative_eps : float
        A triple is active iff ``area <= min_area * (1 + relative_eps)``.
    absolute_eps : float
        Additional additive tolerance on ``area - min_area``.

    Returns
    -------
    Fingerprint
    """
    pts = np.asarray(points, dtype=np.float64)
    if pts.ndim != 2 or pts.shape[1] != 2:
        raise ValueError(f"points must be (n, 2); got {pts.shape}")

    norm = _resolve_normalizer(pts, normalizer)
    if not np.isfinite(norm) or norm <= 0:
        raise ValueError(f"invalid normalizer value: {norm}")

    areas = triangle_areas(pts)
    combos = list(itertools.combinations(range(len(pts)), 3))

    min_area = float(areas.min())
    threshold = min_area * (1.0 + relative_eps) + absolute_eps

    active_mask = areas <= threshold
    active_idx = np.where(active_mask)[0]
    active_triples = [combos[i] for i in active_idx]
    active_triples.sort(key=lambda t: areas[combos.index(t)])

    # Top-K smallest (for diagnostics, even below active threshold)
    top_k = max(len(active_triples), 10)
    order = np.argsort(areas)[:top_k]
    top_triples = [(combos[i], float(areas[i])) for i in order]

    return Fingerprint(
        min_area=min_area,
        normalizer=norm,
        score=min_area / norm,
        active_count=len(active_triples),
        active_triples=active_triples,
        top_triples=top_triples,
        n_points=len(pts),
        relative_eps=relative_eps,
        absolute_eps=absolute_eps,
    )


def describe_active_set(fp: Fingerprint, points: Sequence[Sequence[float]]) -> dict:
    """Summarize which points participate in the active set.

    Returns a dict with per-point participation counts and the active-set
    Jacobian rank heuristic (number of unique triples / number of unique
    points involved).
    """
    pts = np.asarray(points, dtype=np.float64)
    involved = np.zeros(len(pts), dtype=int)
    for i, j, k in fp.active_triples:
        involved[i] += 1
        involved[j] += 1
        involved[k] += 1
    return {
        "n_active_triples": fp.active_count,
        "n_points_involved": int((involved > 0).sum()),
        "per_point_participation": involved.tolist(),
        "max_point_participation": int(involved.max(initial=0)),
        "min_involved_participation": int(involved[involved > 0].min()) if (involved > 0).any() else 0,
    }
