"""Tests for Tier F: per-claim deep links (writing_ops + verify_ops F4)."""

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / ".claude" / "skills" / "sci-writing" / "scripts"))

from writing_ops import resolve_deep_link_url, format_bibliography_with_deep_links


class TestResolveDeepLinkUrl(unittest.TestCase):
    def _entry(self, doi="", eprint="", url=""):
        return {"key": "k", "author": "A", "title": "T", "year": "2024",
                "doi": doi, "eprint": eprint, "url": url}

    def test_paperclip_anchor_takes_priority(self):
        url = resolve_deep_link_url(
            self._entry(doi="10.1234/x"),
            quote="some quote",
            source_anchor="https://citations.gxl.ai/papers/abc123#L42",
        )
        self.assertEqual(url, "https://citations.gxl.ai/papers/abc123#L42")

    def test_doi_with_quote_produces_text_fragment(self):
        url = resolve_deep_link_url(
            self._entry(doi="10.1038/nature12373"),
            quote="a sufficiently long quoted passage from the paper",
        )
        self.assertIn("https://doi.org/10.1038/nature12373", url)
        self.assertIn("#:~:text=", url)

    def test_arxiv_with_quote_produces_text_fragment(self):
        url = resolve_deep_link_url(
            self._entry(eprint="2107.06519"),
            quote="a sufficiently long quoted passage here for testing",
        )
        self.assertIn("https://arxiv.org/abs/2107.06519", url)
        self.assertIn("#:~:text=", url)

    def test_doi_without_quote_plain_url(self):
        url = resolve_deep_link_url(self._entry(doi="10.1038/nature12373"))
        self.assertEqual(url, "https://doi.org/10.1038/nature12373")
        self.assertNotIn("#:~:text=", url)

    def test_no_identifiers_returns_empty(self):
        url = resolve_deep_link_url(self._entry())
        self.assertEqual(url, "")

    def test_snippet_truncated_at_word_boundary(self):
        long_quote = "word " * 30  # 150 chars
        url = resolve_deep_link_url(self._entry(doi="10.1/x"), quote=long_quote)
        fragment = url.split("#:~:text=")[1]
        import urllib.parse
        decoded = urllib.parse.unquote(fragment)
        self.assertLessEqual(len(decoded), 105)  # max 100 + word boundary slack

    def test_url_fallback_when_no_doi_eprint(self):
        entry = self._entry(url="https://example.com/paper")
        url = resolve_deep_link_url(entry)
        self.assertEqual(url, "https://example.com/paper")

    def test_quote_encoded_in_fragment(self):
        url = resolve_deep_link_url(
            self._entry(doi="10.1/x"),
            quote="results show p < 0.001 significance",
        )
        # Spaces and special chars should be percent-encoded
        self.assertIn("%20", url)


class TestFormatBibliographyWithDeepLinks(unittest.TestCase):
    def _entries(self):
        return [
            {"key": "smith2023", "entry_type": "article", "author": "Smith, J",
             "title": "Test Paper", "year": "2023", "doi": "10.1234/test",
             "journal": "Nature"},
            {"key": "jones2021", "entry_type": "article", "author": "Jones, A",
             "title": "Another Paper", "year": "2021", "eprint": "2101.00001",
             "journal": "Science"},
        ]

    def _sidecar(self):
        return {"claims": [
            {"key": "smith2023", "quote": "results demonstrate the efficacy of the proposed method",
             "source_anchor": "", "source_type": "doi"},
            {"key": "jones2021", "quote": "our approach outperforms all baseline methods significantly",
             "source_anchor": "https://citations.gxl.ai/papers/xyz#L10", "source_type": "paperclip"},
        ]}

    def test_produces_references_section(self):
        bib = format_bibliography_with_deep_links(self._entries(), "apa")
        self.assertIn("## References", bib)

    def test_doi_entry_gets_text_fragment(self):
        bib = format_bibliography_with_deep_links(self._entries(), "apa", self._sidecar())
        self.assertIn("doi.org/10.1234/test#:~:text=", bib)

    def test_paperclip_entry_gets_anchor(self):
        bib = format_bibliography_with_deep_links(self._entries(), "apa", self._sidecar())
        self.assertIn("citations.gxl.ai/papers/xyz#L10", bib)

    def test_no_sidecar_produces_plain_urls(self):
        bib = format_bibliography_with_deep_links(self._entries(), "apa")
        self.assertIn("doi.org/10.1234/test", bib)
        self.assertNotIn("#:~:text=", bib)

    def test_entries_wrapped_as_markdown_links(self):
        bib = format_bibliography_with_deep_links(self._entries(), "apa", self._sidecar())
        self.assertIn("](https://", bib)

    def test_numbered_style_prefixes(self):
        bib = format_bibliography_with_deep_links(self._entries(), "nature")
        self.assertRegex(bib, r"\[\d\]")

    def test_alphabetical_sort_preserved(self):
        bib = format_bibliography_with_deep_links(self._entries(), "apa")
        idx_jones = bib.index("Jones")
        idx_smith = bib.index("Smith")
        self.assertLess(idx_jones, idx_smith)


class TestCheckPerClaimLinksPresent(unittest.TestCase):
    def setUp(self):
        import verify_ops
        self.check = verify_ops.check_per_claim_links_present

    def test_flags_entry_without_deep_link(self):
        bib = "## References\n\nSmith (2023). Test. https://doi.org/10.1234/plain\n"
        sidecar = {"claims": [{"key": "smith2023", "quote": "some quoted passage here"}]}
        findings = self.check(bib, {"smith2023"}, sidecar)
        self.assertTrue(len(findings) >= 1)
        self.assertEqual(findings[0]["severity"], "major")
        self.assertIn("Tier F", findings[0]["criterion"])

    def test_passes_entry_with_text_fragment(self):
        bib = "## References\n\n[Smith (2023). Test.](https://doi.org/10.1234/x#:~:text=passage)\n"
        sidecar = {"claims": [{"key": "smith2023", "quote": "some quoted passage here"}]}
        findings = self.check(bib, {"smith2023"}, sidecar)
        self.assertEqual(findings, [])

    def test_passes_entry_with_paperclip_anchor(self):
        bib = "## References\n\n[Smith (2023)](https://citations.gxl.ai/papers/abc#L42)\n"
        sidecar = {"claims": [{"key": "smith2023", "quote": "passage text here long enough"}]}
        findings = self.check(bib, {"smith2023"}, sidecar)
        self.assertEqual(findings, [])

    def test_skips_keys_without_quote(self):
        bib = "## References\n\nSmith (2023). Test. https://doi.org/10.1234/plain\n"
        sidecar = {"claims": [{"key": "smith2023", "quote": ""}]}
        findings = self.check(bib, {"smith2023"}, sidecar)
        self.assertEqual(findings, [])

    def test_empty_inputs(self):
        self.assertEqual(self.check("", set(), None), [])
        self.assertEqual(self.check("## References\n", set(), None), [])

    def test_no_sidecar_no_findings(self):
        bib = "## References\n\nSmith (2023). Test.\n"
        findings = self.check(bib, {"smith2023"}, None)
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
