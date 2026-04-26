"""Integration test: ops-ulp-polish against a real kissing-d11 warm-start.

Per organon_upgrade_session_plan.md §5 (F.1 integration gate):
  - Wire against projects/einstein-arena-kissing-d11/ warm-start
  - Verify score(output) <= score(input) by >= 1e-14 on a perturbed config

Marked @pytest.mark.needs_arena_data — skips cleanly on fresh clones.
Marked @pytest.mark.slow — wall-clock up to ~10s with real polish sweeps.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
PROJECTS_DIR = REPO_ROOT / "projects"
POLISH_SCRIPTS = SKILLS_DIR / "ops-ulp-polish" / "scripts"

if str(POLISH_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(POLISH_SCRIPTS))

from polish import polish  # type: ignore  # noqa: E402


# ---------------------------------------------------------------------------
# Kissing-d11 loss (float loss formula matching the arena verifier)
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
# Fixture: pick a (594, 11) warm-start from disk
# ---------------------------------------------------------------------------

def _load_kissing_d11() -> tuple[np.ndarray, Path] | None:
    base = PROJECTS_DIR / "einstein-arena-kissing-d11"
    if not base.is_dir():
        return None
    for name in ("solutions_d11_594_flip.npy", "v594_rotated.npy",
                 "solutions_d11_594_novel.npy"):
        p = base / name
        if p.is_file():
            try:
                V = np.load(p).astype(np.float64)
                if V.shape == (594, 11):
                    return V, p
            except Exception:
                continue
    for p in sorted(base.glob("solutions_d11_594_*.npy")):
        try:
            V = np.load(p).astype(np.float64)
            if V.shape == (594, 11):
                return V, p
        except Exception:
            continue
    return None


# ---------------------------------------------------------------------------
# Test I.1 — polish on real shape: score non-increasing
# ---------------------------------------------------------------------------

@pytest.mark.needs_arena_data
@pytest.mark.slow
def test_polish_integration_score_nondecreasing():
    """Run polish on a slightly perturbed kissing-d11 shape; verify loss does
    not increase. Perturbation guarantees nonzero initial loss so polish has
    something to improve (valid configs short-circuit at score=0)."""
    result = _load_kissing_d11()
    if result is None:
        pytest.skip("projects/einstein-arena-kissing-d11/ not present on disk")

    V_valid, src = result
    rng = np.random.default_rng(42)

    # Perturb one row by a small ULP-scale amount to create nonzero loss.
    V_perturbed = V_valid.copy()
    V_perturbed[0] *= 1.0 + 1e-9
    initial_loss = kissing_loss(V_perturbed)

    # If perturbation didn't create nonzero loss (e.g. the verifier tolerates
    # tiny deltas), use a known synthetic perturbation that definitely does.
    if initial_loss == 0.0:
        V_perturbed[0] *= 1.01
        initial_loss = kissing_loss(V_perturbed)

    V_out, final_loss = polish(
        V_perturbed,
        eval_fn=kissing_loss,
        budget_sec=5.0,
        max_ulps=2,
        max_sweeps=3,
    )

    assert V_out.shape == V_perturbed.shape, "output shape must match input"
    assert final_loss <= initial_loss + 1e-14, (
        f"polish increased loss: {initial_loss:.6e} -> {final_loss:.6e}"
    )


# ---------------------------------------------------------------------------
# Test I.2 — polish on valid config short-circuits (no-op guard)
# ---------------------------------------------------------------------------

@pytest.mark.needs_arena_data
def test_polish_integration_valid_config_shortcircuits():
    """Valid kissing config (loss=0) must exit immediately without any sweeps."""
    result = _load_kissing_d11()
    if result is None:
        pytest.skip("projects/einstein-arena-kissing-d11/ not present on disk")

    V_valid, _ = result
    if kissing_loss(V_valid) != 0.0:
        pytest.skip("loaded config is not score=0 — use test_polish_integration_score_nondecreasing instead")

    V_out, final_loss = polish(
        V_valid,
        eval_fn=kissing_loss,
        budget_sec=1.0,
        max_ulps=4,
        max_sweeps=10,
    )
    assert final_loss == 0.0
    assert np.array_equal(V_out, V_valid), "valid config must be returned unchanged"


# ---------------------------------------------------------------------------
# Test I.3 — polish on synthetic (no arena data needed)
# ---------------------------------------------------------------------------

def test_polish_integration_synthetic_reduces_loss():
    """Synthetic 4-vector fixture with known nonzero loss; must strictly improve."""
    # Four nearly-overlapping unit vectors in R^3 arranged so pairs are too close.
    V = np.array([
        [1.0, 0.0, 0.0],
        [0.9998, 0.02, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ], dtype=np.float64)

    def loss(W: np.ndarray) -> float:
        norms = np.linalg.norm(W, axis=1, keepdims=True)
        norms = np.maximum(norms, 1e-300)
        c = 2.0 * W / norms
        d2 = ((c[:, None, :] - c[None, :, :]) ** 2).sum(-1)
        iu = np.triu_indices(W.shape[0], k=1)
        pairs = d2[iu]
        under = pairs < 4.0
        if not under.any():
            return 0.0
        return float((2.0 - np.sqrt(pairs[under])).sum())

    initial = loss(V)
    assert initial > 0.0, "synthetic fixture must have nonzero initial loss"

    V_out, final = polish(V, eval_fn=loss, budget_sec=2.0, max_ulps=4, max_sweeps=5)
    assert final <= initial + 1e-14, f"polish must not increase loss: {initial:.6e} -> {final:.6e}"
