"""Tests for sci-writing writing_ops module.

Covers BibTeX parsing, citation formatting (APA 7th, Nature, IEEE, Vancouver),
in-text citation generation, bibliography generation, and citation marker
replacement in draft text.
"""

import sys
from pathlib import Path

import pytest

# Add scripts dir to path for writing_ops import
SCRIPTS_DIR = str(
    Path(__file__).resolve().parent.parent
    / ".claude"
    / "skills"
    / "sci-writing"
    / "scripts"
)
sys.path.insert(0, SCRIPTS_DIR)

from writing_ops import (
    format_bibliography,
    format_citation,
    format_intext,
    parse_bib_file,
    replace_citation_markers,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def bib_entries():
    """Parse the sample.bib fixture and return entries."""
    return parse_bib_file(str(FIXTURES_DIR / "sample.bib"))


@pytest.fixture
def draft_text():
    """Load the sample draft with citation markers."""
    return (FIXTURES_DIR / "sample_draft.md").read_text()


@pytest.fixture
def smith_entry(bib_entries):
    """Return the Smith2024 entry."""
    return next(e for e in bib_entries if e["key"] == "Smith2024")


@pytest.fixture
def johnson_entry(bib_entries):
    """Return the Johnson2024 entry."""
    return next(e for e in bib_entries if e["key"] == "Johnson2024")


@pytest.fixture
def lee_entry(bib_entries):
    """Return the Lee2023 entry."""
    return next(e for e in bib_entries if e["key"] == "Lee2023")


@pytest.fixture
def mueller_entry(bib_entries):
    """Return the Mueller2024 entry."""
    return next(e for e in bib_entries if e["key"] == "Mueller2024")


# ---------------------------------------------------------------------------
# parse_bib_file Tests
# ---------------------------------------------------------------------------


class TestParseBibFile:
    def test_parse_returns_four_entries(self, bib_entries):
        assert len(bib_entries) == 4

    def test_parse_article_type(self, smith_entry):
        assert smith_entry["entry_type"] == "article"
        assert smith_entry["title"] == "A Novel Approach to Gene Expression Analysis"
        assert smith_entry["year"] == "2024"
        assert smith_entry["journal"] == "Nature Methods"
        assert smith_entry["doi"] == "10.1038/s41592-024-00001-0"

    def test_parse_misc_arxiv(self, johnson_entry):
        assert johnson_entry["entry_type"] == "misc"
        assert johnson_entry["title"] == "Transformer Models for Protein Structure Prediction"
        assert johnson_entry["eprint"] == "2401.12345"

    def test_parse_inproceedings(self, lee_entry):
        assert lee_entry["entry_type"] == "inproceedings"
        assert lee_entry["booktitle"] == "Proceedings of ISMB 2023"

    def test_parse_latex_special_chars(self, mueller_entry):
        # The raw title has \& which should be preserved or decoded
        assert "T" in mueller_entry["title"]
        assert mueller_entry["author"] is not None

    def test_parse_empty_file(self, tmp_path):
        empty = tmp_path / "empty.bib"
        empty.write_text("")
        assert parse_bib_file(str(empty)) == []

    def test_parse_nonexistent_file(self):
        assert parse_bib_file("/nonexistent/path.bib") == []


# ---------------------------------------------------------------------------
# format_citation Tests (Bibliography Entry Formatting)
# ---------------------------------------------------------------------------


class TestFormatCitationAPA:
    def test_format_citation_apa(self, smith_entry):
        result = format_citation(smith_entry, "apa")
        # APA: Authors (Year). Title. *Journal*. DOI
        assert "Smith" in result
        assert "(2024)" in result
        assert "A Novel Approach to Gene Expression Analysis" in result
        assert "Nature Methods" in result
        assert "10.1038/s41592-024-00001-0" in result


class TestFormatCitationNature:
    def test_format_citation_nature(self, smith_entry):
        result = format_citation(smith_entry, "nature")
        # Nature: Authors. Title. *Journal* (Year). DOI
        assert "Smith" in result
        assert "(2024)" in result
        assert "Nature Methods" in result


class TestFormatCitationIEEE:
    def test_format_citation_ieee(self, smith_entry):
        result = format_citation(smith_entry, "ieee")
        # IEEE: Authors, "Title," *Journal*, Year, doi: DOI.
        assert "Smith" in result
        assert "2024" in result
        assert "doi:" in result.lower() or "DOI" in result


class TestFormatCitationVancouver:
    def test_format_citation_vancouver(self, smith_entry):
        result = format_citation(smith_entry, "vancouver")
        # Vancouver: Authors. Title. Journal. Year. doi: DOI
        assert "Smith" in result
        assert "2024" in result


class TestFormatCitationArxiv:
    def test_format_citation_apa_arxiv(self, johnson_entry):
        result = format_citation(johnson_entry, "apa")
        assert "Johnson" in result
        assert "2024" in result
        assert "arXiv" in result or "2401.12345" in result


# ---------------------------------------------------------------------------
# format_intext Tests
# ---------------------------------------------------------------------------


class TestFormatIntextAPA:
    def test_format_intext_apa_three_authors(self, smith_entry):
        # 3+ authors: "(Smith et al., 2024)"
        result = format_intext(smith_entry, "apa")
        assert result == "(Smith et al., 2024)"

    def test_format_intext_apa_two_authors(self, johnson_entry):
        # 2 authors: "(Johnson & Brown, 2024)"
        result = format_intext(johnson_entry, "apa")
        assert result == "(Johnson & Brown, 2024)"

    def test_format_intext_apa_two_authors_lee(self, lee_entry):
        # 2 authors: "(Lee & Park, 2023)"
        result = format_intext(lee_entry, "apa")
        assert result == "(Lee & Park, 2023)"


class TestFormatIntextNature:
    def test_format_intext_nature(self, smith_entry):
        result = format_intext(smith_entry, "nature", number=1)
        assert result == "[1]"

    def test_format_intext_nature_number(self, johnson_entry):
        result = format_intext(johnson_entry, "nature", number=5)
        assert result == "[5]"


class TestFormatIntextIEEE:
    def test_format_intext_ieee(self, smith_entry):
        result = format_intext(smith_entry, "ieee", number=1)
        assert result == "[1]"


class TestFormatIntextVancouver:
    def test_format_intext_vancouver(self, smith_entry):
        result = format_intext(smith_entry, "vancouver", number=3)
        assert result == "(3)"


# ---------------------------------------------------------------------------
# format_bibliography Tests
# ---------------------------------------------------------------------------


class TestFormatBibliography:
    def test_format_bibliography_apa(self, bib_entries):
        result = format_bibliography(bib_entries, "apa")
        assert "## References" in result
        lines = [l for l in result.split("\n") if l.strip() and not l.startswith("#")]
        assert len(lines) == 4

    def test_format_bibliography_sorted(self, bib_entries):
        result = format_bibliography(bib_entries, "apa")
        lines = [l for l in result.split("\n") if l.strip() and not l.startswith("#")]
        # Alphabetical: Johnson, Lee, Mueller, Smith
        assert "Johnson" in lines[0]
        assert "Smith" in lines[3]

    def test_format_bibliography_nature_numbered(self, bib_entries):
        result = format_bibliography(bib_entries, "nature")
        assert "[1]" in result
        assert "[4]" in result


# ---------------------------------------------------------------------------
# replace_citation_markers Tests
# ---------------------------------------------------------------------------


class TestReplaceCitationMarkers:
    def test_replace_single_marker(self, bib_entries):
        text = "Results shown [@Smith2024] are significant."
        result, warnings = replace_citation_markers(text, bib_entries, "apa")
        assert "[@Smith2024]" not in result
        assert "Smith" in result
        assert len(warnings) == 0

    def test_replace_multi_marker(self, bib_entries):
        text = "Studies [@Johnson2024; @Mueller2024] confirm this."
        result, warnings = replace_citation_markers(text, bib_entries, "apa")
        assert "[@Johnson2024; @Mueller2024]" not in result
        assert "Johnson" in result
        assert len(warnings) == 0

    def test_replace_case_insensitive(self, bib_entries):
        text = "As shown by [@smith2024]."
        result, warnings = replace_citation_markers(text, bib_entries, "apa")
        assert "[@smith2024]" not in result
        assert "Smith" in result

    def test_replace_warns_on_unmatched(self, bib_entries):
        text = "Unknown reference [@NoSuchKey2024]."
        result, warnings = replace_citation_markers(text, bib_entries, "apa")
        assert len(warnings) == 1
        assert "NoSuchKey2024" in warnings[0]

    def test_replace_full_draft(self, bib_entries, draft_text):
        result, warnings = replace_citation_markers(draft_text, bib_entries, "apa")
        # Should have one warning for UnknownKey2024
        assert any("UnknownKey2024" in w for w in warnings)
        # All known markers replaced
        assert "[@Smith2024]" not in result
        assert "[@Lee2023]" not in result
