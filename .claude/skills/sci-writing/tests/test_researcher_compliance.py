"""Phase 3 tests: researcher_ops.py verification-receipts compliance.

TDD: written before researcher_ops.py exists. Tests confirm that
check_research_receipts() correctly validates research.md for the
Verification receipts table introduced in Phase 3.

Architecture: tests are pure-offline (no network, no tmp_path state
machine). They build minimal research.md content strings in-memory
and call the validator directly via a tmp file.

Criterion used by the finding: "Researcher Integrity (Phase 3)".
Severity: "critical" — a research.md without receipts cannot be
trusted (we don't know whether the researcher verified anything).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS = ROOT / ".claude" / "skills" / "sci-writing" / "scripts"
for p in (str(ROOT), str(SCRIPTS)):
    if p not in sys.path:
        sys.path.insert(0, p)

# researcher_ops is the module under test — import lazily so the
# collection phase doesn't blow up before the module exists.
try:
    import researcher_ops  # type: ignore
    _MODULE_AVAILABLE = True
except ImportError:
    _MODULE_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _MODULE_AVAILABLE,
    reason="researcher_ops.py not yet implemented (TDD: these tests drive the implementation)",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_RESEARCH_MD = """\
# Research: CRISPR in somatic cells

## Sub-claims to support
1. Cas9 can cleave dsDNA at guide-specified sites.
2. Efficiency varies by cell type.

## Evidence table

| # | Key | Title | Year | DOI | Source | Confidence |
|---|-----|-------|------|-----|--------|------------|
| 1 | Mali2013 | RNA-guided human genome engineering via Cas9 | 2013 | 10.1126/science.1232033 | PubMed | high |

## Findings

Mali et al. [1] demonstrated site-specific cleavage.

## Coverage status

- Checked directly: [1]
- Abstract only: none
- Unresolved / gaps: none

## Verification receipts

| # | API source | Returned title (verbatim from API) | First author (from API) | DOI/eprint confirmed |
|---|-----------|------------------------------------|-----------------------|---------------------|
| 1 | paper-search | RNA-guided human genome engineering via Cas9 | Mali | 10.1126/science.1232033 |
"""

_NO_RECEIPTS_SECTION = """\
# Research: CRISPR in somatic cells

## Evidence table

| # | Key | Title | Year | DOI | Source | Confidence |
|---|-----|-------|------|-----|--------|------------|
| 1 | Mali2013 | RNA-guided human genome engineering via Cas9 | 2013 | 10.1126/science.1232033 | PubMed | high |

## Findings

Some text.

## Coverage status

- Checked directly: [1]
"""

_RECEIPTS_SECTION_NO_ROWS = """\
# Research: test

## Evidence table

| # | Key | Title | Year | DOI | Source | Confidence |
|---|-----|-------|------|-----|--------|------------|
| 1 | Mali2013 | RNA-guided human genome engineering via Cas9 | 2013 | 10.1126/science.1232033 | PubMed | high |

## Verification receipts

| # | API source | Returned title (verbatim from API) | First author (from API) | DOI/eprint confirmed |
|---|-----------|------------------------------------|-----------------------|---------------------|
"""

_RECEIPTS_SECTION_SEPARATOR_ONLY = """\
# Research: test

## Evidence table

| # | Key | Title | Year | DOI | Source | Confidence |
|---|-----|-------|------|-----|--------|------------|
| 1 | Mali2013 | RNA-guided human genome engineering via Cas9 | 2013 | 10.1126/science.1232033 | PubMed | high |

## Verification receipts

Only prose here, no table at all.
"""

_MULTI_ROW_RECEIPTS = """\
# Research: test

## Evidence table

| # | Key | Title | Year | DOI | Source | Confidence |
|---|-----|-------|------|-----|--------|------------|
| 1 | Mali2013 | T1 | 2013 | 10.1/a | PubMed | high |
| 2 | Ran2013  | T2 | 2013 | 10.1/b | PubMed | high |

## Verification receipts

| # | API source | Returned title (verbatim from API) | First author (from API) | DOI/eprint confirmed |
|---|-----------|------------------------------------|-----------------------|---------------------|
| 1 | paper-search | T1 | Mali | 10.1/a |
| 2 | paper-search | T2 | Ran  | 10.1/b |
"""


def _write(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "research.md"
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestVerificationReceiptsCheck:

    def test_valid_receipts_passes(self, tmp_path):
        """A research.md with a proper Verification receipts table returns no findings."""
        path = _write(tmp_path, _VALID_RESEARCH_MD)
        findings = researcher_ops.check_research_receipts(path)
        assert findings == [], f"Expected no findings, got: {findings}"

    def test_multi_row_receipts_passes(self, tmp_path):
        """Multiple rows in the receipts table still passes."""
        path = _write(tmp_path, _MULTI_ROW_RECEIPTS)
        findings = researcher_ops.check_research_receipts(path)
        assert findings == [], f"Expected no findings for multi-row receipts, got: {findings}"

    def test_missing_section_returns_critical_finding(self, tmp_path):
        """research.md with no Verification receipts section → CRITICAL finding."""
        path = _write(tmp_path, _NO_RECEIPTS_SECTION)
        findings = researcher_ops.check_research_receipts(path)
        assert findings, "Expected at least one finding when receipts section is absent"
        criticals = [f for f in findings if f["severity"] == "critical"]
        assert criticals, f"Finding must be CRITICAL, got severities: {[f['severity'] for f in findings]}"

    def test_missing_section_uses_correct_criterion(self, tmp_path):
        """Finding criterion must be 'Researcher Integrity (Phase 3)'."""
        path = _write(tmp_path, _NO_RECEIPTS_SECTION)
        findings = researcher_ops.check_research_receipts(path)
        criteria = [f["criterion"] for f in findings]
        assert "Researcher Integrity (Phase 3)" in criteria, (
            f"Expected 'Researcher Integrity (Phase 3)' criterion, got: {criteria}"
        )

    def test_empty_table_returns_finding(self, tmp_path):
        """Section exists but has no data rows (only header + separator) → finding."""
        path = _write(tmp_path, _RECEIPTS_SECTION_NO_ROWS)
        findings = researcher_ops.check_research_receipts(path)
        assert findings, "Expected a finding when receipts table has no data rows"
        criticals = [f for f in findings if f["severity"] == "critical"]
        assert criticals, "Empty receipts table finding must be CRITICAL"

    def test_no_table_at_all_returns_finding(self, tmp_path):
        """Section header present but only prose (no table) → finding."""
        path = _write(tmp_path, _RECEIPTS_SECTION_SEPARATOR_ONLY)
        findings = researcher_ops.check_research_receipts(path)
        assert findings, "Expected a finding when receipts section has no table"

    def test_finding_contains_actionable_suggestion(self, tmp_path):
        """Each finding must include a non-empty suggestion string."""
        path = _write(tmp_path, _NO_RECEIPTS_SECTION)
        findings = researcher_ops.check_research_receipts(path)
        for f in findings:
            assert f.get("suggestion"), f"Finding missing suggestion: {f}"

    def test_file_not_found_raises(self, tmp_path):
        """Passing a non-existent path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            researcher_ops.check_research_receipts(tmp_path / "no_such_file.md")

    def test_finding_format_is_complete(self, tmp_path):
        """Every finding dict must have all required keys."""
        required_keys = {"criterion", "severity", "section", "finding", "suggestion"}
        path = _write(tmp_path, _NO_RECEIPTS_SECTION)
        findings = researcher_ops.check_research_receipts(path)
        for f in findings:
            missing = required_keys - f.keys()
            assert not missing, f"Finding missing keys {missing}: {f}"


class TestCheckResearchReceiptsIntegration:
    """Validate that researcher_ops integrates with paper_pipeline's check-research."""

    def test_validate_research_compliance_pass(self, tmp_path):
        """validate_research_compliance returns (True, []) for a clean research.md."""
        path = _write(tmp_path, _VALID_RESEARCH_MD)
        ok, findings = researcher_ops.validate_research_compliance(path)
        assert ok is True
        assert findings == []

    def test_validate_research_compliance_fail(self, tmp_path):
        """validate_research_compliance returns (False, findings) when receipts missing."""
        path = _write(tmp_path, _NO_RECEIPTS_SECTION)
        ok, findings = researcher_ops.validate_research_compliance(path)
        assert ok is False
        assert findings

    def test_validate_research_compliance_missing_file(self, tmp_path):
        """validate_research_compliance raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            researcher_ops.validate_research_compliance(tmp_path / "ghost.md")
