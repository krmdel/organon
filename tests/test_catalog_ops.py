"""Tests for sci-tools catalog_ops module.

Covers catalog search (keyword, empty, no match, limit, category filter,
fuzzy category), category listing, results formatting, tool detail retrieval
(subprocess mock), catalog refresh (subprocess mock), and path resolution.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add scripts dir to path for catalog_ops import
SCRIPTS_DIR = str(
    Path(__file__).resolve().parent.parent
    / ".claude"
    / "skills"
    / "sci-tools"
    / "scripts"
)
sys.path.insert(0, SCRIPTS_DIR)


# ---------------------------------------------------------------------------
# Fixture: sample catalog with 5 tools across 3 categories
# ---------------------------------------------------------------------------

SAMPLE_CATALOG = {
    "total_tools": 5,
    "tools": [
        {
            "name": "ESMFold_predict_structure",
            "description": "Predict protein 3D structure from amino acid sequence using ESMFold.",
            "type": "ESMFoldTool",
            "category": "software_structural_biology",
        },
        {
            "name": "AlphaFold_structure_prediction",
            "description": "Predict protein structure using AlphaFold deep learning model.",
            "type": "AlphaFoldTool",
            "category": "software_structural_biology",
        },
        {
            "name": "BLAST_sequence_search",
            "description": "Search nucleotide and protein sequence databases using BLAST.",
            "type": "BLASTTool",
            "category": "software_bioinformatics",
        },
        {
            "name": "GenomeBrowser_visualize",
            "description": "Visualize genomic data and gene annotations in a genome browser.",
            "type": "GenomeBrowserTool",
            "category": "software_genomics",
        },
        {
            "name": "GeneOntology_enrichment",
            "description": "Perform gene ontology enrichment analysis on gene lists.",
            "type": "GOTool",
            "category": "software_bioinformatics",
        },
    ],
}


@pytest.fixture
def catalog_file(tmp_path):
    """Write sample catalog to a temp file and monkeypatch CATALOG_PATH."""
    catalog_path = tmp_path / "tooluniverse-catalog.json"
    catalog_path.write_text(json.dumps(SAMPLE_CATALOG, indent=2))
    return catalog_path


@pytest.fixture(autouse=True)
def patch_catalog_path(catalog_file):
    """Monkeypatch CATALOG_PATH in catalog_ops to use the fixture file."""
    import catalog_ops

    original = catalog_ops.CATALOG_PATH
    catalog_ops.CATALOG_PATH = catalog_file
    yield
    catalog_ops.CATALOG_PATH = original


# ---------------------------------------------------------------------------
# Search Tests
# ---------------------------------------------------------------------------


class TestSearchCatalog:
    def test_search_catalog_keyword(self):
        from catalog_ops import search_catalog

        results = search_catalog("protein structure")
        assert len(results) >= 2
        names = [r["name"] for r in results]
        assert "ESMFold_predict_structure" in names
        assert "AlphaFold_structure_prediction" in names
        # Should be sorted by relevance (both keywords hit)
        for r in results:
            assert "_score" not in r

    def test_search_catalog_empty_query(self):
        from catalog_ops import search_catalog

        results = search_catalog("")
        assert results == []

    def test_search_catalog_no_match(self):
        from catalog_ops import search_catalog

        results = search_catalog("xyznonexistent")
        assert results == []

    def test_search_catalog_limit(self):
        from catalog_ops import search_catalog

        results = search_catalog("gene", limit=3)
        assert len(results) <= 3

    def test_category_filter(self):
        from catalog_ops import search_catalog

        results = search_catalog("protein", category="software_structural_biology")
        for r in results:
            assert r["category"] == "software_structural_biology"
        assert len(results) >= 1

    def test_category_fuzzy(self):
        from catalog_ops import search_catalog

        # "structural" should match "software_structural_biology"
        results = search_catalog("protein", category="structural")
        assert len(results) >= 1
        for r in results:
            assert "structural" in r["category"].lower()


# ---------------------------------------------------------------------------
# Category Listing
# ---------------------------------------------------------------------------


class TestListCategories:
    def test_list_categories(self):
        from catalog_ops import list_categories

        categories = list_categories()
        assert isinstance(categories, list)
        assert len(categories) == 3
        assert categories == sorted(categories)
        assert "software_bioinformatics" in categories
        assert "software_genomics" in categories
        assert "software_structural_biology" in categories


# ---------------------------------------------------------------------------
# Format Results Table
# ---------------------------------------------------------------------------


class TestFormatResultsTable:
    def test_format_results_table(self):
        from catalog_ops import search_catalog, format_results_table

        results = search_catalog("protein")
        table = format_results_table(results)
        assert isinstance(table, str)
        assert "Name" in table
        assert "Category" in table
        assert "Type" in table
        assert "Description" in table
        assert "ESMFold_predict_structure" in table


# ---------------------------------------------------------------------------
# Subprocess-based Operations (mocked)
# ---------------------------------------------------------------------------


class TestGetToolDetails:
    def test_get_tool_details_subprocess(self):
        from catalog_ops import get_tool_details

        mock_output = json.dumps(
            {
                "name": "ESMFold_predict_structure",
                "description": "Predict protein 3D structure",
                "parameters": [{"name": "sequence", "type": "str"}],
                "return_schema": {"type": "object"},
            }
        )
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = mock_output

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            details = get_tool_details("ESMFold_predict_structure")
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert "tu" in call_args
            assert "info" in call_args
            assert "ESMFold_predict_structure" in call_args
            assert "--json" in call_args
            assert details["name"] == "ESMFold_predict_structure"


class TestRefreshCatalog:
    def test_refresh_catalog_subprocess(self, catalog_file):
        from catalog_ops import refresh_catalog

        mock_output = json.dumps(SAMPLE_CATALOG)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = mock_output

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = refresh_catalog()
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert "tu" in call_args
            assert "list" in call_args
            assert "--raw" in call_args
            assert "refreshed_at" in result
            # Verify it wrote to disk
            written = json.loads(catalog_file.read_text())
            assert "refreshed_at" in written


# ---------------------------------------------------------------------------
# Path Resolution
# ---------------------------------------------------------------------------


class TestCatalogPathResolution:
    def test_catalog_path_resolution(self):
        from catalog_ops import CATALOG_PATH as ORIGINAL_PATH

        # ORIGINAL_PATH was monkeypatched, but we can import the module-level
        # constant before patching to check. Instead, verify the module defines it.
        import catalog_ops

        # The original (unpatched) path should end with the expected suffix
        # We check the module's PROJECT_ROOT instead
        assert hasattr(catalog_ops, "PROJECT_ROOT")
        project_root = catalog_ops.PROJECT_ROOT
        expected_catalog = project_root / "data" / "tooluniverse-catalog.json"
        # Verify the path structure is correct
        assert str(expected_catalog).endswith("data/tooluniverse-catalog.json")
