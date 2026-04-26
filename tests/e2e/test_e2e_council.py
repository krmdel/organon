"""E.3 — sci-council end-to-end tests.

Per context/memory/organon_upgrade_final_handoff.md §3.3. Unit tests mock
`_call_persona`; these tests exercise the full parse → dedup → rank → render
pipeline on realistic response strings and confirm the orchestrator's
parallelism, determinism, and failure-degradation guarantees.
"""
from __future__ import annotations

import threading
import time
from unittest.mock import patch

import pytest

import council
from council import CouncilAllFailedError, run_council, synthesize_responses


def _side_effect_from(mapping: dict[str, str]):
    def side_effect(persona, problem):
        if persona not in mapping:
            raise RuntimeError(f"no response configured for {persona}")
        return mapping[persona]
    return side_effect


# ---------------------------------------------------------------------------
# E.3.1 — 3/3 consensus round-trip
# ---------------------------------------------------------------------------

def test_e3_1_full_consensus(council_mock_responses):
    responses = council_mock_responses(mode="all_agree", names=["Singer construction"])
    out = synthesize_responses(responses)

    assert "Singer construction" in out
    # Exactly one row for Singer (3/3 flag).
    assert out.count("Singer construction") == 1
    assert "3/3" in out


# ---------------------------------------------------------------------------
# E.3.2 — 2/3 consensus + dissent
# ---------------------------------------------------------------------------

def test_e3_2_two_of_three_plus_dissent(council_mock_responses):
    responses = council_mock_responses(mode="2of3_plus_dissent")
    out = synthesize_responses(responses)

    assert "Shared-approach" in out
    assert "Dissenting-approach" in out
    assert "2/3" in out
    assert "1/3" in out

    # Shared should outrank Dissenting. Find row indices in the rendered table.
    lines = out.splitlines()
    shared_idx = next(i for i, ln in enumerate(lines) if "Shared-approach" in ln)
    dissent_idx = next(i for i, ln in enumerate(lines) if "Dissenting-approach" in ln)
    assert shared_idx < dissent_idx, "2/3 consensus should rank above 1/3 dissent"


# ---------------------------------------------------------------------------
# E.3.3 — 0/3 consensus (9 distinct approaches)
# ---------------------------------------------------------------------------

def test_e3_3_zero_consensus_nine_distinct(council_mock_responses):
    responses = council_mock_responses(mode="all_distinct")
    out = synthesize_responses(responses)

    # Every approach 1/3. Exactly 9 distinct approach rows.
    assert out.count("1/3") == 9
    assert "2/3" not in out
    assert "3/3" not in out


# ---------------------------------------------------------------------------
# E.3.4 — Determinism across repeated synthesis calls
# ---------------------------------------------------------------------------

def test_e3_4_synthesis_determinism(council_mock_responses):
    responses = council_mock_responses(mode="2of3_plus_dissent")
    first = synthesize_responses(responses)
    for _ in range(9):
        assert synthesize_responses(responses) == first


# ---------------------------------------------------------------------------
# E.3.5 — Single-persona timeout degrades to 2/3 without dying
# ---------------------------------------------------------------------------

def test_e3_5_single_persona_timeout_degradation(council_mock_responses):
    responses = council_mock_responses(mode="all_distinct")

    def side_effect(persona, problem):
        if persona == "Erdős":
            # Simulate a slow call: sleep past the council's wait budget so the
            # Event times out and Erdős gets recorded as unavailable.
            time.sleep(2.0)
            return responses[persona]
        return responses[persona]

    with patch("council._call_persona", side_effect=side_effect):
        out = run_council("Prove a theorem.", timeout_sec=0.4)

    # 2-of-3 banner fires.
    assert "2-of-3" in out or "Erdős unavailable" in out or "Erdős" in out
    # Only Gauss + Tao approaches landed (6 rows of 1/3).
    assert "Alpha-A" in out
    assert "Gamma-A" in out
    # Erdős's distinct approaches should NOT appear as successful rows.
    # (They might still appear inside a WARNING line, so check the approach
    # name outside a "unavailable" marker.)
    lines_with_beta = [
        ln for ln in out.splitlines()
        if "Beta-" in ln and "unavailable" not in ln and "WARNING" not in ln
    ]
    assert not lines_with_beta, f"Erdős content leaked: {lines_with_beta}"


# ---------------------------------------------------------------------------
# E.3.6 — All personas fail → CouncilAllFailedError
# ---------------------------------------------------------------------------

def test_e3_6_all_personas_fail_raises():
    def side_effect(persona, problem):
        raise RuntimeError(f"{persona} offline for maintenance")

    with patch("council._call_persona", side_effect=side_effect):
        with pytest.raises(CouncilAllFailedError) as exc_info:
            run_council("anything", timeout_sec=1.0)

    msg = str(exc_info.value)
    assert "Gauss" in msg and "Erdős" in msg and "Tao" in msg
    # Each persona's failure reason is enumerated.
    assert msg.count("RuntimeError") >= 3 or "maintenance" in msg


# ---------------------------------------------------------------------------
# E.3.7 — Persona-selector override (2-persona council)
# ---------------------------------------------------------------------------

def test_e3_7_persona_override_two_personas(council_mock_responses):
    responses = council_mock_responses(mode="all_distinct")
    call_log = []

    def side_effect(persona, problem):
        call_log.append(persona)
        return responses[persona]

    with patch("council._call_persona", side_effect=side_effect):
        out = run_council("anything", personas=["Gauss", "Erdős"], timeout_sec=2.0)

    assert sorted(call_log) == ["Erdős", "Gauss"]
    assert "Tao" not in call_log
    # Only Gauss + Erdős approaches in output.
    assert "Alpha-A" in out
    assert "Beta-A" in out
    # Tao's distinct approaches should not appear as synthesised rows.
    lines_with_gamma = [
        ln for ln in out.splitlines()
        if "Gamma-" in ln and "unavailable" not in ln and "WARNING" not in ln
    ]
    assert not lines_with_gamma


# ---------------------------------------------------------------------------
# E.3.8 — Empty-problem fast-fail, never calls personas
# ---------------------------------------------------------------------------

def test_e3_8_empty_problem_fast_fail():
    calls = []

    def side_effect(persona, problem):
        calls.append(persona)
        return ""

    with patch("council._call_persona", side_effect=side_effect):
        with pytest.raises(ValueError):
            run_council("", timeout_sec=1.0)
        with pytest.raises(ValueError):
            run_council("   \n\t", timeout_sec=1.0)

    assert calls == [], f"personas were called despite empty input: {calls}"


# ---------------------------------------------------------------------------
# E.3.9 — Parallelism is real
# ---------------------------------------------------------------------------

def test_e3_9_parallelism_real(council_mock_responses):
    """Three personas each sleep 0.3s. If calls run sequentially we'd see ~0.9s;
    parallel execution should finish in < 0.7s (50% slack for CI jitter)."""
    responses = council_mock_responses(mode="all_agree", names=["Shared-tech"])

    def slow_side_effect(persona, problem):
        time.sleep(0.3)
        return responses[persona]

    with patch("council._call_persona", side_effect=slow_side_effect):
        t0 = time.time()
        out = run_council("Prove a theorem.", timeout_sec=3.0)
        dt = time.time() - t0

    assert "Shared-tech" in out
    assert dt < 0.7, f"personas ran sequentially: {dt:.2f}s wall-clock"
