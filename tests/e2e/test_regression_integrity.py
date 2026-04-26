"""E.9 — Integrity regression tests.

Per context/memory/organon_upgrade_final_handoff.md §3.9. Specific
invariants that have been broken before or could silently break in
refactors:

  - CLAUDE.md Skill Registry ↔ disk parity (catches Reconciliation drift).
  - CLAUDE.md Context Matrix ↔ Registry parity.
  - SKILL.md YAML frontmatter ≤ 1024 chars (Anthropic's hard limit).
  - SKILL.md body ≤ 200 lines (soft rule; tracked with an allowlist).
  - References / tests / catalog consistency.
  - Smoke transcripts cross-reference real pytest tests.

These tests are fast and no-data; they run on every clone.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
CATALOG = SKILLS_DIR / "_catalog" / "catalog.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _skill_folders() -> list[str]:
    return sorted(
        d.name for d in SKILLS_DIR.iterdir()
        if d.is_dir() and not d.name.startswith("_")
    )


_SKILL_PREFIXES = ("sci-", "viz-", "tool-", "meta-", "ops-")


def _registry_section() -> str:
    text = CLAUDE_MD.read_text()
    start = text.find("## Skill Registry")
    end = text.find("## Context Matrix")
    assert start >= 0 and end > start, "CLAUDE.md missing Skill Registry / Context Matrix headers"
    return text[start:end]


def _context_matrix_section() -> str:
    text = CLAUDE_MD.read_text()
    start = text.find("## Context Matrix")
    end = text.find("## Output Standards")
    assert start >= 0 and end > start, "CLAUDE.md missing Context Matrix / Output Standards headers"
    return text[start:end]


def _extract_backtick_names(blob: str) -> set[str]:
    names = set()
    for m in re.finditer(r"`([a-z][a-z0-9-]+)`", blob):
        n = m.group(1)
        if any(n.startswith(p) for p in _SKILL_PREFIXES):
            names.add(n)
    return names


# ---------------------------------------------------------------------------
# E.9.1 — Registry ↔ disk consistency
# ---------------------------------------------------------------------------

# Skills intentionally excluded from the public repo via .gitignore. These
# may exist on disk (local install) or only in CLAUDE.md (CI clone), so the
# consistency check exempts them from both directions: a registry row
# without the folder is fine (CI), and a folder without a registry row is
# fine (local install where the user added/dropped the row).
_GITIGNORED_SKILLS = {"tool-substack", "tool-social-publisher"}


def test_e9_1_registry_disk_consistency():
    registry = _extract_backtick_names(_registry_section())
    disk = set(_skill_folders())
    missing_on_disk = (registry - disk) - _GITIGNORED_SKILLS
    missing_in_registry = (disk - registry) - _GITIGNORED_SKILLS
    assert not missing_on_disk, (
        f"Skill Registry names with no folder: {sorted(missing_on_disk)}"
    )
    assert not missing_in_registry, (
        f"Skill folders with no Registry row: {sorted(missing_in_registry)}"
    )


# ---------------------------------------------------------------------------
# E.9.2 — Context Matrix ↔ Registry parity
# ---------------------------------------------------------------------------

def test_e9_2_context_matrix_parity():
    registry = _extract_backtick_names(_registry_section())
    matrix = _extract_backtick_names(_context_matrix_section())
    missing_in_matrix = registry - matrix
    assert not missing_in_matrix, (
        f"Registry rows missing from Context Matrix: {sorted(missing_in_matrix)}"
    )


# ---------------------------------------------------------------------------
# E.9.3 — SKILL.md YAML frontmatter ≤ 1024 chars
# ---------------------------------------------------------------------------

def _parse_frontmatter(path: Path) -> tuple[str, str] | None:
    text = path.read_text()
    m = re.match(r"^---\n(.*?\n)---\n(.*)", text, re.DOTALL)
    if not m:
        return None
    return m.group(1), m.group(2)


@pytest.mark.parametrize("skill", _skill_folders())
def test_e9_3_yaml_frontmatter_under_1024(skill):
    sm = SKILLS_DIR / skill / "SKILL.md"
    assert sm.is_file(), f"{skill}: SKILL.md missing"
    fm = _parse_frontmatter(sm)
    assert fm is not None, f"{skill}: SKILL.md has no YAML frontmatter"
    assert len(fm[0]) <= 1024, (
        f"{skill}: frontmatter is {len(fm[0])} chars (CLAUDE.md rule: ≤ 1024)"
    )


# ---------------------------------------------------------------------------
# E.9.4 — SKILL.md body ≤ 200 lines (allowlist documents current debt)
# ---------------------------------------------------------------------------

# Skills currently over the 200-line rule as of 2026-04-22. Trimming one of
# these below 200 should make the test tighten automatically; adding a NEW
# skill that ships > 200 lines trips the test.
_OVERSIZE_ALLOWLIST = {
    "sci-communication",
    "sci-literature-research",
    "sci-trending-research",
    "tool-paperclip",
    "viz-presentation",
}


@pytest.mark.parametrize("skill", _skill_folders())
def test_e9_4_skill_md_body_under_200(skill):
    sm = SKILLS_DIR / skill / "SKILL.md"
    fm = _parse_frontmatter(sm)
    assert fm is not None
    body_lines = len(fm[1].splitlines())
    if skill in _OVERSIZE_ALLOWLIST:
        # Documented debt — assert it still exceeds 200 (prompts trim when fixed).
        if body_lines <= 200:
            pytest.fail(
                f"{skill} now ≤ 200 lines ({body_lines}) — remove it from "
                "_OVERSIZE_ALLOWLIST in tests/e2e/test_regression_integrity.py"
            )
        return
    assert body_lines <= 200, (
        f"{skill}: SKILL.md body is {body_lines} lines (rule: ≤ 200). "
        "If this is intentional debt, add to _OVERSIZE_ALLOWLIST."
    )


# ---------------------------------------------------------------------------
# E.9.5 — Every skill has a non-empty references/ folder (with allowlist)
# ---------------------------------------------------------------------------

_NO_REFERENCES_ALLOWLIST = {
    "meta-wrap-up",
    "sci-optimization",  # currently empty references/
    "tool-gdrive",
    "tool-obsidian",
    "tool-paperclip",
    "tool-youtube",
}


@pytest.mark.parametrize("skill", _skill_folders())
def test_e9_5_skill_has_references(skill):
    refs = SKILLS_DIR / skill / "references"
    has_any = refs.is_dir() and any(refs.glob("*.md"))
    if skill in _NO_REFERENCES_ALLOWLIST:
        # No-op — this skill is documented as lacking references/ for now.
        return
    assert has_any, (
        f"{skill}: references/ missing or empty "
        "(add reference docs or allowlist in _NO_REFERENCES_ALLOWLIST)"
    )


# ---------------------------------------------------------------------------
# E.9.6 — TDD skills have ≥ 1 test file
# ---------------------------------------------------------------------------

TDD_SKILLS = [
    "ops-parallel-tempering-sa",
    "ops-ulp-polish",
    "sci-council",
    "sci-literature-research",
    "sci-optimization-recipes",
    "tool-arena-runner",
    "tool-einstein-arena",
]


@pytest.mark.parametrize("skill", TDD_SKILLS)
def test_e9_6_tdd_skill_has_tests(skill):
    tests_dir = SKILLS_DIR / skill / "tests"
    assert tests_dir.is_dir(), f"{skill}: tests/ missing"
    test_files = list(tests_dir.glob("test_*.py"))
    assert test_files, f"{skill}: tests/ has no test_*.py"


# ---------------------------------------------------------------------------
# E.9.7 — Catalog consistency with disk + Registry
# ---------------------------------------------------------------------------

def test_e9_7_catalog_consistency():
    assert CATALOG.is_file(), f"missing {CATALOG}"
    data = json.loads(CATALOG.read_text())
    catalog_skills = set(data.get("skills", {}).keys())
    disk = set(_skill_folders())
    registry = _extract_backtick_names(_registry_section())

    # Every catalog entry has a folder on disk (gitignored skills exempt).
    missing_on_disk = (catalog_skills - disk) - _GITIGNORED_SKILLS
    assert not missing_on_disk, (
        f"catalog entries with no folder: {sorted(missing_on_disk)}"
    )
    # Every catalog entry is in the Registry (gitignored skills exempt).
    missing_in_registry = (catalog_skills - registry) - _GITIGNORED_SKILLS
    assert not missing_in_registry, (
        f"catalog entries missing from Registry: {sorted(missing_in_registry)}"
    )


# ---------------------------------------------------------------------------
# E.9.8 — Smoke transcripts cross-reference a real pytest test
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("skill", TDD_SKILLS)
def test_e9_8_smoke_transcript_cross_refs_pytest(skill):
    refs = SKILLS_DIR / skill / "references"
    transcripts = list(refs.glob("smoke-transcript*.md")) if refs.is_dir() else []
    if not transcripts:
        pytest.skip(f"{skill}: no smoke-transcript*.md files")
    for tr in transcripts:
        text = tr.read_text()
        assert "pytest" in text or "tests/test_" in text or "test_" in text, (
            f"{tr}: no cross-reference to pytest / tests/test_ / test_*.py"
        )


# ---------------------------------------------------------------------------
# E.9.9 — All TDD-skill unit test suites green
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_e9_9_all_tdd_unit_suites_green():
    """Belt-and-braces: programmatically run each TDD skill's tests/ folder
    and assert every invocation returns 0. ~0.5–1s per suite."""
    for skill in TDD_SKILLS:
        tests_dir = SKILLS_DIR / skill / "tests"
        if not tests_dir.is_dir():
            continue
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(tests_dir), "-q", "--tb=short"],
            capture_output=True, text=True, timeout=120,
        )
        assert result.returncode == 0, (
            f"{skill}: unit suite failed (exit {result.returncode})\n"
            f"stdout tail: {result.stdout[-600:]}\n"
            f"stderr tail: {result.stderr[-200:]}"
        )
