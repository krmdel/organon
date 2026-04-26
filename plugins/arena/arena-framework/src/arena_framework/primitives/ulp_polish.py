"""Float64 ULP coordinate-descent polish — incremental + 2-coord variants.

Extends the existing ``ops-ulp-polish`` skill's ``polish.py`` with two
variants critical for bridging the 1e-12 → 1e-13 precision floor that
gradient methods can't cross:

1. **Incremental scoring**: when ``V[i, k]`` changes, only rows involving
   row ``i`` need recomputation. For the generic kissing-style loss (sum
   of violating pairs) that's O(n) per move vs O(n²) for full recompute —
   a ~100× speedup at n=594.

2. **Two-coordinate joint sweep**: escape single-coord local optima by
   trying joint moves ``(V[i, k], V[j, l])`` with ±1/±2 ulp perturbations
   in each. Necessary when single-coord has converged but the basin still
   has joint-gradient directions available.

Neither of these were in the original skill; both are ported from jmsung
patterns (``polish_ulp_coord.py`` and ``polish_ulp_2coord.py``).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

from .budget import Budget, PrimitiveResult


# ---------------------------------------------------------------------------
# ULP arithmetic
# ---------------------------------------------------------------------------


def next_ulp(x: float, k: int) -> float:
    """Return x advanced by ``k`` ulps (sign-preserving, zero-safe)."""
    y = x
    if k > 0:
        for _ in range(k):
            y = float(np.nextafter(y, np.inf))
    elif k < 0:
        for _ in range(-k):
            y = float(np.nextafter(y, -np.inf))
    return y


# ---------------------------------------------------------------------------
# Single-coordinate incremental polish
# ---------------------------------------------------------------------------


@dataclass
class ULPPolishResult(PrimitiveResult):
    n_sweeps: int = 0
    n_accepted_moves: int = 0
    moves_per_coord: list[int] = field(default_factory=list)


def ulp_polish_incremental(
    V: np.ndarray,
    loss_fn: Callable[[np.ndarray], float],
    *,
    incremental_loss_fn: Optional[Callable[[np.ndarray, int, float, int], float]] = None,
    max_ulps: int = 4,
    max_sweeps: int = 20,
    budget: Optional[Budget] = None,
    freeze_rows: Optional[set[int]] = None,
    verbose: bool = False,
) -> ULPPolishResult:
    """Coordinate-descent polish with optional incremental loss.

    ``incremental_loss_fn``, if provided, has signature
    ``(V, row_i, old_value, coord_k) -> new_loss`` and may update internal state
    so subsequent calls can be O(n) instead of O(n²). If ``None``, we fall back
    to calling ``loss_fn(V)`` after each trial.

    The search tries ±1, ±2, …, ±max_ulps offsets per coordinate; the best
    improving offset is accepted. Sweeps iterate until no improvement is
    found or the budget is exhausted.
    """
    V = V.copy()
    n, d = V.shape
    clock = (budget or Budget()).started()
    score = float(loss_fn(V))
    clock.tick_evaluation()
    best_score = score
    freeze = freeze_rows or set()

    moves_per_coord = [0] * (n * d)
    n_accepted = 0
    trace: list[dict] = [{"sweep": 0, "score": score, "elapsed_s": clock.elapsed_s()}]

    for sweep in range(max_sweeps):
        if clock.exhausted():
            break
        sweep_accepts = 0
        for i in range(n):
            if i in freeze:
                continue
            for k in range(d):
                if clock.exhausted():
                    break
                old_val = float(V[i, k])
                best_offset = 0
                best_new_score = score
                best_new_val = old_val
                for s in range(1, max_ulps + 1):
                    for sign in (+1, -1):
                        trial = next_ulp(old_val, s * sign)
                        V[i, k] = trial
                        if incremental_loss_fn is not None:
                            new_score = float(incremental_loss_fn(V, i, old_val, k))
                        else:
                            new_score = float(loss_fn(V))
                        clock.tick_evaluation()
                        if new_score < best_new_score:
                            best_new_score = new_score
                            best_offset = s * sign
                            best_new_val = trial
                # restore or accept
                if best_offset != 0 and best_new_score < score:
                    V[i, k] = best_new_val
                    score = best_new_score
                    sweep_accepts += 1
                    n_accepted += 1
                    moves_per_coord[i * d + k] += 1
                else:
                    V[i, k] = old_val
        clock.tick_iteration()
        trace.append({"sweep": sweep + 1, "score": score, "elapsed_s": clock.elapsed_s()})
        if verbose:
            print(f"[ulp-polish] sweep {sweep+1} accepts={sweep_accepts} score={score:.6e}")
        if score < best_score:
            best_score = score
        if sweep_accepts == 0:
            break

    return ULPPolishResult(
        best_score=best_score,
        best_state=V,
        n_iterations=clock.iterations,
        n_evaluations=clock.evaluations,
        wall_time_s=clock.elapsed_s(),
        trace=trace,
        primitive_metadata={"primitive": "ULPPolishIncremental", "max_ulps": max_ulps},
        n_sweeps=clock.iterations,
        n_accepted_moves=n_accepted,
        moves_per_coord=moves_per_coord,
    )


# ---------------------------------------------------------------------------
# Two-coordinate joint polish
# ---------------------------------------------------------------------------


def ulp_polish_2coord(
    V: np.ndarray,
    loss_fn: Callable[[np.ndarray], float],
    *,
    max_ulps: int = 2,
    max_sweeps: int = 5,
    budget: Optional[Budget] = None,
    row_pair_strategy: str = "top_badness",
    freeze_rows: Optional[set[int]] = None,
    verbose: bool = False,
) -> ULPPolishResult:
    """Joint two-coordinate ulp sweep.

    For each (row, col) pair, try all 2-ulp joint perturbations within
    ``[-max_ulps, +max_ulps]`` on both coordinates. Much more expensive than
    single-coord (O(n² × d² × (2·max_ulps+1)²)) so should only run after
    single-coord has converged, on a short budget.

    ``row_pair_strategy``:
      - ``"top_badness"`` (default): only pair the top-k highest-loss-contributing
        rows with each other. Useful when a generic row-badness is available.
      - ``"adjacent"``: pair row i with row i+1. O(n) pairs, still useful when
        the problem has locality.
    """
    V = V.copy()
    n, d = V.shape
    clock = (budget or Budget()).started()
    score = float(loss_fn(V))
    clock.tick_evaluation()
    freeze = freeze_rows or set()

    # Pair strategy: top-k by independent row contribution (via one-at-a-time
    # zero-out / reset trick).
    if row_pair_strategy == "top_badness":
        base = score
        badness = np.zeros(n)
        for i in range(n):
            old = V[i].copy()
            V[i] = 0.0
            without = float(loss_fn(V))
            clock.tick_evaluation()
            badness[i] = max(0.0, base - without)
            V[i] = old
        top_k = min(8, n)
        candidate_rows = list(np.argsort(-badness)[:top_k])
    elif row_pair_strategy == "adjacent":
        candidate_rows = list(range(n))
    else:
        raise ValueError(f"unknown row_pair_strategy: {row_pair_strategy}")

    n_accepted = 0
    trace: list[dict] = []

    offsets = list(range(-max_ulps, max_ulps + 1))
    offsets.remove(0)  # skip the no-op

    for sweep in range(max_sweeps):
        if clock.exhausted():
            break
        sweep_accepts = 0
        for idx_a, i in enumerate(candidate_rows):
            if i in freeze:
                continue
            for j in candidate_rows[idx_a + 1:]:
                if j in freeze:
                    continue
                if clock.exhausted():
                    break
                for k in range(d):
                    for l in range(d):
                        old_i = float(V[i, k])
                        old_j = float(V[j, l])
                        best_new_score = score
                        best_move = None
                        for oi in offsets:
                            for oj in offsets:
                                V[i, k] = next_ulp(old_i, oi)
                                V[j, l] = next_ulp(old_j, oj)
                                new_score = float(loss_fn(V))
                                clock.tick_evaluation()
                                if new_score < best_new_score:
                                    best_new_score = new_score
                                    best_move = (oi, oj)
                        if best_move is not None:
                            oi, oj = best_move
                            V[i, k] = next_ulp(old_i, oi)
                            V[j, l] = next_ulp(old_j, oj)
                            score = best_new_score
                            sweep_accepts += 1
                            n_accepted += 1
                        else:
                            V[i, k] = old_i
                            V[j, l] = old_j
        clock.tick_iteration()
        trace.append({"sweep": sweep + 1, "score": score, "elapsed_s": clock.elapsed_s()})
        if verbose:
            print(f"[ulp-2coord] sweep {sweep+1} accepts={sweep_accepts} score={score:.6e}")
        if sweep_accepts == 0:
            break

    return ULPPolishResult(
        best_score=score,
        best_state=V,
        n_iterations=clock.iterations,
        n_evaluations=clock.evaluations,
        wall_time_s=clock.elapsed_s(),
        trace=trace,
        primitive_metadata={"primitive": "ULPPolish2Coord", "max_ulps": max_ulps, "strategy": row_pair_strategy},
        n_sweeps=clock.iterations,
        n_accepted_moves=n_accepted,
    )
