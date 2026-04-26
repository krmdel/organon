"""Install validation tests for Organon.

Covers INSTALL-01 through INSTALL-05:
  INSTALL-01: install.sh exits 0 on fresh clone
  INSTALL-02: install.sh creates .env and installed.json
  INSTALL-03: install.sh is idempotent (double-run produces no errors)
  INSTALL-04: Empty research_context/ is correctly identified as first-run state
  INSTALL-05: .env.example documents all Service Registry API keys
"""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.conftest import ROOT, ENV_EXAMPLE, CLAUDE_MD, parse_service_registry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_minimal_repo(base_dir: Path) -> tuple:
    """Replicate essential repo structure for install.sh.

    install.sh resolves paths as: SCRIPT_DIR = base_dir/scripts
    and REPO_ROOT = dirname(SCRIPT_DIR) = base_dir

    Returns (clone_dir, scripts_dir, stub_dir).
    """
    clone_dir = base_dir / "repo"
    clone_dir.mkdir()

    # Required directory structure
    scripts_dir = clone_dir / "scripts"
    scripts_dir.mkdir()

    catalog_dir = clone_dir / ".claude" / "skills" / "_catalog"
    catalog_dir.mkdir(parents=True)

    context_dir = clone_dir / "context"
    context_dir.mkdir()

    (clone_dir / "research_context").mkdir()

    # Copy real install.sh
    shutil.copy(ROOT / "scripts" / "install.sh", scripts_dir / "install.sh")
    (scripts_dir / "install.sh").chmod(0o755)

    # Stub scripts that install.sh calls
    for stub_name in ["setup.sh", "install-crons.sh"]:
        stub = scripts_dir / stub_name
        stub.write_text("#!/bin/bash\nexit 0\n")
        stub.chmod(0o755)

    # Copy .env.example
    shutil.copy(ENV_EXAMPLE, clone_dir / ".env.example")

    # Copy catalog.json (install.sh reads this to build installed.json)
    shutil.copy(
        ROOT / ".claude" / "skills" / "_catalog" / "catalog.json",
        catalog_dir / "catalog.json",
    )

    # Create empty installed.json placeholder
    (catalog_dir / "installed.json").write_text("{}\n")

    # Create context files so install.sh takes the 'already exists' branch
    # (avoids the cp USER.md.template path which would fail)
    (context_dir / "USER.md").write_text("# User\nTest user\n")
    (context_dir / "learnings.md").write_text("# Learnings\n")

    # Stub dir for fake package managers
    stub_dir = base_dir / "stubs"
    stub_dir.mkdir()

    return clone_dir, scripts_dir, stub_dir


def _create_stub_bins(stub_dir: Path) -> None:
    """Create stub executables for external commands install.sh might invoke."""
    for cmd in ["npm", "npx", "brew", "node", "pip", "pip3", "uv", "git"]:
        stub = stub_dir / cmd
        # node --version must return a string like "v18.0.0"
        if cmd == "node":
            stub.write_text('#!/bin/bash\necho "v18.0.0"\nexit 0\n')
        elif cmd == "git":
            stub.write_text(
                '#!/bin/bash\n'
                'if [[ "$1" == "--version" ]]; then echo "git version 2.39.0"; fi\n'
                'exit 0\n'
            )
        else:
            stub.write_text("#!/bin/bash\nexit 0\n")
        stub.chmod(0o755)


def _run_install(clone_dir: Path, stub_dir: Path, scripts_dir: Path) -> subprocess.CompletedProcess:
    """Run install.sh with stubs on PATH. Returns the CompletedProcess."""
    env = {
        **os.environ,
        "PATH": f"{stub_dir}:{os.environ['PATH']}",
        # Suppress interactive clear
        "TERM": "dumb",
    }
    return subprocess.run(
        ["bash", str(scripts_dir / "install.sh")],
        env=env,
        capture_output=True,
        text=True,
        cwd=str(clone_dir),
    )


# ---------------------------------------------------------------------------
# TestInstallFresh  (INSTALL-01, INSTALL-02)
# ---------------------------------------------------------------------------


class TestInstallFresh:
    """Tests for fresh install behaviour."""

    def test_install_exits_zero(self, tmp_path):
        """INSTALL-01: install.sh exits 0 in a simulated fresh clone directory."""
        clone_dir, scripts_dir, stub_dir = _create_minimal_repo(tmp_path)
        _create_stub_bins(stub_dir)

        result = _run_install(clone_dir, stub_dir, scripts_dir)

        assert result.returncode == 0, (
            f"install.sh exited {result.returncode}\n"
            f"--- STDOUT ---\n{result.stdout}\n"
            f"--- STDERR ---\n{result.stderr}\n"
        )

    def test_install_creates_env_file(self, tmp_path):
        """INSTALL-02a: install.sh creates .env from .env.example."""
        clone_dir, scripts_dir, stub_dir = _create_minimal_repo(tmp_path)
        _create_stub_bins(stub_dir)

        _run_install(clone_dir, stub_dir, scripts_dir)

        env_file = clone_dir / ".env"
        assert env_file.exists(), ".env was not created by install.sh"

        env_content = env_file.read_text()
        # .env should contain at least one API key variable
        assert re.search(r"^[A-Z_]+=", env_content, re.MULTILINE), (
            ".env appears to be empty or contains no KEY=value lines"
        )

    def test_install_creates_installed_json(self, tmp_path):
        """INSTALL-02b: install.sh creates installed.json with correct structure."""
        clone_dir, scripts_dir, stub_dir = _create_minimal_repo(tmp_path)
        _create_stub_bins(stub_dir)

        _run_install(clone_dir, stub_dir, scripts_dir)

        installed_path = clone_dir / ".claude" / "skills" / "_catalog" / "installed.json"
        assert installed_path.exists(), "installed.json was not created by install.sh"

        data = json.loads(installed_path.read_text())

        # Verify required keys
        assert "installed_at" in data, "installed.json missing 'installed_at'"
        assert "version" in data, "installed.json missing 'version'"
        assert "installed_skills" in data, "installed.json missing 'installed_skills'"
        assert "removed_skills" in data, "installed.json missing 'removed_skills'"
        assert "selection_pending" in data, "installed.json missing 'selection_pending'"

        # Verify types / values
        assert isinstance(data["installed_at"], str), "installed_at should be an ISO date string"
        assert re.match(r"\d{4}-\d{2}-\d{2}", data["installed_at"]), (
            "installed_at does not look like an ISO date"
        )
        assert isinstance(data["installed_skills"], list), "installed_skills should be a list"
        assert len(data["installed_skills"]) > 0, "installed_skills list is empty"
        assert isinstance(data["removed_skills"], list), "removed_skills should be a list"
        assert data["removed_skills"] == [], "removed_skills should be empty on fresh install"
        assert data["selection_pending"] is True, "selection_pending should be True on fresh install"


# ---------------------------------------------------------------------------
# TestInstallIdempotent  (INSTALL-03)
# ---------------------------------------------------------------------------


class TestInstallIdempotent:
    """Tests for idempotent re-install behaviour."""

    def test_install_twice_no_errors(self, tmp_path):
        """INSTALL-03: Running install.sh twice produces no errors."""
        clone_dir, scripts_dir, stub_dir = _create_minimal_repo(tmp_path)
        _create_stub_bins(stub_dir)

        # First run
        result1 = _run_install(clone_dir, stub_dir, scripts_dir)
        assert result1.returncode == 0, (
            f"First install run failed (exit {result1.returncode}):\n{result1.stderr}"
        )

        # Second run
        result2 = _run_install(clone_dir, stub_dir, scripts_dir)
        assert result2.returncode == 0, (
            f"Second install run failed (exit {result2.returncode}):\n{result2.stderr}"
        )

    def test_install_twice_no_duplicate_installed_skills(self, tmp_path):
        """INSTALL-03: Double-run produces no duplicate entries in installed.json."""
        clone_dir, scripts_dir, stub_dir = _create_minimal_repo(tmp_path)
        _create_stub_bins(stub_dir)

        _run_install(clone_dir, stub_dir, scripts_dir)
        _run_install(clone_dir, stub_dir, scripts_dir)

        installed_path = clone_dir / ".claude" / "skills" / "_catalog" / "installed.json"
        data = json.loads(installed_path.read_text())
        skills = data.get("installed_skills", [])

        assert len(skills) == len(set(skills)), (
            f"installed_skills contains duplicates after double run: "
            f"{[s for s in skills if skills.count(s) > 1]}"
        )

    def test_install_twice_no_duplicate_env_lines(self, tmp_path):
        """INSTALL-03: Double-run does not double-write lines in .env."""
        clone_dir, scripts_dir, stub_dir = _create_minimal_repo(tmp_path)
        _create_stub_bins(stub_dir)

        _run_install(clone_dir, stub_dir, scripts_dir)
        _run_install(clone_dir, stub_dir, scripts_dir)

        env_file = clone_dir / ".env"
        lines = [
            line.strip() for line in env_file.read_text().splitlines()
            if "=" in line and not line.strip().startswith("#")
        ]
        assert len(lines) == len(set(lines)), (
            f".env contains duplicate key lines after double run: "
            f"{[l for l in lines if lines.count(l) > 1]}"
        )


# ---------------------------------------------------------------------------
# TestFirstRunDetection  (INSTALL-04)
# ---------------------------------------------------------------------------


class TestFirstRunDetection:
    """Tests for first-run state detection via research_context/ file-system state.

    Per CLAUDE.md heartbeat step 1: "scan research_context/ for populated .md files.
    If none exist, this is a first-time user."
    The actual routing to /start-here is Claude agent behaviour (untestable here).
    We test the file-system preconditions.
    """

    def test_empty_research_context_is_first_run(self, tmp_path):
        """INSTALL-04: research_context/ with no .md files represents first-run state."""
        research_ctx = tmp_path / "research_context"
        research_ctx.mkdir()

        # No .md files — first-run state
        md_files = list(research_ctx.glob("*.md"))
        assert len(md_files) == 0, (
            "Expected no .md files in empty research_context/, "
            f"but found: {[f.name for f in md_files]}"
        )

    def test_research_context_with_only_non_md_files_is_first_run(self, tmp_path):
        """INSTALL-04: research_context/ with non-.md files is still first-run state."""
        research_ctx = tmp_path / "research_context"
        research_ctx.mkdir()
        (research_ctx / "notes.txt").write_text("some text")
        (research_ctx / ".gitkeep").write_text("")

        md_files = list(research_ctx.glob("*.md"))
        assert len(md_files) == 0, (
            "Only .md files should trigger non-first-run detection"
        )

    def test_populated_research_context_is_not_first_run(self, tmp_path):
        """INSTALL-04: research_context/ with .md files is NOT first-run state."""
        research_ctx = tmp_path / "research_context"
        research_ctx.mkdir()
        (research_ctx / "research-profile.md").write_text(
            "# Research Profile\nField: bioinformatics\n"
        )

        md_files = list(research_ctx.glob("*.md"))
        assert len(md_files) > 0, (
            "Expected at least one .md file in populated research_context/"
        )

    def test_install_creates_empty_research_context(self, tmp_path):
        """INSTALL-04: After fresh install, research_context/ exists but has no .md files."""
        clone_dir, scripts_dir, stub_dir = _create_minimal_repo(tmp_path)
        _create_stub_bins(stub_dir)

        # Remove research_context so install.sh creates it fresh
        shutil.rmtree(clone_dir / "research_context")

        _run_install(clone_dir, stub_dir, scripts_dir)

        research_ctx = clone_dir / "research_context"
        assert research_ctx.exists(), "install.sh did not create research_context/"

        md_files = list(research_ctx.glob("*.md"))
        assert len(md_files) == 0, (
            f"install.sh wrote .md files to research_context/ — this should not happen: "
            f"{[f.name for f in md_files]}"
        )


# ---------------------------------------------------------------------------
# TestEnvExampleDocumentation  (INSTALL-05)
# ---------------------------------------------------------------------------


class TestEnvExampleDocumentation:
    """Tests for .env.example documentation completeness.

    All API keys in the CLAUDE.md Service Registry must be documented in .env.example.
    """

    def test_all_service_registry_keys_in_env_example(self):
        """INSTALL-05: Every Service Registry key appears in .env.example."""
        rows = parse_service_registry()
        assert rows, "parse_service_registry() returned no rows — check CLAUDE.md Service Registry table"

        env_example_text = ENV_EXAMPLE.read_text()

        missing = []
        for row in rows:
            api_key = row.get("API Key", "").strip()
            # Skip rows that are not API key entries (e.g. header repeats, empty)
            if not api_key or not re.match(r"^`?[A-Z][A-Z0-9_]+`?$", api_key):
                continue
            # Strip backticks if present
            api_key_clean = api_key.strip("`")
            if api_key_clean not in env_example_text:
                missing.append(api_key_clean)

        assert not missing, (
            f"These Service Registry keys are missing from .env.example: {missing}"
        )

    def test_env_example_has_descriptions(self):
        """INSTALL-05: Each key in .env.example has a comment with a description."""
        env_example_text = ENV_EXAMPLE.read_text()
        lines = env_example_text.splitlines()

        # Find KEY= lines and verify a comment appears nearby (within 3 preceding lines)
        undescribed = []
        for i, line in enumerate(lines):
            if re.match(r"^[A-Z][A-Z0-9_]+=", line):
                key_name = line.split("=")[0]
                # Look in preceding 3 lines for a # comment
                start = max(0, i - 3)
                context_lines = lines[start:i]
                has_comment = any(l.strip().startswith("#") for l in context_lines)
                if not has_comment:
                    undescribed.append(key_name)

        assert not undescribed, (
            f"These keys in .env.example have no nearby comment/description: {undescribed}"
        )

    def test_env_example_has_signup_urls(self):
        """INSTALL-05: Each API key in .env.example has a signup URL documented nearby."""
        env_example_text = ENV_EXAMPLE.read_text()
        lines = env_example_text.splitlines()

        url_pattern = re.compile(r"https?://\S+")
        missing_urls = []
        for i, line in enumerate(lines):
            if re.match(r"^[A-Z][A-Z0-9_]+=", line):
                key_name = line.split("=")[0]
                # Check the preceding 5 lines for a URL
                start = max(0, i - 5)
                context = "\n".join(lines[start:i])
                if not url_pattern.search(context):
                    missing_urls.append(key_name)

        assert not missing_urls, (
            f"These keys in .env.example have no signup URL in the preceding lines: {missing_urls}"
        )
