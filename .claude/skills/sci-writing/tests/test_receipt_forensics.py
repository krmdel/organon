"""Tier B receipt forensics tests.

Covers:
  B1 — parse_receipts_table: extracts structured rows from research.md
  B2 — cross_reference_receipts: diffs receipts vs bib entries (CRITICAL on mismatch)
  B3 — verify_receipts_against_api: re-calls live APIs (mocked; env-gated)
  B5 — check_receipt_confidence: sidecar confidence must not exceed seed confidence
  Integration — cmd_check_research returns incomplete with compliance_findings on tampered receipt

All tests are offline unless marked @pytest.mark.network.
"""

from __future__ import annotations

import json
import os
import sys
import textwrap
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
for p in (str(ROOT), str(SCRIPTS)):
    if p not in sys.path:
        sys.path.insert(0, p)

import researcher_ops
from researcher_ops import (
    parse_receipts_table,
    cross_reference_receipts,
    verify_receipts_against_api,
    check_receipt_confidence,
    TITLE_CROSS_THRESHOLD,
    TITLE_API_THRESHOLD,
    AUTHOR_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_RECEIPT_SECTION = """\
## Verification receipts

| # | API source | Returned title (verbatim from API) | First author (from API) | DOI/eprint confirmed |
|---|-----------|------------------------------------|-----------------------|---------------------|
{rows}
"""

_FULL_MD = """\
# Research: CRISPR in somatic cells

## Evidence table

| # | Key | Title | Year | DOI | Source | Confidence |
|---|-----|-------|------|-----|--------|------------|
| 1 | Mali2013 | RNA-guided human genome engineering via Cas9 | 2013 | 10.1126/science.1232033 | PubMed | high |

## Verification receipts

| # | API source | Returned title (verbatim from API) | First author (from API) | DOI/eprint confirmed |
|---|-----------|------------------------------------|-----------------------|---------------------|
| 1 | paper-search | RNA-guided human genome engineering via Cas9 | Mali | 10.1126/science.1232033 |
"""

_TWO_ROW_MD = """\
# Research: test

## Verification receipts

| # | API source | Returned title (verbatim from API) | First author (from API) | DOI/eprint confirmed |
|---|-----------|------------------------------------|-----------------------|---------------------|
| 1 | paper-search | Alpha Title | Smith | 10.1/alpha |
| 2 | arxiv       | Beta Title  | Jones | 2106.00001 |
"""

_NO_RECEIPTS_MD = """\
# Research: no receipts

## Evidence table

| # | Key | Title |
|---|-----|-------|
| 1 | foo | Bar   |
"""

_EMPTY_RECEIPTS_MD = """\
# Research: empty receipts

## Verification receipts

| # | API source | Returned title | First author | DOI/eprint |
|---|-----------|---------------|-------------|-----------|
"""


def _write(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "research.md"
    p.write_text(content, encoding="utf-8")
    return p


def _entry(key: str, author: str, title: str, doi: str = "", eprint: str = "") -> dict:
    e: dict = {"key": key, "entry_type": "article", "author": author, "title": title}
    if doi:
        e["doi"] = doi
    if eprint:
        e["eprint"] = eprint
    return e


# ---------------------------------------------------------------------------
# B1 — parse_receipts_table
# ---------------------------------------------------------------------------

class TestParseReceiptsTable:

    def test_single_row_returns_one_dict(self, tmp_path):
        path = _write(tmp_path, _FULL_MD)
        rows = parse_receipts_table(path)
        assert len(rows) == 1

    def test_single_row_fields(self, tmp_path):
        path = _write(tmp_path, _FULL_MD)
        row = parse_receipts_table(path)[0]
        assert row["entry_num"] == "1"
        assert row["api_source"] == "paper-search"
        assert "RNA-guided" in row["returned_title"]
        assert row["first_author"] == "Mali"
        assert row["identifier"] == "10.1126/science.1232033"

    def test_two_rows_returns_two_dicts(self, tmp_path):
        path = _write(tmp_path, _TWO_ROW_MD)
        rows = parse_receipts_table(path)
        assert len(rows) == 2
        assert rows[0]["entry_num"] == "1"
        assert rows[1]["entry_num"] == "2"

    def test_second_row_arxiv_identifier(self, tmp_path):
        path = _write(tmp_path, _TWO_ROW_MD)
        rows = parse_receipts_table(path)
        assert rows[1]["identifier"] == "2106.00001"

    def test_missing_section_returns_empty_list(self, tmp_path):
        path = _write(tmp_path, _NO_RECEIPTS_MD)
        assert parse_receipts_table(path) == []

    def test_empty_table_returns_empty_list(self, tmp_path):
        path = _write(tmp_path, _EMPTY_RECEIPTS_MD)
        assert parse_receipts_table(path) == []

    def test_nonexistent_file_returns_empty_list(self, tmp_path):
        assert parse_receipts_table(tmp_path / "ghost.md") == []

    def test_all_required_fields_present(self, tmp_path):
        path = _write(tmp_path, _FULL_MD)
        row = parse_receipts_table(path)[0]
        for field in ("entry_num", "api_source", "returned_title", "first_author", "identifier"):
            assert field in row, f"Missing field: {field}"

    def test_stops_at_next_heading(self, tmp_path):
        md = """\
## Verification receipts

| # | API source | Returned title | First author | DOI/eprint |
|---|-----------|---------------|-------------|-----------|
| 1 | arxiv | Title One | Smith | 2101.00001 |

## Some other section

| # | API source | Returned title | First author | DOI/eprint |
|---|-----------|---------------|-------------|-----------|
| 2 | arxiv | Title Two | Jones | 2102.00002 |
"""
        path = _write(tmp_path, md)
        rows = parse_receipts_table(path)
        assert len(rows) == 1
        assert rows[0]["entry_num"] == "1"


# ---------------------------------------------------------------------------
# B2 — cross_reference_receipts
# ---------------------------------------------------------------------------

class TestCrossReferenceReceipts:

    def _receipts(self, **kwargs) -> list[dict]:
        defaults = {
            "entry_num": "1",
            "api_source": "paper-search",
            "returned_title": "RNA-guided human genome engineering via Cas9",
            "first_author": "Mali",
            "identifier": "10.1126/science.1232033",
        }
        defaults.update(kwargs)
        return [defaults]

    def _bib(self, **kwargs) -> list[dict]:
        defaults = {
            "key": "Mali2013",
            "entry_type": "article",
            "title": "RNA-guided human genome engineering via Cas9",
            "author": "Mali, Prashant and others",
            "doi": "10.1126/science.1232033",
        }
        defaults.update(kwargs)
        return [defaults]

    def test_matching_receipt_and_bib_no_findings(self):
        findings = cross_reference_receipts(self._receipts(), self._bib())
        assert findings == [], f"Expected no findings, got: {findings}"

    def test_empty_receipts_returns_empty(self):
        assert cross_reference_receipts([], self._bib()) == []

    def test_empty_bib_returns_empty(self):
        assert cross_reference_receipts(self._receipts(), []) == []

    def test_title_mismatch_is_critical(self):
        receipts = self._receipts(returned_title="Completely Different Title")
        findings = cross_reference_receipts(receipts, self._bib())
        criticals = [f for f in findings if f["severity"] == "critical"]
        assert criticals, "Title mismatch must produce a CRITICAL finding"

    def test_title_mismatch_criterion(self):
        receipts = self._receipts(returned_title="Completely Different Title")
        findings = cross_reference_receipts(receipts, self._bib())
        criteria = [f["criterion"] for f in findings]
        assert "Receipt Forensics (Tier B)" in criteria

    def test_author_mismatch_is_critical(self):
        receipts = self._receipts(first_author="Salvagnin")
        bib = self._bib(author="Mali, Prashant and Yang, Le")
        findings = cross_reference_receipts(receipts, bib)
        criticals = [f for f in findings if f["severity"] == "critical"]
        assert criticals, "Author mismatch must produce a CRITICAL finding"

    def test_author_mismatch_finding_contains_names(self):
        receipts = self._receipts(first_author="Ghost")
        bib = self._bib(author="Mali, Prashant")
        findings = cross_reference_receipts(receipts, bib)
        criticals = [f for f in findings if f["severity"] == "critical"]
        assert criticals
        text = criticals[0]["finding"].lower()
        assert "ghost" in text or "mali" in text

    def test_identifier_not_in_bib_is_major(self):
        receipts = self._receipts(identifier="10.9999/nonexistent")
        findings = cross_reference_receipts(receipts, self._bib())
        majors = [f for f in findings if f["severity"] == "major"]
        assert majors, "Identifier absent from bib must produce a MAJOR finding"

    def test_arxiv_eprint_lookup(self):
        receipts = self._receipts(
            returned_title="Some arXiv Paper",
            first_author="Smith",
            identifier="2101.12345",
        )
        bib = [_entry(
            key="smith2021",
            author="Smith, John",
            title="Some arXiv Paper",
            eprint="2101.12345",
        )]
        findings = cross_reference_receipts(receipts, bib)
        criticals = [f for f in findings if f["severity"] == "critical"]
        assert not criticals, f"Matching arXiv receipt should produce no CRITICAL, got: {criticals}"

    def test_finding_contains_entry_num(self):
        receipts = self._receipts(returned_title="Wrong Title Entirely")
        findings = cross_reference_receipts(receipts, self._bib())
        for f in findings:
            assert "1" in f["finding"], f"Finding should reference entry_num '1': {f['finding']}"

    def test_finding_has_suggestion(self):
        receipts = self._receipts(returned_title="Wrong Title Entirely")
        findings = cross_reference_receipts(receipts, self._bib())
        for f in findings:
            assert f.get("suggestion"), f"Finding missing suggestion: {f}"

    def test_finding_format_complete(self):
        receipts = self._receipts(returned_title="Wrong Title Entirely")
        findings = cross_reference_receipts(receipts, self._bib())
        required_keys = {"criterion", "severity", "section", "finding", "suggestion"}
        for f in findings:
            missing = required_keys - f.keys()
            assert not missing, f"Finding missing keys {missing}: {f}"

    def test_similar_enough_title_passes(self):
        receipts = self._receipts(
            returned_title="RNA-guided human genome engineering via Cas9 (preprint)"
        )
        findings = cross_reference_receipts(receipts, self._bib())
        criticals = [f for f in findings if f["severity"] == "critical"]
        assert not criticals, "Near-identical titles should not trigger CRITICAL"

    def test_partial_match_author_passes(self):
        receipts = self._receipts(first_author="Mäli")
        bib = self._bib(author="Mali, Prashant")
        findings = cross_reference_receipts(receipts, bib)
        criticals = [f for f in findings if f["severity"] == "critical"]
        assert not criticals, "Diacritic variant of same surname should pass"


# ---------------------------------------------------------------------------
# B3 — verify_receipts_against_api
# ---------------------------------------------------------------------------

class TestVerifyReceiptsAgainstApi:

    _RECEIPT = {
        "entry_num": "1",
        "api_source": "arxiv",
        "returned_title": "RNA-guided human genome engineering via Cas9",
        "first_author": "Mali",
        "identifier": "10.1126/science.1232033",
    }

    def test_returns_empty_when_flag_not_set(self, monkeypatch):
        monkeypatch.delenv("SCI_OS_VERIFY_RECEIPTS", raising=False)
        monkeypatch.delenv("CI", raising=False)
        findings = verify_receipts_against_api([self._RECEIPT])
        assert findings == []

    def test_returns_empty_for_no_receipts_even_with_flag(self, monkeypatch):
        monkeypatch.setenv("SCI_OS_VERIFY_RECEIPTS", "1")
        findings = verify_receipts_against_api([])
        assert findings == []

    def test_matching_api_response_no_findings(self, monkeypatch):
        monkeypatch.setenv("SCI_OS_VERIFY_RECEIPTS", "1")
        monkeypatch.delenv("CI", raising=False)

        import types
        fake_cv = types.ModuleType("citation_verify")
        fake_cv.verify_citation = lambda entry: {  # type: ignore
            "title": "RNA-guided human genome engineering via Cas9",
            "authors": ["Mali", "Yang", "Esvelt"],
            "source": "crossref",
        }

        original = sys.modules.get("citation_verify")
        sys.modules["citation_verify"] = fake_cv
        try:
            findings = verify_receipts_against_api([self._RECEIPT])
        finally:
            if original is None:
                sys.modules.pop("citation_verify", None)
            else:
                sys.modules["citation_verify"] = original

        assert findings == [], f"Expected no findings for matching response, got: {findings}"

    def test_title_mismatch_from_api_is_critical(self, monkeypatch):
        monkeypatch.setenv("SCI_OS_VERIFY_RECEIPTS", "1")
        monkeypatch.delenv("CI", raising=False)

        _live = {
            "title": "Completely Different Paper Title From API",
            "authors": ["Mali"],
            "source": "crossref",
        }

        import types
        fake_cv = types.ModuleType("citation_verify")
        fake_cv.verify_citation = lambda entry: _live  # type: ignore

        original = sys.modules.get("citation_verify")
        sys.modules["citation_verify"] = fake_cv
        try:
            findings = verify_receipts_against_api([self._RECEIPT])
        finally:
            if original is None:
                sys.modules.pop("citation_verify", None)
            else:
                sys.modules["citation_verify"] = original

        criticals = [f for f in findings if f["severity"] == "critical"]
        assert criticals, "Title mismatch from live API must produce CRITICAL"
        assert "Receipt Forensics (Tier B)" in criticals[0]["criterion"]

    def test_author_mismatch_from_api_is_critical(self, monkeypatch):
        monkeypatch.setenv("SCI_OS_VERIFY_RECEIPTS", "1")
        monkeypatch.delenv("CI", raising=False)

        _live = {
            "title": "RNA-guided human genome engineering via Cas9",
            "authors": ["Salvagnin", "Berthold"],
            "source": "crossref",
        }

        import types
        fake_cv = types.ModuleType("citation_verify")
        fake_cv.verify_citation = lambda entry: _live  # type: ignore

        original = sys.modules.get("citation_verify")
        sys.modules["citation_verify"] = fake_cv
        try:
            findings = verify_receipts_against_api([self._RECEIPT])
        finally:
            if original is None:
                sys.modules.pop("citation_verify", None)
            else:
                sys.modules["citation_verify"] = original

        criticals = [f for f in findings if f["severity"] == "critical"]
        assert criticals, "Author mismatch from live API must produce CRITICAL"

    def test_network_error_is_swallowed(self, monkeypatch):
        monkeypatch.setenv("SCI_OS_VERIFY_RECEIPTS", "1")
        monkeypatch.delenv("CI", raising=False)

        import types
        fake_cv = types.ModuleType("citation_verify")

        def _raise(entry):
            raise ConnectionError("network down")
        fake_cv.verify_citation = _raise  # type: ignore

        original = sys.modules.get("citation_verify")
        sys.modules["citation_verify"] = fake_cv
        try:
            findings = verify_receipts_against_api([self._RECEIPT])
        finally:
            if original is None:
                sys.modules.pop("citation_verify", None)
            else:
                sys.modules["citation_verify"] = original

        assert findings == [], "Network errors must be swallowed (non-fatal)"

    def test_missing_identifier_skipped(self, monkeypatch):
        monkeypatch.setenv("SCI_OS_VERIFY_RECEIPTS", "1")
        monkeypatch.delenv("CI", raising=False)
        receipt_no_id = {**self._RECEIPT, "identifier": ""}
        import types
        fake_cv = types.ModuleType("citation_verify")
        fake_cv.verify_citation = lambda e: {"title": "X", "authors": ["Y"]}  # type: ignore
        original = sys.modules.get("citation_verify")
        sys.modules["citation_verify"] = fake_cv
        try:
            findings = verify_receipts_against_api([receipt_no_id])
        finally:
            if original is None:
                sys.modules.pop("citation_verify", None)
            else:
                sys.modules["citation_verify"] = original
        assert findings == []


# ---------------------------------------------------------------------------
# B5 — check_receipt_confidence
# ---------------------------------------------------------------------------

class TestCheckReceiptConfidence:

    def test_sidecar_full_text_seed_abstract_is_major(self):
        seed = {"Mali2013": {"confidence": "abstract"}}
        sidecar = {"Mali2013": {"source_confidence": "full-text"}}
        findings = check_receipt_confidence([], seed, sidecar)
        majors = [f for f in findings if f["severity"] == "major"]
        assert majors, "Sidecar claiming full-text when seed is abstract must be MAJOR"

    def test_sidecar_full_text_seed_full_text_passes(self):
        seed = {"Mali2013": {"confidence": "full-text"}}
        sidecar = {"Mali2013": {"source_confidence": "full-text"}}
        findings = check_receipt_confidence([], seed, sidecar)
        assert findings == []

    def test_sidecar_abstract_seed_abstract_passes(self):
        seed = {"Mali2013": {"confidence": "abstract"}}
        sidecar = {"Mali2013": {"source_confidence": "abstract"}}
        findings = check_receipt_confidence([], seed, sidecar)
        assert findings == []

    def test_sidecar_partial_seed_abstract_is_major(self):
        seed = {"foo": {"confidence": "abstract"}}
        sidecar = {"foo": {"source_confidence": "partial"}}
        findings = check_receipt_confidence([], seed, sidecar)
        majors = [f for f in findings if f["severity"] == "major"]
        assert majors, "Partial > abstract should produce MAJOR"

    def test_sidecar_abstract_seed_full_text_passes(self):
        seed = {"foo": {"confidence": "full-text"}}
        sidecar = {"foo": {"source_confidence": "abstract"}}
        findings = check_receipt_confidence([], seed, sidecar)
        assert findings == [], "Lower sidecar confidence is always fine"

    def test_key_only_in_sidecar_skipped(self):
        seed = {}
        sidecar = {"orphan_key": {"source_confidence": "full-text"}}
        findings = check_receipt_confidence([], seed, sidecar)
        assert findings == []

    def test_finding_contains_key_name(self):
        seed = {"Mali2013": {"confidence": "abstract"}}
        sidecar = {"Mali2013": {"source_confidence": "full-text"}}
        findings = check_receipt_confidence([], seed, sidecar)
        assert findings
        assert "Mali2013" in findings[0]["finding"]

    def test_finding_has_suggestion(self):
        seed = {"k": {"confidence": "abstract"}}
        sidecar = {"k": {"source_confidence": "full-text"}}
        findings = check_receipt_confidence([], seed, sidecar)
        assert findings[0].get("suggestion")

    def test_criterion_is_tier_b(self):
        seed = {"k": {"confidence": "abstract"}}
        sidecar = {"k": {"source_confidence": "full-text"}}
        findings = check_receipt_confidence([], seed, sidecar)
        assert findings[0]["criterion"] == "Receipt Forensics (Tier B)"

    def test_unknown_confidence_value_skipped(self):
        seed = {"k": {"confidence": "unknown-level"}}
        sidecar = {"k": {"source_confidence": "full-text"}}
        findings = check_receipt_confidence([], seed, sidecar)
        assert findings == [], "Unknown seed confidence level must be skipped silently"


# ---------------------------------------------------------------------------
# Integration: cmd_check_research blocks on tampered receipt
# ---------------------------------------------------------------------------

class TestCmdCheckResearchTierB:
    """Integration: tampered receipt → incomplete with compliance_findings."""

    def _make_workspace(self, tmp_path: Path, receipt_title: str = "RNA-guided human genome engineering via Cas9") -> str:
        """Build a minimal valid paper pipeline workspace with one tweakable receipt row."""
        slug = "test-" + uuid.uuid4().hex[:8]
        ws = tmp_path / "projects" / "sci-writing" / slug
        ws.mkdir(parents=True)

        # .bib
        bib = ws / f"{slug}.bib"
        bib.write_text(textwrap.dedent(f"""\
            @article{{Mali2013,
              author  = {{Mali, Prashant and Yang, Le}},
              title   = {{RNA-guided human genome engineering via Cas9}},
              journal = {{Science}},
              doi     = {{10.1126/science.1232033}},
              year    = {{2013}}
            }}
        """), encoding="utf-8")

        # quotes.json
        quotes = ws / f"{slug}.quotes.json"
        quotes.write_text(json.dumps({"Mali2013": {"confidence": "abstract", "candidates": []}}))

        # research.md with controllable receipt title
        research = ws / "research.md"
        research.write_text(textwrap.dedent(f"""\
            # Research: CRISPR

            ## Evidence table

            | # | Key | Title | Year | DOI | Source | Confidence |
            |---|-----|-------|------|-----|--------|------------|
            | 1 | Mali2013 | RNA-guided human genome engineering via Cas9 | 2013 | 10.1126/science.1232033 | PubMed | high |

            ## Verification receipts

            | # | API source | Returned title (verbatim from API) | First author (from API) | DOI/eprint confirmed |
            |---|-----------|------------------------------------|-----------------------|---------------------|
            | 1 | paper-search | {receipt_title} | Mali | 10.1126/science.1232033 |
        """), encoding="utf-8")

        return slug, ws, tmp_path

    def test_tampered_receipt_title_blocks_pipeline(self, tmp_path, monkeypatch):
        """A receipt with a completely different title blocks check-research as incomplete."""
        # Point paper_pipeline PROJECT_ROOT at tmp_path so state files land there
        import paper_pipeline as pp
        original_root = pp.PROJECT_ROOT
        monkeypatch.setattr(pp, "PROJECT_ROOT", tmp_path)
        monkeypatch.setenv("SCI_OS_SKIP_DOI_VERIFY", "1")  # disable CrossRef network

        slug, ws, _ = self._make_workspace(tmp_path, receipt_title="Completely Fabricated Paper Title")

        # Create pipeline state file
        state_dir = tmp_path / "projects" / "sci-writing" / slug
        state_dir.mkdir(parents=True, exist_ok=True)
        state_file = state_dir / ".pipeline_state.json"
        state_file.write_text(json.dumps({
            "pipeline": "paper",
            "slug": slug,
            "topic": "test",
            "section": "",
            "phase": "init",
            "nonce": uuid.uuid4().hex,
            "retry_count": 0,
            "max_retries": 1,
            "mechanical_exits": [],
            "last_gate_status": None,
            "verification_counts": [],
            "review_counts": [],
            "history": [],
        }), encoding="utf-8")

        result = pp.cmd_check_research(slug)

        assert result["status"] == "incomplete", (
            f"Expected incomplete status for tampered receipt, got: {result}"
        )
        findings = result.get("compliance_findings", [])
        assert findings, "Expected compliance_findings to be non-empty"
        criticals = [f for f in findings if f.get("severity") == "critical"]
        assert criticals, "Expected at least one CRITICAL finding in compliance_findings"

    def test_clean_receipt_advances_pipeline(self, tmp_path, monkeypatch):
        """A correct receipt (matching title + author) allows check-research to advance."""
        import paper_pipeline as pp
        monkeypatch.setattr(pp, "PROJECT_ROOT", tmp_path)
        monkeypatch.setenv("SCI_OS_SKIP_DOI_VERIFY", "1")

        slug, ws, _ = self._make_workspace(
            tmp_path,
            receipt_title="RNA-guided human genome engineering via Cas9",
        )

        state_dir = tmp_path / "projects" / "sci-writing" / slug
        state_dir.mkdir(parents=True, exist_ok=True)
        state_file = state_dir / ".pipeline_state.json"
        state_file.write_text(json.dumps({
            "pipeline": "paper",
            "slug": slug,
            "topic": "test",
            "section": "",
            "phase": "init",
            "nonce": uuid.uuid4().hex,
            "retry_count": 0,
            "max_retries": 1,
            "mechanical_exits": [],
            "last_gate_status": None,
            "verification_counts": [],
            "review_counts": [],
            "history": [],
        }), encoding="utf-8")

        result = pp.cmd_check_research(slug)

        assert result["status"] == "ok", (
            f"Expected ok status for clean receipt, got: {result}"
        )
