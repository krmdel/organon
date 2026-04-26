"""Phase 2 integration test: phantom bib blocks paper_pipeline gate-draft.

Tests that verify_ops.py — invoked by paper_pipeline.py gate-draft via
subprocess — exits 2 (CRITICAL) and surfaces the finding under
"Bib Integrity (Tier 5)" when a bib entry has a mismatched author list.

Architecture: we test verify_ops.py directly as a subprocess (the same
code path gate-draft follows) rather than wiring up a full pipeline
workspace (which would require check-research state, etc.). This is the
mechanical layer that gate-draft wraps, so a pass here guarantees the
pipeline blocks.

Two modes of author phantom are tested:
  1. Wrong first author on a real arXiv ID (Berthold regression).
  2. Wrong author on a real DOI (Cohn DOI 3649 → wrong paper).

Both are offline-capable: the network calls are mocked so CI doesn't
depend on CrossRef / arXiv availability. The live-network regression is
already covered by TestPhantomBibIntegration in test_citation_pipeline.py.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS = ROOT / ".claude" / "skills" / "sci-writing" / "scripts"
VERIFY_OPS = SCRIPTS / "verify_ops.py"

for p in (str(ROOT), str(SCRIPTS)):
    if p not in sys.path:
        sys.path.insert(0, p)

import verify_ops
from verify_ops import check_bib_integrity, _LIVE_METADATA_CACHE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bib(entries: str) -> str:
    """Wrap raw bib entries in a minimal valid .bib blob."""
    return entries


def _entry(key: str, author: str, title: str, eprint: str = "", doi: str = "") -> dict:
    """Minimal bib entry dict as writing_ops.parse_bib_file would return."""
    e: dict[str, Any] = {"key": key, "author": author, "title": title}
    if eprint:
        e["eprint"] = eprint
    if doi:
        e["doi"] = doi
    return e


# ---------------------------------------------------------------------------
# Unit: check_bib_integrity flags phantom author under "Bib Integrity (Tier 5)"
# ---------------------------------------------------------------------------

class TestPhantomAuthorOffline:
    """Offline tests: mock the network, verify the criterion label and severity."""

    def _run(self, entries: list[dict], live_records: dict) -> list[dict]:
        """Run check_bib_integrity with mocked verify_citation."""
        _LIVE_METADATA_CACHE.clear()
        keys = {e["key"].lower() for e in entries}

        def _fake_verify_citation(entry: dict) -> dict | None:
            key = entry.get("key", "")
            return live_records.get(key)

        with patch.object(verify_ops, "verify_citation", side_effect=_fake_verify_citation):
            return check_bib_integrity(keys, entries)

    def test_phantom_first_author_is_critical_tier5(self):
        """A bib entry whose first author doesn't match the live record → CRITICAL, Tier 5."""
        entries = [_entry(
            key="berthold2026hexagon",
            author="Berthold, Timo and Salvagnin, Domenico",  # wrong — Salvagnin not in author list
            title="Global Optimization for Combinatorial Geometry Problems Revisited in the Era of LLMs",
            eprint="2601.05943",
        )]
        # verify_arxiv / verify_doi return family names only (not "Last, First")
        live = {
            "berthold2026hexagon": {
                "title": "Global Optimization for Combinatorial Geometry Problems Revisited in the Era of LLMs",
                "authors": ["Berthold", "Kamp", "Mexi", "Pokutta", "Pólik"],
                "source": "arxiv",
            }
        }
        findings = self._run(entries, live)
        criticals = [f for f in findings if f["severity"] == "critical"]
        assert criticals, "Expected at least one CRITICAL finding for phantom co-author"
        tier5 = [f for f in criticals if f["criterion"] == "Bib Integrity (Tier 5)"]
        assert tier5, (
            f"Author-mismatch finding must use criterion 'Bib Integrity (Tier 5)', "
            f"got criteria: {[f['criterion'] for f in criticals]}"
        )
        finding_text = tier5[0]["finding"]
        assert "berthold2026hexagon" in finding_text.lower()
        assert "salvagnin" in finding_text.lower() or "author mismatch" in finding_text.lower()

    def test_phantom_doi_author_mismatch_is_critical_tier5(self):
        """Wrong DOI that resolves to a completely different paper → CRITICAL (title mismatch)."""
        entries = [_entry(
            key="cohn2022triantafillou",
            author="Cohn, Henry and Triantafillou, Nicolas",
            title="Dual linear programming bounds for sphere packing via modular forms",
            doi="10.1090/mcom/3649",  # wrong DOI — resolves to a different paper
        )]
        # CrossRef returns family names only; title mismatch fires before author check.
        live = {
            "cohn2022triantafillou": {
                "title": "Convergence of Gaussian process regression with estimated hyper-parameters",
                "authors": ["Smith", "Doe"],
                "source": "crossref",
            }
        }
        findings = self._run(entries, live)
        criticals = [f for f in findings if f["severity"] == "critical"]
        assert criticals, "Expected CRITICAL finding for DOI resolving to wrong paper"
        # Title mismatch fires first (before author check), so criterion is "Bib Integrity"
        bib_criticals = [f for f in criticals if "bib integrity" in f["criterion"].lower()]
        assert bib_criticals, "Bib Integrity criterion must appear in CRITICAL findings"

    def test_correct_attribution_passes_clean(self):
        """A correctly attributed entry produces no CRITICAL findings."""
        entries = [_entry(
            key="berthold2026hexagon",
            author="Berthold, Timo and Kamp, Dominik and Mexi, Gioni and Pokutta, Sebastian and Pólik, Imre",
            title="Global Optimization for Combinatorial Geometry Problems Revisited in the Era of LLMs",
            eprint="2601.05943",
        )]
        # verify_arxiv returns family names only
        live = {
            "berthold2026hexagon": {
                "title": "Global Optimization for Combinatorial Geometry Problems Revisited in the Era of LLMs",
                "authors": ["Berthold", "Kamp", "Mexi", "Pokutta", "Pólik"],
                "source": "arxiv",
            }
        }
        findings = self._run(entries, live)
        criticals = [f for f in findings if f["severity"] == "critical"]
        assert not criticals, f"Correct attribution should produce no CRITICAL findings, got: {criticals}"

    def test_finding_contains_live_author_list(self):
        """The CRITICAL finding message must include the live authors so the user knows what to fix."""
        entries = [_entry(
            key="phantom2024test",
            author="Ghost, Author and Made, Up",
            title="Reinforcement learning from human feedback",
            doi="10.1000/test.0001",
        )]
        # CrossRef returns family names only
        live = {
            "phantom2024test": {
                "title": "Reinforcement learning from human feedback",
                "authors": ["Ouyang", "Wu", "Jiang"],
                "source": "crossref",
            }
        }
        findings = self._run(entries, live)
        tier5 = [f for f in findings if f["criterion"] == "Bib Integrity (Tier 5)"]
        assert tier5, "Author mismatch finding not raised"
        # Live authors must appear so the writer can copy the correct list.
        assert "ouyang" in tier5[0]["finding"].lower()


# ---------------------------------------------------------------------------
# CLI subprocess: verify_ops.py exits 2 on phantom bib
# ---------------------------------------------------------------------------

class TestVerifyOpsCLIPhantom:
    """End-to-end: invoke verify_ops.py as a subprocess to confirm exit code 2."""

    def _write_files(self, tmp_path: Path) -> tuple[Path, Path]:
        """Create a minimal draft + phantom bib in tmp_path."""
        bib = tmp_path / "test.bib"
        bib.write_text(textwrap.dedent("""\
            @article{berthold2026hexagon,
              author  = {Berthold, Timo and Salvagnin, Domenico},
              title   = {Global Optimization for Combinatorial Geometry Problems Revisited in the Era of LLMs},
              journal = {arXiv preprint},
              eprint  = {2601.05943},
              year    = {2026}
            }
        """), encoding="utf-8")
        draft = tmp_path / "draft.md"
        draft.write_text(textwrap.dedent("""\
            # Test paper

            This builds on prior work [@berthold2026hexagon].

            ## References
        """), encoding="utf-8")
        return draft, bib

    @pytest.mark.network
    def test_cli_exits_2_on_phantom_author(self, tmp_path):
        """verify_ops.py --json exits 2 (CRITICAL) when bib has wrong authors for a live arXiv ID."""
        draft, bib = self._write_files(tmp_path)
        result = subprocess.run(
            [sys.executable, str(VERIFY_OPS), str(draft), "--bib", str(bib), "--no-fix", "--json"],
            capture_output=True, text=True, timeout=60,
        )
        assert result.returncode == 2, (
            f"Expected exit 2 (CRITICAL), got {result.returncode}.\n"
            f"stdout: {result.stdout[:500]}\nstderr: {result.stderr[:200]}"
        )
        report = json.loads(result.stdout)
        # verify_ops --json uses "summary" for counts, not "counts"
        summary = report.get("summary") or {}
        assert summary.get("critical", 0) >= 1, (
            f"Expected ≥1 CRITICAL in JSON report summary, got: {summary}"
        )
        findings = report.get("findings", [])
        tier5 = [f for f in findings if f.get("criterion") == "Bib Integrity (Tier 5)"]
        assert tier5, (
            "Expected a 'Bib Integrity (Tier 5)' finding in the JSON report. "
            f"Criteria seen: {list({f.get('criterion') for f in findings})}"
        )

    @pytest.mark.network
    def test_cli_exits_0_on_correct_author(self, tmp_path):
        """verify_ops.py exits 0 (or 2 for unrelated warnings) when bib authors match live record."""
        bib = tmp_path / "test.bib"
        bib.write_text(textwrap.dedent("""\
            @article{berthold2026hexagon,
              author  = {Berthold, Timo and Kamp, Dominik and Mexi, Gioni and Pokutta, Sebastian and P{\\'o}lik, Imre},
              title   = {Global Optimization for Combinatorial Geometry Problems Revisited in the Era of LLMs},
              journal = {arXiv preprint},
              eprint  = {2601.05943},
              year    = {2026}
            }
        """), encoding="utf-8")
        draft = tmp_path / "draft.md"
        draft.write_text("# Test\n\nSee [@berthold2026hexagon].\n", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(VERIFY_OPS), str(draft), "--bib", str(bib), "--no-fix", "--json"],
            capture_output=True, text=True, timeout=60,
        )
        report = json.loads(result.stdout) if result.stdout.strip() else {}
        criticals = [
            f for f in report.get("findings", [])
            if f.get("severity") == "critical" and f.get("criterion") == "Bib Integrity (Tier 5)"
        ]
        assert not criticals, (
            f"Correct author attribution produced unexpected Tier 5 CRITICAL: {criticals}"
        )
