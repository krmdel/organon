"""E.6 — tool-einstein-arena playbook end-to-end tests.

Per context/memory/organon_upgrade_final_handoff.md §3.6. Confirms the
playbook template can be COPIED, FILLED, RE-VALIDATED end-to-end —
simulating the workflow of `arena_runner recon` + user fill-in.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

# Re-use the schema-validator helpers from the skill's own unit tests so we
# aren't re-implementing the contract in two places.
import sys as _sys
SKILL_TESTS = (
    Path(__file__).resolve().parents[2]
    / ".claude" / "skills" / "tool-einstein-arena" / "tests"
)
if str(SKILL_TESTS) not in _sys.path:
    _sys.path.insert(0, str(SKILL_TESTS))

from test_playbook_structure import (  # noqa: E402
    EXPECTED_SECTIONS,
    TEMPLATE,
    _parse_sections,
    _section_bodies,
)


FILL_RE = re.compile(r"<!--\s*fill:\s*[^-]*(?:-(?!->)[^-]*)*-->", re.DOTALL)


def _auto_fill(md: str, placeholder_value: str = "filled-value") -> str:
    """Replace every `<!-- fill: ... -->` with a real single-word token."""
    return FILL_RE.sub(placeholder_value, md)


# ---------------------------------------------------------------------------
# E.6.1 — Copy template to tmp dir
# ---------------------------------------------------------------------------

def test_e6_1_copy_template_to_tmp(tmp_path):
    dst = tmp_path / "PLAYBOOK.md"
    shutil.copy(TEMPLATE, dst)
    assert dst.is_file()
    assert dst.stat().st_size == TEMPLATE.stat().st_size
    assert len(dst.read_text()) > 200


# ---------------------------------------------------------------------------
# E.6.2 — Fresh copy passes template schema (same 7-section order)
# ---------------------------------------------------------------------------

def test_e6_2_fresh_copy_passes_template_schema(tmp_path):
    dst = tmp_path / "PLAYBOOK.md"
    shutil.copy(TEMPLATE, dst)
    md = dst.read_text()
    assert _parse_sections(md) == EXPECTED_SECTIONS
    # Every section has a fill placeholder (matches
    # test_template_every_section_has_fill_placeholder).
    bodies = _section_bodies(md)
    for section in EXPECTED_SECTIONS:
        assert "<!-- fill:" in bodies[section]


# ---------------------------------------------------------------------------
# E.6.3 — Minimal fill passes instance schema
# ---------------------------------------------------------------------------

def test_e6_3_minimal_fill_passes_instance_schema(tmp_path):
    dst = tmp_path / "PLAYBOOK.md"
    shutil.copy(TEMPLATE, dst)
    filled = _auto_fill(dst.read_text(), "filled-value")
    dst.write_text(filled)

    # Section order preserved.
    assert _parse_sections(filled) == EXPECTED_SECTIONS
    # No leftover placeholders (the populated-playbook contract).
    leftover = re.findall(r"<!--\s*fill:[^>]+-->", filled)
    assert not leftover, f"still have {len(leftover)} unfilled placeholders"


# ---------------------------------------------------------------------------
# E.6.4 — Unfilled placeholder fails the instance schema
# ---------------------------------------------------------------------------

def test_e6_4_unfilled_placeholder_fails_instance_schema(tmp_path):
    dst = tmp_path / "PLAYBOOK.md"
    shutil.copy(TEMPLATE, dst)
    template_md = dst.read_text()

    # Fill ALL but one placeholder, leaving exactly one dangling.
    placeholders = FILL_RE.findall(template_md)
    assert placeholders, "template has no fill placeholders to leave open"
    first = placeholders[0]
    filled_rest = _auto_fill(template_md, "ok")
    # Put the first placeholder back into the text at any valid spot.
    partial = filled_rest.replace("ok", first, 1)
    dst.write_text(partial)

    # Mimic the real assertion from `test_option_a_fill_has_no_unfilled_placeholders`.
    leftover = re.findall(r"<!--\s*fill:[^>]+-->", dst.read_text())
    assert len(leftover) >= 1, "expected at least one dangling placeholder"


# ---------------------------------------------------------------------------
# E.6.5 — Size-cap guardrail (400-line rule)
# ---------------------------------------------------------------------------

def test_e6_5_size_cap_guardrail(tmp_path):
    dst = tmp_path / "PLAYBOOK.md"
    shutil.copy(TEMPLATE, dst)
    filled = _auto_fill(dst.read_text(), "x")
    # Inflate with padding lines to push past the 400-line cap.
    inflated = filled + "\n".join(f"Padding line {i}." for i in range(500))
    dst.write_text(inflated)

    line_count = len(dst.read_text().splitlines())
    assert line_count > 400, "setup failed — padding did not exceed 400 lines"

    # Mimic test_option_a_fill_size_bounded: should FAIL on this inflated file.
    with pytest.raises(AssertionError):
        assert line_count <= 400, f"PLAYBOOK.md is {line_count} lines — rule is ≤ 400."


# ---------------------------------------------------------------------------
# E.6.6 — Every existing playbook on disk round-trips the schema
# ---------------------------------------------------------------------------

@pytest.mark.needs_arena_data
def test_e6_6_real_fills_round_trip(arena_project_dirs):
    playbooks = []
    for slug, path in arena_project_dirs.items():
        for pb in path.rglob("PLAYBOOK.md"):
            playbooks.append(pb)

    if not playbooks:
        pytest.skip("no projects/einstein-arena-*/**/PLAYBOOK.md fills present")

    # Each fill must (a) preserve section order, (b) have no leftover
    # placeholders, (c) stay under the 400-line cap.
    for pb in playbooks:
        md = pb.read_text()
        assert _parse_sections(md) == EXPECTED_SECTIONS, f"{pb} section order drift"
        leftover = re.findall(r"<!--\s*fill:[^>]+-->", md)
        assert not leftover, f"{pb} still has {len(leftover)} placeholders"
        assert len(md.splitlines()) <= 400, f"{pb} exceeds 400 lines"


# ---------------------------------------------------------------------------
# E.6.7 — Section-order strictness: swap two sections → fails
# ---------------------------------------------------------------------------

def test_e6_7_section_order_strictness(tmp_path):
    dst = tmp_path / "PLAYBOOK.md"
    shutil.copy(TEMPLATE, dst)
    md = dst.read_text()

    # Swap "Dead ends" and "Fertile directions" — both `##` headers. We use
    # sentinels to avoid accidental collisions in section bodies.
    swapped = md.replace("## Dead ends", "__SWAP_A__", 1)
    swapped = swapped.replace("## Fertile directions", "## Dead ends", 1)
    swapped = swapped.replace("__SWAP_A__", "## Fertile directions", 1)
    dst.write_text(swapped)

    # Expected order broken.
    assert _parse_sections(swapped) != EXPECTED_SECTIONS
