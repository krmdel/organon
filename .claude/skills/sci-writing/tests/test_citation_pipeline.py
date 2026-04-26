"""Citation-pipeline anti-hallucination tests.

Covers Tier 5 changes (April 2026) and Phase 4a PubMed backend (April 2026):

1. citation_verify.verify_arxiv  — fetches author lists from the arXiv
   Atom API; new shape mirrors verify_doi.
2. citation_verify.verify_citation — dispatcher; arXiv > CrossRef.
3. verify_ops.compare_authors — first-author + Jaccard set match,
   "and others" truncation handling, diacritic / LaTeX normalization.
4. verify_ops.check_bib_integrity — phantom-citation regression: the
   two known-bad attributions (`Pakter-Levin → Ono`, `Berthold-Salvagnin
   → Berthold et al.`) MUST come back CRITICAL.
5. verify_ops.check_quotes_against_live_source — quote substring check
   against the LIVE abstract (CrossRef / arXiv) catches a fabricated
   quote attributed to a real paper.

Network calls hit real APIs (arXiv + CrossRef) so a single
`pytest tests/test_citation_pipeline.py` exercises the whole pipeline.
Failures are real signal, not flakes — both APIs have been stable since
2010 and we use the polite-pool User-Agent.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Make sci-writing scripts importable. Test path is
# .../.claude/skills/sci-writing/tests/test_citation_pipeline.py — the
# repo root is parents[4].
ROOT = Path(__file__).resolve().parents[4]
SCRIPTS = ROOT / ".claude" / "skills" / "sci-writing" / "scripts"
for p in (str(ROOT), str(SCRIPTS)):
    if p not in sys.path:
        sys.path.insert(0, p)

from repro.citation_verify import (
    verify_arxiv,
    verify_doi,
    verify_pubmed,
    verify_citation,
    extract_arxiv_id_from_doi,
    normalize_arxiv_id,
    normalize_pmid,
    _arxiv_surname,
    _strip_diacritics,
)
import verify_ops
from verify_ops import (
    _normalize_surname,
    _bib_surnames,
    compare_authors,
    check_bib_integrity,
    check_quotes_against_live_source,
    TITLE_MATCH_THRESHOLD,
    FIRST_AUTHOR_MATCH_THRESHOLD,
    COAUTHOR_JACCARD_MIN,
)


# ---------- offline unit tests --------------------------------------------


class TestArxivIdNormalization:
    def test_canonical_new(self):
        assert normalize_arxiv_id("2107.06519") == "2107.06519"

    def test_strips_prefix_and_version(self):
        assert normalize_arxiv_id("arXiv:2107.06519v3") == "2107.06519"

    def test_legacy_id(self):
        assert normalize_arxiv_id("astro-ph/0608061") == "astro-ph/0608061"
        assert normalize_arxiv_id("cond-mat/0102001v2") == "cond-mat/0102001"

    def test_extract_arxiv_from_doi(self):
        assert extract_arxiv_id_from_doi("10.48550/arXiv.2107.06519") == "2107.06519"
        assert extract_arxiv_id_from_doi("10.1103/PhysRevB.104.094105") is None
        assert extract_arxiv_id_from_doi("") is None

    def test_garbage_raises(self):
        with pytest.raises(ValueError):
            normalize_arxiv_id("not-an-id")
        with pytest.raises(ValueError):
            normalize_arxiv_id("")


class TestSurnameExtraction:
    def test_arxiv_surname_simple(self):
        assert _arxiv_surname("Timo Berthold") == "Berthold"

    def test_arxiv_surname_diacritic(self):
        assert _arxiv_surname("Imre Pólik") == "Pólik"

    def test_arxiv_surname_particle(self):
        assert _arxiv_surname("Charles-Jean de la Vallée Poussin") == "de la Vallée Poussin"

    def test_arxiv_surname_initial(self):
        assert _arxiv_surname("M. Pawan Kumar") == "Kumar"

    def test_strip_diacritics(self):
        assert _strip_diacritics("Pólik") == "Polik"
        assert _strip_diacritics("Müller") == "Muller"
        assert _strip_diacritics("Erdős") == "Erdos"


class TestBibAuthorParsing:
    def test_normalize_surname(self):
        assert _normalize_surname("Pólik") == "polik"
        assert _normalize_surname('{\\"u}ller') == "uller"
        assert _normalize_surname("") == ""

    def test_two_authors(self):
        s, t = _bib_surnames("Berthold, Timo and Salvagnin, Domenico")
        assert s == ["berthold", "salvagnin"]
        assert t is False

    def test_single_author(self):
        s, t = _bib_surnames("Hadamard, Jacques")
        assert s == ["hadamard"]

    def test_and_others_truncation(self):
        s, t = _bib_surnames("Novikov, Alexander and others")
        assert s == ["novikov"]
        assert t is True

    def test_et_al_truncation(self):
        s, t = _bib_surnames("Smith, John et al.")
        assert s == ["smith"]
        assert t is True


class TestCompareAuthors:
    def test_clean_match(self):
        ok, _ = compare_authors("Ono, Shota", ["Ono"])
        assert ok

    def test_clean_multi(self):
        ok, _ = compare_authors(
            "Berthold, Timo and Kamp, Dominik and Mexi, Gioni and Pokutta, Sebastian and Pólik, Imre",
            ["Berthold", "Kamp", "Mexi", "Pokutta", "Pólik"],
        )
        assert ok

    def test_diacritic_difference(self):
        ok, _ = compare_authors("Polik, Imre", ["Pólik"])
        assert ok

    def test_truncation_first_author_match(self):
        ok, _ = compare_authors(
            "Novikov, Alexander and others",
            ["Novikov", "Vu", "Eisenberger"],
        )
        assert ok

    def test_truncation_first_author_mismatch(self):
        ok, reason = compare_authors(
            "Smith, John and others",
            ["Novikov", "Vu", "Eisenberger"],
        )
        assert not ok
        assert "novikov" in reason.lower() or "smith" in reason.lower()

    def test_phantom_pakter_levin(self):
        # arXiv 2107.06519 actually = Ono. Bib falsely says Pakter & Levin.
        ok, reason = compare_authors("Pakter, Renato and Levin, Yan", ["Ono"])
        assert not ok
        assert "ono" in reason.lower()

    def test_phantom_berthold_salvagnin(self):
        # arXiv 2601.05943 actually = Berthold + 4 others (no Salvagnin).
        ok, reason = compare_authors(
            "Berthold, Timo and Salvagnin, Domenico",
            ["Berthold", "Kamp", "Mexi", "Pokutta", "Pólik"],
        )
        assert not ok
        assert "salvagnin" in reason.lower()

    def test_empty_bib(self):
        ok, reason = compare_authors("", ["Smith"])
        assert not ok

    def test_empty_live_corporate_author(self):
        # CrossRef sometimes returns no individuals for collections /
        # corporate authors. Author check defers; title check still runs.
        ok, _ = compare_authors("Smith, John", [])
        assert ok


class TestThresholds:
    def test_title_threshold_tightened(self):
        assert TITLE_MATCH_THRESHOLD == 0.95

    def test_first_author_threshold(self):
        assert FIRST_AUTHOR_MATCH_THRESHOLD == 0.85

    def test_coauthor_jaccard_floor(self):
        assert COAUTHOR_JACCARD_MIN == 0.70


# ---------- integration tests (network) -----------------------------------


@pytest.mark.network
class TestArxivLive:
    def test_ono_2021(self):
        result = verify_arxiv("2107.06519")
        assert result["source"] == "arxiv"
        assert "Magic numbers" in result["title"]
        assert result["authors"] == ["Ono"]

    def test_berthold_2026(self):
        result = verify_arxiv("2601.05943")
        assert "Global Optimization" in result["title"]
        assert "Salvagnin" not in result["authors"]
        assert result["authors"][0] == "Berthold"
        assert any("Pólik" in a or "Polik" in a for a in result["authors"])

    def test_dispatcher_prefers_arxiv(self):
        out = verify_citation({
            "eprint": "2107.06519",
            "doi": "10.1103/PhysRevB.104.094105",
        })
        assert out["source"] == "arxiv"

    def test_dispatcher_falls_back_to_crossref(self):
        out = verify_citation({"doi": "10.1103/PhysRevB.104.094105"})
        assert out["source"] == "crossref"


@pytest.mark.network
class TestPhantomBibIntegration:
    """Both phantom citations from the Organon whitepaper MUST be
    flagged CRITICAL by check_bib_integrity. Synthetic regression: we
    rebuild the *original* (wrong) bib entries the writer had at the
    time of publication, then run the gate and inspect the findings.
    """

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        verify_ops._LIVE_METADATA_CACHE.clear()
        yield
        verify_ops._LIVE_METADATA_CACHE.clear()

    def _run(self, entry):
        return check_bib_integrity({entry["key"]}, [entry])

    def test_pakter_levin_caught(self):
        # Bib drift: arXiv 2107.06519 is Ono, but the LLM wrote Pakter-Levin.
        # Title remained correct (matches arXiv exactly) so the title
        # check would pass — only the author check catches this.
        entry = {
            "key": "pakter2021phantom",
            "entry_type": "article",
            "author": "Pakter, Renato and Levin, Yan",
            "title": "Magic numbers for vibrational frequency of charged particles on a sphere",
            "eprint": "2107.06519",
            "year": "2021",
        }
        findings = self._run(entry)
        criticals = [f for f in findings if f["severity"] == "critical"]
        assert criticals, f"expected CRITICAL, got: {findings}"
        author_findings = [
            f for f in criticals
            if "Author mismatch" in f["finding"]
        ]
        assert author_findings, (
            f"phantom Pakter-Levin attribution not flagged as author "
            f"mismatch. Findings: {findings}"
        )

    def test_berthold_salvagnin_caught(self):
        entry = {
            "key": "berthold2026hexagon",
            "entry_type": "article",
            "author": "Berthold, Timo and Salvagnin, Domenico",
            "title": "Global Optimization for Combinatorial Geometry Problems Revisited in the Era of LLMs",
            "eprint": "2601.05943",
            "year": "2026",
        }
        findings = self._run(entry)
        criticals = [f for f in findings if f["severity"] == "critical"]
        assert criticals, f"expected CRITICAL, got: {findings}"
        author_findings = [
            f for f in criticals
            if "Author mismatch" in f["finding"]
        ]
        assert author_findings, (
            f"phantom Berthold-Salvagnin attribution not flagged as "
            f"author mismatch. Findings: {findings}"
        )

    def test_correct_attribution_passes(self):
        # Sanity: the corrected bib (Ono alone) must pass cleanly
        # — no CRITICAL findings allowed.
        entry = {
            "key": "ono2021magic",
            "entry_type": "article",
            "author": "Ono, Shota",
            "title": "Magic numbers for vibrational frequency of charged particles on a sphere",
            "doi": "10.1103/PhysRevB.104.094105",
            "year": "2021",
        }
        findings = self._run(entry)
        criticals = [f for f in findings if f["severity"] == "critical"]
        assert not criticals, (
            f"correct attribution should not trigger CRITICAL: {criticals}"
        )

    def test_correct_berthold_full_attribution_passes(self):
        entry = {
            "key": "berthold2026hexagon_fixed",
            "entry_type": "article",
            "author": "Berthold, Timo and Kamp, Dominik and Mexi, Gioni and Pokutta, Sebastian and Pólik, Imre",
            "title": "Global Optimization for Combinatorial Geometry Problems Revisited in the Era of LLMs",
            "eprint": "2601.05943",
            "year": "2026",
            "gray_lit": "approved",  # explicitly approve the preprint
        }
        findings = self._run(entry)
        criticals = [f for f in findings if f["severity"] == "critical"]
        assert not criticals, (
            f"corrected Berthold attribution should not trigger CRITICAL: {criticals}"
        )


@pytest.mark.network
class TestLiveQuoteSubstringCheck:
    """check_quotes_against_live_source MAJORs a quote that does not
    appear in the live abstract. Catches fabricated quotes attributed
    to real papers (the upstream provenance gate can't catch this if
    the same LLM also wrote the upstream seed)."""

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        verify_ops._LIVE_METADATA_CACHE.clear()
        yield
        verify_ops._LIVE_METADATA_CACHE.clear()

    def _make_workspace(self, tmp_path, sidecar_claims):
        manuscript = tmp_path / "draft.md"
        manuscript.write_text("Body.\n", encoding="utf-8")
        sidecar = tmp_path / "draft.md.citations.json"
        sidecar.write_text(
            json.dumps({"version": 1, "claims": sidecar_claims}),
            encoding="utf-8",
        )
        return manuscript, sidecar

    def test_fabricated_quote_flagged_arxiv(self, tmp_path):
        # Real arXiv id, fabricated quote. Uses the arXiv backend
        # because arXiv always returns an abstract; CrossRef does not
        # for most physics journals (the live-source check defers
        # silently when no abstract is available).
        manuscript, _ = self._make_workspace(tmp_path, [
            {
                "key": "berthold2026hexagon",
                "quote": (
                    "Berthold and Salvagnin show that quartic-mode-following "
                    "predicts a continuous family of N=282 ground states "
                    "embedded in the I_h irreducible representation block."
                ),
                "source_anchor": "arXiv:2601.05943",
                "source_type": "arxiv",
                "source_confidence": "abstract",
            }
        ])
        bib = [{
            "key": "berthold2026hexagon",
            "entry_type": "article",
            "eprint": "2601.05943",
            "title": "Global Optimization for Combinatorial Geometry Problems Revisited in the Era of LLMs",
            # Use the corrected attribution so author check passes —
            # we are isolating the live-source quote check here.
            "author": "Berthold, Timo and Kamp, Dominik and Mexi, Gioni and Pokutta, Sebastian and Pólik, Imre",
            "gray_lit": "approved",
        }]
        findings = check_quotes_against_live_source(
            str(manuscript), {"berthold2026hexagon"}, bib
        )
        live_findings = [f for f in findings if f["criterion"] == "Live-Source Quote"]
        assert live_findings, f"fabricated quote should be flagged: {findings}"
        assert live_findings[0]["severity"] == "major"

    def test_real_quote_passes(self, tmp_path):
        # A real substring of the arXiv abstract should pass cleanly.
        # We cannot hardcode the abstract (it could change), so fetch
        # it live and lift a real fragment.
        from repro.citation_verify import verify_arxiv

        live = verify_arxiv("2601.05943")
        # Lift the first ~200 chars of the abstract as the "real" quote.
        real_fragment = live["abstract"][:200].strip()
        if len(real_fragment) < 80:
            pytest.skip("arxiv abstract unexpectedly short — skipping")

        manuscript, _ = self._make_workspace(tmp_path, [
            {
                "key": "berthold2026hexagon",
                "quote": real_fragment,
                "source_anchor": "arXiv:2601.05943",
                "source_type": "arxiv",
                "source_confidence": "abstract",
            }
        ])
        bib = [{
            "key": "berthold2026hexagon",
            "entry_type": "article",
            "eprint": "2601.05943",
            "title": "Global Optimization for Combinatorial Geometry Problems Revisited in the Era of LLMs",
            "author": "Berthold, Timo and Kamp, Dominik and Mexi, Gioni and Pokutta, Sebastian and Pólik, Imre",
            "gray_lit": "approved",
        }]
        findings = check_quotes_against_live_source(
            str(manuscript), {"berthold2026hexagon"}, bib
        )
        live_findings = [f for f in findings if f["criterion"] == "Live-Source Quote"]
        assert not live_findings, f"real abstract substring should pass: {live_findings}"


# ---------- PubMed backend — offline unit tests ---------------------------


class TestNormalizePmid:
    def test_bare_digits(self):
        assert normalize_pmid("12345678") == "12345678"

    def test_strips_whitespace(self):
        assert normalize_pmid("  9876543  ") == "9876543"

    def test_strips_pmid_prefix_colon(self):
        assert normalize_pmid("PMID:12345678") == "12345678"

    def test_strips_pmid_prefix_space(self):
        assert normalize_pmid("PMID: 12345678") == "12345678"

    def test_lowercase_prefix(self):
        assert normalize_pmid("pmid:99999") == "99999"

    def test_single_digit(self):
        assert normalize_pmid("1") == "1"

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            normalize_pmid("")

    def test_non_numeric_raises(self):
        with pytest.raises(ValueError):
            normalize_pmid("abc123")

    def test_too_long_raises(self):
        # 9 digits exceeds the 8-digit cap
        with pytest.raises(ValueError):
            normalize_pmid("123456789")

    def test_doi_string_raises(self):
        with pytest.raises(ValueError):
            normalize_pmid("10.1038/nature12345")


class TestVerifyCitationDispatcherPmid:
    """Dispatcher routes pmid-only entries to the pubmed backend (offline logic check)."""

    def test_eprint_takes_priority_over_pmid(self, monkeypatch):
        calls = []

        def fake_arxiv(arxiv_id, **kw):
            calls.append(("arxiv", arxiv_id))
            return {"source": "arxiv", "title": "T", "authors": []}

        def fake_pubmed(pmid, **kw):
            calls.append(("pubmed", pmid))
            return {"source": "pubmed", "title": "T", "authors": []}

        import repro.citation_verify as cv
        monkeypatch.setattr(cv, "verify_arxiv", fake_arxiv)
        monkeypatch.setattr(cv, "verify_pubmed", fake_pubmed)

        entry = {"eprint": "2107.06519", "pmid": "12345678"}
        cv.verify_citation(entry)
        assert calls[0][0] == "arxiv", "arXiv should take priority over PMID"

    def test_pmid_beats_crossref_doi(self, monkeypatch):
        calls = []

        def fake_doi(doi, **kw):
            calls.append(("crossref", doi))
            return {"source": "crossref", "title": "T", "authors": []}

        def fake_pubmed(pmid, **kw):
            calls.append(("pubmed", pmid))
            return {"source": "pubmed", "title": "T", "authors": []}

        import repro.citation_verify as cv
        monkeypatch.setattr(cv, "verify_doi", fake_doi)
        monkeypatch.setattr(cv, "verify_pubmed", fake_pubmed)
        # doi is plain CrossRef (not arXiv DOI), so pmid should win
        entry = {"doi": "10.1038/nature12345", "pmid": "12345678"}
        cv.verify_citation(entry)
        assert calls[0][0] == "pubmed", "PMID should beat plain CrossRef DOI"

    def test_no_identifiers_raises(self):
        import repro.citation_verify as cv
        with pytest.raises(ValueError, match="PMID"):
            cv.verify_citation({})


# ---------- PubMed backend — network integration tests --------------------


@pytest.mark.network
class TestVerifyPubmedNetwork:
    """Live NCBI calls — excluded from CI with -m 'not network'."""

    # PMID 17073300 = Watson & Crick (1953) DNA structure paper (Nature).
    # Stable, well-indexed, has abstract, consistently returned by NCBI.
    WATSON_CRICK_PMID = "13054692"

    # PMID 25056061 = Crick (1970) Central Dogma of Molecular Biology.
    CENTRAL_DOGMA_PMID = "25056061"

    def test_basic_shape(self):
        result = verify_pubmed(self.WATSON_CRICK_PMID)
        assert result["source"] == "pubmed"
        assert result["pmid"] == self.WATSON_CRICK_PMID
        assert result["title"], "title should be non-empty"
        assert isinstance(result["authors"], list)
        assert result["is_retracted"] is False
        assert result["retraction_info"] is None

    def test_watson_crick_authors(self):
        result = verify_pubmed(self.WATSON_CRICK_PMID)
        surnames = [s.lower() for s in result["authors"]]
        assert any("watson" in s for s in surnames), f"Watson missing from {result['authors']}"
        assert any("crick" in s for s in surnames), f"Crick missing from {result['authors']}"

    def test_has_journal(self):
        result = verify_pubmed(self.WATSON_CRICK_PMID)
        assert result["journal"], "journal should be populated"

    def test_pmid_prefix_accepted(self):
        result = verify_pubmed(f"PMID:{self.WATSON_CRICK_PMID}")
        assert result["pmid"] == self.WATSON_CRICK_PMID

    def test_invalid_pmid_raises_value_error(self):
        with pytest.raises((ValueError, ConnectionError)):
            verify_pubmed("99999999")  # valid format but very unlikely to exist

    def test_verify_citation_dispatcher_routes_to_pubmed(self):
        entry = {"pmid": self.WATSON_CRICK_PMID, "title": "Molecular Structure"}
        result = verify_citation(entry)
        assert result["source"] == "pubmed"
        assert result["pmid"] == self.WATSON_CRICK_PMID
