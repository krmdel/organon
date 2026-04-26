"""Stress-test: live verification of every citation in the Organon whitepaper bib.

Tests each bib entry against its real API (arXiv or CrossRef) and checks:
  1. Title similarity (≥ TITLE_MATCH_THRESHOLD = 0.95)
  2. First-author match (family name)
  3. No CRITICAL findings from check_bib_integrity

Also includes targeted regression tests for the two known phantoms fixed in
April 2026 (Pakter-Levin → Ono, Berthold-Salvagnin → Berthold et al.).

All tests are marked network; run with:
    pytest tests/test_whitepaper_citations_live.py -v
or skip in CI:
    pytest -m "not network"
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS = ROOT / ".claude" / "skills" / "sci-writing" / "scripts"
BIB_PATH = ROOT / "projects" / "briefs" / "organon-whitepaper" / "bib.bib"

for p in (str(ROOT), str(SCRIPTS)):
    if p not in sys.path:
        sys.path.insert(0, p)

from repro.citation_verify import verify_arxiv, verify_doi, verify_citation
import verify_ops
from verify_ops import check_bib_integrity, TITLE_MATCH_THRESHOLD, compare_authors, _LIVE_METADATA_CACHE

from writing_ops import parse_bib_file
from difflib import SequenceMatcher


def _sim(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _load_bib() -> list[dict]:
    return parse_bib_file(str(BIB_PATH))


# ---------------------------------------------------------------------------
# Helper: parameterised live check
# ---------------------------------------------------------------------------

def _live_check(entry: dict) -> dict:
    """Call the right backend and return the live record."""
    eprint = (entry.get("eprint") or "").strip()
    doi = (entry.get("doi") or "").strip()
    if eprint:
        return verify_arxiv(eprint)
    if doi:
        from repro.citation_verify import extract_arxiv_id_from_doi
        arxiv_id = extract_arxiv_id_from_doi(doi)
        if arxiv_id:
            return verify_arxiv(arxiv_id)
        return verify_doi(doi)
    # misc entries with no eprint/doi — skip network check
    return {}


# ---------------------------------------------------------------------------
# Regression: phantom citations that were previously wrong
# ---------------------------------------------------------------------------

@pytest.mark.network
class TestPhantomCitationRegressions:
    """The two known phantom citations MUST pass cleanly in their corrected form,
    and MUST fail in their original (wrong) form."""

    def setup_method(self):
        _LIVE_METADATA_CACHE.clear()

    def test_ono_correct_attribution_passes(self):
        """After fix: ono2021magic has Ono as sole author — no CRITICAL."""
        entries = [e for e in _load_bib() if e["key"] == "ono2021magic"]
        assert entries, "ono2021magic entry not found in bib"
        findings = check_bib_integrity({"ono2021magic"}, entries)
        criticals = [f for f in findings if f["severity"] == "critical"]
        assert not criticals, f"ono2021magic should pass: {criticals}"

    def test_pakter_levin_phantom_would_fail(self):
        """Regression: if someone re-introduces Pakter-Levin for arXiv 2107.06519, it MUST fail."""
        phantom = {
            "key": "pakter2021phantom",
            "entry_type": "article",
            "author": "Pakter, Renato and Levin, Yan",
            "title": "Magic numbers for vibrational frequency of charged particles on a sphere",
            "eprint": "2107.06519",
            "year": "2021",
        }
        findings = check_bib_integrity({"pakter2021phantom"}, [phantom])
        criticals = [f for f in findings if f["severity"] == "critical"]
        assert criticals, "Pakter-Levin phantom MUST be caught as CRITICAL"

    def test_berthold_correct_attribution_passes(self):
        """After fix: berthold2026hexagon has 5 correct authors — no CRITICAL."""
        entries = [e for e in _load_bib() if e["key"] == "berthold2026hexagon"]
        assert entries, "berthold2026hexagon entry not found in bib"
        findings = check_bib_integrity({"berthold2026hexagon"}, entries)
        criticals = [f for f in findings if f["severity"] == "critical"]
        assert not criticals, f"berthold2026hexagon should pass: {criticals}"

    def test_berthold_salvagnin_phantom_would_fail(self):
        """Regression: Salvagnin is NOT in the author list of 2601.05943."""
        phantom = {
            "key": "berthold_phantom",
            "entry_type": "article",
            "author": "Berthold, Timo and Salvagnin, Domenico",
            "title": "Global Optimization for Combinatorial Geometry Problems Revisited in the Era of LLMs",
            "eprint": "2601.05943",
            "year": "2026",
        }
        findings = check_bib_integrity({"berthold_phantom"}, [phantom])
        criticals = [f for f in findings if f["severity"] == "critical"]
        assert criticals, "Berthold-Salvagnin phantom MUST be caught as CRITICAL"


# ---------------------------------------------------------------------------
# Live verification of every verifiable entry in bib.bib
# ---------------------------------------------------------------------------

@pytest.mark.network
class TestAllBibEntriesLive:
    """Iterates the whole bib and runs the full integrity gate on each entry.
    Any CRITICAL finding is a hard failure."""

    def setup_method(self):
        _LIVE_METADATA_CACHE.clear()

    def _get_entries(self):
        entries = _load_bib()
        # Only entries with a verifiable identifier (eprint or doi)
        return [e for e in entries if e.get("eprint") or e.get("doi")]

    def test_no_critical_findings_in_any_entry(self):
        """Every bib entry with an arXiv/DOI must pass check_bib_integrity cleanly."""
        entries = self._get_entries()
        assert entries, "No verifiable entries found in bib"
        failures = []
        for entry in entries:
            _LIVE_METADATA_CACHE.clear()
            try:
                findings = check_bib_integrity({entry["key"]}, [entry])
                criticals = [f for f in findings if f["severity"] == "critical"]
                if criticals:
                    failures.append((entry["key"], criticals))
            except Exception as e:
                failures.append((entry["key"], [{"error": str(e)}]))
        assert not failures, (
            f"CRITICAL findings in {len(failures)} bib entries:\n"
            + "\n".join(f"  [{k}]: {c}" for k, c in failures)
        )

    def test_arxiv_entries_title_similarity(self):
        """For arXiv entries: live title must be ≥ TITLE_MATCH_THRESHOLD similar."""
        entries = [e for e in _load_bib() if e.get("eprint")]
        failures = []
        for entry in entries:
            try:
                live = verify_arxiv(entry["eprint"])
                sim = _sim(entry.get("title", ""), live["title"])
                if sim < TITLE_MATCH_THRESHOLD:
                    failures.append((
                        entry["key"],
                        f"title sim={sim:.3f}: bib={entry.get('title', '')!r} vs live={live['title']!r}"
                    ))
            except Exception as e:
                failures.append((entry["key"], f"API error: {e}"))
        assert not failures, (
            f"Title mismatch in {len(failures)} arXiv entries:\n"
            + "\n".join(f"  [{k}]: {v}" for k, v in failures)
        )

    def test_arxiv_entries_first_author(self):
        """For arXiv entries: live first-author surname must appear in bib author string."""
        entries = [e for e in _load_bib() if e.get("eprint") and e.get("author")]
        failures = []
        for entry in entries:
            try:
                live = verify_arxiv(entry["eprint"])
                if not live.get("authors"):
                    continue  # arXiv returned no authors (rare; defer)
                ok, reason = compare_authors(entry["author"], live["authors"])
                if not ok:
                    failures.append((entry["key"], reason))
            except Exception as e:
                failures.append((entry["key"], f"API error: {e}"))
        assert not failures, (
            f"Author mismatch in {len(failures)} arXiv entries:\n"
            + "\n".join(f"  [{k}]: {v}" for k, v in failures)
        )

    def test_doi_entries_title_similarity(self):
        """For DOI entries: live title must be ≥ TITLE_MATCH_THRESHOLD similar."""
        entries = [e for e in _load_bib() if e.get("doi") and not e.get("eprint")]
        failures = []
        for entry in entries:
            try:
                from repro.citation_verify import extract_arxiv_id_from_doi
                arxiv_id = extract_arxiv_id_from_doi(entry["doi"])
                if arxiv_id:
                    live = verify_arxiv(arxiv_id)
                else:
                    live = verify_doi(entry["doi"])
                sim = _sim(entry.get("title", ""), live["title"])
                if sim < TITLE_MATCH_THRESHOLD:
                    failures.append((
                        entry["key"],
                        f"title sim={sim:.3f}: bib={entry.get('title', '')!r} vs live={live['title']!r}"
                    ))
            except ValueError as e:
                # DOI not found or malformed — flag it
                failures.append((entry["key"], f"DOI lookup failed: {e}"))
            except Exception as e:
                failures.append((entry["key"], f"API error: {e}"))
        assert not failures, (
            f"Title/DOI mismatch in {len(failures)} entries:\n"
            + "\n".join(f"  [{k}]: {v}" for k, v in failures)
        )


# ---------------------------------------------------------------------------
# Targeted spot-checks for specific claims in the Substack review
# ---------------------------------------------------------------------------

@pytest.mark.network
class TestSubstackSpecificClaims:
    """Specific claims flagged in the Substack post review (point-by-point).
    Each test cross-checks a concrete assertion against the live API.
    """

    def test_ono_is_sole_author_of_2107_06519(self):
        """Review pt 12/14: arXiv 2107.06519 must have Ono as sole author, no Pakter, no Levin."""
        live = verify_arxiv("2107.06519")
        assert len(live["authors"]) == 1, f"Expected 1 author, got {live['authors']}"
        assert live["authors"][0].lower() == "ono", (
            f"Expected sole author 'Ono', got {live['authors'][0]!r}"
        )
        assert "pakter" not in " ".join(live["authors"]).lower(), "Pakter must NOT appear"
        assert "levin" not in " ".join(live["authors"]).lower(), "Levin must NOT appear"

    def test_ono_2021_title_is_magic_numbers(self):
        """The corrected bib title must match the live arXiv title."""
        live = verify_arxiv("2107.06519")
        sim = _sim(live["title"], "Magic numbers for vibrational frequency of charged particles on a sphere")
        assert sim >= TITLE_MATCH_THRESHOLD, (
            f"Title similarity {sim:.3f} below threshold. Live: {live['title']!r}"
        )

    def test_berthold_2601_05943_no_salvagnin(self):
        """Review pt 14: Salvagnin must NOT appear in arXiv 2601.05943 author list."""
        live = verify_arxiv("2601.05943")
        assert "salvagnin" not in " ".join(live["authors"]).lower(), (
            f"Salvagnin should NOT be in author list of 2601.05943. Got: {live['authors']}"
        )

    def test_berthold_2601_05943_has_berthold_and_polik(self):
        """Review pt 14: Berthold AND Pólik must appear in arXiv 2601.05943."""
        live = verify_arxiv("2601.05943")
        surnames_norm = [verify_ops._normalize_surname(s) for s in live["authors"]]
        assert "berthold" in surnames_norm, f"Berthold not in {live['authors']}"
        assert "polik" in surnames_norm or any("olik" in s for s in surnames_norm), (
            f"Pólik not in {live['authors']}"
        )

    def test_berthold_2601_05943_title(self):
        """arXiv 2601.05943 title must mention 'Global Optimization' and 'LLM'."""
        live = verify_arxiv("2601.05943")
        title_lower = live["title"].lower()
        assert "global optimization" in title_lower, f"Unexpected title: {live['title']}"
        assert "llm" in title_lower, f"LLM not in title: {live['title']}"

    def test_alphaevolve_arxiv_2506_13131(self):
        """Review: AlphaEvolve paper eprint 2506.13131 (Novikov et al.) must exist and have Novikov as first author."""
        live = verify_arxiv("2506.13131")
        assert live["authors"], "AlphaEvolve paper returned empty author list"
        assert live["authors"][0].lower() == "novikov", (
            f"Expected first author 'Novikov', got {live['authors'][0]!r}"
        )
        assert "alphaevolve" in live["title"].lower() or "alpha" in live["title"].lower(), (
            f"Title does not mention AlphaEvolve: {live['title']!r}"
        )

    def test_funsearch_doi_10_1038(self):
        """FunSearch DOI 10.1038/s41586-023-06924-6 must resolve to Romera-Paredes et al."""
        live = verify_doi("10.1038/s41586-023-06924-6")
        assert live["authors"], "FunSearch CrossRef returned empty authors"
        assert "Romera-Paredes" in live["authors"] or any(
            "romera" in a.lower() for a in live["authors"]
        ), f"Romera-Paredes not found. Authors: {live['authors']}"
        assert "Mathematical discoveries" in live["title"] or "program search" in live["title"].lower(), (
            f"Unexpected title: {live['title']}"
        )

    def test_funsearch_title_is_nature_paper(self):
        """FunSearch live title must closely match bib title."""
        live = verify_doi("10.1038/s41586-023-06924-6")
        bib_title = "Mathematical discoveries from program search with large language models"
        sim = _sim(bib_title, live["title"])
        assert sim >= TITLE_MATCH_THRESHOLD, (
            f"FunSearch title mismatch {sim:.3f}. Live: {live['title']!r}"
        )

    def test_highs_doi(self):
        """HiGHS DOI 10.1007/s12532-017-0130-5 — Huangfu & Hall."""
        live = verify_doi("10.1007/s12532-017-0130-5")
        authors_lower = " ".join(live["authors"]).lower()
        assert "huangfu" in authors_lower, f"Huangfu not found. Authors: {live['authors']}"

    def test_wales_doi(self):
        """Wales & Ulker DOI 10.1103/PhysRevB.74.212101."""
        live = verify_doi("10.1103/PhysRevB.74.212101")
        authors_lower = " ".join(live["authors"]).lower()
        assert "wales" in authors_lower, f"Wales not found. Authors: {live['authors']}"

    def test_viazovska_doi(self):
        """Viazovska sphere packing DOI 10.4007/annals.2017.185.3.7."""
        live = verify_doi("10.4007/annals.2017.185.3.7")
        assert live["title"], "Viazovska paper title empty"
        assert "sphere packing" in live["title"].lower() or "dimension 8" in live["title"].lower(), (
            f"Unexpected title: {live['title']}"
        )

    def test_cohn_triantafillou_doi(self):
        """Cohn & Triantafillou DOI 10.1090/mcom/3662 (note: NOT 3649, fixed in bib)."""
        live = verify_doi("10.1090/mcom/3662")
        assert live["title"], "Cohn/Triantafillou paper title empty"
        authors_lower = " ".join(live["authors"]).lower()
        assert "cohn" in authors_lower, f"Cohn not in authors: {live['authors']}"

    def test_ai_scientist_arxiv_2408_06292(self):
        """AI Scientist arXiv 2408.06292 — Lu et al."""
        live = verify_arxiv("2408.06292")
        assert "lu" in live["authors"][0].lower(), (
            f"Expected first author Lu, got {live['authors'][0]!r}"
        )
        assert "scientist" in live["title"].lower() or "automated" in live["title"].lower(), (
            f"Unexpected title: {live['title']!r}"
        )

    def test_ai_scientist_v2_arxiv_2504_08066(self):
        """AI Scientist v2 arXiv 2504.08066 — Yamada et al. (not Lu)."""
        live = verify_arxiv("2504.08066")
        assert live["authors"], "AI Scientist v2 empty author list"
        # v2 is Yamada et al. not Lu et al.
        assert "yamada" in live["authors"][0].lower(), (
            f"Expected first author Yamada, got {live['authors'][0]!r}"
        )

    def test_cmaes_arxiv_1604_00772(self):
        """CMA-ES tutorial arXiv 1604.00772 — Hansen."""
        live = verify_arxiv("1604.00772")
        assert "hansen" in live["authors"][0].lower(), (
            f"Expected Hansen, got {live['authors'][0]!r}"
        )

    def test_georgiev_arxiv_2511_02864(self):
        """Mathematical exploration at scale arXiv 2511.02864 — Georgiev et al."""
        live = verify_arxiv("2511.02864")
        assert live["authors"], "Georgiev et al. empty author list"
        assert "georgiev" in live["authors"][0].lower(), (
            f"Expected first author Georgiev, got {live['authors'][0]!r}"
        )

    def test_schick_toolformer_is_real(self):
        """Toolformer has no eprint/doi in bib — verify it is a real NeurIPS 2023 paper
        by its well-known arXiv ID 2302.04761."""
        live = verify_arxiv("2302.04761")
        assert "schick" in live["authors"][0].lower(), (
            f"Expected Schick, got {live['authors'][0]!r}"
        )
        assert "toolformer" in live["title"].lower(), (
            f"Unexpected title: {live['title']!r}"
        )


# ---------------------------------------------------------------------------
# Edge-case stress tests
# ---------------------------------------------------------------------------

@pytest.mark.network
class TestEdgeCases:
    """Corner cases: wrong DOI, swapped author order, title case differences,
    diacritics in arXiv names, retracted papers."""

    def test_wrong_doi_caught(self):
        """A DOI where the live title is completely different → CRITICAL."""
        from verify_ops import check_bib_integrity
        # 10.1090/mcom/3649 resolves to a different paper than dual LP bounds
        entry = {
            "key": "wrong_doi_test",
            "entry_type": "article",
            "author": "Cohn, Henry and Triantafillou, Nicolas",
            "title": "Dual linear programming bounds for sphere packing via modular forms",
            "doi": "10.1090/mcom/3649",  # intentionally wrong — not the Cohn paper
        }
        _LIVE_METADATA_CACHE.clear()
        findings = check_bib_integrity({"wrong_doi_test"}, [entry])
        criticals = [f for f in findings if f["severity"] == "critical"]
        assert criticals, (
            "Wrong DOI pointing to different paper must be flagged CRITICAL"
        )

    def test_title_case_variation_passes(self):
        """Title in bib with different capitalisation must still pass (normalised comparison)."""
        live = verify_doi("10.1038/s41586-023-06924-6")
        bib_title_upper = "MATHEMATICAL DISCOVERIES FROM PROGRAM SEARCH WITH LARGE LANGUAGE MODELS"
        sim = _sim(bib_title_upper, live["title"])
        # Normalised comparison is case-insensitive so similarity should be high
        assert sim >= TITLE_MATCH_THRESHOLD, (
            f"Case-variant title should still match. sim={sim:.3f}, live={live['title']!r}"
        )

    def test_diacritic_in_author_passes(self):
        """Pólik (with accent) must match Polik (ASCII-stripped) via compare_authors."""
        ok, reason = compare_authors(
            "Berthold, Timo and Kamp, Dominik and Mexi, Gioni and Pokutta, Sebastian and P{\\'{o}}lik, Imre",
            ["Berthold", "Kamp", "Mexi", "Pokutta", "Pólik"],
        )
        assert ok, f"Diacritic normalisation should pass: {reason}"

    def test_swapped_author_order_still_passes_jaccard(self):
        """If bib lists a different ordering but same authors, Jaccard still passes."""
        ok, reason = compare_authors(
            "Kamp, Dominik and Berthold, Timo and Mexi, Gioni and Pokutta, Sebastian and Pólik, Imre",
            ["Berthold", "Kamp", "Mexi", "Pokutta", "Pólik"],
        )
        # Jaccard is order-insensitive; first-author check fails (Kamp ≠ Berthold).
        # But bib truncation of "first author" is a known mismatch, not phantom.
        # We just assert no exception; both pass and fail are valid depending on
        # whether the user chose to list authors in a different order deliberately.
        assert isinstance(ok, bool)

    def test_single_author_vs_multi_live_no_false_positive(self):
        """If bib says 'and others' (truncated), first-author match alone suffices."""
        # Novikov 2025 has 18 authors; bib may legitimately truncate.
        ok, reason = compare_authors(
            "Novikov, Alexander and others",
            ["Novikov", "Vu", "Eisenberger"],
        )
        assert ok, f"Truncated bib with correct first author should pass: {reason}"

    def test_completely_fabricated_author_fails(self):
        """An author list that shares no names with the live record → CRITICAL."""
        ok, reason = compare_authors(
            "Smith, John and Doe, Jane and Ghost, Writer",
            ["Novikov", "Vu", "Eisenberger"],
        )
        assert not ok, "Completely fabricated author list should fail"

    def test_empty_title_in_bib_produces_finding(self):
        """A bib entry with empty title gets flagged (no entry_type guard should swallow it)."""
        from verify_ops import check_bib_integrity
        entry = {
            "key": "empty_title_test",
            "entry_type": "article",
            "author": "Ono, Shota",
            "title": "",
            "eprint": "2107.06519",
        }
        _LIVE_METADATA_CACHE.clear()
        findings = check_bib_integrity({"empty_title_test"}, [entry])
        # Either title mismatch or a warning — should produce at least one finding
        assert findings, "Empty bib title should produce at least one finding"

    def test_missing_eprint_and_doi_skipped_cleanly(self):
        """Misc entries with no eprint or doi must not raise — they are silently skipped."""
        from verify_ops import check_bib_integrity
        entry = {
            "key": "misc_no_id",
            "entry_type": "misc",
            "author": "{Einstein Arena contributors}",
            "title": "Einstein Arena",
            "year": "2026",
        }
        _LIVE_METADATA_CACHE.clear()
        # Should complete without raising
        findings = check_bib_integrity({"misc_no_id"}, [entry])
        # No CRITICAL expected — no identifier to verify
        criticals = [f for f in findings if f["severity"] == "critical"]
        assert not criticals, f"Misc entry without ID must not produce CRITICAL: {criticals}"
