"""test_publish_gates.py — offline tests for Tier-E publish gates (E1, E4).

Tests verify that:
  - substack_ops.cmd_push / cmd_edit block on CRITICAL citations and allow
    --no-verify bypass (logged to ledger)
  - export-md._run_export_gate blocks on CRITICAL and respects --force
  - Pure-expertise drafts (no [@Key], no .bib) pass both gates cleanly
  - Missing .bib alongside [@Key] markers is treated as blocked (VerificationError)
"""
from __future__ import annotations

import importlib
import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers to locate scripts without running them as __main__
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[4]
SUBSTACK_SCRIPT = (
    REPO_ROOT / ".claude" / "skills" / "tool-substack" / "scripts" / "substack_ops.py"
)
EXPORT_SCRIPT = REPO_ROOT / "scripts" / "export-md.py"


def _stub_module(name: str, **attrs) -> types.ModuleType:
    """Create a lightweight stub module and insert it into sys.modules."""
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m


def _load_module(path: Path, name: str):
    """Import a script file as a module without executing __main__.

    Stubs out optional heavy deps (requests, markdown_it) so the module
    loads cleanly in a bare test environment.
    """
    # Stub requests so the module-level import guard doesn't sys.exit
    if "requests" not in sys.modules:
        req_stub = _stub_module("requests")
        req_stub.Session = MagicMock
        req_stub.RequestException = Exception
    # Stub markdown_it so substack_ops doesn't sys.exit on missing dep
    if "markdown_it" not in sys.modules:
        mi_stub = _stub_module("markdown_it")
        mi_stub.MarkdownIt = MagicMock
        token_stub = _stub_module("markdown_it.token")
        token_stub.Token = MagicMock

    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    with patch.dict("os.environ", {
        "SUBSTACK_PUBLICATION_URL": "https://example.substack.com",
        "SUBSTACK_SESSION_TOKEN": "test-token",
        "SUBSTACK_USER_ID": "12345",
    }):
        spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def substack_mod():
    if not SUBSTACK_SCRIPT.exists():
        pytest.skip("substack_ops.py not found")
    return _load_module(SUBSTACK_SCRIPT, "substack_ops_test")


@pytest.fixture(scope="module")
def export_mod():
    if not EXPORT_SCRIPT.exists():
        pytest.skip("export-md.py not found")
    return _load_module(EXPORT_SCRIPT, "export_md_test")


@pytest.fixture()
def tmp_draft(tmp_path):
    """A markdown draft with [@Key] markers but no .bib (triggers VerificationError)."""
    md = tmp_path / "draft.md"
    md.write_text(
        "---\ntitle: Test Draft\n---\n\nSome claim [@smith2023].\n",
        encoding="utf-8",
    )
    return md


@pytest.fixture()
def tmp_draft_no_cite(tmp_path):
    """A pure-expertise markdown with no [@Key] markers and no .bib."""
    md = tmp_path / "pure.md"
    md.write_text(
        "---\ntitle: Pure Expertise\n---\n\nNo citations here.\n",
        encoding="utf-8",
    )
    return md


@pytest.fixture()
def tmp_draft_with_bib_clean(tmp_path):
    """Draft + .bib that produces no CRITICAL findings (mocked gate returns clean)."""
    md = tmp_path / "clean.md"
    md.write_text(
        "---\ntitle: Clean Draft\n---\n\nSome claim [@jones2020].\n",
        encoding="utf-8",
    )
    bib = tmp_path / "clean.bib"
    bib.write_text(
        "@article{jones2020, author={Jones, A}, title={Real Title}, "
        "doi={10.1234/real}, year={2020}}\n",
        encoding="utf-8",
    )
    return md


@pytest.fixture()
def tmp_draft_with_bib_critical(tmp_path):
    """Draft + .bib that the mocked gate reports as CRITICAL."""
    md = tmp_path / "tainted.md"
    md.write_text(
        "---\ntitle: Tainted Draft\n---\n\nFabricated claim [@phantom2023].\n",
        encoding="utf-8",
    )
    bib = tmp_path / "tainted.bib"
    bib.write_text(
        "@article{phantom2023, author={Ghost, A}, title={Fake Title}, "
        "doi={10.9999/fake}, year={2023}}\n",
        encoding="utf-8",
    )
    return md


# ---------------------------------------------------------------------------
# _run_verify_gate (substack) — unit tests with mocked verify_ops
# ---------------------------------------------------------------------------

class TestSubstackGate:

    def test_pure_expertise_passes_without_bib(self, substack_mod, tmp_draft_no_cite):
        """No markers, no .bib → gate not triggered → (False, '')."""
        blocked, summary = substack_mod._run_verify_gate(tmp_draft_no_cite)
        assert not blocked
        assert summary == ""

    def test_missing_bib_with_markers_is_blocked(self, substack_mod, tmp_draft):
        """[@Key] markers but no .bib → VerificationError → blocked=True."""
        # verify_ops.VerificationError is raised; gate catches it and returns blocked
        with patch.dict(sys.modules, {}):
            # Ensure verify_ops is importable with VerificationError behaviour
            fake_vo = types.ModuleType("verify_ops")

            class FakeVerificationError(ValueError):
                pass

            def fake_run_verification(**kwargs):
                raise FakeVerificationError("no bib found")

            fake_vo.run_verification = fake_run_verification
            fake_vo.VerificationError = FakeVerificationError

            sci_scripts = str(
                REPO_ROOT / ".claude" / "skills" / "sci-writing" / "scripts"
            )
            with patch.dict(sys.modules, {"verify_ops": fake_vo}):
                # Temporarily inject the module into the path
                if sci_scripts not in sys.path:
                    sys.path.insert(0, sci_scripts)
                blocked, summary = substack_mod._run_verify_gate(tmp_draft)
        assert blocked

    def test_clean_bib_passes(self, substack_mod, tmp_draft_with_bib_clean):
        """Gate returns not-blocked when no CRITICAL findings."""
        fake_result = {
            "blocked": False,
            "findings": [],
            "summary": {"critical": 0, "major": 1, "info": 0},
        }
        fake_vo = types.ModuleType("verify_ops")

        class FakeVerificationError(ValueError):
            pass

        fake_vo.run_verification = MagicMock(return_value=fake_result)
        fake_vo.VerificationError = FakeVerificationError

        with patch.dict(sys.modules, {"verify_ops": fake_vo}):
            blocked, summary = substack_mod._run_verify_gate(tmp_draft_with_bib_clean)

        assert not blocked
        assert "CRITICAL=0" in summary

    def test_critical_bib_is_blocked(self, substack_mod, tmp_draft_with_bib_critical):
        """Gate returns blocked=True when CRITICAL findings exist."""
        fake_finding = {
            "criterion": "Bib Integrity",
            "severity": "critical",
            "finding": "Title mismatch for phantom2023",
            "suggestion": "Fix the citation",
            "section": "References",
        }
        fake_result = {
            "blocked": True,
            "findings": [fake_finding],
            "summary": {"critical": 1, "major": 0, "info": 0},
        }
        fake_vo = types.ModuleType("verify_ops")

        class FakeVerificationError(ValueError):
            pass

        fake_vo.run_verification = MagicMock(return_value=fake_result)
        fake_vo.VerificationError = FakeVerificationError

        with patch.dict(sys.modules, {"verify_ops": fake_vo}):
            blocked, summary = substack_mod._run_verify_gate(tmp_draft_with_bib_critical)

        assert blocked
        assert "CRITICAL=1" in summary

    def test_verify_ops_unavailable_blocks_by_default(
        self, substack_mod, tmp_draft_with_bib_critical, capsys, monkeypatch
    ):
        """Phase 8: an unavailable verify_ops fails closed — push refused."""
        monkeypatch.delenv("SCI_OS_ALLOW_UNGATED", raising=False)
        with patch.dict(sys.modules, {"verify_ops": None}):
            blocked, summary = substack_mod._run_verify_gate(tmp_draft_with_bib_critical)
        assert blocked
        assert "verify_ops_unavailable" in summary
        captured = capsys.readouterr()
        assert "BLOCKED" in captured.err

    def test_verify_ops_unavailable_bypass_via_env(
        self, substack_mod, tmp_draft_with_bib_critical, monkeypatch, tmp_path
    ):
        """Phase 8: SCI_OS_ALLOW_UNGATED=1 lets the push through, ledger logged."""
        ledger = tmp_path / "ledger.jsonl"
        monkeypatch.setattr(substack_mod, "LEDGER_PATH", ledger)
        monkeypatch.setenv("SCI_OS_ALLOW_UNGATED", "1")
        with patch.dict(sys.modules, {"verify_ops": None}):
            blocked, summary = substack_mod._run_verify_gate(tmp_draft_with_bib_critical)
        assert not blocked
        assert summary == "ungated_bypass"
        assert ledger.exists()
        record = json.loads(ledger.read_text().strip())
        assert record["outcome"] == "ungated_bypass"


# ---------------------------------------------------------------------------
# cmd_push — integration tests with mocked gate + network
# ---------------------------------------------------------------------------

class TestCmdPush:

    def test_push_blocked_without_no_verify(
        self, substack_mod, tmp_draft_with_bib_critical, tmp_path
    ):
        """cmd_push returns 1 when gate is blocked and --no-verify not set."""
        ledger = tmp_path / "ledger.jsonl"
        with (
            patch.object(substack_mod, "_run_verify_gate", return_value=(True, "CRITICAL=1")),
            patch.object(substack_mod, "LEDGER_PATH", ledger),
        ):
            rc = substack_mod.cmd_push(str(tmp_draft_with_bib_critical), no_verify=False)
        assert rc == 1
        assert ledger.exists()
        entry = json.loads(ledger.read_text().strip())
        assert entry["override"] == "refused"

    def test_push_no_verify_bypasses_and_logs(
        self, substack_mod, tmp_draft_with_bib_critical, tmp_path
    ):
        """cmd_push with --no-verify bypasses gate and logs to ledger."""
        ledger = tmp_path / "ledger.jsonl"
        # Mock everything after the gate check so we don't hit the network
        with (
            patch.object(substack_mod, "_run_verify_gate", return_value=(True, "CRITICAL=1")),
            patch.object(substack_mod, "LEDGER_PATH", ledger),
            patch.object(substack_mod, "_require_credentials"),
            patch.object(substack_mod, "preprocess_mermaid", side_effect=lambda b, **kw: b),
            patch.object(substack_mod, "PMConverter") as MockConv,
            patch.object(substack_mod, "_session") as MockSess,
        ):
            MockConv.return_value.convert.return_value = {"type": "doc", "content": []}
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"id": 999}
            MockSess.return_value.post.return_value = mock_resp
            rc = substack_mod.cmd_push(
                str(tmp_draft_with_bib_critical), no_verify=True
            )
        assert rc == 0
        lines = [l for l in ledger.read_text().strip().splitlines() if l]
        assert any(json.loads(l)["override"] == "--no-verify" for l in lines)

    def test_push_clean_draft_succeeds(
        self, substack_mod, tmp_draft_with_bib_clean, tmp_path
    ):
        """cmd_push with clean gate succeeds and logs 'clean' to ledger."""
        ledger = tmp_path / "ledger.jsonl"
        with (
            patch.object(substack_mod, "_run_verify_gate", return_value=(False, "CRITICAL=0 MAJOR=0 INFO=0")),
            patch.object(substack_mod, "LEDGER_PATH", ledger),
            patch.object(substack_mod, "_require_credentials"),
            patch.object(substack_mod, "preprocess_mermaid", side_effect=lambda b, **kw: b),
            patch.object(substack_mod, "PMConverter") as MockConv,
            patch.object(substack_mod, "_session") as MockSess,
        ):
            MockConv.return_value.convert.return_value = {"type": "doc", "content": []}
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"id": 42}
            MockSess.return_value.post.return_value = mock_resp
            rc = substack_mod.cmd_push(str(tmp_draft_with_bib_clean), no_verify=False)
        assert rc == 0
        entry = json.loads(ledger.read_text().strip().splitlines()[-1])
        assert entry["override"] == "clean"
        assert entry["draft_id"] == "42"

    def test_push_pure_expertise_skips_gate(
        self, substack_mod, tmp_draft_no_cite, tmp_path
    ):
        """cmd_push on a pure-expertise draft calls gate but it returns clean."""
        ledger = tmp_path / "ledger.jsonl"
        with (
            patch.object(substack_mod, "LEDGER_PATH", ledger),
            patch.object(substack_mod, "_require_credentials"),
            patch.object(substack_mod, "preprocess_mermaid", side_effect=lambda b, **kw: b),
            patch.object(substack_mod, "PMConverter") as MockConv,
            patch.object(substack_mod, "_session") as MockSess,
        ):
            MockConv.return_value.convert.return_value = {"type": "doc", "content": []}
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"id": 77}
            MockSess.return_value.post.return_value = mock_resp
            rc = substack_mod.cmd_push(str(tmp_draft_no_cite), no_verify=False)
        assert rc == 0


# ---------------------------------------------------------------------------
# cmd_edit — mirrors cmd_push gate behaviour
# ---------------------------------------------------------------------------

class TestCmdEdit:

    def test_edit_blocked_without_no_verify(
        self, substack_mod, tmp_draft_with_bib_critical, tmp_path
    ):
        ledger = tmp_path / "ledger.jsonl"
        with (
            patch.object(substack_mod, "_run_verify_gate", return_value=(True, "CRITICAL=1")),
            patch.object(substack_mod, "LEDGER_PATH", ledger),
        ):
            rc = substack_mod.cmd_edit("123", str(tmp_draft_with_bib_critical), no_verify=False)
        assert rc == 1
        entry = json.loads(ledger.read_text().strip())
        assert entry["draft_id"] == "123"
        assert entry["override"] == "refused"

    def test_edit_no_verify_bypasses_and_logs(
        self, substack_mod, tmp_draft_with_bib_critical, tmp_path
    ):
        ledger = tmp_path / "ledger.jsonl"
        with (
            patch.object(substack_mod, "_run_verify_gate", return_value=(True, "CRITICAL=1")),
            patch.object(substack_mod, "LEDGER_PATH", ledger),
            patch.object(substack_mod, "_require_credentials"),
            patch.object(substack_mod, "preprocess_mermaid", side_effect=lambda b, **kw: b),
            patch.object(substack_mod, "PMConverter") as MockConv,
            patch.object(substack_mod, "_session") as MockSess,
        ):
            MockConv.return_value.convert.return_value = {"type": "doc", "content": []}
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            MockSess.return_value.put.return_value = mock_resp
            rc = substack_mod.cmd_edit(
                "123", str(tmp_draft_with_bib_critical), no_verify=True
            )
        assert rc == 0
        lines = [l for l in ledger.read_text().strip().splitlines() if l]
        assert any(json.loads(l)["override"] == "--no-verify" for l in lines)


# ---------------------------------------------------------------------------
# _run_export_gate (export-md) — unit tests
# ---------------------------------------------------------------------------

class TestExportGate:

    def test_pure_expertise_passes(self, export_mod, tmp_draft_no_cite):
        blocked, summary = export_mod._run_export_gate(tmp_draft_no_cite)
        assert not blocked
        assert summary == ""

    def test_clean_bib_passes(self, export_mod, tmp_draft_with_bib_clean):
        fake_result = {
            "blocked": False,
            "findings": [],
            "summary": {"critical": 0, "major": 0, "info": 0},
        }
        fake_vo = types.ModuleType("verify_ops")

        class FakeVE(ValueError):
            pass

        fake_vo.run_verification = MagicMock(return_value=fake_result)
        fake_vo.VerificationError = FakeVE

        with patch.dict(sys.modules, {"verify_ops": fake_vo}):
            blocked, summary = export_mod._run_export_gate(tmp_draft_with_bib_clean)

        assert not blocked

    def test_critical_bib_is_blocked(self, export_mod, tmp_draft_with_bib_critical):
        fake_result = {
            "blocked": True,
            "findings": [{"criterion": "Bib", "severity": "critical",
                          "finding": "phantom", "suggestion": "", "section": ""}],
            "summary": {"critical": 1, "major": 0, "info": 0},
        }
        fake_vo = types.ModuleType("verify_ops")

        class FakeVE(ValueError):
            pass

        fake_vo.run_verification = MagicMock(return_value=fake_result)
        fake_vo.VerificationError = FakeVE

        with patch.dict(sys.modules, {"verify_ops": fake_vo}):
            blocked, summary = export_mod._run_export_gate(tmp_draft_with_bib_critical)

        assert blocked
        assert "CRITICAL=1" in summary

    def test_verify_ops_unavailable_blocks_by_default(
        self, export_mod, tmp_draft_with_bib_critical, monkeypatch
    ):
        """Phase 8: an unavailable verify_ops fails closed — export refused."""
        monkeypatch.delenv("SCI_OS_ALLOW_UNGATED", raising=False)
        with patch.dict(sys.modules, {"verify_ops": None}):
            blocked, summary = export_mod._run_export_gate(tmp_draft_with_bib_critical)
        assert blocked
        assert summary == "verify_ops_unavailable"

    def test_verify_ops_unavailable_bypass_via_env(
        self, export_mod, tmp_draft_with_bib_critical, monkeypatch, tmp_path
    ):
        """Phase 8: SCI_OS_ALLOW_UNGATED=1 lets the export through, ledger logged."""
        ledger = tmp_path / "export_ledger.jsonl"
        monkeypatch.setattr(export_mod, "_EXPORT_LEDGER", ledger)
        monkeypatch.setenv("SCI_OS_ALLOW_UNGATED", "1")
        with patch.dict(sys.modules, {"verify_ops": None}):
            blocked, summary = export_mod._run_export_gate(tmp_draft_with_bib_critical)
        assert not blocked
        assert summary == "ungated_bypass"
        assert ledger.exists()
        record = json.loads(ledger.read_text().strip())
        assert record["outcome"] == "ungated_bypass"


# ---------------------------------------------------------------------------
# main() --force flag integration (export-md)
# ---------------------------------------------------------------------------

class TestExportMainForce:

    def test_blocked_without_force_returns_1(
        self, export_mod, tmp_draft_with_bib_critical, tmp_path, monkeypatch
    ):
        ledger = tmp_path / "export_ledger.jsonl"
        monkeypatch.setattr(export_mod, "_EXPORT_LEDGER", ledger)
        monkeypatch.setattr(
            export_mod, "_run_export_gate", lambda p: (True, "CRITICAL=1")
        )
        monkeypatch.setattr(sys, "argv", ["export-md.py", str(tmp_draft_with_bib_critical)])
        rc = export_mod.main()
        assert rc == 1
        entry = json.loads(ledger.read_text().strip())
        assert entry["override"] == "refused"

    def test_blocked_with_force_calls_export(
        self, export_mod, tmp_draft_with_bib_critical, tmp_path, monkeypatch
    ):
        ledger = tmp_path / "export_ledger.jsonl"
        monkeypatch.setattr(export_mod, "_EXPORT_LEDGER", ledger)
        monkeypatch.setattr(
            export_mod, "_run_export_gate", lambda p: (True, "CRITICAL=1")
        )
        dummy_out = tmp_path / "tainted.docx"
        dummy_out.write_bytes(b"FAKE")
        monkeypatch.setattr(
            export_mod, "export", lambda *a, **kw: {"docx": dummy_out}
        )
        monkeypatch.setattr(
            sys, "argv",
            ["export-md.py", str(tmp_draft_with_bib_critical), "--force"],
        )
        rc = export_mod.main()
        assert rc == 0
        lines = [l for l in ledger.read_text().strip().splitlines() if l]
        assert any(json.loads(l)["override"] == "--force" for l in lines)

    def test_clean_draft_exports_without_ledger_entry(
        self, export_mod, tmp_draft_with_bib_clean, tmp_path, monkeypatch
    ):
        ledger = tmp_path / "export_ledger.jsonl"
        monkeypatch.setattr(export_mod, "_EXPORT_LEDGER", ledger)
        monkeypatch.setattr(
            export_mod, "_run_export_gate", lambda p: (False, "CRITICAL=0 MAJOR=0 INFO=0")
        )
        dummy_out = tmp_path / "clean.docx"
        dummy_out.write_bytes(b"FAKE")
        monkeypatch.setattr(
            export_mod, "export", lambda *a, **kw: {"docx": dummy_out}
        )
        monkeypatch.setattr(
            sys, "argv", ["export-md.py", str(tmp_draft_with_bib_clean)]
        )
        rc = export_mod.main()
        assert rc == 0
        # No ledger entry expected for clean run
        assert not ledger.exists()
