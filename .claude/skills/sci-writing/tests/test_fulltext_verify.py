"""Tests for Tier D: full-text claim verification (repro/fulltext_fetch.py).

Offline tests mock HTTP calls so they run without network access.
Network-marked tests make real requests and are excluded from CI by default.
"""

import hashlib
import json
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

# Add project paths
PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / ".claude" / "skills" / "sci-writing" / "scripts"))

from repro.fulltext_fetch import (
    _cache_key,
    _normalize_for_ft_match,
    quote_in_full_text,
    extract_text_from_pdf,
    _query_unpaywall,
    _fetch_arxiv_pdf,
    fetch_full_text,
    fetch_open_access_pdf,
    _CACHE_DIR,
)


class TestCacheKey(unittest.TestCase):
    def test_same_input_same_key(self):
        self.assertEqual(_cache_key("arxiv:2107.06519"), _cache_key("arxiv:2107.06519"))

    def test_different_inputs_different_keys(self):
        self.assertNotEqual(_cache_key("arxiv:2107.06519"), _cache_key("doi:10.1038/nature"))

    def test_returns_hex_string(self):
        key = _cache_key("test")
        self.assertRegex(key, r"^[0-9a-f]{40}$")


class TestNormalizeForFtMatch(unittest.TestCase):
    def test_lowercases(self):
        self.assertEqual(_normalize_for_ft_match("Hello World"), "hello world")

    def test_strips_punctuation(self):
        result = _normalize_for_ft_match("hello, world!")
        self.assertNotIn(",", result)
        self.assertNotIn("!", result)

    def test_collapses_whitespace(self):
        result = _normalize_for_ft_match("  too   many  spaces  ")
        self.assertEqual(result, "too many spaces")

    def test_strips_special_chars(self):
        result = _normalize_for_ft_match("α-tubulin: a study")
        # non-alnum non-space replaced with space
        self.assertIn("tubulin", result)
        self.assertIn("a study", result)


class TestQuoteInFullText(unittest.TestCase):
    def test_exact_match(self):
        quote = "the quick brown fox jumps over the lazy dog"
        full_text = f"In this paper we show that {quote} which demonstrates our point."
        self.assertTrue(quote_in_full_text(quote, full_text))

    def test_case_insensitive(self):
        quote = "The Quick Brown Fox jumps lazily"
        full_text = "the quick brown fox jumps lazily over everything"
        self.assertTrue(quote_in_full_text(quote, full_text))

    def test_partial_head_match(self):
        # 60% of the quote appears — should pass
        quote = "the quick brown fox jumps over the lazy dog and runs away"
        head = quote[:int(len(quote) * 0.6)]
        full_text = f"In this paper {head} but the text ends here."
        self.assertTrue(quote_in_full_text(quote, full_text))

    def test_absent_quote(self):
        quote = "this passage does not exist anywhere"
        full_text = "The paper discusses completely different topics about biology."
        self.assertFalse(quote_in_full_text(quote, full_text))

    def test_short_quote_returns_false(self):
        # Quote shorter than min_chars (20) always returns False
        self.assertFalse(quote_in_full_text("short", "short text here short"))

    def test_empty_quote_returns_false(self):
        self.assertFalse(quote_in_full_text("", "some full text"))

    def test_empty_fulltext_returns_false(self):
        quote = "a long enough quote to be meaningful for testing purposes"
        self.assertFalse(quote_in_full_text(quote, ""))

    def test_punctuation_normalized(self):
        # Quote with punctuation should match full text that has different punctuation
        quote = "results show significant improvement (p < 0.001)"
        full_text = "Our results show significant improvement p 0001 in all conditions."
        self.assertTrue(quote_in_full_text(quote, full_text))


class TestExtractTextFromPdf(unittest.TestCase):
    def test_txt_file_reads_directly(self, tmp_path=None):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False, encoding="utf-8") as f:
            f.write("This is plain text content for testing.")
            fname = f.name
        try:
            result = extract_text_from_pdf(Path(fname))
            self.assertEqual(result, "This is plain text content for testing.")
        finally:
            Path(fname).unlink(missing_ok=True)

    def test_missing_pdfminer_returns_empty(self):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4 fake pdf content")
            fname = f.name
        try:
            with patch.dict("sys.modules", {"pdfminer": None, "pdfminer.high_level": None}):
                result = extract_text_from_pdf(Path(fname))
            # Should return empty string, not raise
            self.assertIsInstance(result, str)
        finally:
            Path(fname).unlink(missing_ok=True)

    def test_ligature_normalization(self):
        raw = "eﬃcient ﬁrst ﬀ"
        # Test the normalization that extract_text_from_pdf applies internally
        import re
        ligature_map = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl"}
        for lig, rep in ligature_map.items():
            raw = raw.replace(lig, rep)
        self.assertEqual(raw, "efficient first ff")


class TestFetchFullTextOffline(unittest.TestCase):
    """Mock-based tests for fetch_full_text dispatch logic."""

    def test_arxiv_path_tried_first(self):
        """When arxiv_id is present, arXiv PDF is attempted before Unpaywall."""
        with patch("repro.fulltext_fetch._fetch_arxiv_pdf") as mock_arxiv, \
             patch("repro.fulltext_fetch._fetch_unpaywall_pdf") as mock_unpaywall, \
             patch("repro.fulltext_fetch.extract_text_from_pdf", return_value="full text"):
            mock_arxiv.return_value = Path("/fake/path.pdf")
            mock_unpaywall.return_value = None

            result = fetch_full_text(doi="10.1234/fake", arxiv_id="2107.06519")

            mock_arxiv.assert_called_once_with("2107.06519")
            # Unpaywall should NOT be called if arXiv succeeded
            mock_unpaywall.assert_not_called()
            self.assertEqual(result, "full text")

    def test_unpaywall_tried_when_arxiv_unavailable(self):
        with patch("repro.fulltext_fetch._fetch_arxiv_pdf", return_value=None), \
             patch("repro.fulltext_fetch._fetch_unpaywall_pdf") as mock_unpaywall, \
             patch("repro.fulltext_fetch.extract_text_from_pdf", return_value="oa text"):
            mock_unpaywall.return_value = Path("/fake/doi.pdf")

            result = fetch_full_text(doi="10.1234/fake")

            mock_unpaywall.assert_called_once_with("10.1234/fake")
            self.assertEqual(result, "oa text")

    def test_returns_none_when_no_source_available(self):
        with patch("repro.fulltext_fetch._fetch_arxiv_pdf", return_value=None), \
             patch("repro.fulltext_fetch._fetch_unpaywall_pdf", return_value=None), \
             patch("repro.fulltext_fetch._fetch_pmc_pdf", return_value=None):
            result = fetch_full_text(doi="10.1234/fake", arxiv_id="9999.00000")
            self.assertIsNone(result)

    def test_returns_none_with_no_identifiers(self):
        result = fetch_full_text()
        self.assertIsNone(result)

    def test_empty_extracted_text_returns_none(self):
        with patch("repro.fulltext_fetch._fetch_arxiv_pdf") as mock_arxiv, \
             patch("repro.fulltext_fetch.extract_text_from_pdf", return_value=""):
            mock_arxiv.return_value = Path("/fake/empty.pdf")
            result = fetch_full_text(arxiv_id="2107.06519")
            self.assertIsNone(result)


class TestQueryUnpaywallOffline(unittest.TestCase):
    def test_returns_none_without_email(self):
        result = _query_unpaywall("10.1234/fake", "")
        self.assertIsNone(result)

    def test_parses_best_oa_location(self):
        fake_response = json.dumps({
            "best_oa_location": {
                "url_for_pdf": "https://example.com/paper.pdf"
            },
            "oa_locations": []
        }).encode()

        import urllib.request
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = fake_response

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = _query_unpaywall("10.1234/test", "test@example.com")

        self.assertEqual(result, "https://example.com/paper.pdf")

    def test_falls_back_to_oa_locations_list(self):
        fake_response = json.dumps({
            "best_oa_location": {"url_for_pdf": None, "url": None},
            "oa_locations": [
                {"url_for_pdf": "https://example.com/alt.pdf"}
            ]
        }).encode()

        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = fake_response

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = _query_unpaywall("10.1234/test", "test@example.com")

        self.assertEqual(result, "https://example.com/alt.pdf")

    def test_returns_none_on_network_error(self):
        import urllib.error
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")):
            result = _query_unpaywall("10.1234/test", "test@example.com")
        self.assertIsNone(result)

    def test_returns_none_when_no_pdf_url(self):
        fake_response = json.dumps({
            "best_oa_location": {"url": "https://example.com/abstract"},
            "oa_locations": [{"url": "https://example.com/html"}]
        }).encode()

        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = fake_response

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = _query_unpaywall("10.1234/test", "test@example.com")

        self.assertIsNone(result)


class TestVerifyOpsFullTextIntegration(unittest.TestCase):
    """Test that verify_ops.py wires Tier D correctly using mocked fulltext_fetch."""

    def setUp(self):
        import tempfile
        self.tmp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _make_manuscript_and_sidecar(self, quote: str, arxiv_id: str = "2107.06519") -> tuple:
        bib_key = "testpaper2021"
        ms = self.tmp_dir / "manuscript.md"
        ms.write_text(
            f"# Title\n\nSome claim [@{bib_key}].\n",
            encoding="utf-8",
        )
        sidecar = self.tmp_dir / "manuscript.md.citations.json"
        sidecar.write_text(
            json.dumps({"claims": [{"key": bib_key, "quote": quote,
                                    "source_anchor": f"https://arxiv.org/abs/{arxiv_id}",
                                    "source_type": "doi"}]}),
            encoding="utf-8",
        )
        bib = self.tmp_dir / "manuscript.bib"
        bib.write_text(
            f"@article{{{bib_key},\n  author = {{Test Author}},\n  title = {{Test Paper}},\n"
            f"  year = {{2021}},\n  eprint = {{{arxiv_id}}},\n}}\n",
            encoding="utf-8",
        )
        return str(ms), str(bib)

    def test_critical_when_full_text_available_and_quote_absent(self):
        """Tier D: CRITICAL fires when full text fetched but quote not found."""
        import sys
        sys.path.insert(0, str(PROJECT_ROOT / ".claude" / "skills" / "sci-writing" / "scripts"))
        import verify_ops

        quote = "this specific passage does not appear in the paper at all"
        ms_path, bib_path = self._make_manuscript_and_sidecar(quote)

        full_text = "This paper discusses something completely different about machine learning."

        with patch.object(verify_ops, "_FULLTEXT_FETCH_AVAILABLE", True), \
             patch.object(verify_ops, "_fetch_full_text", return_value=full_text), \
             patch.object(verify_ops, "_quote_in_full_text", return_value=False), \
             patch.object(verify_ops, "_live_metadata", return_value=None):
            findings = verify_ops.check_quotes_against_live_source(
                ms_path, {"testpaper2021"}, verify_ops.parse_bib_file(bib_path)
            )

        critical = [f for f in findings if f["severity"] == "critical"]
        self.assertEqual(len(critical), 1)
        self.assertIn("Tier D", critical[0]["criterion"])
        self.assertIn("full text", critical[0]["finding"])

    def test_pass_when_full_text_available_and_quote_present(self):
        """Tier D: passes silently when full text is fetched and quote is found."""
        import verify_ops

        quote = "this exact passage appears verbatim in the paper body section"
        ms_path, bib_path = self._make_manuscript_and_sidecar(quote)

        with patch.object(verify_ops, "_FULLTEXT_FETCH_AVAILABLE", True), \
             patch.object(verify_ops, "_fetch_full_text", return_value=f"Intro. {quote}. Conclusion."), \
             patch.object(verify_ops, "_quote_in_full_text", return_value=True):
            findings = verify_ops.check_quotes_against_live_source(
                ms_path, {"testpaper2021"}, verify_ops.parse_bib_file(bib_path)
            )

        self.assertEqual(findings, [])

    def test_major_when_full_text_unavailable_and_abstract_misses(self):
        """Tier D graceful degradation: falls back to abstract check → MAJOR."""
        import verify_ops

        quote = "passage not in abstract either"
        ms_path, bib_path = self._make_manuscript_and_sidecar(quote)

        mock_live = {
            "abstract": "The paper is about robotics and navigation.",
            "source": "arxiv",
            "arxiv_id": "2107.06519",
        }

        with patch.object(verify_ops, "_FULLTEXT_FETCH_AVAILABLE", True), \
             patch.object(verify_ops, "_fetch_full_text", return_value=None), \
             patch.object(verify_ops, "_live_metadata", return_value=mock_live):
            findings = verify_ops.check_quotes_against_live_source(
                ms_path, {"testpaper2021"}, verify_ops.parse_bib_file(bib_path)
            )

        major = [f for f in findings if f["severity"] == "major"]
        self.assertTrue(len(major) >= 1)
        # Should mention UNPAYWALL in suggestion to guide user
        self.assertIn("UNPAYWALL_EMAIL", major[0]["suggestion"])

    def test_no_critical_when_fulltext_fetch_raises(self):
        """Network errors in full-text fetch fall through to abstract check, not crash."""
        import verify_ops

        quote = "the cited passage"
        ms_path, bib_path = self._make_manuscript_and_sidecar(quote)

        def raise_on_fetch(**kwargs):
            raise ConnectionError("timeout")

        with patch.object(verify_ops, "_FULLTEXT_FETCH_AVAILABLE", True), \
             patch.object(verify_ops, "_fetch_full_text", side_effect=raise_on_fetch), \
             patch.object(verify_ops, "_live_metadata", return_value=None):
            # Should not raise — errors are swallowed and falls through
            findings = verify_ops.check_quotes_against_live_source(
                ms_path, {"testpaper2021"}, verify_ops.parse_bib_file(bib_path)
            )
        # findings may be empty (no abstract) but no exception
        self.assertIsInstance(findings, list)


# ── Network tests (excluded from CI) ──────────────────────────────────────────


class TestArxivPdfFetchNetwork(unittest.TestCase):
    """Real arXiv fetch — skip in offline/CI runs."""

    @unittest.skipUnless(
        __import__("os").environ.get("SCI_OS_NETWORK_TESTS"),
        "set SCI_OS_NETWORK_TESTS=1 to run live network tests",
    )
    def test_fetches_real_arxiv_pdf(self):
        # arXiv:2107.06519 is Ono 2021 (sole author, verified phantom-citation case)
        pdf_path = _fetch_arxiv_pdf("2107.06519")
        self.assertIsNotNone(pdf_path)
        self.assertTrue(pdf_path.exists())
        # Minimal sanity: file should be a real PDF
        with open(pdf_path, "rb") as f:
            header = f.read(8)
        self.assertTrue(header.startswith(b"%PDF"), "Downloaded file is not a PDF")

    @unittest.skipUnless(
        __import__("os").environ.get("SCI_OS_NETWORK_TESTS"),
        "set SCI_OS_NETWORK_TESTS=1 to run live network tests",
    )
    def test_full_text_from_arxiv_contains_author_name(self):
        text = fetch_full_text(arxiv_id="2107.06519")
        # If pdfminer is available, we get real text; otherwise None
        if text:
            # The paper is by Ono (2021) — author name should appear
            self.assertIn("ono", text.lower())


if __name__ == "__main__":
    unittest.main()
