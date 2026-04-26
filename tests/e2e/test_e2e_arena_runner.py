"""E.7 — tool-arena-runner end-to-end tests.

Per context/memory/organon_upgrade_final_handoff.md §3.7. Confirms that the
arena-runner composition (polish + tri-verify + recon) isn't broken by
future edits to any of the three underlying pieces.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import arena_runner
from recon import recon
from tri_verify import tri_verify

SKILLS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "skills"
TEMPLATE = SKILLS_DIR / "tool-einstein-arena" / "assets" / "playbook-template.md"


# ---------------------------------------------------------------------------
# E.7.1 — recon end-to-end: PLAYBOOK + NOTES both created, header stamped
# ---------------------------------------------------------------------------

def test_e7_1_recon_end_to_end(tmp_path):
    project = tmp_path / "demo"
    out = recon(slug="demo", project_dir=project, template_path=TEMPLATE)

    playbook = project / "PLAYBOOK.md"
    notes = project / "NOTES.md"
    assert playbook.is_file()
    assert notes.is_file()
    text = playbook.read_text()
    assert text.startswith("<!-- recon-slug: demo -->"), "recon header not stamped"
    assert not out["playbook_skipped"]
    assert not out["notes_skipped"]


# ---------------------------------------------------------------------------
# E.7.2 — recon is idempotent
# ---------------------------------------------------------------------------

def test_e7_2_recon_idempotence(tmp_path, capsys):
    project = tmp_path / "demo"
    recon(slug="demo", project_dir=project, template_path=TEMPLATE)
    stamp_first = (project / "PLAYBOOK.md").stat().st_mtime

    # Second call must NOT overwrite.
    out = recon(slug="demo", project_dir=project, template_path=TEMPLATE)
    assert out["playbook_skipped"] is True
    assert out["notes_skipped"] is True
    stamp_after = (project / "PLAYBOOK.md").stat().st_mtime
    assert stamp_first == stamp_after

    # Captured warning mentions skip semantic.
    captured = capsys.readouterr()
    assert "not overwriting" in captured.err or "not overwriting" in captured.out


# ---------------------------------------------------------------------------
# E.7.3 — recon output round-trips the playbook schema
# ---------------------------------------------------------------------------

def test_e7_3_recon_schema_round_trip(tmp_path):
    import sys as _sys
    skill_tests = SKILLS_DIR / "tool-einstein-arena" / "tests"
    if str(skill_tests) not in _sys.path:
        _sys.path.insert(0, str(skill_tests))
    from test_playbook_structure import EXPECTED_SECTIONS, _parse_sections

    project = tmp_path / "demo"
    recon(slug="demo", project_dir=project, template_path=TEMPLATE)
    md = (project / "PLAYBOOK.md").read_text()

    # Section order preserved despite the prepended recon-slug header.
    assert _parse_sections(md) == EXPECTED_SECTIONS


# ---------------------------------------------------------------------------
# E.7.4 — polish dispatch invokes ops-ulp-polish/scripts/polish.py
# ---------------------------------------------------------------------------

def test_e7_4_polish_dispatches_to_ops_ulp_polish(tmp_path):
    """Confirm arena_runner.cmd_polish calls subprocess.run with the real
    polish.py script path from ops-ulp-polish. We stub subprocess.run to
    avoid actually executing a 3600s polish."""
    project = tmp_path / "proj"
    (project / "solutions").mkdir(parents=True)
    # minimal warm-start
    import numpy as np
    np.save(project / "solutions" / "best.npy", np.zeros(3))
    (project / "solutions" / "best.json").write_text('{"vectors": [[1.0]]}')

    captured = {}

    def fake_run(cmd, cwd=None, **kwargs):
        captured["cmd"] = list(cmd)
        captured["cwd"] = cwd

        class _R:
            returncode = 0
        return _R()

    with patch("arena_runner.subprocess.run", side_effect=fake_run):
        rc = arena_runner.cmd_polish([
            "--project-dir", str(project),
            "--evaluator", "fakemod:eval_fn",
            "--budget-sec", "5",
        ])
    assert rc == 0
    assert any("polish.py" in part for part in captured["cmd"]), captured
    assert "ops-ulp-polish" in " ".join(captured["cmd"])
    assert "--evaluator" in captured["cmd"]
    assert "fakemod:eval_fn" in captured["cmd"]


# ---------------------------------------------------------------------------
# E.7.5 — polish errors on missing warm-start with non-zero exit
# ---------------------------------------------------------------------------

def test_e7_5_polish_missing_warm_start(tmp_path, capsys):
    project = tmp_path / "empty-proj"
    project.mkdir()
    rc = arena_runner.cmd_polish([
        "--project-dir", str(project),
        "--evaluator", "fakemod:eval_fn",
    ])
    assert rc == 2
    err = capsys.readouterr().err
    assert "warm-start file not found" in err


# ---------------------------------------------------------------------------
# E.7.6 — tri-verify disagree (3 verifiers, 2 agree, 1 dissents)
# ---------------------------------------------------------------------------

def test_e7_6_tri_verify_disagree():
    result = tri_verify(
        lambda: 0.10000,
        lambda: 0.10001,
        lambda: 0.20000,
        tolerance=1e-3,
    )
    assert result["status"] == "disagree"
    assert result["methods_run"] == 3
    assert result["methods_agree"] == 2
    assert "best_cluster_score" in result


# ---------------------------------------------------------------------------
# E.7.7 — tri-verify all-agree (3 verifiers within tolerance)
# ---------------------------------------------------------------------------

def test_e7_7_tri_verify_all_agree():
    result = tri_verify(
        lambda: 0.10000,
        lambda: 0.10001,
        lambda: 0.10002,
        tolerance=1e-3,
    )
    assert result["status"] == "pass"
    assert result["methods_run"] == 3
    assert result["methods_agree"] == 3
    assert "consensus_score" in result
    assert abs(result["consensus_score"] - 0.10001) < 1e-5


# ---------------------------------------------------------------------------
# E.7.8 — tri-verify 2-method mode (mpmath_fn=None)
# ---------------------------------------------------------------------------

def test_e7_8_tri_verify_two_method_mode():
    result = tri_verify(
        lambda: 0.5,
        None,
        lambda: 0.5000001,
        tolerance=1e-4,
    )
    assert result["status"] == "pass"
    assert result["methods_run"] == 2
    assert result["methods_agree"] == 2


# ---------------------------------------------------------------------------
# E.7.9 — unknown subcommand exits with error
# ---------------------------------------------------------------------------

def test_e7_9_unknown_subcommand():
    with pytest.raises(SystemExit) as exc_info:
        arena_runner.run("not-a-subcommand", [])
    assert exc_info.value.code == 2


# ---------------------------------------------------------------------------
# E.7.10 — --help exits 0 and mentions all three subcommands
# ---------------------------------------------------------------------------

def test_e7_10_help_mentions_all_subcommands():
    script = SKILLS_DIR / "tool-arena-runner" / "scripts" / "arena_runner.py"
    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0
    out = result.stdout + result.stderr
    for sub in ("polish", "tri-verify", "recon"):
        assert sub in out, f"--help missing {sub!r} in output"
