#!/usr/bin/env python3
"""Three-method verification harness.

Runs up to three independent score functions and decides whether they agree.
Designed for arena-style solutions where a single evaluator might disagree
with an exact-arithmetic or alternate implementation.

Public API:
    tri_verify(float_fn, mpmath_fn, extra_fn, *, tolerance=1e-9) -> dict
"""
from __future__ import annotations

from typing import Callable, Optional


class VerificationDisagreementError(RuntimeError):
    """Raised (optionally by callers) when tri_verify reports 'disagree' status."""


ScoreFn = Optional[Callable[[], float]]


def _collect_scores(
    float_fn: ScoreFn,
    mpmath_fn: ScoreFn,
    extra_fn: ScoreFn,
) -> dict[str, float]:
    scores: dict[str, float] = {}
    if float_fn is not None:
        scores["float64"] = float(float_fn())
    if mpmath_fn is not None:
        scores["mpmath"] = float(mpmath_fn())
    if extra_fn is not None:
        scores["extra"] = float(extra_fn())
    return scores


def _max_agreeing_cluster(values: list[float], tolerance: float) -> tuple[int, float]:
    """Return (size, mean) of the largest cluster of values within `tolerance`
    of each other (pairwise). Ties broken by mean of the first maximal cluster."""
    if not values:
        return (0, 0.0)
    best_size = 1
    best_mean = values[0]
    for i, anchor in enumerate(values):
        cluster = [v for v in values if abs(v - anchor) <= tolerance]
        if len(cluster) > best_size:
            best_size = len(cluster)
            best_mean = sum(cluster) / len(cluster)
    return (best_size, best_mean)


def tri_verify(
    float_fn: ScoreFn,
    mpmath_fn: ScoreFn,
    extra_fn: ScoreFn,
    *,
    tolerance: float = 1e-9,
) -> dict:
    """Run 2 or 3 verification methods and summarise agreement.

    Returns:
        dict with keys:
            status           : "pass" | "disagree" | "empty"
            methods_run      : int (number of callables supplied)
            methods_agree    : int (size of the largest consensus cluster)
            scores           : per-method scores (keys: float64 / mpmath / extra)
            consensus_score  : mean of the consensus cluster (only if status == "pass")
            tolerance        : the tolerance used

    Rules:
        - With 3 methods, pass requires all 3 within tolerance of each other.
        - With 2 methods, pass requires both within tolerance.
        - Any missing method is simply not run; at least 1 must be supplied.
    """
    scores = _collect_scores(float_fn, mpmath_fn, extra_fn)
    methods_run = len(scores)

    if methods_run == 0:
        return {
            "status": "empty",
            "methods_run": 0,
            "methods_agree": 0,
            "scores": {},
            "tolerance": tolerance,
        }

    values = list(scores.values())
    cluster_size, cluster_mean = _max_agreeing_cluster(values, tolerance)

    result = {
        "methods_run": methods_run,
        "methods_agree": cluster_size,
        "scores": scores,
        "tolerance": tolerance,
    }

    if cluster_size == methods_run:
        result["status"] = "pass"
        result["consensus_score"] = cluster_mean
    else:
        result["status"] = "disagree"
        # Still report the strongest cluster's mean as a pointer to "best guess".
        result["best_cluster_score"] = cluster_mean

    return result


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    import json
    out = tri_verify(
        lambda: 0.123456789,
        lambda: 0.123456790,
        lambda: 0.123456788,
    )
    print(json.dumps(out, indent=2))
