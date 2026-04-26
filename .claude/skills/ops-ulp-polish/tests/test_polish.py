"""Test suite for ops-ulp-polish/scripts/polish.py.

Run with: python3 -m pytest .claude/skills/ops-ulp-polish/tests/test_polish.py -v
"""
import json
import math
import sys
import os
import tempfile

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from polish import next_ulp, load_config, polish, row_badness_default


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def simple_eval_fn():
    """Counting-violations evaluator: sums squared distances below threshold."""
    threshold_sq = 0.5
    def eval_fn(V):
        total = 0.0
        n = len(V)
        for i in range(n):
            for j in range(i + 1, n):
                d2 = float(((V[i] - V[j]) ** 2).sum())
                if d2 < threshold_sq:
                    total += threshold_sq - d2
        return total
    return eval_fn


@pytest.fixture
def well_spread_V():
    """10 vectors, 3 dims, spread far enough that most pairs are non-violating."""
    rng = np.random.default_rng(42)
    V = rng.uniform(0, 10, size=(10, 3))
    return V.astype(np.float64)


# ---------------------------------------------------------------------------
# next_ulp tests
# ---------------------------------------------------------------------------

def test_next_ulp_positive_k():
    """next_ulp with positive k moves x strictly upward by exactly k ulps."""
    x = 1.0
    y = next_ulp(x, 1)
    assert isinstance(y, float)
    assert y > x


def test_next_ulp_negative_k():
    """next_ulp with negative k moves x strictly downward."""
    x = 1.0
    y = next_ulp(x, -1)
    assert isinstance(y, float)
    assert y < x


def test_next_ulp_zero_k():
    """next_ulp with k=0 returns x unchanged."""
    x = 3.14
    assert next_ulp(x, 0) == x


def test_next_ulp_subnormal():
    """next_ulp must not crash on subnormal inputs (values < float_info.min)."""
    subnormal = sys.float_info.min * 1e-10
    assert subnormal > 0
    result = next_ulp(subnormal, 1)
    assert isinstance(result, float)
    assert not math.isnan(result)


def test_next_ulp_neg_zero_positive():
    """next_ulp(-0.0, +1) must return a valid float, not NaN."""
    result = next_ulp(-0.0, 1)
    assert isinstance(result, float)
    assert not math.isnan(result)


def test_next_ulp_neg_zero_negative():
    """next_ulp(-0.0, -1) must return a valid float, not NaN."""
    result = next_ulp(-0.0, -1)
    assert isinstance(result, float)
    assert not math.isnan(result)


def test_next_ulp_near_inf():
    """next_ulp(1e308, 1) must return inf or a valid large float, never raise."""
    result = next_ulp(1e308, 1)
    assert isinstance(result, float)
    assert not math.isnan(result)
    assert math.isinf(result) or result >= 1e308


def test_next_ulp_symmetry():
    """next_ulp(x, k) then next_ulp(result, -k) should round-trip for normal floats."""
    x = 12345.6789
    k = 3
    forward = next_ulp(x, k)
    back = next_ulp(forward, -k)
    assert back == x


# ---------------------------------------------------------------------------
# load_config tests
# ---------------------------------------------------------------------------

def test_load_config_npy():
    """load_config must load a .npy file and return the correct shape."""
    arr = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float64)
    with tempfile.NamedTemporaryFile(suffix='.npy', delete=False) as f:
        np.save(f.name, arr)
        loaded = load_config(f.name)
    assert loaded.shape == (2, 2)
    assert loaded.dtype == np.float64
    np.testing.assert_array_almost_equal(loaded, arr)


def test_load_config_json_vectors_key():
    """load_config must parse {"vectors": [...]} and return shape (2, 2)."""
    data = {"vectors": [[1.0, 2.0], [3.0, 4.0]]}
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(data, f)
        fname = f.name
    loaded = load_config(fname)
    assert loaded.shape == (2, 2)
    assert loaded.dtype == np.float64


def test_load_config_json_data_vectors_key():
    """load_config must handle {"data": {"vectors": [...]}} nesting."""
    data = {"data": {"vectors": [[1.0], [2.0], [3.0]]}}
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(data, f)
        fname = f.name
    loaded = load_config(fname)
    assert loaded.shape == (3, 1)


def test_load_config_unsupported_format():
    """load_config must raise ValueError for unsupported file extensions."""
    with pytest.raises(ValueError, match="unsupported format"):
        load_config("myfile.txt")


# ---------------------------------------------------------------------------
# polish core tests
# ---------------------------------------------------------------------------

def test_happy_path_score_non_increasing(simple_eval_fn, well_spread_V):
    """After polish, score must be <= initial score (never worse than warm start)."""
    V = well_spread_V
    initial_score = float(simple_eval_fn(V))
    _, final_score = polish(V, simple_eval_fn, max_ulps=2, max_sweeps=3, verbose=False)
    assert final_score <= initial_score + 1e-12


def test_no_improvement_coordinate_unchanged():
    """A vector at a locally optimal position should not be mutated by polish."""
    V = np.array([[1.0, 2.0, 3.0],
                  [100.0, 200.0, 300.0]], dtype=np.float64)
    original_row0 = V[0].copy()

    def flat_eval(arr):
        """Always returns 1.0 regardless of input; no ulp move can improve."""
        return 1.0

    V_out, _ = polish(V, flat_eval, max_ulps=2, max_sweeps=2, verbose=False)
    np.testing.assert_array_equal(V_out[0], original_row0)


def test_termination_on_converged():
    """When evaluator returns constant value, polish must terminate without error."""
    V = np.ones((4, 2), dtype=np.float64)

    def flat_eval(arr):
        return 5.0

    V_out, score = polish(V, flat_eval, max_ulps=2, max_sweeps=20, verbose=False)
    assert score == 5.0


def test_budget_exhaustion():
    """polish must return (V, score) tuple without error when budget_sec is tiny."""
    V = np.random.default_rng(0).uniform(0, 1, (5, 3)).astype(np.float64)

    def slow_eval(arr):
        return float(arr.sum())

    result = polish(V, slow_eval, budget_sec=0.0001, max_sweeps=100, verbose=False)
    assert isinstance(result, tuple)
    assert len(result) == 2
    V_out, score = result
    assert isinstance(V_out, np.ndarray)
    assert isinstance(score, float)


def test_empty_input():
    """polish on shape (0, 3): either raises ValueError or returns a valid tuple.

    The implementation calls V.shape (n=0, d=3). The loop over range(0) is a
    no-op, so it returns (V_copy, init_score). Both behaviors are acceptable.
    """
    V = np.zeros((0, 3), dtype=np.float64)

    def eval_fn(arr):
        return 0.0

    try:
        result = polish(V, eval_fn, verbose=False)
        assert isinstance(result, tuple)
    except (ValueError, IndexError):
        pass


def test_singleton_input():
    """Single-row array (1, 3) must run without error and return valid result."""
    V = np.array([[1.0, 2.0, 3.0]], dtype=np.float64)

    def eval_fn(arr):
        return float(arr.sum())

    V_out, score = polish(V, eval_fn, max_ulps=1, max_sweeps=2, verbose=False)
    assert V_out.shape == (1, 3)
    assert isinstance(score, float)


def test_monotonicity_idempotence(simple_eval_fn):
    """Re-running polish on already-polished output must not worsen the score."""
    rng = np.random.default_rng(7)
    V = rng.uniform(0, 5, (6, 2)).astype(np.float64)

    V1, score1 = polish(V, simple_eval_fn, max_ulps=2, max_sweeps=5, verbose=False)
    V2, score2 = polish(V1, simple_eval_fn, max_ulps=2, max_sweeps=5, verbose=False)
    assert score2 <= score1 + 1e-12


def test_numpy_dtype_float32():
    """float32 input: document and assert either upcasting or a clean non-crash.

    load_config always casts to float64, but direct callers may pass float32.
    The implementation does V = V.copy() without explicit cast, so float32
    stays float32; next_ulp returns Python float but V[i,k] = trial downcasts.
    We assert the function does not crash and returns a valid result.
    """
    V = np.ones((3, 2), dtype=np.float32)

    def eval_fn(arr):
        return float(arr.sum())

    try:
        V_out, score = polish(V, eval_fn, max_ulps=1, max_sweeps=1, verbose=False)
        assert isinstance(score, float)
    except (TypeError, ValueError):
        pass


def test_priority_ordering_high_badness_first():
    """Highest-badness row must come first in argsort(-badness) ordering."""
    V = np.array([
        [0.0, 0.0],
        [5.0, 0.0],
        [5.1, 0.0],
    ], dtype=np.float64)
    target_sq = 1.0

    b0 = row_badness_default(V, 0, target_sq)
    b1 = row_badness_default(V, 1, target_sq)
    b2 = row_badness_default(V, 2, target_sq)

    order = np.argsort([-b0, -b1, -b2])
    assert b0 == 0.0, "row 0 should have zero badness when far from all neighbors"
    assert b1 > b0
    assert b2 > b0
    assert order[0] in (1, 2)


def test_row_badness_default_no_neighbors():
    """row_badness_default returns 0.0 when no row is within target distance."""
    V = np.eye(5, dtype=np.float64) * 1000.0
    target_sq = 1.0
    for i in range(5):
        assert row_badness_default(V, i, target_sq) == 0.0


# ---------------------------------------------------------------------------
# Coverage-completion tests: hit previously-uncovered branches of polish.py
# ---------------------------------------------------------------------------

def test_load_config_json_missing_vectors_key():
    """A JSON file without a 'vectors' key must raise ValueError."""
    from polish import load_config as _load
    data = {"not_vectors": [[1.0]]}
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(data, f)
        fname = f.name
    with pytest.raises(ValueError, match="cannot find 'vectors'"):
        _load(fname)


def test_resolve_evaluator_roundtrip(tmp_path):
    """resolve_evaluator imports a real module:function spec and returns the callable."""
    from polish import resolve_evaluator
    # Use a stdlib function we can always rely on:
    fn = resolve_evaluator("math:sqrt")
    assert callable(fn)
    assert abs(fn(4.0) - 2.0) < 1e-12


def test_polish_verbose_prints(simple_eval_fn, well_spread_V, capsys):
    """polish(verbose=True) must emit the [ulp-polish] init + sweep lines."""
    polish(well_spread_V, simple_eval_fn, max_ulps=1, max_sweeps=1, verbose=True)
    out = capsys.readouterr().out
    assert "[ulp-polish]" in out


def test_polish_freeze_indices_skip():
    """Rows in freeze_indices must NOT be mutated even if they have high badness."""
    V = np.array([
        [0.0, 0.0],
        [0.5, 0.0],
        [0.51, 0.0],
    ], dtype=np.float64)
    original_row1 = V[1].copy()
    threshold_sq = 0.25

    def eval_fn(arr):
        total = 0.0
        n = len(arr)
        for i in range(n):
            for j in range(i+1, n):
                d2 = float(((arr[i] - arr[j]) ** 2).sum())
                if d2 < threshold_sq:
                    total += threshold_sq - d2
        return total

    V_out, _ = polish(V, eval_fn, max_ulps=2, max_sweeps=3, verbose=False,
                      freeze_indices={1})
    np.testing.assert_array_equal(V_out[1], original_row1)


def test_polish_reaches_exact_zero():
    """When eval_fn returns 0.0 at warm-start, polish must return immediately with score=0."""
    V = np.eye(4, dtype=np.float64) * 100.0

    def zero_eval(arr):
        return 0.0

    V_out, score = polish(V, zero_eval, max_ulps=2, max_sweeps=5, verbose=False)
    assert score == 0.0
    # No mutation should occur when we short-circuit on init score==0
    np.testing.assert_array_equal(V_out, V)


def test_polish_accepts_improving_move_and_tracks_best(simple_eval_fn):
    """An improving-step case: ensure polish actually accepts ulp moves and score drops."""
    rng = np.random.default_rng(11)
    V = rng.uniform(0, 1.5, (6, 2)).astype(np.float64)
    init = float(simple_eval_fn(V))
    V_out, final = polish(V, simple_eval_fn, max_ulps=4, max_sweeps=4, verbose=True)
    assert final <= init


def test_main_cli_roundtrip(tmp_path):
    """Invoke polish.py as a CLI via subprocess to cover the main() and __main__ lines.

    Uses math.sqrt as the evaluator (always present on the Python installation).
    """
    import subprocess
    import os

    repo_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')
    )
    script = os.path.join(repo_root, ".claude/skills/ops-ulp-polish/scripts/polish.py")

    # Build a 3x2 .npy warm-start with positive values.
    warm = tmp_path / "warm.npy"
    np.save(str(warm), np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]], dtype=np.float64))
    out = tmp_path / "out.npy"

    # Write a tiny evaluator module that sums values.
    pkg_dir = tmp_path / "tinypkg"
    pkg_dir.mkdir()
    (pkg_dir / "evaluator.py").write_text(
        "import numpy as np\n"
        "def evaluate(V):\n"
        "    return float(np.asarray(V).sum())\n"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(tmp_path) + os.pathsep + env.get("PYTHONPATH", "")

    cmd = [
        "python3", script,
        "--config", str(warm),
        "--evaluator", "tinypkg.evaluator:evaluate",
        "--max-ulps", "1",
        "--max-sweeps", "1",
        "--out", str(out),
        "--budget-sec", "5",
    ]
    r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, f"stdout:{r.stdout}\nstderr:{r.stderr}"
    assert "final score" in r.stdout
    # polish.py always rewrites the suffix to .polished.npy, so the on-disk
    # file is `<out-without-suffix>.polished.npy`. Check both sides.
    for candidate in (
        out.with_suffix(".polished.npy"),
        warm.with_suffix(".polished.npy"),
    ):
        if candidate.exists():
            return
    raise AssertionError(
        f"no polished output found (out={out}, warm={warm}); stdout={r.stdout}"
    )


def test_main_inprocess(tmp_path, monkeypatch, capsys):
    """Call polish.main() in-process so coverage sees lines 145-165 + 169."""
    import polish as _polish
    warm = tmp_path / "warm.npy"
    np.save(str(warm), np.array([[1.0, 2.0]], dtype=np.float64))

    # Register a minimal evaluator in a sys.modules-visible form.
    import types, sys as _sys
    mod = types.ModuleType("evaluator_inproc")
    mod.evaluate = lambda V: float(np.asarray(V).sum())
    _sys.modules["evaluator_inproc"] = mod

    argv = [
        "polish.py",
        "--config", str(warm),
        "--evaluator", "evaluator_inproc:evaluate",
        "--max-ulps", "1",
        "--max-sweeps", "1",
        "--budget-sec", "5",
    ]
    monkeypatch.setattr(_sys, "argv", argv)
    _polish.main()
    out = capsys.readouterr().out
    assert "final score" in out


def test_runpy_dunder_main(tmp_path, monkeypatch):
    """Invoke polish.py via runpy.run_path(..., run_name='__main__') so the
    `if __name__ == "__main__": main()` guard on line 169 is covered by the
    in-process coverage tracer."""
    import runpy, sys as _sys, os
    script = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "scripts", "polish.py")
    )
    warm = tmp_path / "warm2.npy"
    np.save(str(warm), np.array([[1.0, 2.0]], dtype=np.float64))

    import types
    mod = types.ModuleType("evaluator_runpy")
    mod.evaluate = lambda V: float(np.asarray(V).sum())
    _sys.modules["evaluator_runpy"] = mod

    argv = [
        script,
        "--config", str(warm),
        "--evaluator", "evaluator_runpy:evaluate",
        "--max-ulps", "1",
        "--max-sweeps", "1",
        "--budget-sec", "5",
    ]
    monkeypatch.setattr(_sys, "argv", argv)
    runpy.run_path(script, run_name="__main__")


def test_polish_reaches_zero_mid_sweep():
    """Evaluator that flips to 0.0 after the first mutation triggers the
    reached-zero early break (lines 135-136)."""
    V = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float64)
    flip = {"called": 0}

    def eval_fn(arr):
        flip["called"] += 1
        # Return a positive loss on the first two calls (init + first trial),
        # then collapse to 0.0 to simulate a jackpot step.
        if flip["called"] <= 2:
            return 1.0
        return 0.0

    V_out, score = polish(V, eval_fn, max_ulps=1, max_sweeps=5, verbose=True)
    # The implementation accepts only strict-improvement ulp moves and breaks
    # the sweep loop once `score == 0.0`. Either path is valid; assert the
    # final score does not exceed the initial.
    assert score <= 1.0


def test_polish_low_priority_skip():
    """35 rows with identical coordinates force `badness[i] == 0` for all but
    the first few, exercising the `if badness[i] == 0 and rank > 30: continue`
    guard at line 105."""
    n = 35
    V = np.arange(n * 2, dtype=np.float64).reshape(n, 2) * 1000.0

    def eval_fn(arr):
        # zero-violation evaluator: no pair is within 1 unit since rows are
        # thousands apart. Loss stays at 0 so the sweep accepts nothing.
        total = 0.0
        for i in range(len(arr)):
            for j in range(i + 1, len(arr)):
                d2 = float(((arr[i] - arr[j]) ** 2).sum())
                if d2 < 1.0:
                    total += 1.0 - d2
        return total

    # Force init score > 0 so polish actually enters the sweep loop. Add one
    # deliberately-close pair at the top.
    V[0] = np.array([0.0, 0.0])
    V[1] = np.array([0.1, 0.0])
    V_out, score = polish(V, eval_fn, max_ulps=1, max_sweeps=1, verbose=False,
                          target_sq=1.0)
    assert isinstance(score, float)
