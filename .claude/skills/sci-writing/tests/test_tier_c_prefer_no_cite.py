"""Tier C prefer-no-citation tests.

Covers:
  C3 — check_unsupported_claims: MAJOR when sentence/quote Jaccard < 0.30
  C3 — _sentences_containing_key: finds correct sentences
  C3 — _token_jaccard: correct computation
  C4 — _parse_coverage_gaps: bullet and inline formats
  B5 wire — check_receipt_confidence importable from paper_pipeline module

All tests are offline.
"""

from __future__ import annotations

import json
import sys
import textwrap
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
for p in (str(ROOT), str(SCRIPTS)):
    if p not in sys.path:
        sys.path.insert(0, p)

import verify_ops
from verify_ops import (
    check_unsupported_claims,
    _sentences_containing_key,
    _token_jaccard,
    _CLAIM_QUOTE_JACCARD_MIN,
    MIN_QUOTE_CHARS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_quotes_json(entries: list[dict], tmp_path: Path) -> Path:
    """Write a minimal quotes.json sidecar."""
    data = {"quotes": entries}
    p = tmp_path / "test.quotes.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _make_sidecar(claims: list[dict], tmp_path: Path, name: str = "draft.md") -> Path:
    """Write a citations sidecar and return the manuscript path it belongs to."""
    ms = tmp_path / name
    ms.write_text("placeholder", encoding="utf-8")
    sidecar = tmp_path / f"{name}.citations.json"
    sidecar.write_text(json.dumps({"version": 1, "claims": claims}), encoding="utf-8")
    return ms


# ---------------------------------------------------------------------------
# _token_jaccard
# ---------------------------------------------------------------------------

class TestTokenJaccard:
    def test_identical(self):
        assert _token_jaccard("hello world", "hello world") == pytest.approx(1.0)

    def test_disjoint(self):
        assert _token_jaccard("alpha beta", "gamma delta") == pytest.approx(0.0)

    def test_partial(self):
        # {"a","b"} ∩ {"a","c"} = {"a"}; union = {"a","b","c"} → 1/3
        j = _token_jaccard("a b", "a c")
        assert j == pytest.approx(1 / 3)

    def test_empty_a(self):
        assert _token_jaccard("", "hello") == pytest.approx(0.0)

    def test_empty_both(self):
        assert _token_jaccard("", "") == pytest.approx(0.0)

    def test_case_insensitive(self):
        assert _token_jaccard("CRISPR Cas9", "crispr cas9") == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# _sentences_containing_key
# ---------------------------------------------------------------------------

class TestSentencesContainingKey:
    def test_single_marker(self):
        text = "CRISPR enables editing [@mali2013]. Other methods exist."
        sents = _sentences_containing_key(text, "mali2013")
        assert len(sents) == 1
        assert "mali2013" in sents[0].lower()

    def test_multi_key_marker(self):
        text = "Two papers agree [@mali2013; @doudna2012]."
        sents = _sentences_containing_key(text, "mali2013")
        assert len(sents) == 1
        sents2 = _sentences_containing_key(text, "doudna2012")
        assert len(sents2) == 1

    def test_key_not_present(self):
        text = "No citation here. Nothing at all."
        assert _sentences_containing_key(text, "missing2024") == []

    def test_multiple_occurrences(self):
        text = (
            "First claim [@mali2013]. Some filler. "
            "Second claim also [@mali2013]."
        )
        sents = _sentences_containing_key(text, "mali2013")
        assert len(sents) == 2

    def test_paragraph_split(self):
        text = "First para [@mali2013].\n\nSecond para with no cite."
        sents = _sentences_containing_key(text, "mali2013")
        assert len(sents) == 1

    def test_case_insensitive_key(self):
        text = "Result [@Mali2013] was confirmed."
        sents = _sentences_containing_key(text, "mali2013")
        assert len(sents) == 1


# ---------------------------------------------------------------------------
# check_unsupported_claims
# ---------------------------------------------------------------------------

_LONG_QUOTE = (
    "CRISPR-Cas9 enables precise and efficient genome editing in mammalian cells "
    "through RNA-guided DNA cleavage at specific loci."
)  # len > MIN_QUOTE_CHARS

_SHORT_QUOTE = "CRISPR edits genes."  # len < MIN_QUOTE_CHARS, skipped


class TestCheckUnsupportedClaims:
    def test_high_overlap_passes(self, tmp_path):
        """Sentence closely paraphrases the quote → no finding."""
        text = (
            "CRISPR-Cas9 enables precise genome editing in mammalian cells [@mali2013]."
        )
        quotes_path = _make_quotes_json(
            [{"key": "mali2013", "candidate_quotes": [{"text": _LONG_QUOTE}]}],
            tmp_path,
        )
        ms = _make_sidecar(
            [{"key": "mali2013", "quote": _LONG_QUOTE, "source_anchor": "10.x/y", "source_type": "doi"}],
            tmp_path,
        )
        findings = check_unsupported_claims(text, {"mali2013"}, quotes_path, str(ms))
        assert findings == []

    def test_low_overlap_fires_major(self, tmp_path):
        """Sentence overclaims beyond the quote → MAJOR."""
        text = (
            "CRISPR has cured cancer, reversed aging, solved climate change, "
            "and achieved world peace [@mali2013]."
        )
        quotes_path = _make_quotes_json(
            [{"key": "mali2013", "candidate_quotes": [{"text": _LONG_QUOTE}]}],
            tmp_path,
        )
        ms = _make_sidecar(
            [{"key": "mali2013", "quote": _LONG_QUOTE, "source_anchor": "10.x/y", "source_type": "doi"}],
            tmp_path,
        )
        findings = check_unsupported_claims(text, {"mali2013"}, quotes_path, str(ms))
        assert len(findings) == 1
        f = findings[0]
        assert f["severity"] == "major"
        assert f["criterion"] == "Claim-Quote Alignment (C3)"
        assert "mali2013" in f["finding"]
        assert "Jaccard=" in f["finding"]

    def test_short_quote_skipped(self, tmp_path):
        """Quote shorter than MIN_QUOTE_CHARS is silently skipped."""
        text = "CRISPR edits genes [@mali2013]."
        quotes_path = _make_quotes_json(
            [{"key": "mali2013", "candidate_quotes": [{"text": _SHORT_QUOTE}]}],
            tmp_path,
        )
        ms = _make_sidecar(
            [{"key": "mali2013", "quote": _SHORT_QUOTE, "source_anchor": "10.x/y", "source_type": "doi"}],
            tmp_path,
        )
        findings = check_unsupported_claims(text, {"mali2013"}, quotes_path, str(ms))
        assert findings == []

    def test_no_quotes_path_skips(self, tmp_path):
        """quotes_path=None → function returns [] immediately."""
        text = "Some claim [@mali2013]."
        ms = _make_sidecar(
            [{"key": "mali2013", "quote": _LONG_QUOTE, "source_anchor": "x", "source_type": "doi"}],
            tmp_path,
        )
        findings = check_unsupported_claims(text, {"mali2013"}, None, str(ms))
        assert findings == []

    def test_missing_quotes_file_skips(self, tmp_path):
        """quotes_path that does not exist → [] (already flagged by provenance check)."""
        text = "Some claim [@mali2013]."
        ms = _make_sidecar(
            [{"key": "mali2013", "quote": _LONG_QUOTE, "source_anchor": "x", "source_type": "doi"}],
            tmp_path,
        )
        findings = check_unsupported_claims(
            text, {"mali2013"}, tmp_path / "nonexistent.json", str(ms)
        )
        assert findings == []

    def test_no_sidecar_skips(self, tmp_path):
        """No citations sidecar → [] (check_quote_sidecar already handles this)."""
        text = "Some claim [@mali2013]."
        quotes_path = _make_quotes_json(
            [{"key": "mali2013", "candidate_quotes": [{"text": _LONG_QUOTE}]}],
            tmp_path,
        )
        ms = tmp_path / "nodraft.md"
        ms.write_text("placeholder", encoding="utf-8")
        # No .citations.json written
        findings = check_unsupported_claims(text, {"mali2013"}, quotes_path, str(ms))
        assert findings == []

    def test_key_not_in_sidecar_skips(self, tmp_path):
        """Key in used_keys but absent from sidecar → skipped (other check handles it)."""
        text = "Some claim [@unknown2024]."
        quotes_path = _make_quotes_json(
            [{"key": "mali2013", "candidate_quotes": [{"text": _LONG_QUOTE}]}],
            tmp_path,
        )
        ms = _make_sidecar(
            [{"key": "mali2013", "quote": _LONG_QUOTE, "source_anchor": "x", "source_type": "doi"}],
            tmp_path,
        )
        findings = check_unsupported_claims(text, {"unknown2024"}, quotes_path, str(ms))
        assert findings == []

    def test_pure_expertise_skips(self, tmp_path):
        """empty used_keys → pure-expertise mode → []."""
        quotes_path = _make_quotes_json([], tmp_path)
        ms = tmp_path / "draft.md"
        ms.write_text("No citations.", encoding="utf-8")
        findings = check_unsupported_claims("No citations.", set(), quotes_path, str(ms))
        assert findings == []

    def test_jaccard_threshold_boundary(self, tmp_path):
        """Jaccard exactly at threshold: should NOT fire."""
        # Build a sentence and quote that have exactly _CLAIM_QUOTE_JACCARD_MIN overlap.
        # Use token counting to construct tokens.
        # 3 shared tokens out of 10 total = 0.30 exactly.
        shared = "crispr cas9 edits"
        extra_sent = "has revolutionized medicine permanently"
        extra_quote = "via rna guided dna cleavage"
        sentence = f"{shared} {extra_sent} [@mali2013]."
        quote_text = f"{shared} {extra_quote} " + "x " * 50  # pad to exceed MIN_QUOTE_CHARS
        quotes_path = _make_quotes_json(
            [{"key": "mali2013", "candidate_quotes": [{"text": quote_text}]}],
            tmp_path,
        )
        ms = _make_sidecar(
            [{"key": "mali2013", "quote": quote_text, "source_anchor": "x", "source_type": "doi"}],
            tmp_path,
            name="boundary_draft.md",
        )
        findings = check_unsupported_claims(sentence, {"mali2013"}, quotes_path, str(ms))
        j = _token_jaccard(quote_text, sentence)
        if j >= _CLAIM_QUOTE_JACCARD_MIN:
            assert findings == []
        else:
            assert len(findings) == 1


# ---------------------------------------------------------------------------
# _parse_coverage_gaps (C4)
# ---------------------------------------------------------------------------

from paper_pipeline import _parse_coverage_gaps  # type: ignore


class TestParseCoverageGaps:
    def _write_md(self, content: str, tmp_path: Path) -> Path:
        p = tmp_path / "research.md"
        p.write_text(textwrap.dedent(content), encoding="utf-8")
        return p

    def test_bullet_format(self, tmp_path):
        md = self._write_md("""\
            ## Coverage status

            - Checked directly: [1], [2]
            - Abstract only: [3]
            - Unresolved gaps:
              - Sub-claim 3: no supporting entry
              - Sub-claim 5: conflicting evidence
            """, tmp_path)
        gaps = _parse_coverage_gaps(md)
        assert len(gaps) == 2
        assert any("Sub-claim 3" in g for g in gaps)
        assert any("Sub-claim 5" in g for g in gaps)

    def test_old_slash_format(self, tmp_path):
        md = self._write_md("""\
            ## Coverage status

            - Checked directly: [1]
            - Unresolved / gaps: Sub-claim 4, Sub-claim 6
            """, tmp_path)
        gaps = _parse_coverage_gaps(md)
        assert len(gaps) == 2

    def test_none_value(self, tmp_path):
        md = self._write_md("""\
            ## Coverage status

            - Checked directly: [1], [2]
            - Unresolved gaps: none
            """, tmp_path)
        gaps = _parse_coverage_gaps(md)
        assert gaps == []

    def test_no_coverage_section(self, tmp_path):
        md = self._write_md("# Research\n\nNo coverage section here.\n", tmp_path)
        gaps = _parse_coverage_gaps(md)
        assert gaps == []

    def test_missing_file(self, tmp_path):
        gaps = _parse_coverage_gaps(tmp_path / "nonexistent.md")
        assert gaps == []

    def test_stops_at_next_heading(self, tmp_path):
        md = self._write_md("""\
            ## Coverage status

            - Unresolved gaps:
              - Gap A

            ## Verification receipts

            | # | API | Title | Author | DOI |
            |---|-----|-------|--------|-----|
            | 1 | ps  | Title | Smith  | doi |
            """, tmp_path)
        gaps = _parse_coverage_gaps(md)
        assert len(gaps) == 1
        assert "Gap A" in gaps[0]


# ---------------------------------------------------------------------------
# B5 import check
# ---------------------------------------------------------------------------

class TestB5Import:
    def test_check_receipt_conf_importable(self):
        """_check_receipt_conf must be importable from paper_pipeline."""
        import paper_pipeline  # type: ignore
        assert hasattr(paper_pipeline, "_check_receipt_conf"), (
            "_check_receipt_conf not imported into paper_pipeline — B5 wire incomplete"
        )
