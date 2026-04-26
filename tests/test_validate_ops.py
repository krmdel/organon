"""Tests for sci-tools validate_ops module."""

import os
import sys
import textwrap

import pytest

# Add sci-tools scripts to path
sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(__file__),
        "..",
        ".claude",
        "skills",
        "sci-tools",
        "scripts",
    ),
)

from validate_ops import check_trigger_conflicts, get_scientific_defaults, validate_skill


def _write_skill_md(skill_dir, content):
    """Helper to write a SKILL.md file in a skill directory."""
    os.makedirs(skill_dir, exist_ok=True)
    with open(os.path.join(skill_dir, "SKILL.md"), "w") as f:
        f.write(textwrap.dedent(content))


VALID_SKILL_MD = """\
---
name: sci-example
description: >
  A valid example skill for testing.
  Triggers on: "example", "test example".
---

# Example Skill

## Outcome

Does example things. Outputs to `projects/sci-example/`.
"""

# --- validate_skill tests ---


def test_validate_valid_skill(tmp_path):
    """A well-formed skill dir returns no errors and no warnings."""
    skill_dir = tmp_path / "sci-example"
    _write_skill_md(str(skill_dir), VALID_SKILL_MD)
    errors, warnings = validate_skill(str(skill_dir))
    assert errors == []
    assert warnings == []


def test_validate_missing_skill_md(tmp_path):
    """A dir without SKILL.md returns error containing 'Missing SKILL.md'."""
    skill_dir = tmp_path / "sci-empty"
    skill_dir.mkdir()
    errors, warnings = validate_skill(str(skill_dir))
    assert any("Missing SKILL.md" in e for e in errors)


def test_validate_missing_frontmatter(tmp_path):
    """SKILL.md without --- frontmatter returns error about frontmatter."""
    skill_dir = tmp_path / "sci-nofm"
    _write_skill_md(
        str(skill_dir),
        """\
    # No Frontmatter Here

    Just a regular markdown file.
    """,
    )
    errors, warnings = validate_skill(str(skill_dir))
    assert any("Missing YAML frontmatter" in e for e in errors)


def test_validate_missing_name(tmp_path):
    """Frontmatter missing 'name' field returns error about missing name."""
    skill_dir = tmp_path / "sci-noname"
    _write_skill_md(
        str(skill_dir),
        """\
---
description: A skill without a name field.
---

# No Name
""",
    )
    errors, warnings = validate_skill(str(skill_dir))
    assert any("Missing 'name'" in e for e in errors)


def test_validate_missing_description(tmp_path):
    """Frontmatter missing 'description' returns error about missing description."""
    skill_dir = tmp_path / "sci-nodesc"
    _write_skill_md(
        str(skill_dir),
        """\
---
name: sci-nodesc
---

# No Description
""",
    )
    errors, warnings = validate_skill(str(skill_dir))
    assert any("Missing 'description'" in e for e in errors)


def test_validate_name_mismatch(tmp_path):
    """Frontmatter name != folder name returns error with '!= folder name'."""
    skill_dir = tmp_path / "sci-actual"
    _write_skill_md(
        str(skill_dir),
        """\
---
name: sci-wrong
description: Name doesn't match folder.
---

# Mismatch
""",
    )
    errors, warnings = validate_skill(str(skill_dir))
    assert any("!= folder name" in e for e in errors)


def test_validate_bad_folder_format(tmp_path):
    """Folder not matching {category}-{name} pattern returns error."""
    skill_dir = tmp_path / "BadFolderName"
    _write_skill_md(
        str(skill_dir),
        """\
---
name: BadFolderName
description: Bad folder naming.
---

# Bad Name
""",
    )
    errors, warnings = validate_skill(str(skill_dir))
    assert any("kebab-case" in e.lower() or "must be" in e.lower() for e in errors)


# --- check_trigger_conflicts tests ---


def test_check_trigger_conflicts_found(tmp_path, monkeypatch):
    """Overlapping triggers return conflicts with skill name."""
    # Create a mock skills directory with an existing skill
    skills_dir = tmp_path / "skills"
    existing_skill = skills_dir / "sci-existing"
    _write_skill_md(
        str(existing_skill),
        """\
---
name: sci-existing
description: >
  Triggers on: "analyze data", "run analysis", "statistics".
---

# Existing Skill
""",
    )

    # Create the new skill being checked
    new_skill = skills_dir / "sci-new"
    _write_skill_md(
        str(new_skill),
        """\
---
name: sci-new
description: >
  Triggers on: "analyze data", "plot chart".
---

# New Skill
""",
    )

    # Monkeypatch SKILLS_DIR to use our tmp dir
    import validate_ops

    monkeypatch.setattr(validate_ops, "SKILLS_DIR", skills_dir)

    conflicts = check_trigger_conflicts(
        str(new_skill), trigger_phrases=["analyze data", "plot chart"]
    )
    assert len(conflicts) > 0
    assert any(c["conflicts_with"] == "sci-existing" for c in conflicts)
    assert any(c["phrase"] == "analyze data" for c in conflicts)


def test_check_trigger_conflicts_none(tmp_path, monkeypatch):
    """Unique triggers return empty conflict list."""
    skills_dir = tmp_path / "skills"
    existing_skill = skills_dir / "sci-existing"
    _write_skill_md(
        str(existing_skill),
        """\
---
name: sci-existing
description: >
  Triggers on: "literature search", "find papers".
---

# Existing
""",
    )

    new_skill = skills_dir / "sci-unique"
    _write_skill_md(
        str(new_skill),
        """\
---
name: sci-unique
description: >
  Triggers on: "totally unique phrase".
---

# Unique
""",
    )

    import validate_ops

    monkeypatch.setattr(validate_ops, "SKILLS_DIR", skills_dir)

    conflicts = check_trigger_conflicts(
        str(new_skill), trigger_phrases=["totally unique phrase"]
    )
    assert conflicts == []


# --- get_scientific_defaults tests ---


def test_get_scientific_defaults():
    """Returns dict with correct scientific defaults."""
    defaults = get_scientific_defaults()
    assert defaults["category_prefix"] == "sci-"
    assert defaults["output_path_prefix"] == "projects/sci-"
    assert any(
        "research-profile.md" in cn["file"] for cn in defaults["context_needs"]
    )
    assert defaults["has_reproducibility_logging"] is True


# --- Regex fallback parser tests (no PyYAML) ---


from validate_ops import _parse_frontmatter, _extract_triggers_from_skill


class TestRegexFallbackParser:
    """Tests for _parse_frontmatter when PyYAML is unavailable (regex path)."""

    def _force_regex_path(self, monkeypatch):
        """Monkeypatch yaml to None to force regex fallback."""
        import validate_ops

        monkeypatch.setattr(validate_ops, "yaml", None)

    def test_folded_scalar_description(self, monkeypatch):
        """Folded scalar (>) joins continuation lines with spaces, not 'present'."""
        self._force_regex_path(monkeypatch)
        fm_text = "name: sci-test\ndescription: >\n  line one\n  line two\ncategory: sci"
        parsed, err = _parse_frontmatter(fm_text)
        assert err is None
        assert parsed["description"] != "present"
        assert "line one" in parsed["description"]
        assert "line two" in parsed["description"]
        # Folded: joined with spaces
        assert "line one line two" == parsed["description"]

    def test_literal_scalar_description(self, monkeypatch):
        """Literal scalar (|) preserves newlines in continuation lines."""
        self._force_regex_path(monkeypatch)
        fm_text = "name: sci-test\ndescription: |\n  line one\n  line two\ncategory: sci"
        parsed, err = _parse_frontmatter(fm_text)
        assert err is None
        assert "line one" in parsed["description"]
        assert "line two" in parsed["description"]
        # Literal: joined with newlines
        assert "line one\nline two" == parsed["description"]

    def test_inline_description(self, monkeypatch):
        """Inline value returns the text directly."""
        self._force_regex_path(monkeypatch)
        fm_text = "name: sci-test\ndescription: simple text here\ncategory: sci"
        parsed, err = _parse_frontmatter(fm_text)
        assert err is None
        assert parsed["description"] == "simple text here"

    def test_quoted_inline_description(self, monkeypatch):
        """Quoted inline value has quotes stripped."""
        self._force_regex_path(monkeypatch)
        fm_text = 'name: sci-test\ndescription: "quoted text"\ncategory: sci'
        parsed, err = _parse_frontmatter(fm_text)
        assert err is None
        assert parsed["description"] == "quoted text"

    def test_check_trigger_conflicts_regex_path(self, tmp_path, monkeypatch):
        """check_trigger_conflicts finds real conflicts when PyYAML is unavailable."""
        import validate_ops

        monkeypatch.setattr(validate_ops, "yaml", None)

        # Create mock skills directory with an existing skill using folded description
        skills_dir = tmp_path / "skills"
        existing_skill = skills_dir / "sci-existing-skill"
        _write_skill_md(
            str(existing_skill),
            """\
---
name: sci-existing-skill
description: >
  Research profile analysis and creation.
  Triggers on: "research profile", "field", "writing style".
---

# Research Profile
""",
        )

        new_skill = skills_dir / "sci-new"
        new_skill.mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(validate_ops, "SKILLS_DIR", skills_dir)

        conflicts = check_trigger_conflicts(
            str(new_skill), trigger_phrases=["research profile"]
        )
        assert len(conflicts) > 0
        assert any(c["conflicts_with"] == "sci-existing-skill" for c in conflicts)

    def test_extract_triggers_from_folded_description(self, tmp_path, monkeypatch):
        """_extract_triggers_from_skill extracts quoted phrases from folded description."""
        import validate_ops

        monkeypatch.setattr(validate_ops, "yaml", None)

        skill_dir = tmp_path / "sci-example"
        _write_skill_md(
            str(skill_dir),
            """\
---
name: sci-example
description: >
  A valid example skill for testing.
  Triggers on: "example", "test example".
---

# Example
""",
        )

        triggers = _extract_triggers_from_skill(str(skill_dir))
        assert "example" in triggers
        assert "test example" in triggers
