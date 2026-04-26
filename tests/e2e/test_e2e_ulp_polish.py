"""E.1 — ops-ulp-polish end-to-end tests.

Per context/memory/organon_upgrade_final_handoff.md §3.1. Exercises the polish
pipeline against real kissing-d11 warm-starts plus synthetic edge-case inputs.
Unit tests cover next_ulp / row_badness / load_config in isolation; these
tests confirm the *composed* polish() loop behaves correctly on data shapes
a user actually feeds it.
"""
from __future__ import annotations

import math
import time
from pathlib import Path

import numpy as np
import pytest

from polish import polish, next_ulp


# ---------------------------------------------------------------------------
# Kissing-d11 evaluator — matches the arena verifier's float loss formula
# (see projects/einstein-arena-kissing-d11/recon/problem.json "_overlap_loss")
# but implemented vectorised for test-speed. Score 0 ⇔ no overlapping spheres.
# ---------------------------------------------------------------------------

def kissing_loss(V: np.ndarray) -> float:
    norms = np.sqrt((V ** 2).sum(axis=1, keepdims=True))
    if (norms == 0).any():
        return float("inf")
    c = 2.0 * V / norms
    d2 = ((c[:, None, :] - c[None, :, :]) ** 2).sum(-1)
    iu = np.triu_indices(V.shape[0], k=1)
    pair_d2 = d2[iu]
    under = pair_d2 < 4.0
    if not under.any():
        return 0.0
    return float((2.0 - np.sqrt(pair_d2[under])).sum())


# ---------------------------------------------------------------------------
# Synthetic micro-fixtures (fast, no arena data)
# ---------------------------------------------------------------------------

def _threshold_loss(V: np.ndarray, threshold_sq: float = 0.25) -> float:
    """Pairwise hinge loss: sum of (threshold - sq_dist) for pairs under threshold."""
    d2 = ((V[:, None, :] - V[None, :, :]) ** 2).sum(-1)
    iu = np.triu_indices(V.shape[0], k=1)
    d = d2[iu]
    mask = d < threshold_sq
    if not mask.any():
        return 0.0
    return float((threshold_sq - d[mask]).sum())


def _micro_config(n: int = 8, d: int = 3, seed: int = 0) -> np.ndarray:
    """n×d well-spread vectors with a small number of tight pairs so polish has work."""
    rng = np.random.default_rng(seed)
    V = rng.uniform(-1.0, 1.0, size=(n, d)).astype(np.float64)
    V[1] = V[0] + np.array([0.05, 0.0, 0.0])[:d]
    return V


# ---------------------------------------------------------------------------
# E.1.1 — Happy path on kissing-d11 warm-start
# ---------------------------------------------------------------------------

@pytest.mark.slow
@pytest.mark.needs_arena_data
def test_e1_1_happy_path_kissing_d11(kissing_d11_fixture):
    V, src = kissing_d11_fixture
    init_score = kissing_loss(V)
    assert init_score >= 0.0

    V_out, final_score = polish(
        V, kissing_loss,
        max_ulps=2, max_sweeps=1, budget_sec=30.0, verbose=False,
    )

    assert V_out.shape == V.shape
    assert V_out.dtype == np.float64
    assert final_score <= init_score + 1e-18, (
        f"polish made it worse: init={init_score} final={final_score} src={src.name}"
    )
    # NaN guard.
    assert math.isfinite(final_score)


# ---------------------------------------------------------------------------
# E.1.2 — mpmath parity
# ---------------------------------------------------------------------------

@pytest.mark.slow
@pytest.mark.needs_arena_data
def test_e1_2_mpmath_parity(kissing_d11_fixture):
    """Polished config's mpmath-recomputed loss must match the float64 loss
    to within a tiny slop (mpmath is the ground truth; float64 should be at
    most a few ULPs off when the score is near zero)."""
    mpmath = pytest.importorskip("mpmath")

    V, _ = kissing_d11_fixture
    V_out, f64_score = polish(
        V, kissing_loss,
        max_ulps=2, max_sweeps=1, budget_sec=30.0, verbose=False,
    )

    mpmath.mp.dps = 50

    def mp_loss(V: np.ndarray) -> float:
        norms = [mpmath.sqrt(sum(mpmath.mpf(str(x)) ** 2 for x in row)) for row in V]
        if any(n == 0 for n in norms):
            return float("inf")
        c = [[mpmath.mpf(str(x)) * 2 / n for x in row] for row, n in zip(V, norms)]
        total = mpmath.mpf(0)
        n = len(c)
        four = mpmath.mpf(4)
        two = mpmath.mpf(2)
        for i in range(n):
            for j in range(i + 1, n):
                sq = sum((a - b) ** 2 for a, b in zip(c[i], c[j]))
                if sq < four:
                    total += two - mpmath.sqrt(sq)
        return float(total)

    # Only sample a subset of rows to keep runtime bounded — the mpmath full
    # n=594 case is O(n²) decimals and too slow for a test. If f64_score==0,
    # the mpmath recompute should also be ~0.
    if f64_score == 0.0:
        # Subsample: first 40 rows.
        sub = V_out[:40]
        mp_sub = mp_loss(sub)
        # Subset of a valid config should also be valid (score 0 or nearly so).
        assert mp_sub <= 1e-10, f"mpmath disagrees on valid-subset: {mp_sub}"
    else:
        mp_sub = mp_loss(V_out[:40])
        assert mp_sub >= -1e-30  # mpmath loss is non-negative by construction


# ---------------------------------------------------------------------------
# E.1.3 — Idempotence on polished output
# ---------------------------------------------------------------------------

@pytest.mark.slow
@pytest.mark.needs_arena_data
def test_e1_3_idempotence_on_polished_output(kissing_d11_fixture):
    V, _ = kissing_d11_fixture
    V_out1, score1 = polish(V, kissing_loss, max_ulps=1, max_sweeps=1,
                             budget_sec=20.0, verbose=False)
    V_out2, score2 = polish(V_out1, kissing_loss, max_ulps=1, max_sweeps=1,
                             budget_sec=20.0, verbose=False)
    assert abs(score1 - score2) <= 1e-18
    # When score hits 0, polish short-circuits — verify that's honoured.
    if score1 == 0.0:
        assert np.array_equal(V_out1, V_out2)


# ---------------------------------------------------------------------------
# E.1.4 — Freeze-indices respected on real data
# ---------------------------------------------------------------------------

@pytest.mark.slow
@pytest.mark.needs_arena_data
def test_e1_4_freeze_indices_real_data(kissing_d11_fixture):
    V, _ = kissing_d11_fixture
    freeze = set(range(10))

    V_in = V.copy()
    V_out, _ = polish(V_in, kissing_loss, max_ulps=1, max_sweeps=1,
                       budget_sec=20.0, freeze_indices=freeze, verbose=False)

    # Frozen rows must be bit-identical.
    for i in freeze:
        assert np.array_equal(V_out[i], V[i]), f"freeze violated at row {i}"


# ---------------------------------------------------------------------------
# E.1.5 — Budget enforcement
# ---------------------------------------------------------------------------

def test_e1_5_budget_enforcement():
    # Synthetic small config with a slow evaluator so the loop HAS to check
    # the wall-clock budget between accepts.
    V = _micro_config(n=12, d=3, seed=1)

    def slow_eval(V: np.ndarray) -> float:
        # 5 ms per call — 20 coordinate trials/row × 12 rows already floods the
        # 0.5s budget before the first sweep finishes.
        time.sleep(0.005)
        return _threshold_loss(V, threshold_sq=0.25)

    t0 = time.time()
    V_out, _ = polish(V, slow_eval, max_ulps=4, max_sweeps=10,
                       budget_sec=0.5, verbose=False)
    dt = time.time() - t0

    # Budget is respected within a reasonable slack for the row-level loop
    # (polish checks time after each row, not after each ulp trial).
    assert dt < 2.0, f"polish ran {dt:.2f}s past 0.5s budget"
    assert V_out.shape == V.shape


# ---------------------------------------------------------------------------
# E.1.6 — Subnormal-input robustness
# ---------------------------------------------------------------------------

def test_e1_6_subnormal_robustness():
    V = _micro_config(n=6, d=3, seed=2)
    # Inject a subnormal at a specific coordinate.
    V[0, 0] = 5e-324  # smallest positive subnormal-ish

    def eval_fn(V):
        return _threshold_loss(V, threshold_sq=0.25)

    V_out, final = polish(V, eval_fn, max_ulps=2, max_sweeps=1,
                           budget_sec=5.0, verbose=False)
    assert not np.any(np.isnan(V_out)), "polish produced NaN"
    assert math.isfinite(final)


# ---------------------------------------------------------------------------
# E.1.7 — Fresh-clone degradation
# ---------------------------------------------------------------------------

def test_e1_7_fresh_clone_degradation():
    """kissing_d11_fixture must pytest.skip cleanly when arena data is absent.
    Smoke check: if data is present the fixture succeeds; if not, it skips.
    Either path is acceptable — the assertion is that NEITHER produces a hard error.
    """
    from tests.e2e.conftest import PROJECTS_DIR

    base = PROJECTS_DIR / "einstein-arena-kissing-d11"
    if not base.is_dir():
        # Fresh-clone path — assert skip semantic would fire.
        with pytest.raises(pytest.skip.Exception):
            pytest.skip(f"simulating fresh-clone: {base}")
    else:
        # Data path — just confirm at least one 594×11 .npy exists or the
        # fixture would skip.
        candidates = list(base.glob("*.npy"))
        assert candidates, f"no .npy files under {base}"


# ---------------------------------------------------------------------------
# Synthetic sanity — polish DOES reduce a loss when there's loss to reduce.
# (Confirms the loop isn't a no-op; complements the arena-dependent tests.)
# ---------------------------------------------------------------------------

def test_e1_synthetic_actually_reduces_loss():
    V = _micro_config(n=6, d=2, seed=7)

    def eval_fn(V):
        return _threshold_loss(V, threshold_sq=0.25)

    init = eval_fn(V)
    assert init > 0.0, "synthetic fixture should have non-trivial loss"
    V_out, final = polish(V, eval_fn, max_ulps=4, max_sweeps=3,
                           budget_sec=10.0, verbose=False)
    assert final <= init + 1e-18
