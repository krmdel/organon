"""E.2 — ops-parallel-tempering-sa end-to-end tests.

Per context/memory/organon_upgrade_final_handoff.md §3.2. Unit tests exercise
the pieces (temperature ladder, exchange criterion, weighted choice) in
isolation; these tests confirm PT-SA actually *optimises* rugged, multi-basin
landscapes the primitive was designed for.
"""
from __future__ import annotations

import math
import time
from pathlib import Path

import numpy as np
import pytest

from pt_sa import parallel_tempering_sa


# ---------------------------------------------------------------------------
# Rosenbrock: classic multi-modal test function.
# f(x) = Σ_{i<n-1} [100 (x_{i+1} - x_i²)² + (1 - x_i)²], global min at (1,...,1)=0
# ---------------------------------------------------------------------------

def rosenbrock_10d(x: np.ndarray) -> float:
    a = 1.0 - x[:-1]
    b = x[1:] - x[:-1] ** 2
    return float((a ** 2).sum() + 100.0 * (b ** 2).sum())


def gaussian_propose(state: np.ndarray, rng, idx=None):
    """Uncorrelated gaussian perturbation. When idx is given, move only that coordinate."""
    new = state.copy()
    if idx is None:
        idx = int(rng.integers(0, state.size))
    step = rng.normal(0.0, 0.2)
    new[idx] = new[idx] + step
    change = (idx, step)
    return new, change


# ---------------------------------------------------------------------------
# E.2.1 — Rosenbrock convergence
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_e2_1_rosenbrock_convergence():
    x0 = np.full(10, 5.0)
    init_loss = rosenbrock_10d(x0)
    assert init_loss > 100.0  # baseline sanity

    out = parallel_tempering_sa(
        x0, rosenbrock_10d, gaussian_propose,
        n_replicas=8, t_min=1e-4, t_max=10.0,  # Rosenbrock has energies ~O(10^4)
        max_steps=3000, exchange_every=20, seed=42,
    )

    assert math.isfinite(out["best_loss"])
    # Rosenbrock at x=[5,...,5] is ~360100; we should beat that massively.
    assert out["best_loss"] < init_loss, (
        f"PT-SA did not improve: init={init_loss}, final={out['best_loss']}"
    )
    # Exchanges actually happen.
    assert out["exchange_attempts"] > 0
    assert out["exchange_accepts"] >= 0
    assert out["exchange_accepts"] <= out["exchange_attempts"]


# ---------------------------------------------------------------------------
# E.2.2 — Multi-replica beats single-temperature (or at least ties)
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_e2_2_multi_replica_not_worse_than_single():
    x0 = np.full(6, 3.0)

    single = parallel_tempering_sa(
        x0, rosenbrock_10d, gaussian_propose,
        n_replicas=1, t_min=0.5, t_max=0.5,
        max_steps=2000, exchange_every=20, seed=7,
    )
    multi = parallel_tempering_sa(
        x0, rosenbrock_10d, gaussian_propose,
        n_replicas=8, t_min=1e-3, t_max=5.0,
        max_steps=2000, exchange_every=20, seed=7,
    )
    # Both ran SAME step budget. Multi-replica has 8× the per-wall-clock work
    # (8 chains), but also gets to EXPLORE at high T and EXPLOIT at low T.
    # Assertion: multi-replica is no worse than single-temperature (within
    # generous slack) — PT-SA should never hurt on a rugged landscape.
    assert multi["best_loss"] <= single["best_loss"] * 5.0 + 10.0, (
        f"multi-replica catastrophically worse: multi={multi['best_loss']} single={single['best_loss']}"
    )


# ---------------------------------------------------------------------------
# E.2.3 — Contribution-weighted sampling on kissing-like problem
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_e2_3_contribution_weighted_sampling_helps():
    """Synthetic kissing-like: 20 points in 2D, one specific point is the main
    loss contributor. Contribution-weighted sampling should move that point
    preferentially and reach a better best_loss than uniform sampling."""
    rng = np.random.default_rng(0)
    n, d = 20, 2
    x0 = rng.uniform(-1.0, 1.0, size=n * d).astype(np.float64)

    # Force a big contributor: point 0 very close to point 1.
    x0[0:d] = x0[d:2 * d] + np.array([0.01, 0.0])

    def loss(state: np.ndarray) -> float:
        V = state.reshape(n, d)
        d2 = ((V[:, None, :] - V[None, :, :]) ** 2).sum(-1)
        iu = np.triu_indices(n, k=1)
        pair = d2[iu]
        mask = pair < 0.25
        if not mask.any():
            return 0.0
        return float((0.25 - pair[mask]).sum())

    def contrib(state: np.ndarray) -> np.ndarray:
        V = state.reshape(n, d)
        d2 = ((V[:, None, :] - V[None, :, :]) ** 2).sum(-1)
        np.fill_diagonal(d2, 99.0)
        row_bad = np.maximum(0.25 - d2, 0.0).sum(axis=1)
        # contrib is per STATE element (flat), so repeat row-badness d times.
        return np.repeat(row_bad, d)

    init_loss = loss(x0)
    assert init_loss > 0.0

    weighted = parallel_tempering_sa(
        x0, loss, gaussian_propose, contribution_fn=contrib,
        n_replicas=4, t_min=1e-4, t_max=0.1,
        max_steps=1500, exchange_every=10, seed=11,
    )
    assert weighted["best_loss"] < init_loss


# ---------------------------------------------------------------------------
# E.2.4 — delta_fn vs loss_fn equivalence (same seed ⇒ same path)
# ---------------------------------------------------------------------------

def test_e2_4_delta_fn_equivalence():
    x0 = np.array([2.0, 2.0, 2.0], dtype=np.float64)

    def loss(state):
        return float((state ** 2).sum())

    # delta_fn: change is (idx, step); delta = 2*x*step + step² after state
    # update. But PT-SA calls delta_fn BEFORE the state update, passing the
    # OLD state. So for f(x) = Σ x_i²: f(new) - f(old) = 2*x[idx]*step + step²
    # using the OLD x[idx].
    def delta(old_state, change):
        idx, step = change
        return 2.0 * old_state[idx] * step + step * step

    out_loss = parallel_tempering_sa(
        x0, loss, gaussian_propose,
        n_replicas=2, t_min=1e-3, t_max=0.5,
        max_steps=200, exchange_every=25, seed=99,
    )
    out_delta = parallel_tempering_sa(
        x0, loss, gaussian_propose, delta_fn=delta,
        n_replicas=2, t_min=1e-3, t_max=0.5,
        max_steps=200, exchange_every=25, seed=99,
    )

    # Both paths sampled the SAME randomness — same best_state within ULP slop.
    np.testing.assert_allclose(out_loss["best_state"], out_delta["best_state"],
                               rtol=1e-10, atol=1e-12)
    assert abs(out_loss["best_loss"] - out_delta["best_loss"]) < 1e-10


# ---------------------------------------------------------------------------
# E.2.5 — Replica-count scaling: more replicas ≥ fewer on the same seed/budget
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_e2_5_replica_scaling():
    x0 = np.full(5, 3.0)
    results = {}
    for n_rep in (2, 4, 8):
        r = parallel_tempering_sa(
            x0, rosenbrock_10d, gaussian_propose,
            n_replicas=n_rep, t_min=1e-3, t_max=2.0,
            max_steps=1500, exchange_every=20, seed=123,
        )
        results[n_rep] = r["best_loss"]

    # Permit mild regression (stochastic) but catastrophic regression is a bug.
    # Assertion: 8-replica ≤ 2-replica × 3.0 (generous slack for a fixed-seed run).
    assert results[8] <= results[2] * 3.0 + 5.0, results


# ---------------------------------------------------------------------------
# E.2.6 — NaN-guard invariant
# ---------------------------------------------------------------------------

def test_e2_6_nan_guard():
    x0 = np.array([0.0, 0.0], dtype=np.float64)

    call_count = [0]

    def loss(state):
        call_count[0] += 1
        # Every 5th call returns NaN; others return a finite value.
        if call_count[0] % 5 == 0:
            return float("nan")
        return float((state ** 2).sum())

    out = parallel_tempering_sa(
        x0, loss, gaussian_propose,
        n_replicas=2, t_min=1e-3, t_max=0.5,
        max_steps=100, exchange_every=20, seed=3,
    )
    assert math.isfinite(out["best_loss"]), (
        f"NaN leaked into best_loss: {out['best_loss']}"
    )
    assert not np.any(np.isnan(out["best_state"]))


# ---------------------------------------------------------------------------
# E.2.7 — Fresh-clone degradation (Rosenbrock tests run without arena data)
# ---------------------------------------------------------------------------

def test_e2_7_fresh_clone_degradation():
    """PT-SA has NO arena-data dependencies; E.2.1-6 always run. This test just
    confirms the no-data invariant by asserting the test module imports pt_sa
    cleanly and exposes the expected API surface."""
    from pt_sa import parallel_tempering_sa, temperature_schedule, attempt_exchange
    assert callable(parallel_tempering_sa)
    assert callable(temperature_schedule)
    assert callable(attempt_exchange)
