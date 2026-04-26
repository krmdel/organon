"""Schema tests for the arena playbook template.

Every populated playbook MUST share the same 7-section structure as the
template at assets/playbook-template.md. The tests validate BOTH the template
and the option_a retroactive fill at projects/einstein-arena-difference-bases/
option_a/PLAYBOOK.md — if either one drifts from the schema, CI fails.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
TEMPLATE = REPO_ROOT / ".claude/skills/tool-einstein-arena/assets/playbook-template.md"
OPTION_A_FILL = (
    REPO_ROOT / "projects/einstein-arena-difference-bases/option_a/PLAYBOOK.md"
)

EXPECTED_SECTIONS = [
    "Problem",
    "SOTA snapshot",
    "Approaches tried",
    "Dead ends",
    "Fertile directions",
    "Open questions",
    "Submissions",
]


def _parse_sections(md: str) -> list[str]:
    """Return top-level ## section titles in document order."""
    return re.findall(r"^##\s+(.+?)\s*$", md, flags=re.MULTILINE)


def _section_bodies(md: str) -> dict[str, str]:
    """Return {section_title: body_text} for every ## section in order."""
    parts = re.split(r"(?m)^##\s+(.+?)\s*$", md)
    out: dict[str, str] = {}
    it = iter(parts[1:])
    for title in it:
        body = next(it, "")
        out[title.strip()] = body
    return out


@pytest.fixture(scope="module")
def template_md() -> str:
    assert TEMPLATE.exists(), f"missing template at {TEMPLATE}"
    return TEMPLATE.read_text()


@pytest.fixture(scope="module")
def option_a_md() -> str:
    # projects/ is gitignored — on fresh clones the fill won't exist. Skip
    # the instance tests in that case; they're a local-only guardrail.
    if not OPTION_A_FILL.exists():
        pytest.skip(f"local fill not present at {OPTION_A_FILL} (projects/ is gitignored)")
    return OPTION_A_FILL.read_text()


def test_template_exists_and_nonempty(template_md):
    assert len(template_md) > 200, "template is suspiciously short"


def test_template_has_exact_section_order(template_md):
    assert _parse_sections(template_md) == EXPECTED_SECTIONS


def test_template_every_section_has_fill_placeholder(template_md):
    bodies = _section_bodies(template_md)
    for section in EXPECTED_SECTIONS:
        body = bodies[section]
        assert "<!-- fill:" in body, (
            f"section {section!r} has no <!-- fill: ... --> placeholder"
        )


def test_template_no_filled_content_where_placeholder_expected(template_md):
    """Template must not accidentally ship populated rows —
    every non-header line inside tables should be a placeholder, not real data."""
    bodies = _section_bodies(template_md)
    for section in ("Problem", "SOTA snapshot", "Submissions"):
        body = bodies[section]
        for line in body.splitlines():
            # skip header rows, separator rows, blank lines, and HTML comments
            stripped = line.strip()
            if not stripped or stripped.startswith("<!--"):
                continue
            if re.match(r"^\|\s*[-\s|]+\|\s*$", stripped):  # table separator
                continue
            if re.match(r"^\|\s*(Field|Date|Approach)\s*\|", stripped):  # headers
                continue
            if stripped.startswith("|"):
                # every data row in a template should contain a fill-placeholder
                assert "<!-- fill:" in line, (
                    f"template {section!r} has populated-looking row: {stripped!r}"
                )


def test_option_a_fill_has_exact_section_order(option_a_md):
    assert _parse_sections(option_a_md) == EXPECTED_SECTIONS


def test_option_a_fill_every_section_nonempty(option_a_md):
    bodies = _section_bodies(option_a_md)
    for section in EXPECTED_SECTIONS:
        body = bodies[section]
        # strip out pure HTML comments + blanks — the remainder must be non-empty
        meaningful = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL).strip()
        assert meaningful, f"section {section!r} in option_a fill is empty"


def test_option_a_fill_has_no_unfilled_placeholders(option_a_md):
    """A populated playbook should have consumed every <!-- fill: ... --> placeholder."""
    leftover = re.findall(r"<!--\s*fill:[^>]+-->", option_a_md)
    assert not leftover, f"populated playbook still has {len(leftover)} unfilled placeholders"


def test_template_section_count_bounded(template_md):
    sections = _parse_sections(template_md)
    assert 1 <= len(sections) <= 12, "template section count should stay tight (1-12)"


def test_option_a_fill_size_bounded(option_a_md):
    """Guardrail: playbooks should stay under 400 lines."""
    line_count = len(option_a_md.splitlines())
    assert line_count <= 400, (
        f"option_a PLAYBOOK.md is {line_count} lines — template rule is ≤ 400."
    )
