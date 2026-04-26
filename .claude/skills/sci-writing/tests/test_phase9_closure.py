"""test_phase9_closure.py — Phase 9 trust-floor regressions.

Phase 9 closes the residual bypass set surfaced by the post-Phase-8 audit:

  B7  — parse_receipts_table silently [] on column-keyword mismatch
        → check_research_receipts emits CRITICAL when raw data rows exist
          but the parser cannot extract any structured row.
  DP3 — substack bypass ledger entries lacked manuscript md5
        → _safe_md5 helper computes the hex digest, all bypass paths log it.
  WG2 — auditor_pipeline.cmd_gate used a loose `"[@" in text` substring
        → replaced with verify_ops.BROAD_MARKER_RE so the gate's
          precondition and the verifier's detection agree on what counts.
  B1  — NotebookEdit was not in the PreToolUse matcher
        → settings.json now matches NotebookEdit; verify_gate.py refuses
          notebooks in watched workspaces (sibling-bib or primary prefix).
  WG3 fixture regression — bib_sweep walked tests/fixtures/*.bib
        → find_bib_files now excludes the test-fixture directory so the
          cron + CI sweep no longer fails on intentionally-malformed inputs.

These tests pin the contract. If a future change reverts any of the above,
the corresponding regression fires.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[4]
SCI_WRITING_SCRIPTS = REPO_ROOT / ".claude" / "skills" / "sci-writing" / "scripts"
SUBSTACK_SCRIPTS = REPO_ROOT / ".claude" / "skills" / "tool-substack" / "scripts"
HOOKS_INFO = REPO_ROOT / ".claude" / "hooks_info"
REPO_SCRIPTS = REPO_ROOT / "scripts"

for p in (SCI_WRITING_SCRIPTS, SUBSTACK_SCRIPTS, HOOKS_INFO, REPO_SCRIPTS, REPO_ROOT):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)


# ===========================================================================
# B7 — parse_receipts_table CRITICAL on parse failure
# ===========================================================================


class TestB7ReceiptsParseFailureCritical:
    """Raw `| N |` data rows that the parser cannot map to known column
    keywords used to fall through to an empty `cross_reference_receipts`
    no-op. Phase 9 surfaces a CRITICAL so the gate refuses to advance."""

    def _research_md(self, body: str) -> str:
        return (
            "# Research notes\n\n"
            "Some prose.\n\n"
            "## Verification receipts\n\n"
            f"{body}\n"
        )

    def test_unparseable_columns_with_data_rows_emits_critical(self, tmp_path):
        from researcher_ops import check_research_receipts

        # Headers do not match any keyword (entry/api/title/author/doi).
        # The data row has the `| N |` shape, so the section + row checks
        # pass, but parse_receipts_table cannot map columns → returns [].
        body = (
            "| Foo | Bar | Baz |\n"
            "|-----|-----|-----|\n"
            "| 1   | x   | y   |\n"
        )
        md = tmp_path / "research.md"
        md.write_text(self._research_md(body), encoding="utf-8")

        findings = check_research_receipts(md)
        assert findings, "Phase 9 must surface a CRITICAL on unparseable columns"
        assert findings[0]["severity"] == "critical"
        assert "unparseable" in findings[0]["finding"].lower() \
            or "zero structured rows" in findings[0]["finding"].lower()

    def test_recognised_columns_with_data_rows_passes(self, tmp_path):
        from researcher_ops import check_research_receipts

        body = (
            "| # | API source | Title | First author | DOI |\n"
            "|---|------------|-------|--------------|-----|\n"
            "| 1 | paper-search | Real Title | Smith | 10.1234/abc |\n"
        )
        md = tmp_path / "research.md"
        md.write_text(self._research_md(body), encoding="utf-8")

        findings = check_research_receipts(md)
        assert findings == [], "well-formed receipts table must not flag"


# ===========================================================================
# WG2 — auditor_pipeline marker check aligned with verify_ops
# ===========================================================================


class TestWG2MarkerAlignment:
    """A loose `"[@" in text` substring would refuse a sci-communication
    draft for a literal `[@` in code, while verify_ops would not flag it.
    Phase 9 binds the patterns: auditor_pipeline._BROAD_MARKER_RE matches
    iff verify_ops.BROAD_MARKER_RE matches."""

    def test_patterns_agree_on_valid_marker(self):
        from auditor_pipeline import _BROAD_MARKER_RE as auditor_re
        from verify_ops import BROAD_MARKER_RE as verify_re

        text = "Per recent work [@smith2024], the result holds."
        assert bool(auditor_re.search(text)) is bool(verify_re.search(text))
        assert auditor_re.search(text) is not None

    def test_patterns_agree_on_literal_at_without_key_letter(self):
        from auditor_pipeline import _BROAD_MARKER_RE as auditor_re
        from verify_ops import BROAD_MARKER_RE as verify_re

        # `[@` followed by a digit or punctuation — neither pattern fires,
        # but the loose `"[@" in text` substring used to. Regression of
        # WG2's stated benefit: cosmetic divergence between gate
        # precondition and verifier detection is closed.
        text = "Pseudocode: arr[@0] = 1; M[@:].sum(); v[@1+2]"
        assert auditor_re.search(text) is None
        assert verify_re.search(text) is None
        # Sanity: the loose pre-Phase-9 substring would have fired.
        assert "[@" in text

    def test_patterns_agree_on_pandoc_locator(self):
        from auditor_pipeline import _BROAD_MARKER_RE as auditor_re
        from verify_ops import BROAD_MARKER_RE as verify_re

        text = "See [@smith2024, p. 5] for the lemma."
        assert auditor_re.search(text) is not None
        assert verify_re.search(text) is not None


# ===========================================================================
# DP3 — substack bypass ledger entries include md5
# ===========================================================================


_SUBSTACK_OPS_PATH = REPO_ROOT / ".claude/skills/tool-substack/scripts/substack_ops.py"


@pytest.mark.skipif(
    not _SUBSTACK_OPS_PATH.exists(),
    reason="tool-substack is gitignored from the public repo; "
    "the DP3 hash-coverage contract only runs on local installs that "
    "re-enable the skill.",
)
class TestDP3SubstackHashCoverage:
    """Pre-Phase-9, only clean push/edit ledger writes carried `md5`. The
    ungated_bypass, --no-verify, and refused entries did not, so a forensic
    audit could not correlate a bypass row to the manuscript bytes.

    substack_ops.py hard-imports markdown-it-py at module load (sys.exit on
    failure), so on a stripped CI env the module isn't directly importable.
    The tests below stay defensive: we (a) static-grep the source for the
    helper + bypass call sites, and (b) only exercise _safe_md5 live when
    the publish dependency tree is available.
    """

    SUBSTACK_OPS_PATH = _SUBSTACK_OPS_PATH

    def test_safe_md5_helper_defined(self):
        text = self.SUBSTACK_OPS_PATH.read_text(encoding="utf-8")
        assert "def _safe_md5(" in text, (
            "_safe_md5 helper missing — Phase 9 DP3 contract dropped"
        )
        assert "hashlib.md5(path.read_bytes()).hexdigest()" in text, (
            "_safe_md5 must compute manuscript bytes md5 hex digest"
        )

    def test_all_bypass_ledger_writes_include_md5(self):
        """Static-grep regression: every _write_ledger call inside the
        --no-verify / refused / ungated_bypass branches in substack_ops.py
        must include an `md5` key. Five bypass paths total
        (_run_verify_gate ungated, cmd_push --no-verify, cmd_push refused,
        cmd_edit --no-verify, cmd_edit refused) plus two clean-path
        hashlib.md5 calls in cmd_push and cmd_edit success branches."""
        text = self.SUBSTACK_OPS_PATH.read_text(encoding="utf-8")
        bypass_indicators = (
            '"override": "--no-verify"',
            '"override": "refused"',
            '"outcome": "ungated_bypass"',
        )
        for indicator in bypass_indicators:
            assert indicator in text, f"expected bypass shape '{indicator}' missing"
        assert text.count("_safe_md5(") >= 5, (
            "expected ≥5 _safe_md5 call sites across the bypass paths"
        )
        assert text.count("hashlib.md5(") >= 2, (
            "expected ≥2 direct hashlib.md5 calls on the clean-push paths"
        )

    def test_safe_md5_live_when_deps_available(self, tmp_path):
        """Live call when markdown_it is installed; skip otherwise."""
        pytest.importorskip("markdown_it")
        # requests is also a hard dep of substack_ops at import time.
        pytest.importorskip("requests")
        from substack_ops import _safe_md5

        path = tmp_path / "manuscript.md"
        path.write_text("# Hello world\n\nThis is the body.\n", encoding="utf-8")
        digest = _safe_md5(path)
        assert isinstance(digest, str) and len(digest) == 32
        # OSError path: missing file returns empty digest, not an exception.
        assert _safe_md5(tmp_path / "missing.md") == ""


# ===========================================================================
# B1 — NotebookEdit gate
# ===========================================================================


class TestB1NotebookEditGate:
    """Pre-Phase-9 the PreToolUse matcher was Write|Edit|MultiEdit only,
    so a writer could route around the citation gate by burying claims in
    a notebook cell. Phase 9 adds NotebookEdit to the matcher; the hook
    refuses NotebookEdit in any watched workspace."""

    def test_settings_matcher_includes_notebookedit(self):
        settings = json.loads((REPO_ROOT / ".claude/settings.json").read_text())
        hooks = settings.get("hooks", {})
        pretooluse = hooks.get("PreToolUse", [])
        matchers = [h.get("matcher", "") for h in pretooluse]
        assert any("NotebookEdit" in m for m in matchers), (
            "PreToolUse matcher must include NotebookEdit"
        )

    def test_is_watched_notebook_true_for_workspace_ipynb(self, tmp_path, monkeypatch):
        import importlib
        import verify_gate
        importlib.reload(verify_gate)

        # Build a fake watched workspace under projects/briefs/.
        ws = tmp_path / "projects" / "briefs" / "demo"
        ws.mkdir(parents=True)
        nb = ws / "notes.ipynb"
        nb.write_text(json.dumps({"cells": []}), encoding="utf-8")

        monkeypatch.setattr(verify_gate, "PROJECT_ROOT", tmp_path)
        assert verify_gate._is_watched_notebook(nb) is True

    def test_is_watched_notebook_true_for_sibling_bib(self, tmp_path, monkeypatch):
        import importlib
        import verify_gate
        importlib.reload(verify_gate)

        ws = tmp_path / "papers" / "2026" / "demo"
        ws.mkdir(parents=True)
        nb = ws / "scratch.ipynb"
        nb.write_text(json.dumps({"cells": []}), encoding="utf-8")
        (ws / "demo.bib").write_text("@article{x, title={t}}", encoding="utf-8")

        monkeypatch.setattr(verify_gate, "PROJECT_ROOT", tmp_path)
        assert verify_gate._is_watched_notebook(nb) is True

    def test_is_watched_notebook_false_for_unrelated_ipynb(self, tmp_path, monkeypatch):
        import importlib
        import verify_gate
        importlib.reload(verify_gate)

        ws = tmp_path / "scratchpad"
        ws.mkdir()
        nb = ws / "free.ipynb"
        nb.write_text(json.dumps({"cells": []}), encoding="utf-8")

        monkeypatch.setattr(verify_gate, "PROJECT_ROOT", tmp_path)
        assert verify_gate._is_watched_notebook(nb) is False

    def test_extract_path_handles_notebook_path(self):
        import verify_gate

        event = {
            "tool_name": "NotebookEdit",
            "tool_input": {"notebook_path": "/abs/path/x.ipynb"},
        }
        assert verify_gate._extract_path(event) == "/abs/path/x.ipynb"


# ===========================================================================
# WG3 fixture regression — bib_sweep skips test fixtures
# ===========================================================================


class TestBibSweepFixtureExclusion:
    """Phase 9 broadened bib_sweep to walk the whole repo; a regression
    surfaced because tests/fixtures/*.bib are intentionally malformed
    inputs that always trip A1 CRITICAL. find_bib_files now excludes
    them so the cron + CI sweep stays green on a clean checkout."""

    def test_find_bib_files_excludes_tests_fixtures(self):
        import bib_sweep

        # Confirm the malformed fixture exists in-repo (sanity).
        malformed = REPO_ROOT / "tests" / "fixtures" / "malformed.bib"
        assert malformed.exists(), (
            "test fixture moved or deleted — update the test path"
        )
        # find_bib_files must not return any path under tests/fixtures.
        found = bib_sweep.find_bib_files()
        for path in found:
            parts = set(path.parts)
            assert not ("tests" in parts and "fixtures" in parts), (
                f"bib_sweep included a test fixture: {path}"
            )
