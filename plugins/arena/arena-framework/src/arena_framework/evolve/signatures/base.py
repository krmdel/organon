"""Signature protocol + discretization helper.

A signature is a callable that maps a solution ``state`` to a feature tuple.
The feature tuple is consumed by ``ProgramDB.cluster_key_fn`` which buckets
programs for MAP-Elites diversity preservation.

Continuous features must be discretized before they form usable cluster
keys — otherwise every program gets its own cluster and the DB degenerates
to a single flat population. Use ``discretize_features`` to bin each
component by a per-axis resolution.
"""

from __future__ import annotations

from typing import Any, Protocol, Sequence


class Signature(Protocol):
    """Maps a candidate solution state to a feature tuple."""

    def extract_features(self, state: Any) -> tuple: ...


def discretize_features(
    features: Sequence[float],
    *,
    resolutions: Sequence[float],
) -> tuple:
    """Bin each continuous feature by dividing by its resolution + flooring.

    Args:
        features: the raw feature vector.
        resolutions: one bin-width per feature. Must match ``features`` in
            length. Zero or negative resolutions are treated as 1 (no
            binning).

    Returns:
        A tuple of ints — safe to use as a dict key, compares equal for
        programs in the same MAP-Elites cell.
    """
    if len(features) != len(resolutions):
        raise ValueError(
            f"features ({len(features)}) and resolutions ({len(resolutions)}) "
            "must have same length"
        )
    out: list[int] = []
    for f, r in zip(features, resolutions):
        r_eff = float(r) if r and r > 0 else 1.0
        out.append(int(float(f) // r_eff))
    return tuple(out)
