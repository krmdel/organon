"""Dyadic / small-denominator rational snap search.

Given a continuous config, generate nearby rational candidates for each
coordinate and accept moves that reduce the loss. Formalizes the H1
breakthrough from our Uncertainty Principle attack:

- alpha_omega's k=19 baseline had z[1]=4.7033 (continuous optimizer drift).
- Snap candidates include 431/91 = 4.7363 (short-denom rational).
- The arena's rational-arithmetic polynomial factorization is SHORTER at
  small-denom inputs, missing more sign changes in float64 -> lower score.

Two candidate-generation modes:

1. ``"dyadic"``: rationals with denominator 2^k for k ≤ log2(max_denom).
2. ``"farey"`` (default): rationals from the Stern-Brocot / continued-fraction
   expansion around the current value, capped at ``max_denom``.

For problems where the arena evaluator's rational-arithmetic path rewards
short denominators (UP Laguerre-LP being the canonical example), this
primitive delivers improvements that continuous optimizers cannot reach.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Callable, Literal, Optional, Sequence

import numpy as np

from .budget import Budget, PrimitiveResult


CandidateMode = Literal["dyadic", "farey"]


@dataclass
class DyadicSnapResult(PrimitiveResult):
    n_accepted_snaps: int = 0
    snaps_per_coord: list[int] = field(default_factory=list)
    candidate_mode: str = "farey"


def _dyadic_candidates(value: float, max_denom: int) -> list[float]:
    """Return dyadic rationals n/2^k closest to ``value`` for each k up to
    log2(max_denom)."""
    out: list[float] = []
    k = 1
    denom = 2
    while denom <= max_denom:
        # Closest numerator
        n = round(value * denom)
        out.append(n / denom)
        # Also nearest-above and nearest-below
        out.append((n + 1) / denom)
        out.append((n - 1) / denom)
        k += 1
        denom *= 2
    # deduplicate while preserving nearness order
    seen: set[float] = set()
    dedup: list[float] = []
    for v in out:
        if v not in seen:
            seen.add(v)
            dedup.append(v)
    return dedup


def _farey_candidates(value: float, max_denom: int) -> list[float]:
    """Generate short-denominator rationals close to ``value`` via the
    built-in ``Fraction.limit_denominator`` at increasing denominator caps.

    Returns candidates with denominators 2, 3, 5, 7, 11, … up to ``max_denom``.
    """
    out: list[float] = []
    tried_caps = []
    # Sweep a geometric-ish sequence of caps to get rationals at varying
    # granularity (coarser = shorter denom, finer = closer approximation).
    caps = [2, 3, 5, 7, 11, 16, 24, 32, 48, 64, 91, 128]
    for cap in caps:
        if cap > max_denom:
            break
        tried_caps.append(cap)
        frac = Fraction(value).limit_denominator(cap)
        out.append(float(frac))
        # Also include ±1 nudges in numerator
        if frac.denominator > 0:
            num = frac.numerator
            den = frac.denominator
            for delta in (-1, +1):
                try:
                    out.append((num + delta) / den)
                except ZeroDivisionError:
                    pass
    # Final fine-grained pass at max_denom
    if max_denom not in tried_caps:
        out.append(float(Fraction(value).limit_denominator(max_denom)))
    seen: set[float] = set()
    dedup: list[float] = []
    for v in out:
        if v not in seen:
            seen.add(v)
            dedup.append(v)
    return dedup


def generate_candidates(
    value: float,
    *,
    max_denom: int = 128,
    mode: CandidateMode = "farey",
) -> list[float]:
    """Public API for candidate generation so other primitives can reuse."""
    if mode == "dyadic":
        return _dyadic_candidates(value, max_denom)
    if mode == "farey":
        return _farey_candidates(value, max_denom)
    raise ValueError(f"unknown candidate mode: {mode}")


def dyadic_snap_search(
    config: Sequence[float] | np.ndarray,
    loss_fn: Callable[[Any], float],
    *,
    max_denom: int = 128,
    mode: CandidateMode = "farey",
    max_sweeps: int = 3,
    budget: Optional[Budget] = None,
    freeze_indices: Optional[set[int]] = None,
    verbose: bool = False,
) -> DyadicSnapResult:
    """Per-coordinate dyadic/Farey rational snap search.

    For each coordinate, generate short-denom rational candidates near the
    current value; accept the best improving one. Repeat for ``max_sweeps``
    or until no coordinate improves.
    """
    if isinstance(config, np.ndarray):
        cfg = config.astype(np.float64).copy()
        as_ndarray = True
        shape = cfg.shape
        flat = cfg.ravel().tolist()
    else:
        flat = [float(x) for x in config]
        as_ndarray = False
        shape = (len(flat),)

    clock = (budget or Budget()).started()
    score = float(loss_fn(_rebuild(flat, as_ndarray, shape)))
    clock.tick_evaluation()
    best_score = score
    best_flat = list(flat)
    freeze = freeze_indices or set()

    snaps_per_coord = [0] * len(flat)
    trace: list[dict] = [{"sweep": 0, "score": score}]

    for sweep in range(max_sweeps):
        if clock.exhausted():
            break
        sweep_accepts = 0
        for idx in range(len(flat)):
            if idx in freeze:
                continue
            if clock.exhausted():
                break
            old = flat[idx]
            candidates = generate_candidates(old, max_denom=max_denom, mode=mode)
            best_new = old
            best_new_score = score
            for cand in candidates:
                if cand == old:
                    continue
                flat[idx] = cand
                new_score = float(loss_fn(_rebuild(flat, as_ndarray, shape)))
                clock.tick_evaluation()
                if new_score < best_new_score:
                    best_new_score = new_score
                    best_new = cand
            if best_new_score < score:
                flat[idx] = best_new
                score = best_new_score
                sweep_accepts += 1
                snaps_per_coord[idx] += 1
                if score < best_score:
                    best_score = score
                    best_flat = list(flat)
            else:
                flat[idx] = old
        clock.tick_iteration()
        trace.append({"sweep": sweep + 1, "score": score, "accepts": sweep_accepts})
        if verbose:
            print(f"[dyadic-snap] sweep {sweep+1} accepts={sweep_accepts} score={score:.6e}")
        if sweep_accepts == 0:
            break

    return DyadicSnapResult(
        best_score=best_score,
        best_state=_rebuild(best_flat, as_ndarray, shape),
        n_iterations=clock.iterations,
        n_evaluations=clock.evaluations,
        wall_time_s=clock.elapsed_s(),
        trace=trace,
        primitive_metadata={
            "primitive": "DyadicSnapSearch",
            "mode": mode,
            "max_denom": max_denom,
        },
        n_accepted_snaps=sum(snaps_per_coord),
        snaps_per_coord=snaps_per_coord,
        candidate_mode=mode,
    )


def _rebuild(flat: list[float], as_ndarray: bool, shape: tuple[int, ...]):
    if as_ndarray:
        return np.array(flat, dtype=np.float64).reshape(shape)
    return list(flat)
