"""Tests for tool-arena-runner.

TDD suite covering subcommand dispatch, tri-verify, recon, and CLI entry.
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


# Resolve script paths relative to this test file so the tests are independent
# of cwd.
SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_DIR / "scripts"
TEMPLATE_PATH = (
    SKILL_DIR.parent
    / "tool-einstein-arena"
    / "assets"
    / "playbook-template.md"
)


def _load_module(name: str, filename: str):
    """Import a script module from absolute path so tests don't rely on PYTHONPATH."""
    path = SCRIPTS_DIR / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, f"could not load {path}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def arena_runner():
    return _load_module("arena_runner", "arena_runner.py")


@pytest.fixture(scope="module")
def tri_verify_mod():
    return _load_module("tri_verify", "tri_verify.py")


@pytest.fixture(scope="module")
def recon_mod():
    return _load_module("recon", "recon.py")


# ---------------------------------------------------------------------------
# Test 1 — subcommand dispatch
# ---------------------------------------------------------------------------

def test_dispatch_routes_polish(arena_runner):
    with patch.object(arena_runner, "cmd_polish", return_value=0) as stub:
        rc = arena_runner.run("polish", ["--project-dir", "/tmp/x"])
    stub.assert_called_once()
    assert rc == 0


def test_dispatch_routes_tri_verify(arena_runner):
    with patch.object(arena_runner, "cmd_tri_verify", return_value=0) as stub:
        rc = arena_runner.run("tri-verify", ["--solution", "/tmp/sol.json"])
    stub.assert_called_once()
    assert rc == 0


def test_dispatch_routes_recon(arena_runner):
    with patch.object(arena_runner, "cmd_recon", return_value=0) as stub:
        rc = arena_runner.run("recon", ["--slug", "foo", "--project-dir", "/tmp/foo"])
    stub.assert_called_once()
    assert rc == 0


# ---------------------------------------------------------------------------
# Test 2 — unknown subcommand
# ---------------------------------------------------------------------------

def test_unknown_subcommand_exits_2(arena_runner):
    with pytest.raises(SystemExit) as ei:
        arena_runner.run("invalid", [])
    assert ei.value.code == 2


# ---------------------------------------------------------------------------
# Test 3 — polish defaults to solutions/best.json when --config omitted
# ---------------------------------------------------------------------------

def test_polish_defaults_to_best_json(tmp_path, arena_runner):
    project = tmp_path / "arena-foo"
    (project / "solutions").mkdir(parents=True)
    best = project / "solutions" / "best.json"
    best.write_text('{"vectors": []}')
    evaluator = project / "evaluator.py"
    evaluator.write_text("def eval_fn(V):\n    return 0.0\n")

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        class R:
            returncode = 0
            stdout = ""
            stderr = ""
        return R()

    with patch.object(arena_runner.subprocess, "run", side_effect=fake_run):
        rc = arena_runner.run(
            "polish",
            [
                "--project-dir", str(project),
                "--evaluator", "evaluator:eval_fn",
            ],
        )
    assert rc == 0
    cmd = captured["cmd"]
    # Default config path must be the solutions/best.json file.
    joined = " ".join(cmd)
    assert str(best) in joined
    # Budget default is 3600
    assert "3600" in joined
    # Evaluator module is forwarded
    assert "evaluator:eval_fn" in joined


# ---------------------------------------------------------------------------
# Test 4 — polish errors loudly when warm-start file missing
# ---------------------------------------------------------------------------

def test_polish_errors_without_warm_start(tmp_path, arena_runner, capsys):
    project = tmp_path / "arena-empty"
    project.mkdir()
    # Intentionally no solutions/best.json and no evaluator.
    rc = arena_runner.run(
        "polish",
        ["--project-dir", str(project), "--evaluator", "evaluator:eval_fn"],
    )
    assert rc != 0
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "best.json" in combined or "warm-start" in combined.lower()


# ---------------------------------------------------------------------------
# Test 5 — tri-verify all-pass
# ---------------------------------------------------------------------------

def test_tri_verify_all_agree(tri_verify_mod):
    score = 0.1234567890
    out = tri_verify_mod.tri_verify(
        lambda: score,
        lambda: score + 1e-13,
        lambda: score - 1e-13,
        tolerance=1e-9,
    )
    assert out["status"] == "pass"
    assert out["methods_run"] == 3
    assert "consensus_score" in out
    assert abs(out["consensus_score"] - score) < 1e-9
    assert set(out["scores"].keys()) == {"float64", "mpmath", "extra"}


# ---------------------------------------------------------------------------
# Test 6 — tri-verify disagreement
# ---------------------------------------------------------------------------

def test_tri_verify_disagreement(tri_verify_mod):
    out = tri_verify_mod.tri_verify(
        lambda: 0.10000,
        lambda: 0.10005,
        lambda: 0.20000,
        tolerance=1e-9,
    )
    assert out["status"] == "disagree"
    # majority agreement set should have size ≤ 2
    assert out["methods_agree"] <= 2


# ---------------------------------------------------------------------------
# Test 7 — tri-verify with only 2 methods (mpmath_fn=None) still passes if they agree
# ---------------------------------------------------------------------------

def test_tri_verify_two_methods(tri_verify_mod):
    out = tri_verify_mod.tri_verify(
        lambda: 0.5,
        None,
        lambda: 0.5 + 1e-15,
        tolerance=1e-9,
    )
    assert out["methods_run"] == 2
    assert out["status"] == "pass"
    assert "mpmath" not in out["scores"]


# ---------------------------------------------------------------------------
# Test 8 — recon creates expected layout
# ---------------------------------------------------------------------------

def test_recon_creates_layout(tmp_path, recon_mod):
    project = tmp_path / "arena-foo"
    result = recon_mod.recon(
        slug="foo",
        project_dir=project,
        template_path=TEMPLATE_PATH,
    )
    assert project.is_dir()
    assert (project / "PLAYBOOK.md").is_file()
    assert (project / "NOTES.md").is_file()
    assert result["playbook"] == project / "PLAYBOOK.md"
    assert result["notes"] == project / "NOTES.md"


# ---------------------------------------------------------------------------
# Test 9 — recon idempotent (does NOT overwrite existing PLAYBOOK.md)
# ---------------------------------------------------------------------------

def test_recon_idempotent(tmp_path, recon_mod, capsys):
    project = tmp_path / "arena-bar"
    project.mkdir()
    existing = project / "PLAYBOOK.md"
    marker = "USER-EDITED-DO-NOT-OVERWRITE"
    existing.write_text(marker)
    result = recon_mod.recon(
        slug="bar",
        project_dir=project,
        template_path=TEMPLATE_PATH,
    )
    # Existing content preserved.
    assert existing.read_text() == marker
    # Returned metadata flags skip.
    assert result.get("playbook_skipped") is True
    captured = capsys.readouterr()
    assert "exists" in (captured.out + captured.err).lower()


# ---------------------------------------------------------------------------
# Test 10 — recon template exists and PLAYBOOK has 7 sections
# ---------------------------------------------------------------------------

REQUIRED_SECTIONS = (
    "Problem",
    "SOTA snapshot",
    "Approaches tried",
    "Dead ends",
    "Fertile directions",
    "Open questions",
    "Submissions",
)


def test_recon_template_has_seven_sections(tmp_path, recon_mod):
    assert TEMPLATE_PATH.is_file(), f"template missing: {TEMPLATE_PATH}"
    project = tmp_path / "arena-sections"
    recon_mod.recon(
        slug="sections",
        project_dir=project,
        template_path=TEMPLATE_PATH,
    )
    text = (project / "PLAYBOOK.md").read_text()
    for section in REQUIRED_SECTIONS:
        assert f"## {section}" in text, f"missing section: {section}"
    # Slug should appear in the header prepended by recon
    assert "sections" in text.lower()


# ---------------------------------------------------------------------------
# Test 11 — CLI entry point surface
# ---------------------------------------------------------------------------

def test_cli_help_lists_subcommands():
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "arena_runner.py"), "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    combined = result.stdout + result.stderr
    assert "polish" in combined
    assert "tri-verify" in combined
    assert "recon" in combined


# ---------------------------------------------------------------------------
# Test 12 — polish reports missing ops-ulp-polish script clearly
# ---------------------------------------------------------------------------

def test_polish_missing_script_clear_error(tmp_path, arena_runner, capsys, monkeypatch):
    project = tmp_path / "arena-missing"
    (project / "solutions").mkdir(parents=True)
    (project / "solutions" / "best.json").write_text('{"vectors": []}')

    # Force the polish-script resolver to return a non-existent path.
    bogus = tmp_path / "no_such_polish.py"
    monkeypatch.setattr(arena_runner, "OPS_ULP_POLISH_SCRIPT", bogus)

    rc = arena_runner.run(
        "polish",
        ["--project-dir", str(project), "--evaluator", "evaluator:eval_fn"],
    )
    assert rc != 0
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "ops-ulp-polish" in combined or "polish.py" in combined
    assert str(bogus) in combined or "not found" in combined.lower()


# ---------------------------------------------------------------------------
# Test 13 — tri-verify CLI happy path (exercises cmd_tri_verify)
# ---------------------------------------------------------------------------

def _write_verifier_module(tmp_path: Path, name: str, body: str) -> Path:
    """Write a tiny verifier module under tmp_path and return the dir."""
    path = tmp_path / f"{name}.py"
    path.write_text(body)
    return path


def test_cmd_tri_verify_cli_pass(tmp_path, arena_runner, capsys, monkeypatch):
    # Build a verifier module that exposes float_score / mpmath_score / extra_score.
    verifier_body = (
        "def float_score(sol):\n"
        "    return 0.5\n"
        "def mpmath_score(sol):\n"
        "    return 0.5 + 1e-12\n"
        "def extra_score(sol):\n"
        "    return 0.5 - 1e-12\n"
    )
    _write_verifier_module(tmp_path, "my_verifier", verifier_body)
    monkeypatch.syspath_prepend(str(tmp_path))

    sol_path = tmp_path / "sol.json"
    sol_path.write_text('{"v": 1}')

    rc = arena_runner.run(
        "tri-verify",
        ["--solution", str(sol_path), "--verifier", "my_verifier"],
    )
    assert rc == 0
    captured = capsys.readouterr()
    assert '"status": "pass"' in captured.out
    assert '"methods_run": 3' in captured.out


def test_cmd_tri_verify_cli_missing_solution(tmp_path, arena_runner, capsys):
    rc = arena_runner.run(
        "tri-verify",
        ["--solution", str(tmp_path / "no_such.json"), "--verifier", "os"],
    )
    assert rc != 0
    captured = capsys.readouterr()
    assert "solution file not found" in (captured.out + captured.err).lower()


def test_cmd_tri_verify_cli_bad_module(tmp_path, arena_runner, capsys):
    sol_path = tmp_path / "sol.json"
    sol_path.write_text("{}")
    rc = arena_runner.run(
        "tri-verify",
        ["--solution", str(sol_path),
         "--verifier", "definitely_not_a_module_xyz_12345"],
    )
    assert rc != 0
    captured = capsys.readouterr()
    assert "cannot import" in (captured.out + captured.err).lower()


def test_cmd_tri_verify_cli_disagree_returns_1(tmp_path, arena_runner, capsys, monkeypatch):
    body = (
        "def float_score(sol):\n    return 0.1\n"
        "def mpmath_score(sol):\n    return 0.9\n"
        "def extra_score(sol):\n    return 0.5\n"
    )
    _write_verifier_module(tmp_path, "disagree_verifier", body)
    monkeypatch.syspath_prepend(str(tmp_path))
    sol = tmp_path / "sol.json"
    sol.write_text("{}")
    rc = arena_runner.run(
        "tri-verify",
        ["--solution", str(sol), "--verifier", "disagree_verifier"],
    )
    # Disagreement -> non-zero exit code.
    assert rc == 1
    captured = capsys.readouterr()
    assert '"status": "disagree"' in captured.out


# ---------------------------------------------------------------------------
# Test 14 — recon CLI path (exercises cmd_recon + _build_recon_parser)
# ---------------------------------------------------------------------------

def test_cmd_recon_cli_happy_path(tmp_path, arena_runner):
    project = tmp_path / "arena-cli"
    rc = arena_runner.run(
        "recon",
        ["--slug", "cli-slug", "--project-dir", str(project)],
    )
    assert rc == 0
    assert (project / "PLAYBOOK.md").is_file()
    assert (project / "NOTES.md").is_file()


def test_cmd_recon_cli_missing_template(tmp_path, arena_runner, capsys):
    project = tmp_path / "arena-cli-missing-template"
    bogus_template = tmp_path / "no_such_template.md"
    rc = arena_runner.run(
        "recon",
        [
            "--slug", "x",
            "--project-dir", str(project),
            "--template", str(bogus_template),
        ],
    )
    assert rc != 0
    captured = capsys.readouterr()
    assert "template" in (captured.out + captured.err).lower()


# ---------------------------------------------------------------------------
# Test 15 — main() smoke (no args prints help; returns 0)
# ---------------------------------------------------------------------------

def test_main_no_args_prints_help(arena_runner, capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["arena_runner.py"])
    rc = arena_runner.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "polish" in out and "tri-verify" in out and "recon" in out


def test_main_routes_subcommand(arena_runner, monkeypatch):
    monkeypatch.setattr("sys.argv", ["arena_runner.py", "invalid-sub"])
    with pytest.raises(SystemExit) as ei:
        arena_runner.main()
    assert ei.value.code == 2


# ---------------------------------------------------------------------------
# Test 16 — recon raw-function with NOTES.md already present
# ---------------------------------------------------------------------------

def test_recon_skips_existing_notes(tmp_path, recon_mod, capsys):
    project = tmp_path / "arena-notes"
    project.mkdir()
    notes = project / "NOTES.md"
    notes.write_text("EXISTING-NOTES-MARKER")
    result = recon_mod.recon(
        slug="notes-test",
        project_dir=project,
        template_path=TEMPLATE_PATH,
    )
    assert notes.read_text() == "EXISTING-NOTES-MARKER"
    assert result["notes_skipped"] is True


# ---------------------------------------------------------------------------
# Tests 17–21 — API subcommand dispatch (fetch/register/analyze/submit/monitor)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("subcommand,script_name", [
    ("fetch",    "fetch_problem.py"),
    ("register", "register.py"),
    ("analyze",  "analyze_competitors.py"),
    ("submit",   "submit.py"),
    ("monitor",  "monitor.py"),
])
def test_api_subcommand_dispatch(subcommand, script_name, arena_runner):
    """Each API subcommand routes to the correct tool-einstein-arena script."""
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        class R:
            returncode = 0
        return R()

    with patch.object(arena_runner.subprocess, "run", side_effect=fake_run):
        rc = arena_runner.run(subcommand, ["--help"])

    assert rc == 0
    assert script_name in " ".join(str(c) for c in captured["cmd"])


# ---------------------------------------------------------------------------
# Test 22 — missing arena script gives clear error
# ---------------------------------------------------------------------------

def test_api_subcommand_missing_script_clear_error(arena_runner, monkeypatch, capsys, tmp_path):
    """If ARENA_SCRIPTS_DIR doesn't contain the script, exit code 3 with clear message."""
    monkeypatch.setattr(arena_runner, "ARENA_SCRIPTS_DIR", tmp_path / "nonexistent")
    rc = arena_runner.run("fetch", ["difference-bases"])
    assert rc == 3
    captured = capsys.readouterr()
    assert "tool-einstein-arena" in (captured.out + captured.err)


# ---------------------------------------------------------------------------
# Test 23 — --help now mentions all 8 subcommands
# ---------------------------------------------------------------------------

def test_cli_help_lists_all_subcommands():
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "arena_runner.py"), "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    combined = result.stdout + result.stderr
    for sub in ("polish", "tri-verify", "recon", "fetch", "register", "analyze", "submit", "monitor"):
        assert sub in combined, f"--help missing subcommand: {sub}"
