#!/usr/bin/env python3
"""Parallel-tempering simulated annealing (PT-SA).

Generic optimizer for combinatorial and continuous problems where the loss
landscape is rugged, multi-modal, and gradient descent stalls. N replicas run
independent Metropolis-Hastings chains at a geometric temperature ladder; every
`exchange_every` iterations, adjacent-temperature replicas attempt a state swap
under the Metropolis-Hastings replica-exchange criterion

    p(i <-> j) = min(1, exp((beta_i - beta_j) * (E_j - E_i)))

Optional speedups:
  - `contribution_fn(state) -> ndarray[n]` biases proposed-move coordinate
    selection toward elements whose contribution to the total loss is largest
    (the kissing-number trick: high-overlap rows benefit most from movement).
  - `delta_fn(state, change) -> float` bypasses the full O(n) loss recompute
    when a move only affects a local contribution (the jmsung/einstein 730x
    speedup for kissing).

Usage (library):

    from pt_sa import parallel_tempering_sa
    result = parallel_tempering_sa(initial_state, loss_fn, propose_move_fn,
                                   n_replicas=8, t_min=1e-12, t_max=1e-4,
                                   max_steps=10_000, seed=42)

Returned dict keys: best_state, best_loss, replicas, temperatures, history,
exchange_attempts, exchange_accepts.
"""
from __future__ import annotations

import argparse
import math
import sys
from typing import Any, Callable, Optional

import numpy as np


# ============================================================= temperature ladder

def temperature_schedule(t_min: float, t_max: float, n: int) -> np.ndarray:
    """Geometric ladder T_i = t_min * (t_max/t_min)**(i/(n-1)).

    Geometric ladders keep exchange acceptance roughly uniform across neighbors
    (Hukushima-Nemoto 1996 / Kofke 2002).
    """
    if n < 1:
        raise ValueError("n must be >= 1")
    if t_min <= 0:
        raise ValueError("t_min must be > 0")
    if t_max < t_min:
        raise ValueError("t_max must be >= t_min")
    if n == 1:
        return np.array([t_min], dtype=np.float64)
    ratio = t_max / t_min
    exps = np.arange(n, dtype=np.float64) / (n - 1)
    return t_min * (ratio ** exps)


# ============================================================= exchange criterion

def attempt_exchange(E_A: float, E_B: float, beta_A: float, beta_B: float, rng) -> bool:
    """Metropolis-Hastings replica-exchange accept/reject.

    delta = (beta_A - beta_B) * (E_B - E_A)
    accept with prob min(1, exp(delta)).

    `rng` must expose a ``.random() -> float in [0,1)`` method (numpy Generator
    does).
    """
    delta = (beta_A - beta_B) * (E_B - E_A)
    if delta >= 0.0:
        return True
    # exp of potentially large negative -> 0
    try:
        p = math.exp(delta)
    except OverflowError:
        p = 0.0
    return bool(rng.random() < p)


# ============================================================= weighted sampling

def weighted_choice(weights: np.ndarray, rng) -> int:
    """Pick an index proportional to non-negative weights. Fallback: uniform."""
    w = np.asarray(weights, dtype=np.float64)
    if w.size == 0:
        raise ValueError("weights must be non-empty")
    # Clip negatives and handle NaN -> uniform.
    w = np.where(np.isfinite(w) & (w > 0.0), w, 0.0)
    total = float(w.sum())
    if total <= 0.0:
        return int(rng.integers(0, w.size))
    probs = w / total
    # Use searchsorted on cumulative — more stable than rng.choice for weighted.
    cdf = np.cumsum(probs)
    u = rng.random()
    idx = int(np.searchsorted(cdf, u, side="right"))
    if idx >= w.size:
        idx = w.size - 1
    return idx


# ============================================================= main driver

def _safe_loss(loss_fn: Callable, state: np.ndarray) -> float:
    val = float(loss_fn(state))
    return val


def parallel_tempering_sa(
    initial_state,
    loss_fn: Callable,
    propose_move_fn: Callable,
    *,
    delta_fn: Optional[Callable] = None,
    contribution_fn: Optional[Callable] = None,
    n_replicas: int = 8,
    t_min: float = 1e-12,
    t_max: float = 1e-4,
    max_steps: int = 10_000,
    exchange_every: int = 10,
    seed: Optional[int] = None,
    verbose: bool = False,
) -> dict:
    """Run parallel-tempering SA. See module docstring for semantics.

    propose_move_fn signature: ``(state, rng, idx=None) -> (new_state, change)``
    When ``contribution_fn`` is provided the driver samples an ``idx`` with
    probability proportional to per-element contribution and passes it to
    ``propose_move_fn``; otherwise ``idx=None`` and the move selects its own
    coordinate.
    """
    # --- validate ---
    state0 = np.asarray(initial_state, dtype=np.float64)
    if state0.size == 0:
        raise ValueError("initial_state must be non-empty")
    if n_replicas < 1:
        raise ValueError("n_replicas must be >= 1")
    if max_steps < 1:
        raise ValueError("max_steps must be >= 1")
    if exchange_every < 1:
        raise ValueError("exchange_every must be >= 1")

    temps = temperature_schedule(t_min, t_max, n_replicas)
    betas = 1.0 / temps
    rng = np.random.default_rng(seed)

    # One RNG per replica for reproducibility independence, one for exchanges.
    replica_rngs = [np.random.default_rng(rng.integers(0, 2**63 - 1))
                    for _ in range(n_replicas)]
    exchange_rng = np.random.default_rng(rng.integers(0, 2**63 - 1))

    # --- init replicas ---
    states = [state0.copy() for _ in range(n_replicas)]
    energies = [_safe_loss(loss_fn, s) for s in states]
    best_states = [s.copy() for s in states]
    best_losses = list(energies)

    # NaN guard on init: if initial loss is NaN, treat as +inf so anything improves.
    energies = [math.inf if math.isnan(e) else e for e in energies]
    best_losses = [math.inf if math.isnan(e) else e for e in best_losses]

    exchange_attempts = 0
    exchange_accepts = 0

    per_replica_steps = [0] * n_replicas

    # --- main loop ---
    for step in range(max_steps):
        for r in range(n_replicas):
            rrng = replica_rngs[r]

            # Pick an index (contribution-weighted) if configured.
            idx = None
            if contribution_fn is not None:
                contrib = np.asarray(contribution_fn(states[r]), dtype=np.float64)
                idx = weighted_choice(contrib, rrng)

            new_state, change = propose_move_fn(states[r], rrng, idx=idx) \
                if _accepts_idx_kwarg(propose_move_fn) \
                else propose_move_fn(states[r], rrng)

            # Acceptance delta: prefer delta_fn, else recompute full loss.
            if delta_fn is not None:
                try:
                    d_e = float(delta_fn(states[r], change))
                except Exception as exc:  # pragma: no cover - defensive
                    if verbose:
                        print(f"[pt-sa] delta_fn raised {exc!r}; falling back to loss_fn",
                              file=sys.stderr)
                    d_e = _safe_loss(loss_fn, new_state) - energies[r]
                new_E = energies[r] + d_e
            else:
                new_E = _safe_loss(loss_fn, new_state)
                d_e = new_E - energies[r]

            # NaN-guard: reject NaN moves.
            if math.isnan(new_E):
                per_replica_steps[r] += 1
                continue

            # Metropolis accept.
            if d_e <= 0.0:
                accept = True
            else:
                try:
                    p = math.exp(-betas[r] * d_e)
                except OverflowError:
                    p = 0.0
                accept = bool(rrng.random() < p)

            if accept:
                states[r] = new_state
                energies[r] = new_E
                if new_E < best_losses[r]:
                    best_losses[r] = new_E
                    best_states[r] = new_state.copy()

            per_replica_steps[r] += 1

        # Periodic exchange pass.
        if n_replicas > 1 and ((step + 1) % exchange_every == 0):
            # Alternate even/odd pairs to avoid biased ordering.
            start = 0 if ((step + 1) // exchange_every) % 2 == 0 else 1
            for i in range(start, n_replicas - 1, 2):
                j = i + 1
                exchange_attempts += 1
                if attempt_exchange(energies[i], energies[j],
                                    betas[i], betas[j], exchange_rng):
                    states[i], states[j] = states[j], states[i]
                    energies[i], energies[j] = energies[j], energies[i]
                    # per-replica-best trackers track by *replica slot*, not state
                    # identity — update if the swapped-in energy beats the slot's best.
                    if energies[i] < best_losses[i]:
                        best_losses[i] = energies[i]
                        best_states[i] = states[i].copy()
                    if energies[j] < best_losses[j]:
                        best_losses[j] = energies[j]
                        best_states[j] = states[j].copy()
                    exchange_accepts += 1

        if verbose and (step + 1) % max(1, max_steps // 10) == 0:
            print(f"[pt-sa] step={step+1}/{max_steps}  "
                  f"best={min(best_losses):.6e}  "
                  f"exch={exchange_accepts}/{exchange_attempts}", flush=True)

    # Package the result.
    best_idx = int(np.argmin(best_losses))
    replica_summaries = [
        {"temperature": float(temps[r]),
         "final_loss": float(energies[r]),
         "best_loss": float(best_losses[r])}
        for r in range(n_replicas)
    ]
    history = [{"replica": r, "steps": per_replica_steps[r]}
               for r in range(n_replicas)]

    return {
        "best_state": best_states[best_idx].copy(),
        "best_loss": float(best_losses[best_idx]),
        "replicas": replica_summaries,
        "temperatures": temps.tolist(),
        "history": history,
        "exchange_attempts": exchange_attempts,
        "exchange_accepts": exchange_accepts,
    }


def _accepts_idx_kwarg(fn: Callable) -> bool:
    """Return True iff `fn` has an `idx` keyword parameter."""
    try:
        import inspect
        sig = inspect.signature(fn)
        return "idx" in sig.parameters
    except (TypeError, ValueError):  # pragma: no cover
        return False


# ============================================================= CLI

def _cli() -> None:  # pragma: no cover - thin wrapper
    ap = argparse.ArgumentParser(description="Parallel-tempering SA driver.")
    ap.add_argument("--help-only", action="store_true",
                    help="This script is a library; import parallel_tempering_sa.")
    args = ap.parse_args()
    if args.help_only:
        print(__doc__)


if __name__ == "__main__":  # pragma: no cover
    _cli()
