"""TDD suite for parallel_fanout — Organon F.4.C upgrade.

Covers:
    1. fans out to N tracks in parallel (wall-clock proof)
    2. sequential default is still importable (no accidental fanout trigger)
    3. graceful degradation — 1 of 4 sources fails
    4. graceful degradation — 2 of 4 sources fail
    5. all-sources-fail raises FanoutAllFailedError
    6. DOI deduplication
    7. arXiv-ID deduplication when DOI missing
    8. first-appearance ranking preserved
    9. per-source timeout aborts a slow backend
    10. empty query raises ValueError
    11. existing SKILL.md methodology still works (no import-time crash)
    12. N=1 fanout is functionally sequential
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fanout  # noqa: E402
from fanout import FanoutAllFailedError, parallel_fanout  # noqa: E402


# ---------- helpers ---------------------------------------------------------

def _mk_paper(doi=None, arxiv_id=None, title="Untitled", year=2024, authors=None):
    return {
        "doi": doi,
        "arxiv_id": arxiv_id,
        "title": title,
        "year": year,
        "authors": authors or ["Anon"],
    }


def _slow_backend(delay: float, payload):
    def _inner(query: str):
        time.sleep(delay)
        return payload

    return _inner


# ---------- Test 1 ---------------------------------------------------------

def test_fans_out_to_four_tracks_in_parallel():
    delay = 0.25
    payloads = {
        "pubmed":   [_mk_paper(doi="10.1/a", title="A")],
        "arxiv":    [_mk_paper(arxiv_id="2301.001", title="B")],
        "openalex": [_mk_paper(doi="10.1/c", title="C")],
        "s2":       [_mk_paper(doi="10.1/d", title="D")],
    }
    backends = {name: _slow_backend(delay, pl) for name, pl in payloads.items()}

    t0 = time.time()
    out = parallel_fanout("cancer", backends, timeout_per_source=5.0)
    elapsed = time.time() - t0

    # If serial, elapsed >= 4*delay = 1.0s; parallel should finish near delay.
    assert elapsed < (delay * len(backends)) - 0.1, (
        f"fanout not parallel: elapsed={elapsed:.3f} vs serial={delay * len(backends):.3f}"
    )
    assert len(out["results"]) == 4
    assert out["degraded"] is False
    assert out["failed_sources"] == []
    assert set(out["source_counts"]) == set(backends)


# ---------- Test 2 ---------------------------------------------------------

def test_sequential_remains_default_no_side_effects_on_import():
    # Module-level names exist but nothing has run.
    assert hasattr(fanout, "parallel_fanout")
    assert hasattr(fanout, "FanoutAllFailedError")

    # Sequential helper also exists and doesn't secretly fire threads.
    assert hasattr(fanout, "sequential_search")
    backends = {
        "pubmed": lambda q: [_mk_paper(doi="10.1/x", title="X")],
    }
    out = fanout.sequential_search("q", backends)
    assert out["results"][0]["title"] == "X"
    assert out["degraded"] is False


# ---------- Test 3 ---------------------------------------------------------

def test_graceful_degradation_one_source_fails():
    def _bad(query):
        raise TimeoutError("simulated")

    backends = {
        "pubmed":   lambda q: [_mk_paper(doi="10.1/a")],
        "arxiv":    _bad,
        "openalex": lambda q: [_mk_paper(doi="10.1/b")],
        "s2":       lambda q: [_mk_paper(doi="10.1/c")],
    }
    out = parallel_fanout("q", backends, timeout_per_source=1.0)
    assert out["degraded"] is True
    assert "arxiv" in out["failed_sources"]
    assert len(out["results"]) == 3
    assert out["source_counts"]["arxiv"] == 0


# ---------- Test 4 ---------------------------------------------------------

def test_graceful_degradation_two_sources_fail():
    def _bad(query):
        raise RuntimeError("boom")

    backends = {
        "pubmed":   lambda q: [_mk_paper(doi="10.1/a")],
        "arxiv":    _bad,
        "openalex": _bad,
        "s2":       lambda q: [_mk_paper(doi="10.1/b")],
    }
    out = parallel_fanout("q", backends, timeout_per_source=1.0)
    assert out["degraded"] is True
    assert set(out["failed_sources"]) == {"arxiv", "openalex"}
    assert len(out["results"]) == 2


# ---------- Test 5 ---------------------------------------------------------

def test_all_sources_fail_raises():
    def _bad(query):
        raise RuntimeError("down")

    backends = {n: _bad for n in ("pubmed", "arxiv", "openalex", "s2")}
    with pytest.raises(FanoutAllFailedError) as excinfo:
        parallel_fanout("q", backends, timeout_per_source=1.0)
    msg = str(excinfo.value)
    for name in backends:
        assert name in msg


# ---------- Test 6 ---------------------------------------------------------

def test_dedup_by_doi():
    shared_doi = "10.1234/SHARED"
    backends = {
        "pubmed": lambda q: [
            _mk_paper(doi=shared_doi, title="first"),
            _mk_paper(doi="10.1/unique-a", title="unique-a"),
        ],
        "arxiv": lambda q: [
            _mk_paper(doi=shared_doi.lower(), title="second"),  # normalized match
            _mk_paper(doi="10.1/unique-b", title="unique-b"),
        ],
    }
    out = parallel_fanout("q", backends, timeout_per_source=2.0)
    titles = [r["title"] for r in out["results"]]
    dois = [r.get("doi", "").lower().lstrip("https://doi.org/") for r in out["results"] if r.get("doi")]
    # Only one entry per shared DOI survives.
    normalized_shared = "10.1234/shared"
    assert dois.count(normalized_shared) == 1
    assert "first" in titles  # first-seen wins
    assert "second" not in titles


# ---------- Test 7 ---------------------------------------------------------

def test_dedup_by_arxiv_id_when_no_doi():
    backends = {
        "pubmed": lambda q: [_mk_paper(arxiv_id="2301.12345", title="first")],
        "arxiv":  lambda q: [_mk_paper(arxiv_id="2301.12345", title="second")],
    }
    out = parallel_fanout("q", backends, timeout_per_source=2.0)
    assert len(out["results"]) == 1
    assert out["results"][0]["title"] == "first"


# ---------- Test 8 ---------------------------------------------------------

def test_ranking_preserves_first_appearance_order():
    backends = {
        "pubmed": lambda q: [
            _mk_paper(doi="10.1/A", title="A"),
            _mk_paper(doi="10.1/B", title="B"),
            _mk_paper(doi="10.1/C", title="C"),
        ],
        "arxiv": lambda q: [
            _mk_paper(doi="10.1/B", title="B"),
            _mk_paper(doi="10.1/D", title="D"),
            _mk_paper(doi="10.1/E", title="E"),
        ],
    }
    out = parallel_fanout("q", backends, timeout_per_source=2.0)
    titles = [r["title"] for r in out["results"]]
    # Pubmed drains first, then arxiv's novel items: A B C D E
    assert titles == ["A", "B", "C", "D", "E"]


# ---------- Test 9 ---------------------------------------------------------

def test_per_source_timeout_aborts_slow_backend():
    def _very_slow(query):
        time.sleep(10)
        return [_mk_paper(doi="10.1/late")]

    backends = {
        "pubmed":   lambda q: [_mk_paper(doi="10.1/fast-a")],
        "arxiv":    _very_slow,
        "openalex": lambda q: [_mk_paper(doi="10.1/fast-b")],
    }
    t0 = time.time()
    out = parallel_fanout("q", backends, timeout_per_source=0.3)
    elapsed = time.time() - t0
    assert elapsed < 1.0, f"timeout not enforced: elapsed={elapsed:.3f}"
    assert "arxiv" in out["failed_sources"]
    assert out["degraded"] is True


# ---------- Test 10 --------------------------------------------------------

def test_empty_query_raises():
    backends = {"pubmed": lambda q: [_mk_paper(doi="10.1/a")]}
    with pytest.raises(ValueError):
        parallel_fanout("", backends)
    with pytest.raises(ValueError):
        parallel_fanout("   ", backends)


# ---------- Test 11 --------------------------------------------------------

def test_skill_methodology_still_importable():
    # Simulates the existing skill dispatch path. Only requires that the
    # fanout module import is side-effect-free and doesn't need an MCP
    # server at load time.
    import importlib
    mod = importlib.reload(fanout)
    assert callable(mod.parallel_fanout)
    # No network activity happened just by importing.
    # Quick sanity: we can still use sequential path without firing threads.
    out = mod.sequential_search("q", {"pubmed": lambda q: [_mk_paper(doi="10.1/a")]})
    assert len(out["results"]) == 1


# ---------- Test 12 --------------------------------------------------------

def test_n_equal_one_is_functional():
    backends = {
        "solo": lambda q: [
            _mk_paper(doi="10.1/a", title="A"),
            _mk_paper(doi="10.1/b", title="B"),
        ],
    }
    out = parallel_fanout("q", backends, timeout_per_source=2.0)
    assert [r["title"] for r in out["results"]] == ["A", "B"]
    assert out["degraded"] is False
    assert out["source_counts"]["solo"] == 2


# ---------- Test 13 (bonus: max_results_per_source honoured) ---------------

def test_max_results_per_source_truncates_before_merge():
    backends = {
        "pubmed": lambda q: [_mk_paper(doi=f"10.1/a{i}", title=f"A{i}") for i in range(10)],
    }
    out = parallel_fanout("q", backends, timeout_per_source=2.0, max_results_per_source=3)
    assert len(out["results"]) == 3
    assert [r["title"] for r in out["results"]] == ["A0", "A1", "A2"]


# ---------- Test 14 (bonus: prefix-stripped DOIs / arxiv IDs dedupe) --------

def test_url_prefixed_identifiers_are_normalized():
    backends = {
        "pubmed": lambda q: [
            _mk_paper(doi="https://doi.org/10.1/SAME", title="first"),
            _mk_paper(arxiv_id="arXiv:2301.999", title="arx-first"),
        ],
        "arxiv": lambda q: [
            _mk_paper(doi="doi:10.1/same", title="second"),
            _mk_paper(arxiv_id="https://arxiv.org/abs/2301.999", title="arx-second"),
        ],
    }
    out = parallel_fanout("q", backends, timeout_per_source=2.0)
    titles = [r["title"] for r in out["results"]]
    assert "first" in titles and "second" not in titles
    assert "arx-first" in titles and "arx-second" not in titles


# ---------- Test 15 (bonus: papers without any key stay distinct) ----------

def test_papers_without_identifiers_are_not_deduped():
    backends = {
        "pubmed": lambda q: [
            {"title": "No-ID A", "year": 2024, "authors": ["X"]},
            {"title": "No-ID B", "year": 2024, "authors": ["Y"]},
        ],
    }
    out = parallel_fanout("q", backends, timeout_per_source=2.0)
    titles = [r["title"] for r in out["results"]]
    assert titles == ["No-ID A", "No-ID B"]


# ---------- Test 16 (bonus: empty-backends raises) -------------------------

def test_empty_backends_raises():
    with pytest.raises(ValueError):
        parallel_fanout("q", {})


# ---------- Test 17 (bonus: sequential empty query raises) -----------------

def test_sequential_empty_query_raises():
    with pytest.raises(ValueError):
        fanout.sequential_search("", {"p": lambda q: []})


# ---------- Test 18 (bonus: source badges merged on dedupe) ----------------

def test_source_badges_merged_on_dedupe():
    backends = {
        "pubmed": lambda q: [{
            "doi": "10.1/shared", "title": "T", "year": 2024,
            "authors": ["A"], "sources": ["PubMed"],
        }],
        "arxiv": lambda q: [{
            "doi": "10.1/shared", "title": "T", "year": 2024,
            "authors": ["A"], "sources": ["arXiv"],
        }],
    }
    out = parallel_fanout("q", backends, timeout_per_source=2.0)
    assert len(out["results"]) == 1
    assert set(out["results"][0]["sources"]) == {"PubMed", "arXiv"}
