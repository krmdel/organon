"""Tests for parallel_tempering_sa — written FIRST (TDD)."""
import math
import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from pt_sa import (  # noqa: E402
    parallel_tempering_sa,
    temperature_schedule,
    attempt_exchange,
    weighted_choice,
)


# ------------------------------------------------------------------ helpers

def _quadratic_loss(target):
    def _loss(state):
        return float(np.sum((np.asarray(state, dtype=np.float64) - target) ** 2))
    return _loss


def _gaussian_move(step=0.1):
    """Default move: perturb ONE coordinate by N(0, step)."""
    def _propose(state, rng, idx=None):
        state = np.asarray(state, dtype=np.float64).copy()
        if idx is None:
            idx = int(rng.integers(0, state.size))
        delta = float(rng.normal(0.0, step))
        new_state = state.copy()
        new_state[idx] += delta
        change = {"idx": idx, "delta": delta, "old": float(state[idx])}
        return new_state, change
    return _propose


# ------------------------------------------------------------------ temperature_schedule

def test_temperature_schedule_geometric():
    t = temperature_schedule(1e-12, 1e-4, 8)
    assert t.shape == (8,)
    assert t[0] == pytest.approx(1e-12, rel=1e-12)
    assert t[-1] == pytest.approx(1e-4, rel=1e-12)
    # Geometric: ratios must be equal.
    ratios = t[1:] / t[:-1]
    assert np.allclose(ratios, ratios[0], rtol=1e-10)
    # Monotonic increasing.
    assert np.all(np.diff(t) > 0)


def test_temperature_schedule_singleton():
    t = temperature_schedule(1e-4, 1e-4, 1)
    assert t.shape == (1,)
    assert t[0] == pytest.approx(1e-4)


def test_temperature_schedule_invalid():
    with pytest.raises(ValueError):
        temperature_schedule(0.0, 1.0, 4)      # t_min must be > 0
    with pytest.raises(ValueError):
        temperature_schedule(1.0, 0.5, 4)      # t_max must be >= t_min
    with pytest.raises(ValueError):
        temperature_schedule(1e-9, 1e-4, 0)    # n >= 1


# ------------------------------------------------------------------ attempt_exchange

def test_attempt_exchange_accepts_lower_energy():
    """If T_lo state has LOWER energy, swap is favorable -> Metropolis prob >= 1."""
    rng = np.random.default_rng(0)
    # E_lo < E_hi, beta_lo > beta_hi -> (beta_i - beta_j)(E_j - E_i) > 0 -> always accept
    beta_lo, beta_hi = 1.0, 0.1
    E_lo, E_hi = 1.0, 10.0
    # convention: attempt_exchange(E_A, E_B, beta_A, beta_B, rng)
    # delta = (beta_A - beta_B) * (E_B - E_A); if A=lo (cold), B=hi: (1.0 - 0.1)*(10 - 1) = 8.1 -> accept
    accepted = attempt_exchange(E_lo, E_hi, beta_lo, beta_hi, rng)
    assert accepted is True


def test_attempt_exchange_metropolis_probability():
    """Test the Metropolis probability evaluates correctly against known value."""
    # Rig the rng so .random() returns values we control.
    beta_A, beta_B = 2.0, 1.0
    E_A, E_B = 5.0, 3.0  # A is cold but HIGHER energy
    delta = (beta_A - beta_B) * (E_B - E_A)  # (1.0) * (-2.0) = -2.0
    p = math.exp(delta)  # e^-2 ~ 0.1353

    class _FakeRNG:
        def __init__(self, u):
            self._u = u
        def random(self):
            return self._u

    # u just below p -> accept
    assert attempt_exchange(E_A, E_B, beta_A, beta_B, _FakeRNG(p - 1e-6)) is True
    # u just above p -> reject
    assert attempt_exchange(E_A, E_B, beta_A, beta_B, _FakeRNG(p + 1e-6)) is False


def test_attempt_exchange_rejection_deterministic_seed():
    """Same seed + same inputs -> same accept/reject decision."""
    beta_A, beta_B = 10.0, 1.0
    E_A, E_B = 100.0, 1.0   # very unfavorable swap
    out1 = attempt_exchange(E_A, E_B, beta_A, beta_B, np.random.default_rng(42))
    out2 = attempt_exchange(E_A, E_B, beta_A, beta_B, np.random.default_rng(42))
    assert out1 == out2
    assert out1 is False  # delta = 9 * (-99) hugely negative -> rejected


# ------------------------------------------------------------------ weighted_choice (contribution-weighted sampling)

def test_weighted_choice_prefers_high_contribution():
    """weights [10, 1, 1, 1] -> element 0 selected on > 50% of trials."""
    rng = np.random.default_rng(123)
    weights = np.array([10.0, 1.0, 1.0, 1.0])
    picks = np.array([weighted_choice(weights, rng) for _ in range(1000)])
    frac_zero = float((picks == 0).mean())
    assert frac_zero > 0.5


def test_weighted_choice_all_zero_uniform():
    """All-zero weights fall back to uniform selection (no crash)."""
    rng = np.random.default_rng(0)
    weights = np.zeros(5)
    picks = [weighted_choice(weights, rng) for _ in range(500)]
    # Every index should have been picked at least once.
    assert set(picks) == {0, 1, 2, 3, 4}


# ------------------------------------------------------------------ happy path

def test_happy_path_quadratic_minimization():
    target = np.array([1.0, -2.0, 3.0, 0.5])
    loss_fn = _quadratic_loss(target)
    initial = np.zeros(4)
    initial_loss = loss_fn(initial)

    result = parallel_tempering_sa(
        initial,
        loss_fn,
        _gaussian_move(step=0.3),
        n_replicas=4,
        t_min=1e-3,
        t_max=1.0,
        max_steps=1500,
        exchange_every=20,
        seed=7,
    )

    assert result["best_loss"] < initial_loss
    # Should get reasonably close to the target.
    assert np.linalg.norm(result["best_state"] - target) < 0.5


# ------------------------------------------------------------------ delta_fn path

def test_delta_fn_bypasses_loss_fn_on_acceptance():
    """When delta_fn is supplied, acceptance uses delta only; loss_fn not called per-step."""
    target = np.array([1.0, 2.0, 3.0])
    real_loss = _quadratic_loss(target)

    loss_spy = MagicMock(side_effect=real_loss)

    def delta_fn(state, change):
        idx = change["idx"]
        old = change["old"]
        new = old + change["delta"]
        # sum((x-t)^2) delta for one coord change:
        return (new - target[idx]) ** 2 - (old - target[idx]) ** 2

    initial = np.zeros(3)
    parallel_tempering_sa(
        initial,
        loss_spy,
        _gaussian_move(step=0.2),
        delta_fn=delta_fn,
        n_replicas=2,
        t_min=1e-3,
        t_max=0.1,
        max_steps=200,
        exchange_every=50,
        seed=1,
    )
    # loss_fn called only for initial evaluation per replica + at exchange checks.
    # Budget is 200 steps per replica (400 moves total). If delta_fn works,
    # loss_fn call count should be << 400.
    assert loss_spy.call_count < 50, f"loss_fn called {loss_spy.call_count} times"


def test_fallback_to_full_loss_when_no_delta():
    """Without delta_fn, loss_fn IS called on every proposed move."""
    target = np.array([1.0, 2.0])
    loss_spy = MagicMock(side_effect=_quadratic_loss(target))

    parallel_tempering_sa(
        np.zeros(2),
        loss_spy,
        _gaussian_move(step=0.1),
        n_replicas=2,
        t_min=1e-3,
        t_max=0.1,
        max_steps=30,
        exchange_every=10,
        seed=2,
    )
    # Per replica: 1 init + 30 proposals = 31. Two replicas = 62 minimum.
    assert loss_spy.call_count >= 60


# ------------------------------------------------------------------ reproducibility

def test_reproducible_seed():
    target = np.array([0.5, -0.5, 0.25])
    kwargs = dict(
        loss_fn=_quadratic_loss(target),
        propose_move_fn=_gaussian_move(step=0.2),
        n_replicas=3,
        t_min=1e-3,
        t_max=0.1,
        max_steps=100,
        exchange_every=15,
        seed=99,
    )
    r1 = parallel_tempering_sa(np.zeros(3), **kwargs)
    r2 = parallel_tempering_sa(np.zeros(3), **kwargs)
    assert np.array_equal(r1["best_state"], r2["best_state"])
    assert r1["best_loss"] == r2["best_loss"]


# ------------------------------------------------------------------ degenerate inputs

def test_empty_state_raises():
    with pytest.raises(ValueError):
        parallel_tempering_sa(
            np.array([]),
            _quadratic_loss(np.array([])),
            _gaussian_move(),
            n_replicas=2,
            max_steps=5,
            seed=0,
        )


def test_empty_list_state_raises():
    with pytest.raises(ValueError):
        parallel_tempering_sa(
            [],
            lambda s: 0.0,
            _gaussian_move(),
            n_replicas=2,
            max_steps=5,
            seed=0,
        )


def test_singleton_state_runs():
    initial = np.array([5.0])
    target = np.array([0.0])
    result = parallel_tempering_sa(
        initial,
        _quadratic_loss(target),
        _gaussian_move(step=0.5),
        n_replicas=2,
        t_min=1e-3,
        t_max=0.5,
        max_steps=100,
        exchange_every=20,
        seed=3,
    )
    assert result["best_state"].size == 1
    assert result["best_loss"] <= float(_quadratic_loss(target)(initial))


# ------------------------------------------------------------------ replica count boundaries

def test_single_replica_no_exchanges():
    """n_replicas=1 still produces a valid SA run (no exchanges)."""
    target = np.array([2.0, -1.0])
    initial = np.zeros(2)
    result = parallel_tempering_sa(
        initial,
        _quadratic_loss(target),
        _gaussian_move(step=0.3),
        n_replicas=1,
        t_min=0.1,
        t_max=0.1,
        max_steps=300,
        exchange_every=10,
        seed=4,
    )
    assert result["best_loss"] < _quadratic_loss(target)(initial)
    # History should contain zero exchange attempts.
    assert result["exchange_attempts"] == 0


def test_eight_replicas_kissing_config():
    """n_replicas=8 runs and returns best-state across replicas."""
    target = np.ones(3) * 0.5
    initial = np.zeros(3)
    result = parallel_tempering_sa(
        initial,
        _quadratic_loss(target),
        _gaussian_move(step=0.2),
        n_replicas=8,
        t_min=1e-6,
        t_max=1e-1,
        max_steps=200,
        exchange_every=10,
        seed=5,
    )
    assert len(result["replicas"]) == 8
    per_replica_best = [r["best_loss"] for r in result["replicas"]]
    # The reported best is the min over replicas.
    assert result["best_loss"] == pytest.approx(min(per_replica_best))


# ------------------------------------------------------------------ temperature schedule enforcement

def test_temperature_schedule_used_in_kissing_config():
    target = np.array([0.0, 0.0, 0.0])
    result = parallel_tempering_sa(
        np.zeros(3),
        _quadratic_loss(target),
        _gaussian_move(0.01),
        n_replicas=8,
        t_min=1e-12,
        t_max=1e-4,
        max_steps=10,
        exchange_every=5,
        seed=6,
    )
    temps = np.asarray(result["temperatures"])
    expected = temperature_schedule(1e-12, 1e-4, 8)
    assert np.allclose(temps, expected, rtol=1e-12)


# ------------------------------------------------------------------ budget enforcement

def test_max_steps_enforcement():
    """max_steps=100 stops after ~100 steps per replica."""
    calls = {"count": 0}

    def counting_loss(state):
        calls["count"] += 1
        return float(np.sum(state ** 2))

    result = parallel_tempering_sa(
        np.ones(2),
        counting_loss,
        _gaussian_move(0.1),
        n_replicas=2,
        t_min=0.01,
        t_max=0.1,
        max_steps=100,
        exchange_every=50,
        seed=10,
    )
    history = result["history"]
    # Per-replica step counts within ±1 of 100.
    for rec in history:
        assert abs(rec["steps"] - 100) <= 1


# ------------------------------------------------------------------ NaN guard

def test_nan_loss_is_rejected():
    """A proposal yielding NaN loss is rejected (not accepted)."""
    rng_state = {"iter": 0}

    def nan_on_second_call_loss(state):
        rng_state["iter"] += 1
        if rng_state["iter"] == 2:
            return float("nan")
        return float(np.sum(np.asarray(state) ** 2))

    initial = np.array([1.0, 1.0])
    result = parallel_tempering_sa(
        initial,
        nan_on_second_call_loss,
        _gaussian_move(0.01),
        n_replicas=1,
        t_min=0.1,
        t_max=0.1,
        max_steps=5,
        exchange_every=10,
        seed=11,
    )
    # best_loss must not be NaN; NaN-producing moves are rejected.
    assert not math.isnan(result["best_loss"])


# ------------------------------------------------------------------ monotonicity

def test_best_loss_monotone_nonincreasing():
    """best-ever-loss can never be worse than initial loss."""
    target = np.array([3.0, -3.0, 1.5])
    initial = np.array([0.0, 0.0, 0.0])
    init_loss = _quadratic_loss(target)(initial)
    result = parallel_tempering_sa(
        initial,
        _quadratic_loss(target),
        _gaussian_move(0.2),
        n_replicas=3,
        t_min=1e-3,
        t_max=1.0,
        max_steps=250,
        exchange_every=15,
        seed=42,
    )
    assert result["best_loss"] <= init_loss + 1e-12


# ------------------------------------------------------------------ contribution-weighted sampling end-to-end

def test_contribution_fn_is_consulted():
    """When contribution_fn is provided, propose_move_fn receives a weighted-sampled idx."""
    target = np.array([10.0, 0.0, 0.0, 0.0])

    def contribution_fn(state):
        # Element 0 always dominates -> should be picked most.
        return np.array([100.0, 1.0, 1.0, 1.0])

    seen_idx = []

    def recording_move(state, rng, idx=None):
        seen_idx.append(idx)
        state = np.asarray(state, dtype=np.float64).copy()
        if idx is None:
            idx = 0
        delta = float(rng.normal(0.0, 0.1))
        new_state = state.copy()
        new_state[idx] += delta
        return new_state, {"idx": idx, "delta": delta, "old": float(state[idx])}

    parallel_tempering_sa(
        np.zeros(4),
        _quadratic_loss(target),
        recording_move,
        contribution_fn=contribution_fn,
        n_replicas=1,
        t_min=0.1,
        t_max=0.1,
        max_steps=200,
        exchange_every=500,
        seed=77,
    )
    # Idx 0 should be overwhelmingly selected.
    idx_arr = np.array([i for i in seen_idx if i is not None])
    assert idx_arr.size > 0
    assert (idx_arr == 0).mean() > 0.5


# ------------------------------------------------------------------ invalid params

def test_invalid_n_replicas():
    with pytest.raises(ValueError):
        parallel_tempering_sa(
            np.zeros(2),
            _quadratic_loss(np.zeros(2)),
            _gaussian_move(),
            n_replicas=0,
            max_steps=5,
            seed=0,
        )


def test_invalid_max_steps():
    with pytest.raises(ValueError):
        parallel_tempering_sa(
            np.zeros(2),
            _quadratic_loss(np.zeros(2)),
            _gaussian_move(),
            n_replicas=2,
            max_steps=0,
            seed=0,
        )
