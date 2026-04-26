"""End-to-end literature pipeline test — search to BibTeX export.

Scenario: A researcher searches for papers on BiomarkerX immunotherapy,
de-duplicates results from multiple sources, converts them to BibTeX format,
and generates formatted citations and bibliographies.

This test suite validates E2E-02: literature search -> summarization ->
citation export pipeline. Since sci-literature-research has no Python scripts
(MCP-only skill), the test simulates the pipeline as data transformations
using canned search results fed through writing_ops functions.
"""

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — import skill scripts
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"

WRITE_SCRIPTS = str(ROOT / ".claude" / "skills" / "sci-writing" / "scripts")
sys.path.insert(0, WRITE_SCRIPTS)

from writing_ops import (
    parse_bib_file,
    format_citation,
    format_bibliography,
    replace_citation_markers,
)

# ---------------------------------------------------------------------------
# Mock search results — simulate MCP search responses from multiple sources
# ---------------------------------------------------------------------------

MOCK_SEARCH_RESULTS = [
    {
        "title": "BiomarkerX predicts immunotherapy response in solid tumors",
        "authors": [{"name": "Chen, L."}, {"name": "Wang, K."}],
        "year": "2024",
        "doi": "10.1234/jco.2024.001",
        "abstract": "We investigated BiomarkerX as a predictive biomarker for immunotherapy response...",
        "citation_count": 45,
        "journal": "J Clin Oncol",
        "source": "pubmed",
    },
    {
        "title": "Mechanisms of immune checkpoint resistance",
        "authors": [{"name": "Patel, R."}, {"name": "Kim, S."}],
        "year": "2023",
        "doi": "10.5678/ni.2023.042",
        "abstract": "Resistance mechanisms in checkpoint immunotherapy...",
        "citation_count": 120,
        "journal": "Nature Immunology",
        "source": "arxiv",
    },
    {
        "title": "BiomarkerX predicts immunotherapy response in solid tumors",
        "authors": [{"name": "Chen, L."}, {"name": "Wang, K."}],
        "year": "2024",
        "doi": "10.1234/jco.2024.001",
        "abstract": "We investigated BiomarkerX as a predictive biomarker...",
        "citation_count": 45,
        "journal": "J Clin Oncol",
        "source": "semantic_scholar",
    },
    {
        "title": "Phase II trial of anti-PD1 stratified by biomarker levels",
        "authors": [{"name": "Rodriguez, C."}, {"name": "Yamamoto, K."}],
        "year": "2024",
        "doi": "10.9012/lo.2024.089",
        "abstract": "A phase II clinical trial evaluating anti-PD1...",
        "citation_count": 30,
        "journal": "Lancet Oncol",
        "source": "pubmed",
    },
]


# ---------------------------------------------------------------------------
# Pipeline helpers
# ---------------------------------------------------------------------------


def deduplicate_by_doi(results: list[dict]) -> list[dict]:
    """Remove duplicate entries sharing the same DOI, keeping first occurrence.

    Args:
        results: List of search result dicts with a "doi" key.

    Returns:
        Deduplicated list preserving order of first occurrence.
    """
    seen_dois: set[str] = set()
    deduped = []
    for result in results:
        doi = result.get("doi", "")
        if doi and doi in seen_dois:
            continue
        if doi:
            seen_dois.add(doi)
        deduped.append(result)
    return deduped


def convert_search_to_bibtex(results: list[dict]) -> list[dict]:
    """Convert search result dicts into the format that format_citation expects.

    Keys produced: key, title, author, journal, year, volume, pages, doi.
    The "key" is generated from the first author's last name + year.
    Volume and pages are set to empty strings (search results lack them).

    Args:
        results: List of search result dicts.

    Returns:
        List of entry dicts compatible with format_citation and format_bibliography.
    """
    entries = []
    for result in results:
        authors_list = result.get("authors", [])
        if authors_list:
            first_author_name = authors_list[0].get("name", "Unknown")
            # Extract last name from "Last, First" or "First Last" format
            if "," in first_author_name:
                last_name = first_author_name.split(",")[0].strip()
            else:
                parts = first_author_name.strip().split()
                last_name = parts[-1] if parts else "Unknown"
            # Build BibTeX-style author string: "Last, First and Last, First"
            author_parts = []
            for a in authors_list:
                name = a.get("name", "")
                author_parts.append(name)
            author_str = " and ".join(author_parts)
        else:
            last_name = "Unknown"
            author_str = "Unknown"

        year = result.get("year", "")
        key = f"{last_name}{year}"

        entry = {
            "key": key,
            "title": result.get("title", ""),
            "author": author_str,
            "journal": result.get("journal", ""),
            "year": year,
            "volume": "",
            "pages": "",
            "doi": result.get("doi", ""),
            "entry_type": "article",
        }
        entries.append(entry)
    return entries


# ===================================================================
# TEST CLASS 1: Literature Search Pipeline
# ===================================================================


class TestLiteratureSearchPipeline:
    """Validate the search -> dedup -> convert -> format pipeline (E2E-02)."""

    def test_mock_search_returns_results(self):
        """MOCK_SEARCH_RESULTS has 4 entries, each with required keys."""
        assert len(MOCK_SEARCH_RESULTS) == 4
        for result in MOCK_SEARCH_RESULTS:
            assert "title" in result, f"Entry missing 'title': {result}"
            assert "doi" in result, f"Entry missing 'doi': {result}"
            assert "source" in result, f"Entry missing 'source': {result}"

    def test_deduplicate_by_doi(self):
        """Dedup removes the duplicate DOI, leaving 3 unique entries."""
        deduped = deduplicate_by_doi(MOCK_SEARCH_RESULTS)
        assert len(deduped) == 3, f"Expected 3 after dedup, got {len(deduped)}"
        dois = [r["doi"] for r in deduped]
        assert len(dois) == len(set(dois)), "Duplicate DOIs remain after dedup"

    def test_convert_to_bibtex_format(self):
        """Converted entries have all required BibTeX keys."""
        deduped = deduplicate_by_doi(MOCK_SEARCH_RESULTS)
        converted = convert_search_to_bibtex(deduped)
        assert len(converted) == len(deduped)
        for entry in converted:
            assert "key" in entry, f"Entry missing 'key': {entry}"
            assert "title" in entry, f"Entry missing 'title': {entry}"
            assert "author" in entry, f"Entry missing 'author': {entry}"
            assert "year" in entry, f"Entry missing 'year': {entry}"
            assert "doi" in entry, f"Entry missing 'doi': {entry}"

    def test_format_citations_from_search(self):
        """Each converted entry can be formatted as an APA citation string."""
        deduped = deduplicate_by_doi(MOCK_SEARCH_RESULTS)
        converted = convert_search_to_bibtex(deduped)
        for entry in converted:
            citation = format_citation(entry, "apa")
            assert isinstance(citation, str), "Citation must be a string"
            assert len(citation) > 10, f"Citation too short: {repr(citation)}"

    def test_generate_bibliography_from_search(self):
        """format_bibliography produces a string containing author names."""
        deduped = deduplicate_by_doi(MOCK_SEARCH_RESULTS)
        converted = convert_search_to_bibtex(deduped)
        bibliography = format_bibliography(converted, "apa")
        assert isinstance(bibliography, str)
        # At least one of the author last names should appear in bibliography
        author_names = ["Chen", "Patel", "Rodriguez"]
        found = any(name in bibliography for name in author_names)
        assert found, f"No author names found in bibliography: {bibliography[:200]}"


# ===================================================================
# TEST CLASS 2: BibTeX Export Pipeline
# ===================================================================


class TestLiteratureToBibTexExport:
    """Validate reading an existing .bib file and roundtrip export (E2E-02)."""

    def test_existing_bib_file_parses(self):
        """parse_bib_file reads the fixture .bib and returns 4 entries."""
        bib_path = str(FIXTURES / "e2e_references.bib")
        entries = parse_bib_file(bib_path)
        assert len(entries) == 4, f"Expected 4 entries, got {len(entries)}: {entries}"

    def test_bibtex_roundtrip(self):
        """Each entry from the .bib file can be formatted as APA >20 chars."""
        bib_path = str(FIXTURES / "e2e_references.bib")
        entries = parse_bib_file(bib_path)
        assert len(entries) == 4
        for entry in entries:
            formatted = format_citation(entry, "apa")
            assert len(formatted) > 20, (
                f"Formatted citation too short for entry '{entry.get('key')}': "
                f"{repr(formatted)}"
            )

    def test_full_pipeline_search_to_export(self, tmp_path):
        """Full chain: dedup -> convert -> format_bibliography -> file I/O."""
        # Step 1: Dedup
        deduped = deduplicate_by_doi(MOCK_SEARCH_RESULTS)
        assert len(deduped) == 3

        # Step 2: Convert to BibTeX entry format
        converted = convert_search_to_bibtex(deduped)

        # Step 3: Generate bibliography text
        bibliography = format_bibliography(converted, "apa")
        assert isinstance(bibliography, str)
        assert len(bibliography) > 50

        # Step 4: Write to a file
        export_path = tmp_path / "exported_bibliography.txt"
        export_path.write_text(bibliography)
        assert export_path.exists()

        # Step 5: Read back and verify content
        content = export_path.read_text()
        # Should contain at least one year string
        assert any(yr in content for yr in ["2023", "2024"]), (
            f"No year found in exported content: {content[:200]}"
        )
        # Should contain at least one author name
        author_names = ["Chen", "Patel", "Rodriguez"]
        assert any(name in content for name in author_names), (
            f"No author name found in exported content: {content[:200]}"
        )
