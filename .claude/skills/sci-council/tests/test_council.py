"""Test suite for sci-council/scripts/council.py.

Tests are written FIRST (TDD). council.py doesn't exist yet — these tests
define the interface contract. Run with:
  python3 -m pytest .claude/skills/sci-council/tests/test_council.py -v

All tests are fast (mocked sub-agents, no real LLM calls).
"""
import sys
import os
import time
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from council import run_council, synthesize_responses, parse_persona_response, CouncilAllFailedError

PROBLEM = "Find the optimal packing of unit spheres in 3D space."

GAUSS_RESPONSE = """APPROACHES:
1. Lattice packing | P(BEAT): 0.85 | EFFORT: medium | REF: Gauss 1831
   Rationale: Lattice-based sphere packings achieve the theoretical density optimum for known constructions.
2. FCC arrangement | P(BEAT): 0.82 | EFFORT: low | REF: Kepler 1611
   Rationale: Face-centred cubic is the densest known regular packing.
3. Random close packing | P(BEAT): 0.64 | EFFORT: low | REF: Bernal 1960
   Rationale: Empirically achieves ~64% density, useful as a lower-bound baseline.

DEAD_ENDS: Brute force enumeration is intractable beyond small N.

CONFIDENCE: 0.90"""

ERDOS_RESPONSE = """APPROACHES:
1. Probabilistic method | P(BEAT): 0.70 | EFFORT: high | REF: Erdős 1947
   Rationale: Show a random packing achieves the desired density in expectation.
2. Graph coloring bound | P(BEAT): 0.65 | EFFORT: medium | REF: Shannon 1956
   Rationale: Chromatic number of the contact graph bounds the packing density.
3. Lattice packing | P(BEAT): 0.85 | EFFORT: medium | REF: Gauss 1831
   Rationale: Algebraic lattices achieve the best-known densities for most dimensions.

DEAD_ENDS: Pure combinatorial bounds too loose in high dimensions.

CONFIDENCE: 0.75"""

TAO_RESPONSE = """APPROACHES:
1. Harmonic analysis | P(BEAT): 0.80 | EFFORT: high | REF: Cohn-Kumar 2007
   Rationale: Linear programming bounds via Fourier analysis on the sphere.
2. Lattice packing | P(BEAT): 0.85 | EFFORT: medium | REF: Gauss 1831
   Rationale: Structured algebraic constructions are provably optimal in d=8,24.
3. SDP relaxation | P(BEAT): 0.78 | EFFORT: high | REF: Cohn 2012
   Rationale: Semidefinite programming yields tight bounds via Delsarte's method.

DEAD_ENDS: Direct algebraic constructions stall above dimension 8.

CONFIDENCE: 0.88"""


@pytest.fixture
def mock_responses():
    return {"Gauss": GAUSS_RESPONSE, "Erdős": ERDOS_RESPONSE, "Tao": TAO_RESPONSE}


@pytest.fixture
def distinct_responses():
    def _make(name, approaches):
        lines = "\n".join(
            f"{i+1}. {a} | P(BEAT): 0.50 | EFFORT: medium | REF: {name} 2000\n"
            f"   Rationale: Distinct approach {a} from {name}."
            for i, a in enumerate(approaches)
        )
        return f"APPROACHES:\n{lines}\nDEAD_ENDS: none\nCONFIDENCE: 0.50"
    return {
        "Gauss": _make("Gauss", ["AlphaA", "AlphaB", "AlphaC"]),
        "Erdős": _make("Erdős", ["BetaA", "BetaB", "BetaC"]),
        "Tao": _make("Tao", ["GammaA", "GammaB", "GammaC"]),
    }


def _side_effect_map(mapping):
    def side_effect(persona, problem):
        return mapping[persona]
    return side_effect


def test_happy_path_ranked_table(mock_responses):
    """Three personas succeed; synthesis returns a string with ≥3 ranked entries."""
    with patch("council._call_persona", side_effect=_side_effect_map(mock_responses)):
        result = run_council(PROBLEM)
    assert isinstance(result, str)
    lines = [l for l in result.splitlines() if l.strip()]
    assert len(lines) >= 3


def test_parallel_execution():
    """Concurrent persona calls complete faster than sequential would allow (< 0.5s for 3×0.1s tasks)."""
    def slow_persona(persona, problem):
        time.sleep(0.1)
        return GAUSS_RESPONSE

    with patch("council._call_persona", side_effect=slow_persona):
        t0 = time.time()
        run_council(PROBLEM)
        elapsed = time.time() - t0
    assert elapsed < 0.5, f"Expected parallel execution <0.5s, got {elapsed:.2f}s"


def test_single_persona_failure():
    """One persona TimeoutError is tolerated; output notes 2-of-3 partial results."""
    def partial(persona, problem):
        if persona == "Erdős":
            raise TimeoutError("Erdős timed out")
        return GAUSS_RESPONSE

    with patch("council._call_persona", side_effect=partial):
        result = run_council(PROBLEM)
    assert any(s in result for s in ("2-of-3", "single failure", "2 of 3", "unavailable")), result


def test_all_personas_fail():
    """All three persona failures raise CouncilAllFailedError listing all failure reasons."""
    def failing(persona, problem):
        raise RuntimeError(f"{persona} exploded")

    with patch("council._call_persona", side_effect=failing):
        with pytest.raises(CouncilAllFailedError) as exc_info:
            run_council(PROBLEM)
    msg = str(exc_info.value)
    for name in ("Gauss", "Erdős", "Tao"):
        assert name in msg


def test_duplicate_approach_deduplication():
    """Gauss and Tao both propose 'Singer construction'; synthesis merges into one 2/3 entry."""
    singer_resp = (
        "APPROACHES:\n"
        "1. Singer construction | P(BEAT): 0.80 | EFFORT: medium | REF: Singer 1938\n"
        "   Rationale: Singer difference sets have proven density.\n"
        "2. Unique approach A | P(BEAT): 0.60 | EFFORT: low | REF: X 2000\n"
        "   Rationale: Complementary direction.\n"
        "3. Unique approach B | P(BEAT): 0.55 | EFFORT: low | REF: Y 2001\n"
        "   Rationale: Alternative construction.\n"
        "DEAD_ENDS: none\nCONFIDENCE: 0.80"
    )
    other_resp = (
        "APPROACHES:\n"
        "1. Distinct approach | P(BEAT): 0.70 | EFFORT: high | REF: Z 2002\n"
        "   Rationale: Entirely different method.\n"
        "2. Another approach | P(BEAT): 0.65 | EFFORT: medium | REF: W 2003\n"
        "   Rationale: Second method.\n"
        "3. Third approach | P(BEAT): 0.60 | EFFORT: low | REF: V 2004\n"
        "   Rationale: Third method.\n"
        "DEAD_ENDS: none\nCONFIDENCE: 0.75"
    )
    responses = {"Gauss": singer_resp, "Erdős": other_resp, "Tao": singer_resp}

    result = synthesize_responses(responses)
    singer_entries = [l for l in result.splitlines() if "Singer construction" in l]
    assert len(singer_entries) == 1
    assert "2/3" in singer_entries[0] or "2-of-3" in singer_entries[0]


def test_no_agreement_nine_entries(distinct_responses):
    """Nine fully distinct approaches each appear once with 1/3 consensus."""
    result = synthesize_responses(distinct_responses)
    one_of_three_count = result.count("1/3")
    assert one_of_three_count >= 9, f"Expected ≥9 '1/3' flags, found {one_of_three_count}"


def test_empty_problem_raises_before_spawn():
    """Empty problem_statement raises ValueError without calling any sub-agent."""
    mock = MagicMock()
    with patch("council._call_persona", mock):
        with pytest.raises(ValueError):
            run_council("")
    mock.assert_not_called()


def test_persona_selector_override():
    """Passing personas=['Gauss', 'Erdős'] spawns exactly 2 sub-agents."""
    mock = MagicMock(return_value=GAUSS_RESPONSE)
    with patch("council._call_persona", mock):
        run_council(PROBLEM, personas=["Gauss", "Erdős"])
    assert mock.call_count == 2


def test_deterministic_synthesis(mock_responses):
    """synthesize_responses is deterministic: same inputs → same output twice."""
    result_a = synthesize_responses(mock_responses)
    result_b = synthesize_responses(mock_responses)
    assert result_a == result_b


def test_per_persona_timeout_budget():
    """A persona that sleeps 200s is cut off within timeout_sec=0.5; call returns < 1s."""
    def blocker(persona, problem):
        if persona == "Tao":
            time.sleep(200)
        return GAUSS_RESPONSE

    with patch("council._call_persona", side_effect=blocker):
        t0 = time.time()
        result = run_council(PROBLEM, timeout_sec=0.5)
        elapsed = time.time() - t0
    assert elapsed < 1.0, f"Expected abort within 1s, got {elapsed:.2f}s"
    assert any(s in result for s in ("timeout", "timed out", "2-of-3", "2 of 3", "unavailable")), result


def test_parse_persona_response_happy_path():
    """Well-formed response parsed into dict with approaches/dead_ends/confidence."""
    parsed = parse_persona_response(GAUSS_RESPONSE)
    assert isinstance(parsed, dict)
    assert "approaches" in parsed and "dead_ends" in parsed and "confidence" in parsed
    assert len(parsed["approaches"]) == 3
    for approach in parsed["approaches"]:
        for field in ("name", "p_beat", "effort", "ref"):
            assert field in approach, f"Missing field '{field}' in approach: {approach}"


def test_parse_persona_response_malformed():
    """Malformed response (no APPROACHES: block) raises ValueError or returns error dict.

    Accepted: raise ValueError OR return dict with 'error' key OR return empty 'approaches'.
    """
    malformed = "This response has no structure at all. Just prose."
    try:
        result = parse_persona_response(malformed)
        assert (
            "error" in result
            or result.get("approaches") == []
            or result.get("approaches") is None
        ), f"Expected error signal for malformed input, got: {result}"
    except ValueError:
        pass
