"""E.5 — sci-literature-research fanout end-to-end tests.

Per context/memory/organon_upgrade_final_handoff.md §3.5. Unit tests stub
the 4 backends individually; these tests confirm the merge + ranking +
dedup pipeline works on realistic paper metadata shapes.

Zero live network — every backend is a callable returning fake paper dicts.
"""
from __future__ import annotations

import time

import pytest

from fanout import FanoutAllFailedError, parallel_fanout


def _paper(doi: str | None = None, arxiv_id: str | None = None, *,
           title: str = "demo", year: int = 2024) -> dict:
    d = {"title": title, "year": year, "authors": ["A"]}
    if doi is not None:
        d["doi"] = doi
    if arxiv_id is not None:
        d["arxiv_id"] = arxiv_id
    return d


# ---------------------------------------------------------------------------
# E.5.1 — All 4 backends succeed; 30 unique papers after dedup
# ---------------------------------------------------------------------------

def test_e5_1_all_four_backends_succeed():
    def mk_backend(offset: int):
        return lambda q: [
            _paper(doi=f"10.{offset}/{i}", title=f"paper-{offset}-{i}")
            for i in range(10)
        ]
    backends = {
        "pubmed": mk_backend(100),
        "arxiv": mk_backend(200),
        "openalex": mk_backend(300),
        "s2": mk_backend(400),
    }
    out = parallel_fanout("sphere packing", backends, timeout_per_source=2.0)
    assert not out["degraded"]
    assert out["failed_sources"] == []
    # 10 per backend × 4 backends = 40 unique DOIs (no overlap, all distinct).
    assert len(out["results"]) == 40
    for name in backends:
        assert out["source_counts"][name] == 10


# ---------------------------------------------------------------------------
# E.5.2 — DOI dedupe across backends (first-seen wins)
# ---------------------------------------------------------------------------

def test_e5_2_doi_dedupe_across_backends():
    shared = "10.9999/shared"
    backends = {
        "pubmed": lambda q: [_paper(doi=shared, title="pubmed-version")],
        "arxiv":  lambda q: [_paper(doi=shared, title="arxiv-version")],
        "openalex": lambda q: [_paper(doi=shared, title="openalex-version")],
    }
    out = parallel_fanout("q", backends, timeout_per_source=2.0)
    assert len(out["results"]) == 1
    # First-seen winner is the first backend in the dict (pubmed).
    assert out["results"][0]["title"] == "pubmed-version"


# ---------------------------------------------------------------------------
# E.5.3 — arXiv-ID dedupe when DOI missing
# ---------------------------------------------------------------------------

def test_e5_3_arxiv_dedupe_when_doi_missing():
    aid = "2405.12345"
    backends = {
        "arxiv":  lambda q: [_paper(arxiv_id=aid, title="arxiv-version")],
        "s2":     lambda q: [_paper(arxiv_id=aid, title="s2-version")],
    }
    out = parallel_fanout("q", backends, timeout_per_source=2.0)
    assert len(out["results"]) == 1
    assert out["results"][0]["title"] == "arxiv-version"


# ---------------------------------------------------------------------------
# E.5.4 — No cross-match between DOI-only and arxiv-only (per _paper_key)
# ---------------------------------------------------------------------------

def test_e5_4_no_cross_match_doi_vs_arxiv():
    # The contract is: _paper_key returns ("doi", ...) OR ("arxiv", ...),
    # never both. So a paper with only a DOI and one with only an arxiv_id
    # must appear as two rows even if they are "the same paper" in reality.
    backends = {
        "pubmed": lambda q: [_paper(doi="10.1/x", title="doi-only")],
        "arxiv":  lambda q: [_paper(arxiv_id="2407.00000", title="arxiv-only")],
    }
    out = parallel_fanout("q", backends, timeout_per_source=2.0)
    assert len(out["results"]) == 2


# ---------------------------------------------------------------------------
# E.5.5 — One-backend timeout → degraded
# ---------------------------------------------------------------------------

def test_e5_5_single_backend_timeout():
    def slow(q):
        time.sleep(2.0)
        return [_paper(doi="10.slow/1")]

    backends = {
        "fast":  lambda q: [_paper(doi="10.fast/1")],
        "slow":  slow,
    }
    t0 = time.time()
    out = parallel_fanout("q", backends, timeout_per_source=0.3)
    dt = time.time() - t0
    assert dt < 1.0, f"fanout blocked past its timeout: {dt:.2f}s"
    assert out["degraded"] is True
    assert "slow" in out["failed_sources"]
    # Fast backend's result still present.
    assert len(out["results"]) >= 1


# ---------------------------------------------------------------------------
# E.5.6 — All backends fail raises FanoutAllFailedError
# ---------------------------------------------------------------------------

def test_e5_6_all_backends_fail():
    def boom(q):
        raise RuntimeError("backend offline")

    backends = {"a": boom, "b": boom, "c": boom, "d": boom}
    with pytest.raises(FanoutAllFailedError) as exc_info:
        parallel_fanout("q", backends, timeout_per_source=2.0)

    err = exc_info.value
    assert set(err.failures.keys()) == {"a", "b", "c", "d"}
    for reason in err.failures.values():
        assert "backend offline" in reason


# ---------------------------------------------------------------------------
# E.5.7 — Ranking stability / merge order is deterministic (dict-insertion)
# ---------------------------------------------------------------------------

def test_e5_7_ranking_stability():
    # Same papers, different per-backend orderings → final order is
    # first-seen by backend dict iteration order.
    papers_a = [_paper(doi=f"10.A/{i}") for i in range(5)]
    papers_b = list(reversed(papers_a))
    backends = {
        "A": lambda q, p=papers_a: list(p),
        "B": lambda q, p=papers_b: list(p),
    }
    out1 = parallel_fanout("q", backends, timeout_per_source=2.0)
    out2 = parallel_fanout("q", backends, timeout_per_source=2.0)
    dois1 = [r["doi"] for r in out1["results"]]
    dois2 = [r["doi"] for r in out2["results"]]
    assert dois1 == dois2
    # Backend A is first in the dict, so its order wins.
    assert dois1 == [p["doi"] for p in papers_a]


# ---------------------------------------------------------------------------
# E.5.8 — Module import is safe without MCP / network
# ---------------------------------------------------------------------------

def test_e5_8_module_import_is_safe():
    import importlib
    import fanout as f_mod
    importlib.reload(f_mod)
    assert callable(f_mod.parallel_fanout)


# ---------------------------------------------------------------------------
# E.5.9 — Parallelism wall-clock check
# ---------------------------------------------------------------------------

def test_e5_9_parallelism_real():
    def slow_backend(q):
        time.sleep(0.2)
        return [_paper(doi="10.slow/x")]

    backends = {f"b{i}": slow_backend for i in range(4)}
    t0 = time.time()
    out = parallel_fanout("q", backends, timeout_per_source=2.0)
    dt = time.time() - t0
    assert dt < 0.6, f"backends ran sequentially: {dt:.2f}s (expected ~0.2s + overhead)"
    # All 4 succeed → one merged result (same DOI) but failed_sources empty.
    assert out["failed_sources"] == []


# ---------------------------------------------------------------------------
# E.5.10 — URL-prefixed DOI normalisation collapses to one row
# ---------------------------------------------------------------------------

def test_e5_10_url_prefixed_doi_dedupe():
    backends = {
        "a": lambda q: [_paper(doi="https://doi.org/10.1234/x", title="url-form")],
        "b": lambda q: [_paper(doi="10.1234/x", title="bare-form")],
        "c": lambda q: [_paper(doi="doi:10.1234/x", title="doi-prefix-form")],
    }
    out = parallel_fanout("q", backends, timeout_per_source=2.0)
    assert len(out["results"]) == 1
    assert out["results"][0]["title"] == "url-form"  # first-seen wins
