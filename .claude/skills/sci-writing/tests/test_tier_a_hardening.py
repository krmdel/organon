"""Phase A hardening tests (A1–A10).

Covers every Tier-A fix in PLAN-V2.md:
  A1  — no-id → CRITICAL (+ unverifiable/historical opt-outs)
  A2  — historical = {approved} → MAJOR for pre-1950 entries
  A3  — URL-only @misc livecheck (mocked)
  A4  — verify_gate sibling-bib watch logic
  A5  — inline attribution detection (pure-expertise mode)
  A6  — inline DOI/arXiv link verification (mocked)
  A7  — empty live authors → MAJOR not silent pass
  A8  — dual-id conflict (eprint + doi disagree)
  A9  — PubMed retraction via PublicationType / CommentsCorrectionsList
  A10 — non-standard citation grammar detection

All tests are offline unless marked @pytest.mark.network.
"""

import sys
import types
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path setup so we can import from repro/ and scripts/
# ---------------------------------------------------------------------------
REPO = Path(__file__).resolve().parents[4]
SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
HOOKS_INFO = REPO / ".claude" / "hooks_info"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(HOOKS_INFO))


# ===========================================================================
# A1 — no-id CRITICAL escalation
# ===========================================================================

class TestA1NoIdCritical:
    def _run(self, entry_overrides: dict) -> list[dict]:
        from verify_ops import check_bib_integrity
        base = {
            "key": "testkey",
            "entry_type": "article",
            "title": "Some Title",
            "author": "Smith, John",
            "year": "2020",
        }
        base.update(entry_overrides)
        return check_bib_integrity({"testkey"}, [base])

    def test_no_id_defaults_to_critical(self):
        findings = self._run({})
        crits = [f for f in findings if f["severity"] == "critical"]
        assert crits, "Expected CRITICAL for entry with no doi/eprint/pmid"
        assert "A1" in crits[0]["criterion"]

    def test_unverifiable_bare_approval_stays_critical(self):
        """Phase 8: bare `unverifiable={approved}` is no longer enough.
        Without reason+date, the approval contract is incomplete and the
        entry stays CRITICAL."""
        findings = self._run({"unverifiable": "approved"})
        crits = [f for f in findings if f["severity"] == "critical"]
        assert crits
        assert "incomplete" in crits[0]["criterion"].lower()

    def test_unverifiable_full_contract_downgrades_to_major(self):
        """Phase 8: `unverifiable={approved}` + `unverifiable_reason` (≥30 chars,
        not template) + `unverifiable_date` (ISO) downgrades to MAJOR."""
        findings = self._run({
            "unverifiable": "approved",
            "unverifiable_reason": (
                "Personal communication with the original author; "
                "no preprint planned for the next 12 months."
            ),
            "unverifiable_date": "2026-04-26",
        })
        sevs = {f["severity"] for f in findings}
        assert "critical" not in sevs
        assert "major" in sevs

    def test_unverifiable_short_reason_stays_critical(self):
        """Phase 8: reason shorter than 30 chars is rejected as a generic stub."""
        findings = self._run({
            "unverifiable": "approved",
            "unverifiable_reason": "no DOI",
            "unverifiable_date": "2026-04-26",
        })
        crits = [f for f in findings if f["severity"] == "critical"]
        assert crits

    def test_unverifiable_template_reason_stays_critical(self):
        """Phase 8: template/blocklisted reasons are rejected — must be specific."""
        findings = self._run({
            "unverifiable": "approved",
            "unverifiable_reason": "tutorial with no primary sources, pure expertise",
            "unverifiable_date": "2026-04-26",
        })
        crits = [f for f in findings if f["severity"] == "critical"]
        assert crits

    def test_unverifiable_bad_date_stays_critical(self):
        """Phase 8: `unverifiable_date` must be ISO YYYY-MM-DD."""
        findings = self._run({
            "unverifiable": "approved",
            "unverifiable_reason": (
                "Personal communication with the original author; "
                "no preprint planned for 12 months."
            ),
            "unverifiable_date": "yesterday",
        })
        crits = [f for f in findings if f["severity"] == "critical"]
        assert crits

    def test_historical_no_approval_still_critical(self):
        # pre-1950 without historical=approved → CRITICAL (no free pass)
        findings = self._run({"year": "1904"})
        crits = [f for f in findings if f["severity"] == "critical"]
        assert crits


# ===========================================================================
# A2 — historical = {approved} for pre-1950 → MAJOR
# ===========================================================================

class TestA2Historical:
    def _run(self, year: str, historical: str = "", **fields) -> list[dict]:
        from verify_ops import check_bib_integrity
        entry = {
            "key": "hadamard1896",
            "entry_type": "article",
            "title": "Sur la distribution des zeros de la fonction zeta",
            "author": "Hadamard, Jacques",
            "year": year,
        }
        if historical:
            entry["historical"] = historical
        entry.update(fields)
        return check_bib_integrity({"hadamard1896"}, [entry])

    def test_pre1950_bare_historical_approval_is_critical(self):
        """Phase 9: bare `historical = {approved}` is no longer enough — same
        contract as `unverifiable` and `gray_lit`. Without `historical_reason`
        + `historical_date`, the entry stays CRITICAL."""
        findings = self._run("1896", "approved")
        crits = [f for f in findings if f["severity"] == "critical"]
        assert crits, (
            "Phase 9: bare historical={approved} must surface CRITICAL "
            "(reason+date contract)"
        )
        assert any("historical incomplete" in f["criterion"].lower() for f in crits)

    def test_pre1950_with_full_historical_contract_is_major(self):
        """Phase 9: full reason+date contract downgrades to MAJOR as before."""
        findings = self._run(
            "1896",
            "approved",
            historical_reason=(
                "Pre-1950 reference; verified manually against the digitized "
                "JSTOR copy and the Hadamard collected works."
            ),
            historical_date="2026-04-26",
        )
        crits = [f for f in findings if f["severity"] == "critical"]
        majors = [f for f in findings if f["severity"] == "major"]
        assert not crits, (
            "full historical contract (reason+date) must downgrade to MAJOR"
        )
        assert majors

    def test_post1950_with_historical_approval_still_critical(self):
        # historical=approved on a 1975 paper should NOT bypass
        findings = self._run("1975", "approved")
        # No historical=approved relief for modern papers
        # (year >= 1950, no doi/eprint → CRITICAL)
        crits = [f for f in findings if f["severity"] == "critical"]
        assert crits


# ===========================================================================
# A3 — URL-only @misc livecheck (mocked)
# ===========================================================================

class TestA3UrlMisc:
    def _entry(self, url: str = "https://example.com/paper", title: str = "Some Report") -> dict:
        return {
            "key": "webref2023",
            "entry_type": "misc",
            "title": title,
            "url": url,
            "year": "2023",
        }

    def test_accessible_title_match_is_major(self):
        from verify_ops import check_bib_integrity
        mock_result = {
            "url": "https://example.com/paper",
            "status_code": 200,
            "page_title": "Some Report — Example Site",
            "title_match_ratio": 0.82,
            "is_accessible": True,
            "error": "",
        }
        with patch("verify_ops._URL_VERIFY_AVAILABLE", True), \
             patch("verify_ops._verify_url", return_value=mock_result):
            findings = check_bib_integrity({"webref2023"}, [self._entry()])
        sevs = {f["severity"] for f in findings}
        assert "critical" not in sevs
        assert "major" in sevs

    def test_broken_url_is_critical(self):
        from verify_ops import check_bib_integrity
        mock_result = {
            "url": "https://example.com/deleted",
            "status_code": 404,
            "page_title": "",
            "title_match_ratio": -1.0,
            "is_accessible": False,
            "error": "URL returned HTTP 404",
        }
        with patch("verify_ops._URL_VERIFY_AVAILABLE", True), \
             patch("verify_ops._verify_url", return_value=mock_result):
            findings = check_bib_integrity({"webref2023"}, [self._entry(url="https://example.com/deleted")])
        crits = [f for f in findings if f["severity"] == "critical"]
        assert crits

    def test_title_mismatch_is_critical(self):
        from verify_ops import check_bib_integrity
        mock_result = {
            "url": "https://example.com/paper",
            "status_code": 200,
            "page_title": "Completely Different Page About Cats",
            "title_match_ratio": 0.05,
            "is_accessible": True,
            "error": "Page title 'Completely Different Page About Cats' does not match bib title",
        }
        with patch("verify_ops._URL_VERIFY_AVAILABLE", True), \
             patch("verify_ops._verify_url", return_value=mock_result):
            findings = check_bib_integrity({"webref2023"}, [self._entry()])
        crits = [f for f in findings if f["severity"] == "critical"]
        assert crits


# ===========================================================================
# A4 — verify_gate _is_watched sibling-bib rule
# ===========================================================================

class TestA4SiblingBib:
    def test_prefix_path_watched_without_bib(self, tmp_path):
        from verify_gate import _is_watched, PROJECT_ROOT
        # Fake a file under projects/sci-writing/
        watched_dir = tmp_path / "projects" / "sci-writing" / "slug"
        watched_dir.mkdir(parents=True)
        md = watched_dir / "draft.md"
        md.write_text("hello")
        # Monkeypatch PROJECT_ROOT to tmp_path so relative_to works
        with patch("verify_gate.PROJECT_ROOT", tmp_path):
            assert _is_watched(md)

    def test_arbitrary_path_watched_when_sibling_bib_exists(self, tmp_path):
        from verify_gate import _is_watched
        arbitrary = tmp_path / "papers" / "2026" / "slug"
        arbitrary.mkdir(parents=True)
        md = arbitrary / "manuscript.md"
        md.write_text("hello")
        bib = arbitrary / "refs.bib"
        bib.write_text("@article{x,}")
        with patch("verify_gate.PROJECT_ROOT", tmp_path):
            assert _is_watched(md)

    def test_arbitrary_path_not_watched_without_bib(self, tmp_path):
        from verify_gate import _is_watched
        arbitrary = tmp_path / "papers" / "2026" / "slug"
        arbitrary.mkdir(parents=True)
        md = arbitrary / "manuscript.md"
        md.write_text("hello")
        with patch("verify_gate.PROJECT_ROOT", tmp_path):
            assert not _is_watched(md)

    def test_briefs_path_always_watched(self, tmp_path):
        from verify_gate import _is_watched
        briefs = tmp_path / "projects" / "briefs" / "my-project"
        briefs.mkdir(parents=True)
        md = briefs / "whitepaper.md"
        md.write_text("hello")
        with patch("verify_gate.PROJECT_ROOT", tmp_path):
            assert _is_watched(md)


# ===========================================================================
# A5 — inline attribution detection
# ===========================================================================

class TestA5InlineAttributions:
    def test_no_markers_no_attributions_is_clean(self):
        from verify_ops import check_inline_attributions
        text = "This is a pure opinion piece with no references at all."
        findings = check_inline_attributions(text, set())
        assert not findings

    def test_inline_attribution_triggers_major(self):
        from verify_ops import check_inline_attributions
        text = "As shown by Smith et al. (2023), the results are clear."
        findings = check_inline_attributions(text, set())
        assert findings
        assert findings[0]["severity"] == "major"
        assert "A5" in findings[0]["criterion"]

    def test_no_cite_annotation_with_specific_reason_suppresses(self):
        """Phase 8: a specific (≥30 char, non-template) reason in the header
        suppresses A5. Inline attributions in the body still ship without
        verification, but A5 stays silent on the main finding."""
        from verify_ops import check_inline_attributions
        text = (
            "<!-- no-cite: Personal essay on lab onboarding; no published "
            "claims, all examples first-person observations -->\n"
            "Smith et al. (2023) showed X."
        )
        findings = check_inline_attributions(text, set())
        # Main A5 finding should be suppressed; only an info-level density
        # NOTE may appear (because the body still has author-year prose).
        majors = [f for f in findings if f["severity"] == "major"]
        assert not majors

    def test_no_cite_template_reason_rejected(self):
        """Phase 8: template/blocklisted reasons fail the contract."""
        from verify_ops import check_inline_attributions
        text = (
            "<!-- no-cite: tutorial with no primary sources -->\n"
            "Smith et al. (2023) showed X."
        )
        findings = check_inline_attributions(text, set())
        # The annotation reason is a template → MAJOR finding fires.
        assert any(
            "no-cite reason" in f["criterion"].lower() and f["severity"] == "major"
            for f in findings
        )

    def test_no_cite_outside_header_does_not_suppress(self):
        """Phase 8: a no-cite annotation buried in the body does not
        suppress A5 — the main A5 finding fires AND a scope finding."""
        from verify_ops import check_inline_attributions
        body_lines = ["# Title"] + ["Filler line."] * 25
        body_lines.append(
            "<!-- no-cite: this should not be respected this far down -->"
        )
        body_lines.append("Smith et al. (2023) showed X.")
        text = "\n".join(body_lines)
        findings = check_inline_attributions(text, set())
        criteria = {f["criterion"] for f in findings}
        assert any("no-cite scope" in c.lower() for c in criteria)
        assert any(
            c == "Inline Attribution (A5)" for c in criteria
        )

    def test_cited_mode_skips_a5(self):
        from verify_ops import check_inline_attributions
        # When [@Key] markers exist, pure-expertise mode is off → A5 silent
        text = "Smith et al. (2023) showed X [@smith2023]."
        findings = check_inline_attributions(text, {"smith2023"})
        assert not findings

    def test_code_block_not_flagged(self):
        from verify_ops import check_inline_attributions
        text = "```\nSmith et al. (2023) example\n```"
        findings = check_inline_attributions(text, set())
        assert not findings


# ===========================================================================
# A6 — inline DOI/arXiv link verification (mocked)
# ===========================================================================

class TestA6InlineLinks:
    def test_good_doi_link_no_finding(self):
        from verify_ops import check_inline_links
        text = "See [Smith et al.](https://doi.org/10.1038/nature12373) for details."
        good_result = {"title": "Smith et al.", "is_retracted": False, "retraction_info": None}
        with patch("repro.citation_verify.verify_doi", return_value=good_result):
            findings = check_inline_links(text, [])
        assert not [f for f in findings if f["severity"] == "critical"]

    def test_mismatched_doi_link_is_critical(self):
        from verify_ops import check_inline_links
        text = "See [Wrong Title Here](https://doi.org/10.1038/nature12373) for details."
        mismatch_result = {
            "title": "Genome-scale CRISPR-Cas9 knockout screening in human cells",
            "is_retracted": False,
            "retraction_info": None,
        }
        with patch("repro.citation_verify.verify_doi", return_value=mismatch_result):
            findings = check_inline_links(text, [])
        crits = [f for f in findings if f["severity"] == "critical" and "mismatch" in f["criterion"]]
        assert crits

    def test_retracted_doi_link_is_critical(self):
        from verify_ops import check_inline_links
        text = "[Retracted Paper](https://doi.org/10.1234/retracted)"
        retracted_result = {
            "title": "Retracted Paper",
            "is_retracted": True,
            "retraction_info": "CrossRef update-to notice",
        }
        with patch("repro.citation_verify.verify_doi", return_value=retracted_result):
            findings = check_inline_links(text, [])
        crits = [f for f in findings if "retracted" in f["criterion"].lower()]
        assert crits

    def test_arxiv_link_retracted_is_critical(self):
        from verify_ops import check_inline_links
        text = "[Old Paper](https://arxiv.org/abs/2101.12345)"
        retracted_arxiv = {
            "title": "Old Paper",
            "is_retracted": True,
            "retraction_info": "arXiv withdrawal notice",
        }
        with patch("repro.citation_verify.verify_arxiv", return_value=retracted_arxiv):
            findings = check_inline_links(text, [])
        crits = [f for f in findings if "retracted" in f["criterion"].lower()]
        assert crits

    def test_no_inline_links_no_findings(self):
        from verify_ops import check_inline_links
        text = "A plain paragraph with no links at all."
        findings = check_inline_links(text, [])
        assert not findings


# ===========================================================================
# A7 — empty live authors → MAJOR (not silent pass)
# ===========================================================================

class TestA7EmptyLiveAuthors:
    def test_empty_live_authors_produces_major(self):
        from verify_ops import check_bib_integrity
        entry = {
            "key": "corpauthor2020",
            "entry_type": "article",
            "title": "Corporate Report on Things",
            "author": "Smith, John",
            "year": "2020",
            "doi": "10.1234/corp2020",
        }
        good_result = {
            "title": "Corporate Report on Things",
            "authors": [],  # CrossRef returned no individuals
            "is_retracted": False,
            "retraction_info": None,
            "source": "crossref",
            "dual_id_conflict": False,
            "dual_id_detail": "",
        }
        with patch("verify_ops.verify_citation", return_value=good_result):
            findings = check_bib_integrity({"corpauthor2020"}, [entry])
        majors = [f for f in findings if "A7" in f["criterion"]]
        assert majors, "Expected A7 MAJOR for empty live authors"
        assert all(f["severity"] == "major" for f in majors)


# ===========================================================================
# A8 — dual-id conflict detection
# ===========================================================================

class TestA8DualIdConflict:
    def test_eprint_and_doi_conflict_is_critical(self):
        from verify_ops import check_bib_integrity
        entry = {
            "key": "conflicted2023",
            "entry_type": "article",
            "title": "Real ArXiv Paper",
            "author": "Jones, Alice",
            "year": "2023",
            "eprint": "2301.00001",
            "doi": "10.1234/completelydifferent",
        }
        conflict_result = {
            "title": "Real ArXiv Paper",
            "authors": ["Jones"],
            "is_retracted": False,
            "retraction_info": None,
            "source": "arxiv",
            "dual_id_conflict": True,
            "dual_id_detail": (
                "eprint='2301.00001' resolves to 'Real ArXiv Paper' "
                "but doi='10.1234/completelydifferent' resolves to 'Unrelated DOI Paper'."
            ),
        }
        with patch("verify_ops.verify_citation", return_value=conflict_result):
            findings = check_bib_integrity({"conflicted2023"}, [entry])
        crits = [f for f in findings if "A8" in f["criterion"] and f["severity"] == "critical"]
        assert crits

    def test_eprint_and_doi_agree_no_conflict(self):
        from verify_ops import check_bib_integrity
        entry = {
            "key": "consistent2023",
            "entry_type": "article",
            "title": "Good Paper",
            "author": "Lee, Bob",
            "year": "2023",
            "eprint": "2301.00002",
            "doi": "10.1234/real",
        }
        ok_result = {
            "title": "Good Paper",
            "authors": ["Lee"],
            "is_retracted": False,
            "retraction_info": None,
            "source": "arxiv",
            "dual_id_conflict": False,
            "dual_id_detail": "",
        }
        with patch("verify_ops.verify_citation", return_value=ok_result):
            findings = check_bib_integrity({"consistent2023"}, [entry])
        conflict_crits = [f for f in findings if "A8" in f.get("criterion", "")]
        assert not conflict_crits


# ===========================================================================
# A9 — PubMed retraction detection
# ===========================================================================

class TestA9PubmedRetraction:
    def _make_pubmed_xml(self, publication_types: list[str], comments: list[tuple]) -> bytes:
        """Build minimal PubMed efetch XML for testing."""
        pt_elements = "".join(
            f"<PublicationType>{pt}</PublicationType>" for pt in publication_types
        )
        cc_elements = "".join(
            f'<CommentsCorrections RefType="{ref_type}"><PMID>{pmid}</PMID></CommentsCorrections>'
            for ref_type, pmid in comments
        )
        xml_str = f"""<?xml version="1.0"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>12345678</PMID>
      <Article>
        <ArticleTitle>Test Paper</ArticleTitle>
        <PublicationTypeList>{pt_elements}</PublicationTypeList>
        <Abstract><AbstractText>Test abstract.</AbstractText></Abstract>
        <AuthorList><Author><LastName>Smith</LastName></Author></AuthorList>
        <Journal><Title>Test Journal</Title><JournalIssue>
          <PubDate><Year>2020</Year></PubDate>
        </JournalIssue></Journal>
      </Article>
    </MedlineCitation>
    <PubmedData>
      <CommentsCorrectionsList>{cc_elements}</CommentsCorrectionsList>
      <ArticleIdList>
        <ArticleId IdType="doi">10.1234/test</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>"""
        return xml_str.encode("utf-8")

    def test_publication_type_retracted(self):
        from repro.citation_verify import verify_pubmed
        xml_bytes = self._make_pubmed_xml(
            ["Journal Article", "Retracted Publication"], []
        )
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = xml_bytes
            mock_resp.status = 200
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            result = verify_pubmed("12345678")
        assert result["is_retracted"] is True
        assert "Retracted Publication" in result["retraction_info"]

    def test_retraction_of_publication_type(self):
        from repro.citation_verify import verify_pubmed
        xml_bytes = self._make_pubmed_xml(
            ["Journal Article", "Retraction of Publication"], []
        )
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = xml_bytes
            mock_resp.status = 200
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            result = verify_pubmed("12345678")
        assert result["is_retracted"] is True

    def test_comments_corrections_retraction_in(self):
        from repro.citation_verify import verify_pubmed
        xml_bytes = self._make_pubmed_xml(
            ["Journal Article"],
            [("RetractionIn", "99999999")],
        )
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = xml_bytes
            mock_resp.status = 200
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            result = verify_pubmed("12345678")
        assert result["is_retracted"] is True
        assert "RetractionIn" in result["retraction_info"]
        assert "99999999" in result["retraction_info"]

    def test_normal_paper_not_retracted(self):
        from repro.citation_verify import verify_pubmed
        xml_bytes = self._make_pubmed_xml(["Journal Article"], [])
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = xml_bytes
            mock_resp.status = 200
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            result = verify_pubmed("12345678")
        assert result["is_retracted"] is False
        assert result["retraction_info"] is None


# ===========================================================================
# A10 — non-standard citation grammar
# ===========================================================================

class TestA10NonStandardGrammar:
    def test_latex_cite_flagged(self):
        from verify_ops import check_non_standard_grammar
        text = r"As shown by Smith \cite{smith2023}, the method works."
        findings = check_non_standard_grammar(text)
        assert findings
        assert any("LaTeX" in f["criterion"] for f in findings)
        assert all(f["severity"] == "major" for f in findings)

    def test_paren_author_year_flagged(self):
        from verify_ops import check_non_standard_grammar
        text = "This was demonstrated (Smith et al., 2023) in a landmark study."
        findings = check_non_standard_grammar(text)
        assert findings
        assert any("author-year" in f["criterion"] for f in findings)

    def test_numeric_ref_flagged(self):
        from verify_ops import check_non_standard_grammar
        text = "As shown in [1] and [2,3], the approach is effective."
        findings = check_non_standard_grammar(text)
        assert findings
        assert any("numeric" in f["criterion"] for f in findings)

    def test_good_at_key_markers_not_flagged(self):
        from verify_ops import check_non_standard_grammar
        text = "As shown by [@smith2023] and [@jones2021], the results hold."
        findings = check_non_standard_grammar(text)
        assert not findings

    def test_code_block_excluded(self):
        from verify_ops import check_non_standard_grammar
        text = "```python\ncite_key = 'smith2023'  # (Smith, 2023)\n```"
        findings = check_non_standard_grammar(text)
        assert not findings

    def test_clean_text_no_findings(self):
        from verify_ops import check_non_standard_grammar
        text = "This is a plain paragraph about science with no citation markers."
        findings = check_non_standard_grammar(text)
        assert not findings


# ===========================================================================
# url_verify module unit tests (A3 helpers)
# ===========================================================================

class TestUrlVerify:
    def test_non_http_url_returns_error(self):
        from repro.url_verify import verify_url
        result = verify_url("ftp://example.com/paper")
        assert not result["is_accessible"]
        assert "Not a valid http/https URL" in result["error"]

    def test_empty_url_returns_error(self):
        from repro.url_verify import verify_url
        result = verify_url("")
        assert not result["is_accessible"]

    def test_title_extraction(self):
        from repro.url_verify import _extract_page_title
        html = "<html><head><title>My Research Paper</title></head><body></body></html>"
        assert _extract_page_title(html) == "My Research Paper"

    def test_title_match_ratio_computed(self):
        from repro.url_verify import verify_url
        import urllib.error
        html = b"<html><head><title>Deep Learning Survey</title></head></html>"

        call_count = [0]

        def fake_urlopen(req, timeout=10):
            call_count[0] += 1
            # First call = HEAD → raise 405 to force GET fallback
            if call_count[0] == 1:
                raise urllib.error.HTTPError(req.full_url, 405, "Method Not Allowed", {}, None)

            class FakeResp:
                status = 200
                def read(self, n): return html
                def __enter__(self): return self
                def __exit__(self, *a): pass
            return FakeResp()

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = verify_url("https://example.com", bib_title="Deep Learning Survey")
        assert result["is_accessible"]
        assert result["title_match_ratio"] > 0.8
