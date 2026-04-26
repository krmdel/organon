"""CI regression tests — negative assertions for code hygiene.

Covers CI-02 (secrets, stray files, broken symlinks, marketing refs)
and CI-03 (.gitignore coverage of user data directories).
"""

import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Section 1: Secrets detection (CI-02)
# ---------------------------------------------------------------------------

SECRET_PATTERNS = [
    r"sk-[a-zA-Z0-9]{20,}",          # OpenAI API keys
    r"AKIA[0-9A-Z]{16}",              # AWS access key IDs
    r"ghp_[a-zA-Z0-9]{36}",           # GitHub personal access tokens
    r"gho_[a-zA-Z0-9]{36}",           # GitHub OAuth tokens
    r"glpat-[a-zA-Z0-9\-_]{20,}",     # GitLab personal access tokens
    r"xai-[a-zA-Z0-9]{20,}",          # xAI API keys
]

# Files that legitimately contain key pattern examples
SECRETS_SCAN_EXCLUDE = {
    ".env.example",
    "tests/test_ci_regression.py",     # This file contains the patterns themselves
}

BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".ico",
    ".woff", ".woff2", ".ttf", ".eot", ".pyc",
}


def _get_tracked_files() -> list[str]:
    """Return list of tracked file paths from git ls-files."""
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def test_no_secrets_in_tracked_files():
    """No tracked file contains patterns that look like real secrets."""
    tracked = _get_tracked_files()

    violations = []
    for filepath in tracked:
        # Skip excluded files
        filename = Path(filepath).name
        if filepath in SECRETS_SCAN_EXCLUDE or filename in SECRETS_SCAN_EXCLUDE:
            continue
        # Skip binary files
        suffix = Path(filepath).suffix.lower()
        if suffix in BINARY_EXTENSIONS:
            continue

        abs_path = ROOT / filepath
        if not abs_path.exists():
            continue

        try:
            content = abs_path.read_text(errors="ignore")
        except (OSError, PermissionError):
            continue

        for pattern in SECRET_PATTERNS:
            if re.search(pattern, content):
                violations.append(f"{filepath} matches pattern {pattern!r}")

    assert not violations, (
        "Potential secrets found in tracked files:\n" + "\n".join(violations)
    )


def test_no_env_files_tracked():
    """Ensure .env, *.env.local, and credentials.json are not tracked by git."""
    tracked = _get_tracked_files()
    tracked_set = set(tracked)

    # .env should not be tracked (but .env.example is fine)
    assert ".env" not in tracked_set, (
        ".env is tracked by git — it must be listed in .gitignore"
    )

    # No *.env.local files tracked
    env_local = [f for f in tracked if f.endswith(".env.local")]
    assert not env_local, (
        f"*.env.local files are tracked by git: {env_local}"
    )

    # No credentials.json tracked
    creds = [f for f in tracked if Path(f).name == "credentials.json"]
    assert not creds, (
        f"credentials.json file(s) are tracked by git: {creds}"
    )


# ---------------------------------------------------------------------------
# Section 2: Stray output files at repo root (CI-02)
# ---------------------------------------------------------------------------

STRAY_EXTENSIONS = {".csv", ".xlsx", ".png", ".jpg", ".jpeg", ".pdf", ".svg", ".html"}


def test_no_stray_output_files_in_root():
    """No stray output files should exist directly in the repo root."""
    violations = []
    for f in ROOT.iterdir():
        if not f.is_file():
            continue
        if f.suffix.lower() in STRAY_EXTENSIONS:
            violations.append(f.name)

    assert not violations, (
        "Stray output files found at repo root (should be in projects/ or tests/fixtures/):\n"
        + "\n".join(f"  {name}" for name in violations)
    )


# ---------------------------------------------------------------------------
# Section 3: Broken symlinks (CI-02)
# ---------------------------------------------------------------------------

_SYMLINK_SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__"}


def test_no_broken_symlinks():
    """No broken symlinks anywhere in the repository."""
    broken = []

    for dirpath, dirnames, filenames in os.walk(ROOT):
        # Prune skip dirs in place
        dirnames[:] = [
            d for d in dirnames
            if d not in _SYMLINK_SKIP_DIRS
        ]

        # Check all entries (files + any remaining dirs that are symlinks)
        for name in filenames + dirnames:
            entry = os.path.join(dirpath, name)
            if os.path.islink(entry) and not os.path.exists(entry):
                broken.append(os.path.relpath(entry, ROOT))

    assert not broken, (
        "Broken symlinks found:\n" + "\n".join(f"  {p}" for p in broken)
    )


# ---------------------------------------------------------------------------
# Section 4: Marketing refs cross-check (CI-02)
# ---------------------------------------------------------------------------

MARKETING_PATTERNS = [
    "mkt-brand-voice",
    "mkt-content-repurposing",
    "mkt-copywriting",
    "mkt-icp",
    "mkt-positioning",
    "mkt-ugc-scripts",
    "str-trending-research",
    "viz-ugc-heygen",
]

_MARKETING_SOURCE_EXTS = {".py", ".md", ".yml", ".yaml", ".json", ".sh"}
# Exclude this file and test files that contain legacy patterns as negative fixtures
_MARKETING_SCAN_EXCLUDE_PATHS = {
    "tests/test_ci_regression.py",
    "tests/test_full_framework.py",    # contains legacy names in negative test lists
    "tests/test_skill_routing.py",     # contains legacy names in negative test lists
    "tests/test_workflow_scenarios.py", # contains legacy names in negative test fixtures
}
_MARKETING_SCAN_EXCLUDE_PREFIXES = {".planning"}


def test_no_marketing_refs_in_source():
    """No tracked source files reference removed marketing skill names."""
    tracked = _get_tracked_files()

    violations = []
    for filepath in tracked:
        # Skip explicitly excluded files (this file + test files with legacy fixtures)
        if filepath in _MARKETING_SCAN_EXCLUDE_PATHS:
            continue
        # Skip excluded directory prefixes (e.g. .planning/)
        if any(filepath.startswith(prefix) for prefix in _MARKETING_SCAN_EXCLUDE_PREFIXES):
            continue

        # Only scan source file types
        if Path(filepath).suffix.lower() not in _MARKETING_SOURCE_EXTS:
            continue

        abs_path = ROOT / filepath
        if not abs_path.exists():
            continue

        try:
            content = abs_path.read_text(errors="ignore")
        except (OSError, PermissionError):
            continue

        for pattern in MARKETING_PATTERNS:
            if pattern in content:
                violations.append(f"{filepath}: found {pattern!r}")

    assert not violations, (
        "Marketing skill references found in source files:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


# ---------------------------------------------------------------------------
# Section 5: .gitignore coverage (CI-03)
# ---------------------------------------------------------------------------


def _check_ignored(path: str) -> bool:
    """Return True if git check-ignore exits 0 (path is ignored)."""
    result = subprocess.run(
        ["git", "check-ignore", "-q", path],
        cwd=ROOT,
        capture_output=True,
    )
    return result.returncode == 0


def test_gitignore_covers_user_data_dirs():
    """All user data directories listed in CLAUDE.md are covered by .gitignore."""
    required_ignored = [
        "context/memory/2026-01-01.md",
        "research_context/research-profile.md",
        ".env",
        "projects/test-output.md",
        ".claude/skills/_catalog/installed.json",
    ]

    not_ignored = []
    for path in required_ignored:
        if not _check_ignored(path):
            not_ignored.append(path)

    assert not not_ignored, (
        "These paths are NOT covered by .gitignore:\n"
        + "\n".join(f"  {p}" for p in not_ignored)
    )


def test_gitignore_does_not_cover_source():
    """Critical source files must NOT be ignored by .gitignore."""
    must_be_tracked = [
        "CLAUDE.md",
        "tests/conftest.py",
        ".env.example",
        "scripts/install.sh",
    ]

    incorrectly_ignored = []
    for path in must_be_tracked:
        if _check_ignored(path):
            incorrectly_ignored.append(path)

    assert not incorrectly_ignored, (
        "These source files are incorrectly ignored by .gitignore:\n"
        + "\n".join(f"  {p}" for p in incorrectly_ignored)
    )


def test_venv_and_cache_ignored():
    """Virtual env and Python cache directories are ignored by .gitignore."""
    paths_that_must_be_ignored = [
        ".venv/some_file.py",
        "__pycache__/module.pyc",
    ]

    not_ignored = []
    for path in paths_that_must_be_ignored:
        if not _check_ignored(path):
            not_ignored.append(path)

    assert not not_ignored, (
        "These paths should be ignored but are not:\n"
        + "\n".join(f"  {p}" for p in not_ignored)
    )
