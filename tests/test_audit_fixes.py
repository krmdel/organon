"""Regression tests for the 2026-04-14 audit fixes.

One test per finding (C1-C4, H1-H5, M1-M9, L1-L6). Each test locks in the
fix so later work cannot silently regress. Grouped by severity, commented
with the finding ID.
"""

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SETTINGS = ROOT / ".claude" / "settings.json"
LEARNINGS = ROOT / "context" / "learnings.md"
CLAUDE_MD = ROOT / "CLAUDE.md"
SKILLS_DIR = ROOT / ".claude" / "skills"
CATALOG = SKILLS_DIR / "_catalog" / "catalog.json"
AGENTS_DIR = ROOT / ".claude" / "agents"


# ============================================================
# H1 — verify_gate hook is PreToolUse, not PostToolUse
# ============================================================


def test_h1_learnings_says_pretooluse_not_post():
    """learnings.md must describe verify_gate as a PreToolUse hook —
    the earlier PostToolUse entry was stale and confusing."""
    text = LEARNINGS.read_text(encoding="utf-8")

    # The current entry must identify verify_gate as PreToolUse.
    verify_gate_lines = [
        line for line in text.splitlines()
        if "verify_gate.py" in line and ("PreToolUse" in line or "PostToolUse" in line)
    ]
    assert verify_gate_lines, "no learnings entry mentions verify_gate hook type"

    for line in verify_gate_lines:
        # PostToolUse may only appear as a historical correction, never as
        # the current claim. The rule: if a line calls it PostToolUse, it
        # must also contain "Corrects" or "correct" to mark it as a
        # historical note.
        if "PostToolUse" in line and "PreToolUse" not in line:
            pytest.fail(
                f"stale learnings entry still claims PostToolUse: {line!r}"
            )


def test_h1_settings_actually_registers_pretooluse_hook():
    """Cross-validate: settings.json must have verify_gate.py wired as a
    PreToolUse hook on Write|Edit|MultiEdit. If this ever changes, the
    learnings entry must be updated in lock-step."""
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    hooks = settings.get("hooks", {})

    pre = hooks.get("PreToolUse", [])
    assert pre, "PreToolUse hook list missing from settings.json"

    # Find the verify_gate registration.
    matched = False
    for entry in pre:
        matcher = entry.get("matcher", "")
        if not re.search(r"\bWrite\b", matcher):
            continue
        for hook in entry.get("hooks", []):
            if "verify_gate.py" in hook.get("command", ""):
                matched = True
                break
    assert matched, "verify_gate.py is not registered under PreToolUse.Write|Edit|MultiEdit"

    # Guard against regression: verify_gate must NOT also appear under
    # PostToolUse.
    post = hooks.get("PostToolUse", [])
    for entry in post:
        for hook in entry.get("hooks", []):
            assert "verify_gate.py" not in hook.get("command", ""), (
                "verify_gate.py accidentally registered under PostToolUse"
            )


# ============================================================
# H4 — SKILL.md thresholds match verify_ops.py constants
# ============================================================


def _read_verify_ops_constants():
    """Parse MIN_QUOTE_CHARS and TITLE_MATCH_THRESHOLD out of verify_ops.py
    without importing it (it has heavy repro-module side effects)."""
    path = SKILLS_DIR / "sci-writing" / "scripts" / "verify_ops.py"
    source = path.read_text(encoding="utf-8")
    mq = re.search(r"^MIN_QUOTE_CHARS\s*=\s*(\d+)", source, re.MULTILINE)
    tm = re.search(r"^TITLE_MATCH_THRESHOLD\s*=\s*([\d.]+)", source, re.MULTILINE)
    assert mq and tm, "verify_ops.py missing expected constants"
    return int(mq.group(1)), float(tm.group(1))


def test_h4_skill_md_matches_min_quote_chars():
    """sci-writing/SKILL.md must advertise the real MIN_QUOTE_CHARS."""
    min_chars, _ = _read_verify_ops_constants()
    skill = (SKILLS_DIR / "sci-writing" / "SKILL.md").read_text(encoding="utf-8")

    # Must mention the real constant value as a threshold.
    assert f"< {min_chars} chars" in skill or f"{min_chars}-char" in skill, (
        f"sci-writing/SKILL.md does not mention MIN_QUOTE_CHARS={min_chars}"
    )

    # The stale 20-char threshold must no longer be advertised as the rule.
    # It may appear as historical context (e.g. "raised from 20 → 80").
    stale_lines = [
        ln for ln in skill.splitlines()
        if re.search(r"<\s*20\s*chars", ln) and "raised" not in ln.lower()
    ]
    assert not stale_lines, f"stale 20-char threshold still in SKILL.md: {stale_lines}"


def test_h4_skill_md_matches_title_match_threshold():
    """sci-writing/SKILL.md must advertise the real TITLE_MATCH_THRESHOLD."""
    _, title_thr = _read_verify_ops_constants()
    skill = (SKILLS_DIR / "sci-writing" / "SKILL.md").read_text(encoding="utf-8")

    # Accept either "0.9" or "0.90" form, with optional ≥ character.
    thr_str = f"{title_thr:.2f}"  # "0.90"
    thr_alt = f"{title_thr:g}"    # "0.9"
    assert thr_str in skill or thr_alt in skill, (
        f"sci-writing/SKILL.md does not mention TITLE_MATCH_THRESHOLD={title_thr}"
    )

    # Stale 0.75 threshold should not appear as the current rule.
    stale_lines = [
        ln for ln in skill.splitlines()
        if "0.75" in ln and "raised" not in ln.lower()
    ]
    assert not stale_lines, f"stale 0.75 threshold still in SKILL.md: {stale_lines}"


# ============================================================
# L3 — catalog.json dependencies cover humanizer + lit-research
# ============================================================


def test_l3_catalog_writeup_skills_list_humanizer():
    """sci-writing and sci-communication both route through the Humanizer
    Gate in CLAUDE.md. The catalog must declare tool-humanizer as a
    dependency so downstream installers can resolve the graph."""
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    skills = catalog["skills"]

    for skill_name in ("sci-writing", "sci-communication"):
        deps = skills[skill_name]["dependencies"]
        assert "tool-humanizer" in deps, (
            f"{skill_name} must declare tool-humanizer as a dependency "
            f"(needed for the Humanizer Gate); got {deps}"
        )
        # Upstream quotes sidecar comes from sci-literature-research cite mode.
        assert "sci-literature-research" in deps, (
            f"{skill_name} must declare sci-literature-research as a dependency "
            f"(needed for the upstream quotes sidecar contract); got {deps}"
        )


def test_l3_catalog_schema_well_formed():
    """Every skill entry has the required fields and types — basic
    catalog.json hygiene."""
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    required = {"category", "description", "requires_services", "dependencies", "mcp_servers"}
    for name, entry in catalog["skills"].items():
        missing = required - set(entry.keys())
        assert not missing, f"{name} missing fields: {missing}"
        assert isinstance(entry["dependencies"], list), f"{name} dependencies not a list"
        assert isinstance(entry["requires_services"], list), f"{name} requires_services not a list"


# ============================================================
# L4 — USER.md template carries inline field guidance
# ============================================================


def test_l4_user_md_has_field_hints():
    """Fresh USER.md template should guide first-run users on what each
    field means. Previously it shipped as an entirely blank form, which
    offered no signal to new users."""
    user_md = (ROOT / "context" / "USER.md").read_text(encoding="utf-8")

    # The core fields we want hints on must all have inline HTML comments.
    required_hinted_fields = [
        "Name:",
        "Primary Field:",
        "Communication style:",
        "Citation style:",
    ]
    for field in required_hinted_fields:
        # Find the field line and confirm it has an HTML comment attached.
        field_lines = [
            ln for ln in user_md.splitlines()
            if ln.lstrip().startswith(f"- {field}")
        ]
        assert field_lines, f"USER.md missing field '{field}'"
        has_hint = any("<!--" in ln and "-->" in ln for ln in field_lines)
        assert has_hint, f"USER.md field '{field}' lacks an inline hint"

    # At least one field must be tagged [required] so /lets-go can
    # enforce a minimum.
    assert "[required]" in user_md, "USER.md has no [required] field markers"

    # The instructional preamble must explain the template.
    assert "/lets-go" in user_md, "USER.md preamble must reference /lets-go"


# ============================================================
# L5 — sci-writing SKILL.md documents refused-state finality
# ============================================================


def test_l5_skill_md_documents_refused_is_terminal():
    """Users who hit paper_pipeline `refused` need to know the only
    recovery path is --force reinit; otherwise they'll re-run commands
    against a dead workspace forever."""
    skill = (SKILLS_DIR / "sci-writing" / "SKILL.md").read_text(encoding="utf-8")

    # Must mention terminal nature of refused state.
    assert re.search(r"refused.*terminal", skill, re.IGNORECASE), (
        "sci-writing/SKILL.md does not explain refused is terminal within a nonce"
    )

    # Must mention --force as the recovery path.
    assert "--force" in skill, (
        "sci-writing/SKILL.md does not mention --force as the recovery path"
    )


# ============================================================
# L1 — add-client.sh produces SOUL.md symlink + USER.md copy
# ============================================================


def test_l1_add_client_script_links_soul_and_copies_user(tmp_path, monkeypatch):
    """CLAUDE.md documents `SOUL.md → ../../context/SOUL.md` for client
    workspaces. The script previously copied nothing for SOUL.md at all.
    Run add-client.sh in a scratch fake repo and assert the symlink and
    the USER.md copy both land."""
    import shutil
    import subprocess

    # Build a minimal fake repo that mimics the real layout.
    fake_repo = tmp_path / "fake-repo"
    (fake_repo / "context").mkdir(parents=True)
    (fake_repo / "scripts").mkdir()
    (fake_repo / ".claude" / "skills").mkdir(parents=True)
    (fake_repo / ".claude" / "hooks_info").mkdir()
    (fake_repo / "cron" / "templates").mkdir(parents=True)

    (fake_repo / "context" / "SOUL.md").write_text("# SOUL\n")
    (fake_repo / "context" / "USER.md").write_text("# USER template\n")
    (fake_repo / "context" / "learnings.md").write_text("# Learnings\n")
    (fake_repo / ".claude" / "settings.json").write_text("{}\n")

    # Copy the real script into the fake repo so PROJECT_DIR resolves
    # to the fake repo root.
    shutil.copy(ROOT / "scripts" / "add-client.sh", fake_repo / "scripts" / "add-client.sh")

    result = subprocess.run(
        ["bash", str(fake_repo / "scripts" / "add-client.sh"), "Acme Corp"],
        capture_output=True,
        text=True,
        cwd=fake_repo,
    )
    assert result.returncode == 0, f"add-client.sh failed:\n{result.stderr}"

    client = fake_repo / "clients" / "acme-corp"
    assert client.is_dir(), "client directory not created"

    # SOUL.md must be a symlink pointing at the root SOUL.md.
    soul = client / "context" / "SOUL.md"
    assert soul.is_symlink(), f"SOUL.md is not a symlink: {soul}"
    resolved = soul.resolve()
    assert resolved == (fake_repo / "context" / "SOUL.md").resolve(), (
        f"SOUL.md symlink points at {resolved}, expected root SOUL.md"
    )

    # USER.md must exist as a regular file (copied, not linked — clients
    # own their USER.md).
    user = client / "context" / "USER.md"
    assert user.exists() and not user.is_symlink(), (
        "USER.md should be copied, not symlinked (clients own their profile)"
    )
    assert "USER template" in user.read_text(encoding="utf-8")


# ============================================================
# M2 — .env script read pattern is documented as advisory
# ============================================================


def test_m2_claude_md_explains_env_advisory_nature():
    """CLAUDE.md Permissions section must explain that Read(.env) deny
    only filters Claude's tool calls, not standalone scripts. Without
    this note, a reader assumes .env is sandboxed when it isn't."""
    claude_md = CLAUDE_MD.read_text(encoding="utf-8")
    # Find the Permissions section specifically — grep for the scope note.
    assert "advisory" in claude_md and ".env" in claude_md, (
        "CLAUDE.md Permissions missing advisory-scope note about .env"
    )
    # The note should point at generate_image.py as a concrete example.
    assert "generate_image.py" in claude_md, (
        "CLAUDE.md should reference generate_image.py _load_dotenv as example"
    )


def test_m2_generate_image_has_docstring_explaining_bypass():
    """generate_image.py::_load_dotenv must carry a comment explaining
    why it bypasses the Read(.env) deny — otherwise a future reader
    might 'fix' it and break image generation."""
    path = SKILLS_DIR / "viz-nano-banana" / "scripts" / "generate_image.py"
    text = path.read_text(encoding="utf-8")
    # Grab the _load_dotenv function block.
    match = re.search(r"def _load_dotenv\(\):(.*?)^_load_dotenv\(\)", text, re.DOTALL | re.MULTILINE)
    assert match, "could not locate _load_dotenv function in generate_image.py"
    body = match.group(1)
    assert "bypass" in body.lower() or "advisory" in body.lower(), (
        "_load_dotenv missing the bypass/advisory explanation comment"
    )


# ============================================================
# M5 — verify_gate enforces self-loop invariant at runtime
# ============================================================


def test_m5_verify_gate_has_snapshot_helper_and_invariant_assertion():
    """verify_gate.py must carry both a _snapshot helper and a
    _assert_no_real_mutation check that runs after verify_ops so the
    self-loop invariant ('verify_ops only writes to the staged tempfile')
    fails closed at runtime, not just at code review."""
    path = ROOT / ".claude" / "hooks_info" / "verify_gate.py"
    text = path.read_text(encoding="utf-8")

    # Helper exists.
    assert "def _snapshot(" in text, "verify_gate.py missing _snapshot helper"

    # Invariant assertion function exists.
    assert "def _assert_no_real_mutation(" in text, (
        "verify_gate.py missing _assert_no_real_mutation"
    )

    # main() captures a pre-snapshot and calls the assertion.
    assert "real_before = _snapshot(md_path)" in text, (
        "main() does not capture a pre-snapshot of the real target"
    )
    assert "_assert_no_real_mutation(md_path, real_before)" in text, (
        "main() does not invoke the invariant assertion"
    )


def test_m5_snapshot_roundtrip(tmp_path):
    """Load _snapshot and verify its behavior: None for missing files,
    stable tuples for existing files, different tuples after a write."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "verify_gate", ROOT / ".claude" / "hooks_info" / "verify_gate.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    missing = tmp_path / "nope.md"
    assert mod._snapshot(missing) is None

    target = tmp_path / "draft.md"
    target.write_text("v1", encoding="utf-8")
    snap_a = mod._snapshot(target)
    snap_b = mod._snapshot(target)
    assert snap_a == snap_b  # stable for unchanged files

    # Mutating the file must change the snapshot (either size or mtime).
    import time
    time.sleep(0.01)
    target.write_text("v2-longer", encoding="utf-8")
    snap_c = mod._snapshot(target)
    assert snap_c != snap_a

    # Invariant assertion: matching snapshots pass silently.
    mod._assert_no_real_mutation(target, snap_c)
    # Mismatched snapshots raise RuntimeError.
    with pytest.raises(RuntimeError, match="self-loop invariant violated"):
        mod._assert_no_real_mutation(target, snap_a)


# ============================================================
# M6 — remove-skill.sh rejects path-traversal skill names
# ============================================================


def test_m6_remove_skill_rejects_path_traversal():
    """A crafted skill name like '../../../etc' must be refused BEFORE
    reaching rm -rf. The catalog-lookup gate is the primary defense,
    but a strict regex guard on SKILL_NAME is cheap defense-in-depth."""
    import subprocess

    script = ROOT / "scripts" / "remove-skill.sh"

    # Probe several malicious shapes — each must exit non-zero without
    # calling rm. We use `set -x` style expectations: if any of these
    # accidentally succeed, rm could be called on an unintended path.
    probes = [
        "../../../etc",
        "../secrets",
        "./something",
        "foo/bar",
        "foo.bar",
        ".hidden",
        "UPPERCASE",
        "has space",
        "foo;rm",
        "--help",
    ]
    for probe in probes:
        result = subprocess.run(
            ["bash", str(script), probe],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        assert result.returncode != 0, (
            f"remove-skill.sh accepted dangerous name {probe!r}; stdout={result.stdout}"
        )
        assert "invalid skill name" in (result.stdout + result.stderr).lower(), (
            f"remove-skill.sh failed on {probe!r} but not with the invalid-name guard "
            f"message (stdout={result.stdout!r}, stderr={result.stderr!r})"
        )

    # Sanity: a well-formed name that doesn't exist in the catalog still
    # exits with the 'not_found' error, not the regex guard — proves the
    # guard doesn't over-block real slugs.
    result = subprocess.run(
        ["bash", str(script), "definitely-not-a-real-skill"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode != 0
    assert "invalid skill name" not in (result.stdout + result.stderr).lower(), (
        "regex guard is over-blocking valid slug shapes"
    )


# ============================================================
# M9 — repro/citation_verify.py has a CrossRef timeout
# ============================================================


@pytest.mark.real_citation_verify
def test_m9_verify_doi_has_timeout_kwarg():
    """verify_doi must accept a `timeout` kwarg and forward it to
    urllib.request.urlopen so direct callers can't hang forever."""
    import inspect
    from repro import citation_verify

    sig = inspect.signature(citation_verify.verify_doi)
    assert "timeout" in sig.parameters, (
        "verify_doi missing a timeout kwarg"
    )
    default = sig.parameters["timeout"].default
    assert isinstance(default, (int, float)) and default > 0, (
        f"verify_doi timeout default must be a positive number, got {default!r}"
    )


@pytest.mark.real_citation_verify
def test_m9_verify_doi_raises_connection_error_on_timeout(monkeypatch):
    """If urlopen raises TimeoutError (Python 3.10+) or a socket timeout
    wrapped in URLError, verify_doi must map it to ConnectionError with
    an actionable message — never let it propagate raw."""
    from repro import citation_verify
    import urllib.error
    import socket

    def fake_urlopen_timeout(*args, **kwargs):
        raise urllib.error.URLError(socket.timeout("timed out"))

    monkeypatch.setattr(
        citation_verify.urllib.request, "urlopen", fake_urlopen_timeout
    )

    with pytest.raises(ConnectionError, match="timed out"):
        citation_verify.verify_doi("10.1234/fake", timeout=0.1)

    # Also test the bare TimeoutError path.
    def fake_urlopen_bare_timeout(*args, **kwargs):
        raise TimeoutError("bare timeout")

    monkeypatch.setattr(
        citation_verify.urllib.request, "urlopen", fake_urlopen_bare_timeout
    )

    with pytest.raises(ConnectionError, match="timed out"):
        citation_verify.verify_doi("10.1234/fake", timeout=0.1)


# ============================================================
# M4 — memory-search index writes are lock + atomic
# ============================================================


def test_m4_memory_index_atomic_write_helper_exists(tmp_path):
    """_atomic_write_json must serialise concurrent writers via flock
    on POSIX and always swap atomically via os.replace, so readers never
    see a partially-written index.json."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "memory_search", ROOT / "scripts" / "memory-search.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert hasattr(mod, "_atomic_write_json"), (
        "memory-search.py missing _atomic_write_json helper"
    )

    target = tmp_path / "index.json"
    payload = {"version": 1, "total": 2, "sessions": [{"date": "2026-04-14"}]}
    mod._atomic_write_json(target, payload)
    assert target.exists()
    assert json.loads(target.read_text(encoding="utf-8")) == payload

    # Lockfile must be cleaned up after the write.
    lock = target.with_suffix(target.suffix + ".lock")
    assert not lock.exists(), "lockfile left behind after atomic write"


def test_m4_memory_index_concurrent_writes_do_not_corrupt(tmp_path):
    """Spawn several threads hammering _atomic_write_json with
    different payloads; the final file must be a valid JSON payload
    that matches exactly one of the writes (not a torn mix)."""
    import importlib.util
    import threading

    spec = importlib.util.spec_from_file_location(
        "memory_search", ROOT / "scripts" / "memory-search.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    target = tmp_path / "index.json"
    payloads = [{"writer": i, "data": list(range(200))} for i in range(8)]

    def writer(p):
        for _ in range(5):
            mod._atomic_write_json(target, p)

    threads = [threading.Thread(target=writer, args=(p,)) for p in payloads]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Must be parseable.
    final = json.loads(target.read_text(encoding="utf-8"))
    # Must match ONE of the payloads exactly (no interleaving).
    assert final in payloads, f"torn write: got {final}"

    # Lockfile must be cleaned up even after contention.
    lock = target.with_suffix(target.suffix + ".lock")
    assert not lock.exists()


# ============================================================
# M3 — cron dispatcher rotates logs past a size threshold
# ============================================================


def test_m3_run_crons_has_rotate_helper(tmp_path):
    """run-crons.sh must define rotate_log_if_needed and call it before
    every append so unbounded log growth can't fill the filesystem."""
    import subprocess

    text = (ROOT / "scripts" / "run-crons.sh").read_text(encoding="utf-8")
    assert "rotate_log_if_needed()" in text, "helper not defined"
    # Must be called before each log append site. There are three append
    # sites in the script (main run_job, catch-up, dispatcher fallback).
    call_count = text.count("rotate_log_if_needed ")
    assert call_count >= 3, f"rotate_log_if_needed called only {call_count} times, need >=3"

    # Shell-source the helper and drive it through a fake log.
    log = tmp_path / "fake.log"
    log.write_text("x" * 5000, encoding="utf-8")

    # Extract just the helper + constants, run it against the fake log
    # with a very small max-bytes threshold so we can observe rotation.
    harness = f"""
set -euo pipefail
LOG_MAX_BYTES=1024
LOG_KEEP=3
{_extract_function(text, 'rotate_log_if_needed')}
rotate_log_if_needed "{log}"
"""
    result = subprocess.run(
        ["bash", "-c", harness],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"rotate failed: {result.stderr}"

    # Active log must now be empty; .1 must hold the old content.
    assert log.exists()
    assert log.stat().st_size == 0, "active log not truncated after rotation"
    rotated = log.with_suffix(log.suffix + ".1")
    assert rotated.exists(), ".1 archive not created"
    assert rotated.stat().st_size == 5000


def _extract_function(text: str, name: str) -> str:
    """Pull a bash function body (name() { ... }) out of a shell script."""
    lines = text.splitlines()
    out = []
    depth = 0
    started = False
    for ln in lines:
        if not started and ln.startswith(f"{name}()"):
            started = True
            out.append(ln)
            depth += ln.count("{") - ln.count("}")
            continue
        if started:
            out.append(ln)
            depth += ln.count("{") - ln.count("}")
            if depth == 0:
                break
    return "\n".join(out)


# ============================================================
# M1 — settings.json deny list covers all sensitive access paths
# ============================================================


def test_m1_settings_deny_list_is_comprehensive():
    """Even though Claude Code evaluates deny-first in current versions,
    a single missed path (Edit(.env), Bash(cat .env), etc.) could expose
    secrets. Lock the deny list to cover every foreseeable path to
    sensitive files."""
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    deny = set(settings["permissions"]["deny"])

    # .env must be blocked via all three tool paths.
    required = {
        "Read(.env)",
        "Read(.env.local)",
        "Edit(.env)",
        "Edit(.env.local)",
        "Write(.env)",
        "Write(.env.local)",
        "Bash(cat .env)",
    }
    missing = required - deny
    assert not missing, f"settings.json deny list missing: {sorted(missing)}"

    # SSH keys + credentials.
    assert "Read(**/id_rsa*)" in deny
    assert "Read(**/.ssh/*)" in deny
    assert "Read(**/*credential*)" in deny


# ============================================================
# M7 — paper_pipeline disambiguates blocked vs passed gate results
# ============================================================


def _load_paper_pipeline():
    """Dataclasses with Optional[...] annotations need the module to be
    registered in sys.modules before eval. Register, exec, return."""
    import importlib.util, sys
    spec = importlib.util.spec_from_file_location(
        "paper_pipeline_under_test",
        ROOT / ".claude" / "skills" / "sci-writing" / "scripts" / "paper_pipeline.py",
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["paper_pipeline_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_m7_paper_state_has_last_gate_status_field():
    """PaperState must carry a last_gate_status field so downstream
    readers can tell a clean exit 0 from a CRITICAL-blocked exit 2
    without re-parsing mechanical_exits."""
    mod = _load_paper_pipeline()

    state = mod.PaperState(slug="test")
    assert hasattr(state, "last_gate_status"), (
        "PaperState missing last_gate_status field"
    )
    assert state.last_gate_status is None, (
        "last_gate_status should default to None before any gate runs"
    )

    # Value domain must include passed/blocked/refused.
    import dataclasses
    fields = {f.name: f for f in dataclasses.fields(state)}
    assert "last_gate_status" in fields


def test_m7_gate_draft_sets_disambiguated_status(tmp_path, monkeypatch):
    """Smoke-test the three gate_draft paths: exit 0 → passed,
    exit 2 → blocked, exit 3 → refused. We fake subprocess.run so we
    don't need a real verify_ops invocation."""
    from types import SimpleNamespace

    mod = _load_paper_pipeline()

    # Redirect PROJECT_ROOT -> tmp so state files live in the scratch dir.
    monkeypatch.setattr(mod, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(mod, "VERIFY_OPS", tmp_path / "fake_verify_ops.py")

    slug = "m7-test"
    ws = mod.workspace(slug)
    ws.mkdir(parents=True)
    (ws / f"{slug}-draft.md").write_text("# draft\n", encoding="utf-8")
    (ws / f"{slug}.bib").write_text("@article{x,title={t},doi={10.1/x}}\n")
    (ws / "research.md").write_text("research\n")
    # Upstream quotes sidecar is required by cmd_gate_draft (citation
    # integrity contract — check-research enforces its existence).
    (ws / f"{slug}.quotes.json").write_text(
        '{"version": 1, "quotes": []}', encoding="utf-8"
    )

    def _init_state(exit_code):
        # gate-draft transition expects phase="researched" or "retry".
        state = mod.PaperState(slug=slug, phase="researched")
        mod.save_state(state)
        return state

    def fake_run_factory(code):
        def _run(*args, **kwargs):
            return SimpleNamespace(returncode=code, stdout="", stderr="")
        return _run

    for exit_code, expected_status, expected_phase in [
        (0, "passed", "drafted"),
        (2, "blocked", "drafted"),
        (3, "refused", "refused"),
    ]:
        _init_state(exit_code)
        monkeypatch.setattr(mod.subprocess, "run", fake_run_factory(exit_code))
        result = mod.cmd_gate_draft(slug)
        state = mod.load_state(slug)
        assert state.last_gate_status == expected_status, (
            f"exit {exit_code}: expected status={expected_status}, "
            f"got {state.last_gate_status}"
        )
        assert state.phase == expected_phase, (
            f"exit {exit_code}: expected phase={expected_phase}, got {state.phase}"
        )


# ============================================================
# L6 — SKILL.md YAML frontmatter validator
# ============================================================


def test_l6_validator_script_passes_on_real_repo():
    """The validator must return 0 when run against the real repo — if
    it doesn't, some SKILL.md drifted past the CLAUDE.md rules."""
    import subprocess
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_skill_frontmatter.py")],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode == 0, (
        f"validator returned {result.returncode}; stdout={result.stdout!r}"
    )


def test_l6_validator_detects_oversized_frontmatter(tmp_path, monkeypatch):
    """Synthesize a SKILL.md whose frontmatter is past 1024 bytes and
    confirm the validator catches it."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "validate_skill_frontmatter",
        ROOT / "scripts" / "validate_skill_frontmatter.py",
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["validate_skill_frontmatter"] = mod
    spec.loader.exec_module(mod)

    # Redirect SKILLS_DIR to a scratch tree.
    monkeypatch.setattr(mod, "SKILLS_DIR", tmp_path)

    # Case 1: oversized frontmatter.
    big = tmp_path / "sci-bloat"
    big.mkdir()
    padding = "x" * 1200
    (big / "SKILL.md").write_text(
        f"---\nname: sci-bloat\ndescription: {padding}\n---\n\n# body\n",
        encoding="utf-8",
    )

    # Case 2: YAML name mismatch.
    mismatch = tmp_path / "sci-right-name"
    mismatch.mkdir()
    (mismatch / "SKILL.md").write_text(
        "---\nname: sci-wrong-name\ndescription: short\n---\n\n# body\n",
        encoding="utf-8",
    )

    # Case 3: missing SKILL.md.
    (tmp_path / "sci-empty").mkdir()

    # Case 4: clean skill — no findings.
    ok = tmp_path / "sci-clean"
    ok.mkdir()
    (ok / "SKILL.md").write_text(
        "---\nname: sci-clean\ndescription: all good\n---\n\n# body\n",
        encoding="utf-8",
    )

    findings = mod.validate_all()
    skills_with_errors = {f.skill for f in findings if f.level == "error"}

    assert "sci-bloat" in skills_with_errors
    assert "sci-right-name" in skills_with_errors
    assert "sci-empty" in skills_with_errors
    assert "sci-clean" not in skills_with_errors

    # Specific error-text sanity.
    bloat_issues = [f.issue for f in findings if f.skill == "sci-bloat"]
    assert any("1024" in issue for issue in bloat_issues), bloat_issues
    mismatch_issues = [f.issue for f in findings if f.skill == "sci-right-name"]
    assert any("does not match" in issue for issue in mismatch_issues), mismatch_issues


# ============================================================
# M8 — subagent definitions document the JSON sidecar schema
# ============================================================


def test_m8_subagents_document_json_report_schema():
    """paper_pipeline.py / auditor_pipeline.py consume structured JSON
    reports from each subagent with strict schema requirements: nonce,
    phase, verdict, counts, findings. If an agent definition silently
    drifts and writes a different shape, the pipeline refuses with a
    cryptic message. Agent definitions must now carry an explicit
    <json_report_schema> block documenting the contract."""
    expectations = {
        "sci-verifier.md": ("verification.json", "verification"),
        "sci-reviewer.md":  ("review.json", "review"),
        "sci-auditor.md":   ("audit.json", "audit"),
    }
    for filename, (artifact, phase) in expectations.items():
        text = (AGENTS_DIR / filename).read_text(encoding="utf-8")
        assert "<json_report_schema>" in text, (
            f"{filename} missing <json_report_schema> block"
        )
        assert artifact in text, (
            f"{filename} schema block does not mention the sidecar artifact {artifact}"
        )
        # phase value must be called out.
        assert f'"phase": "{phase}"' in text, (
            f'{filename} schema does not declare phase="{phase}"'
        )
        # Nonce anti-forgery note required.
        assert "nonce" in text.lower() and "forgery" in text.lower(), (
            f"{filename} schema block missing nonce/anti-forgery explanation"
        )
        # Required fields mentioned.
        for field in ("version", "verdict", "counts", "findings"):
            assert field in text, f"{filename} schema missing {field}"


# ============================================================
# C1 — run-crons.sh no longer uses unconditional bypass
# ============================================================


def test_c1_run_crons_no_unconditional_bypass():
    """Every cron job used to launch with --dangerously-skip-permissions
    hardcoded into the dispatcher. That made every cron file a root-
    equivalent execution vector. The fix: default to --permission-mode
    acceptEdits, allow per-job opt-in via YAML frontmatter."""
    text = (ROOT / "scripts" / "run-crons.sh").read_text(encoding="utf-8")

    # The literal blanket flag must not be used as a command-line
    # argument any more. It may still appear inside an explanatory
    # comment — that's fine. We scan only the non-comment lines.
    non_comment = "\n".join(
        ln for ln in text.splitlines() if not ln.lstrip().startswith("#")
    )
    assert "--dangerously-skip-permissions" not in non_comment, (
        "run-crons.sh still passes --dangerously-skip-permissions blanket-style"
    )

    # Must now use --permission-mode with a parametrised value.
    assert '--permission-mode "$PERM_MODE"' in text, (
        "run-crons.sh does not parametrise --permission-mode"
    )

    # Safe default.
    assert 'PERM_MODE="${PERM_MODE:-acceptEdits}"' in text, (
        "run-crons.sh default permission mode is not acceptEdits"
    )

    # Per-job opt-in to bypass must be explicit and warn.
    assert 'bypassPermissions' in text
    assert 'WARNING' in text, (
        "bypassPermissions opt-in should log a warning"
    )

    # allowed_tools parse + forward.
    assert 'ALLOWED_TOOLS=$(awk' in text
    assert '--allowed-tools' in text


# ============================================================
# H2 — /lets-go uses marker file, not empty-field inference
# ============================================================


def test_h2_lets_go_detects_first_run_via_marker():
    """The mode detection section must key off context/.lets-go-onboarded
    instead of inferring from empty USER.md fields (which used to
    re-trigger onboarding on every fresh clone)."""
    cmd = (ROOT / ".claude" / "commands" / "lets-go.md").read_text(encoding="utf-8")

    # Must reference the marker file by name.
    assert "context/.lets-go-onboarded" in cmd, (
        "lets-go.md does not reference the .lets-go-onboarded marker"
    )

    # Must NOT rely on 'populated Name field' as a trigger any more.
    # Historical mention inside a 'why we changed this' note is fine as
    # long as it explains the old approach was broken.
    lines = cmd.splitlines()
    for i, line in enumerate(lines):
        if "populated Name field" in line or "populated name field" in line.lower():
            # The line should be part of the explanation of why we moved
            # away from it, not a current rule.
            context = "\n".join(lines[max(0, i - 3): i + 4]).lower()
            assert any(
                marker in context
                for marker in ("used to", "do not use", "instead of", "fixes this")
            ), (
                f"line mentions 'populated Name field' as a current rule: {line!r}"
            )

    # Step 9 must instruct writing the marker at the end of first-run.
    assert "Step 9" in cmd
    assert ".lets-go-onboarded" in cmd


def test_h2_gitignore_excludes_marker():
    """The marker is per-user state — never commit it."""
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "context/.lets-go-onboarded" in gi, (
        ".gitignore must exclude context/.lets-go-onboarded"
    )


# ============================================================
# H3 — sci-communication upstream cite mode guidance
# ============================================================


def test_h3_auditor_refuses_sci_comm_citation_without_quotes(tmp_path, monkeypatch):
    """sci-communication gate must refuse when the draft has [@Key]
    markers but no upstream quotes.json, with a clear error that
    points back at cite mode. Drafts WITHOUT markers proceed."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "auditor_pipeline_under_test",
        ROOT / ".claude" / "skills" / "sci-writing" / "scripts" / "auditor_pipeline.py",
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["auditor_pipeline_under_test"] = mod
    spec.loader.exec_module(mod)

    # Redirect PROJECT_ROOT to a scratch workspace.
    monkeypatch.setattr(mod, "PROJECT_ROOT", tmp_path)

    slug = "blog-x"
    ws = mod.workspace("sci-communication", slug)
    ws.mkdir(parents=True)
    (ws / f"{slug}.bib").write_text("@article{x,title={t},doi={10.1/x}}\n")

    state = mod.PipelineState(
        pipeline="auditor",
        category="sci-communication",
        slug=slug,
        phase="init",
    )
    mod.save_state(state)

    # Case A: draft WITH [@Key] markers, no quotes.json → refused.
    (ws / f"{slug}.md").write_text(
        "# A blog post\n\nClaim [@Smith2023] from a paper.\n",
        encoding="utf-8",
    )
    with pytest.raises(mod.PipelineError, match="upstream seed"):
        mod.cmd_gate("sci-communication", slug)

    # Case B: no [@Key] markers → must NOT refuse on the quotes check
    # (it can still fail elsewhere for other reasons, but should not
    # raise PipelineError about missing upstream seed).
    # Reset state since the failed gate already mutated it.
    state = mod.PipelineState(
        pipeline="auditor",
        category="sci-communication",
        slug=slug,
        phase="init",
    )
    mod.save_state(state)
    (ws / f"{slug}.md").write_text(
        "# Personal take\n\nThis is expertise-only, no citations.\n",
        encoding="utf-8",
    )
    # subprocess.run will fail (verify_ops not set up for this scratch
    # workspace) but we don't care — we only assert that the upstream-
    # seed guard did NOT trigger.
    try:
        mod.cmd_gate("sci-communication", slug)
    except mod.PipelineError as exc:
        assert "upstream seed" not in str(exc), (
            "draft without [@Key] markers was wrongly refused by the "
            f"upstream-seed guard: {exc}"
        )
    except Exception:
        pass  # Downstream failures are fine — the guard is what we care about.


def test_h3_sci_communication_skill_warns_upfront():
    """sci-communication Step 1 must explain the citation decision
    point so a user writing a blog with [@Key] markers doesn't hit
    the gate refusal as a surprise."""
    skill = (SKILLS_DIR / "sci-communication" / "SKILL.md").read_text(encoding="utf-8")

    assert "Citation mode decision point" in skill, (
        "sci-communication/SKILL.md Step 1 missing citation decision callout"
    )
    # Must point back at cite mode by name.
    assert "cite mode" in skill
    # Must mention the quotes.json file that gates this.
    assert "quotes.json" in skill
    # And note the pure-expertise escape hatch (no markers → no gate).
    assert "expertise" in skill.lower()


# ============================================================
# L2 — profile-evolve --show handles missing Activity Log gracefully
# ============================================================


def test_l2_profile_evolve_show_missing_profile(tmp_path, monkeypatch):
    """`profile-evolve.py --show` must emit an explanatory empty-state
    message when research-profile.md doesn't exist yet, rather than
    silently returning nothing."""
    import importlib.util, subprocess
    spec = importlib.util.spec_from_file_location(
        "profile_evolve", ROOT / "scripts" / "profile-evolve.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["profile_evolve"] = mod
    spec.loader.exec_module(mod)

    # Point PROFILE_PATH at a tmp location that doesn't exist.
    missing = tmp_path / "research-profile.md"
    monkeypatch.setattr(mod, "PROFILE_PATH", missing)

    # Call show_activity_log directly and capture stdout.
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = mod.show_activity_log()
    assert rc == 0
    out = buf.getvalue()
    assert "No research profile yet" in out
    assert "sci-research-profile" in out


def test_l2_profile_evolve_show_missing_section(tmp_path, monkeypatch):
    """Profile exists but has no Activity Log section → message that
    explains how the section gets populated."""
    import importlib.util, io, contextlib
    spec = importlib.util.spec_from_file_location(
        "profile_evolve", ROOT / "scripts" / "profile-evolve.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["profile_evolve"] = mod
    spec.loader.exec_module(mod)

    profile = tmp_path / "research-profile.md"
    profile.write_text("# Profile\n\n## Core Identity\n\nName: Test\n", encoding="utf-8")
    monkeypatch.setattr(mod, "PROFILE_PATH", profile)

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = mod.show_activity_log()
    assert rc == 0
    out = buf.getvalue()
    assert "has not been created yet" in out
    assert "meta-wrap-up" in out


def test_l2_profile_evolve_show_empty_section(tmp_path, monkeypatch):
    """Activity Log section exists but has no data rows → message that
    says the section is ready but empty."""
    import importlib.util, io, contextlib
    spec = importlib.util.spec_from_file_location(
        "profile_evolve", ROOT / "scripts" / "profile-evolve.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["profile_evolve"] = mod
    spec.loader.exec_module(mod)

    profile = tmp_path / "research-profile.md"
    profile.write_text(
        "# Profile\n\n## Core Identity\n\nName: Test\n\n"
        "## Research Activity Log\n\n"
        "_Auto-updated by scripts/profile-evolve.py after each session._\n\n"
        "| Date | Skills Used | Topics | Notes |\n"
        "|------|-------------|--------|-------|\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "PROFILE_PATH", profile)

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = mod.show_activity_log()
    assert rc == 0
    out = buf.getvalue()
    assert "no rows yet" in out.lower()


def test_l2_profile_evolve_show_populated_section(tmp_path, monkeypatch):
    """Section with real data → prints the section."""
    import importlib.util, io, contextlib
    spec = importlib.util.spec_from_file_location(
        "profile_evolve", ROOT / "scripts" / "profile-evolve.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["profile_evolve"] = mod
    spec.loader.exec_module(mod)

    profile = tmp_path / "research-profile.md"
    profile.write_text(
        "# Profile\n\n## Research Activity Log\n\n"
        "| Date | Skills Used | Topics | Notes |\n"
        "|------|-------------|--------|-------|\n"
        "| 2026-04-14 | sci-data-analysis | crispr | notable run |\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "PROFILE_PATH", profile)

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = mod.show_activity_log()
    assert rc == 0
    out = buf.getvalue()
    assert "2026-04-14" in out
    assert "crispr" in out


# ============================================================
# H5 — scripts/reconcile.py reports drift
# ============================================================


def test_h5_reconcile_script_passes_real_repo():
    """Reconcile against the real repo must be green — drift here is a
    real problem that should fail CI, not a test bug."""
    import subprocess
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "reconcile.py"), "--strict"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode == 0, (
        f"reconcile --strict failed on real repo:\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )


def test_h5_reconcile_detects_disk_not_catalog(tmp_path, monkeypatch):
    """Synthesize a fake repo with drift and confirm reconcile catches
    each class of drift via its data model."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "reconcile_under_test", ROOT / "scripts" / "reconcile.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["reconcile_under_test"] = mod
    spec.loader.exec_module(mod)

    # Fake skills dir: sci-ondisk (not in catalog/md), sci-renamed
    # (folder renamed, yaml still says old).
    fake_skills = tmp_path / ".claude" / "skills"
    fake_skills.mkdir(parents=True)
    (fake_skills / "_catalog").mkdir()
    (fake_skills / "sci-ondisk").mkdir()
    (fake_skills / "sci-ondisk" / "SKILL.md").write_text(
        "---\nname: sci-ondisk\ndescription: x\n---\n", encoding="utf-8"
    )
    (fake_skills / "sci-renamed").mkdir()
    (fake_skills / "sci-renamed" / "SKILL.md").write_text(
        "---\nname: sci-old-name\ndescription: x\n---\n", encoding="utf-8"
    )

    # Fake catalog: mentions sci-ghost that doesn't exist on disk.
    catalog_path = fake_skills / "_catalog" / "catalog.json"
    catalog_path.write_text(json.dumps({
        "core_skills": [],
        "skills": {"sci-ghost": {"category": "science", "description": "", "requires_services": [], "dependencies": [], "mcp_servers": []}},
    }), encoding="utf-8")

    # Fake CLAUDE.md with a Skill Registry row that references sci-stale.
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text(
        "## Skill Registry\n\n"
        "| Skill | Triggers |\n"
        "|---|---|\n"
        "| `sci-stale` | \"something\" |\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(mod, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(mod, "SKILLS_DIR", fake_skills)
    monkeypatch.setattr(mod, "CATALOG_PATH", catalog_path)
    monkeypatch.setattr(mod, "CLAUDE_MD", claude_md)

    drift = mod.compute_drift()

    assert "sci-ondisk" in drift.on_disk_not_catalog
    assert "sci-renamed" in drift.on_disk_not_catalog
    assert "sci-ghost" in drift.catalog_not_on_disk
    assert "sci-stale" in drift.claude_md_not_on_disk
    assert any("sci-renamed" in m for m in drift.name_folder_mismatches)
    assert not drift.empty()


# ============================================================
# C4 — sci-writing Step 0 routes review mode to Step 3
# ============================================================


def test_c4_sci_writing_step0_routes_review_explicitly():
    """sci-writing/SKILL.md Step 0 must name both draft and review
    modes, list their trigger phrases, AND state explicitly that
    review mode routes to Step 3 (auditor pipeline) without passing
    through Step 1. Previously the skill listed the intents but didn't
    wire them to explicit pipeline entry points, so review requests
    drifted into draft mode and burned the retry budget."""
    skill = (SKILLS_DIR / "sci-writing" / "SKILL.md").read_text(encoding="utf-8")

    # Step 0 must contain a mode → pipeline mapping.
    step0_start = skill.find("## Step 0")
    step1_start = skill.find("## Step 1", step0_start + 1)
    assert step0_start > 0 and step1_start > 0
    step0 = skill[step0_start:step1_start]

    # Must call out the mandatory branching.
    assert "MANDATORY" in step0 or "mandatory" in step0, (
        "Step 0 does not flag branching as mandatory"
    )

    # Must map review → Step 3 explicitly.
    assert "Step 3" in step0 and "review" in step0.lower(), (
        "Step 0 does not explicitly route review mode to Step 3"
    )

    # Must map draft → Step 1 explicitly.
    assert "Step 1" in step0 and "draft" in step0.lower()

    # Review triggers must list real phrases.
    for phrase in ("peer review", "critique"):
        assert phrase in step0, f"Step 0 missing review trigger: {phrase}"

    # Must warn about running draft on existing manuscripts.
    assert "existing" in step0.lower() and "retry" in step0.lower(), (
        "Step 0 does not warn about running draft cascade on existing draft"
    )


# ============================================================
# C3 — paper_pipeline has a read-only `resume` command
# ============================================================


def test_c3_paper_pipeline_resume_preserves_nonce_and_retry(tmp_path, monkeypatch):
    """`resume` must NOT rotate the nonce or reset retry_count. It is a
    read-only continuation hint that reports the current phase and the
    next expected command."""
    mod = _load_paper_pipeline()
    monkeypatch.setattr(mod, "PROJECT_ROOT", tmp_path)

    slug = "c3-test"
    ws = mod.workspace(slug)
    ws.mkdir(parents=True)

    # Seed a state mid-cascade with a specific nonce + retry_count so we
    # can prove resume doesn't touch them.
    original = mod.PaperState(
        slug=slug,
        phase="drafted",
        nonce="ORIGINAL-NONCE-123",
        retry_count=1,
        last_gate_status="blocked",
    )
    mod.save_state(original)

    result = mod.cmd_resume(slug)

    # Core invariants.
    assert result["nonce"] == "ORIGINAL-NONCE-123"
    assert result["retry_count"] == 1
    assert result["phase"] == "drafted"
    assert result["last_gate_status"] == "blocked"
    assert result["status"] == "resumed"

    # Must offer a next-command hint tied to the current phase.
    assert "next" in result
    assert "sci-verifier" in result["next"], (
        f"resume from drafted should point at sci-verifier; got: {result['next']!r}"
    )

    # Re-load from disk and confirm nothing was mutated.
    reloaded = mod.load_state(slug)
    assert reloaded.nonce == "ORIGINAL-NONCE-123"
    assert reloaded.retry_count == 1
    assert reloaded.phase == "drafted"


def test_c3_paper_pipeline_resume_refused_reports_terminal(tmp_path, monkeypatch):
    """Resume from a refused state must still return the state but
    flag the terminal nature — the next hint should point at --force
    init, not at any cascade step."""
    mod = _load_paper_pipeline()
    monkeypatch.setattr(mod, "PROJECT_ROOT", tmp_path)

    slug = "c3-refused"
    ws = mod.workspace(slug)
    ws.mkdir(parents=True)

    original = mod.PaperState(
        slug=slug,
        phase="refused",
        nonce="R-NONCE",
        retry_count=1,
    )
    mod.save_state(original)

    result = mod.cmd_resume(slug)
    assert result["phase"] == "refused"
    assert "force" in result["next"].lower() or "terminal" in result["next"].lower()


def test_c3_paper_pipeline_resume_no_state_raises(tmp_path, monkeypatch):
    """Calling resume on a workspace that has no .pipeline_state.json
    must raise PipelineError pointing at init, not a cryptic
    FileNotFoundError."""
    mod = _load_paper_pipeline()
    monkeypatch.setattr(mod, "PROJECT_ROOT", tmp_path)

    with pytest.raises(mod.PipelineError, match="Nothing to resume"):
        mod.cmd_resume("does-not-exist")


def test_c3_paper_pipeline_cli_exposes_resume():
    """The CLI subparser list must include resume so the conductor can
    actually call it."""
    text = (
        SKILLS_DIR / "sci-writing" / "scripts" / "paper_pipeline.py"
    ).read_text(encoding="utf-8")
    # Check the dispatch wiring AND the subparser registration.
    assert 'args.command == "resume"' in text
    assert '"resume"' in text  # present in the for name in (...) list


# ============================================================
# C2 — humanize_lock enforcement (finalize → verify_gate refusal)
# ============================================================


def test_c2_auditor_state_has_humanize_lock():
    """PipelineState carries humanize_lock + finalized_at for C2."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "auditor_pipeline_c2",
        ROOT / ".claude" / "skills" / "sci-writing" / "scripts" / "auditor_pipeline.py",
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["auditor_pipeline_c2"] = mod
    spec.loader.exec_module(mod)

    state = mod.PipelineState(category="sci-communication", slug="x")
    assert hasattr(state, "humanize_lock")
    assert state.humanize_lock is False
    assert hasattr(state, "finalized_at")
    assert state.finalized_at is None


def test_c2_verify_gate_blocks_write_when_lock_set(tmp_path):
    """Simulate a sci-communication workspace with phase=finalized and
    humanize_lock=true. verify_gate.main() must return exit 2 with a
    post-humanize-refusal message on any Write/Edit to the draft."""
    import importlib.util, io, contextlib

    # Build a scratch repo layout verify_gate recognises.
    draft_dir = tmp_path / "projects" / "sci-communication" / "post"
    draft_dir.mkdir(parents=True)
    draft = draft_dir / "post.md"
    draft.write_text("# Old content\n", encoding="utf-8")
    (draft_dir / "post.bib").write_text("@article{a,title={t},doi={10.1/a}}\n")
    (draft_dir / ".pipeline_state.json").write_text(
        json.dumps({
            "pipeline": "auditor",
            "category": "sci-communication",
            "slug": "post",
            "phase": "finalized",
            "nonce": "fake",
            "humanize_lock": True,
            "finalized_at": "2026-04-14T00:00:00+00:00",
        }),
        encoding="utf-8",
    )

    spec = importlib.util.spec_from_file_location(
        "verify_gate_c2",
        ROOT / ".claude" / "hooks_info" / "verify_gate.py",
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["verify_gate_c2"] = mod
    spec.loader.exec_module(mod)

    # Point the gate at our scratch repo.
    import os
    os.environ["CLAUDE_PROJECT_DIR"] = str(tmp_path)
    mod.PROJECT_ROOT = tmp_path

    event = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": str(draft),
            "content": "# Humanized content\n",
        },
    }

    # Feed the event via stdin and capture stderr.
    with contextlib.ExitStack() as stack:
        stack.enter_context(
            contextlib.redirect_stderr(io.StringIO())
        )
        saved_stdin = sys.stdin
        sys.stdin = io.StringIO(json.dumps(event))
        try:
            rc = mod.main()
        finally:
            sys.stdin = saved_stdin

    assert rc == 2, f"verify_gate should block with exit 2, got {rc}"


def test_c2_auditor_post_humanize_clears_lock(tmp_path, monkeypatch):
    """Running post-humanize with a clean verify_ops (fake subprocess)
    must clear humanize_lock so subsequent gate checks pass."""
    import importlib.util
    from types import SimpleNamespace

    spec = importlib.util.spec_from_file_location(
        "auditor_pipeline_c2b",
        ROOT / ".claude" / "skills" / "sci-writing" / "scripts" / "auditor_pipeline.py",
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["auditor_pipeline_c2b"] = mod
    spec.loader.exec_module(mod)

    monkeypatch.setattr(mod, "PROJECT_ROOT", tmp_path)
    slug = "post"
    category = "sci-communication"
    ws = mod.workspace(category, slug)
    ws.mkdir(parents=True)
    (ws / f"{slug}.md").write_text("# Humanized\n", encoding="utf-8")
    (ws / f"{slug}.bib").write_text("@article{a,title={t},doi={10.1/a}}\n")

    state = mod.PipelineState(
        pipeline="auditor",
        category=category,
        slug=slug,
        phase="finalized",
        humanize_lock=True,
        finalized_at="2026-04-14T00:00:00+00:00",
    )
    mod.save_state(state)

    # Fake verify_ops to exit 0 (clean).
    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *a, **kw: SimpleNamespace(returncode=0, stdout="{}", stderr=""),
    )
    result = mod.cmd_post_humanize(category, slug)
    assert result["status"] == "passed"
    assert result["humanize_lock"] is False

    reloaded = mod.load_state(category, slug)
    assert reloaded.humanize_lock is False
