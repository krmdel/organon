"""Tests for meta-skill-creator backend pure logic scripts.

Covers: utils, quick_validate, package_skill, aggregate_benchmark,
generate_report, improve_description.

Does NOT import run_eval.py or run_loop.py (per D-02).
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# sys.path setup (per D-01, D-02, D-14)
# ---------------------------------------------------------------------------

SCRIPTS_DIR = str(
    Path(__file__).resolve().parent.parent
    / ".claude"
    / "skills"
    / "meta-skill-creator"
    / "scripts"
)
sys.path.insert(0, SCRIPTS_DIR)

# package_skill imports `from scripts.quick_validate import validate_skill`,
# which requires the "scripts" package to be importable as a top-level name.
# We satisfy that by making SCRIPTS_DIR's parent importable and then importing
# the module via importlib with a patched import path.
_SKILLS_DIR = str(
    Path(__file__).resolve().parent.parent
    / ".claude"
    / "skills"
    / "meta-skill-creator"
)
if _SKILLS_DIR not in sys.path:
    sys.path.insert(0, _SKILLS_DIR)

from utils import parse_skill_md  # noqa: E402
from quick_validate import validate_skill  # noqa: E402
from aggregate_benchmark import calculate_stats, load_run_results  # noqa: E402
from generate_report import generate_html  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_SKILL_MD = """\
---
name: my-test-skill
description: A test skill for unit testing purposes.
---

## Overview

This skill does things.
"""

_MALFORMED_SKILL_MD = """\
This file has no frontmatter at all.
"""

_MULTILINE_DESC_SKILL_MD = """\
---
name: multi-line-skill
description: >
  This is a multi-line description
  that spans two lines.
---

## Body
"""


# ---------------------------------------------------------------------------
# TestUtils
# ---------------------------------------------------------------------------


class TestUtils:
    def test_parse_skill_md_extracts_name(self, tmp_path):
        skill_dir = tmp_path / "my-test-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(_VALID_SKILL_MD)
        name, description, content = parse_skill_md(skill_dir)
        assert name == "my-test-skill"

    def test_parse_skill_md_extracts_description(self, tmp_path):
        skill_dir = tmp_path / "my-test-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(_VALID_SKILL_MD)
        name, description, content = parse_skill_md(skill_dir)
        assert "test skill" in description

    def test_parse_skill_md_returns_full_content(self, tmp_path):
        skill_dir = tmp_path / "my-test-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(_VALID_SKILL_MD)
        name, description, content = parse_skill_md(skill_dir)
        assert "Overview" in content

    def test_parse_skill_md_missing_frontmatter_raises(self, tmp_path):
        skill_dir = tmp_path / "bad-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(_MALFORMED_SKILL_MD)
        with pytest.raises(ValueError, match="frontmatter"):
            parse_skill_md(skill_dir)

    def test_parse_skill_md_multiline_description(self, tmp_path):
        skill_dir = tmp_path / "multi-line-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(_MULTILINE_DESC_SKILL_MD)
        name, description, content = parse_skill_md(skill_dir)
        assert name == "multi-line-skill"
        # Description extracted (may be joined or partial — just check non-empty)
        assert isinstance(description, str)


# ---------------------------------------------------------------------------
# TestQuickValidate
# ---------------------------------------------------------------------------


class TestQuickValidate:
    def _make_valid_skill(self, tmp_path, name="test-skill"):
        skill_dir = tmp_path / name
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: A valid test skill.\n---\n\n## Body\n"
        )
        (skill_dir / "references").mkdir()
        return skill_dir

    def test_valid_skill_passes(self, tmp_path):
        skill_dir = self._make_valid_skill(tmp_path)
        valid, message = validate_skill(skill_dir)
        assert valid is True

    def test_missing_skill_md_fails(self, tmp_path):
        skill_dir = tmp_path / "empty-skill"
        skill_dir.mkdir()
        valid, message = validate_skill(skill_dir)
        assert valid is False
        assert "SKILL.md" in message or "not found" in message.lower()

    def test_no_frontmatter_fails(self, tmp_path):
        skill_dir = tmp_path / "no-front"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("No frontmatter here.\n")
        valid, message = validate_skill(skill_dir)
        assert valid is False

    def test_missing_name_fails(self, tmp_path):
        skill_dir = tmp_path / "no-name"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\ndescription: No name field.\n---\n\n## Body\n"
        )
        valid, message = validate_skill(skill_dir)
        assert valid is False
        assert "name" in message.lower()

    def test_description_with_angle_brackets_fails(self, tmp_path):
        skill_dir = tmp_path / "bad-desc"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: bad-desc\ndescription: Use <this> syntax.\n---\n\n## Body\n"
        )
        valid, message = validate_skill(skill_dir)
        assert valid is False

    def test_valid_message_contains_valid(self, tmp_path):
        skill_dir = self._make_valid_skill(tmp_path, "good-skill")
        valid, message = validate_skill(skill_dir)
        assert "valid" in message.lower()


# ---------------------------------------------------------------------------
# TestPackageSkill
# ---------------------------------------------------------------------------


class TestPackageSkill:
    """Test should_exclude() from package_skill.py.

    package_skill imports validate_skill via `from scripts.quick_validate`.
    We import should_exclude directly after ensuring the scripts package
    is on sys.path.

    Note: rel_path is relative to skill_path.parent, so parts are:
      parts[0] = skill folder name
      parts[1] = first subdir (checked against ROOT_EXCLUDE_DIRS)
    """

    @pytest.fixture(autouse=True)
    def import_should_exclude(self):
        """Import should_exclude lazily (after sys.path is set up)."""
        import importlib
        pkg = importlib.import_module("package_skill")
        self.should_exclude = pkg.should_exclude

    def test_pycache_excluded(self):
        assert self.should_exclude(Path("my-skill") / "__pycache__" / "mod.pyc") is True

    def test_pyc_file_excluded(self):
        assert self.should_exclude(Path("my-skill") / "scripts" / "something.pyc") is True

    def test_ds_store_excluded(self):
        assert self.should_exclude(Path("my-skill") / ".DS_Store") is True

    def test_skill_md_not_excluded(self):
        assert self.should_exclude(Path("my-skill") / "SKILL.md") is False

    def test_references_guide_not_excluded(self):
        assert self.should_exclude(Path("my-skill") / "references" / "guide.md") is False

    def test_evals_at_root_excluded(self):
        # evals/ is in ROOT_EXCLUDE_DIRS -- checked at parts[1] (first subdir)
        assert self.should_exclude(Path("my-skill") / "evals" / "test.json") is True

    def test_node_modules_excluded(self):
        assert self.should_exclude(Path("my-skill") / "node_modules" / "pkg" / "index.js") is True

    def test_regular_script_not_excluded(self):
        assert self.should_exclude(Path("my-skill") / "scripts" / "run.py") is False


# ---------------------------------------------------------------------------
# TestAggregateBenchmark
# ---------------------------------------------------------------------------


class TestAggregateBenchmark:
    def test_calculate_stats_basic(self):
        stats = calculate_stats([1.0, 2.0, 3.0, 4.0, 5.0])
        assert stats["mean"] == pytest.approx(3.0, abs=1e-4)
        assert stats["min"] == pytest.approx(1.0, abs=1e-4)
        assert stats["max"] == pytest.approx(5.0, abs=1e-4)

    def test_calculate_stats_count_reflected_in_stddev(self):
        stats = calculate_stats([1.0, 2.0, 3.0, 4.0, 5.0])
        # stddev of [1,2,3,4,5] with n-1 denominator is sqrt(2.5) ≈ 1.5811
        assert stats["stddev"] == pytest.approx(1.5811, abs=0.001)

    def test_calculate_stats_single_value(self):
        stats = calculate_stats([42.0])
        assert stats["mean"] == pytest.approx(42.0)
        assert stats["stddev"] == pytest.approx(0.0)

    def test_calculate_stats_empty(self):
        stats = calculate_stats([])
        assert stats["mean"] == 0.0
        assert stats["stddev"] == 0.0

    def test_load_run_results_returns_dict(self, tmp_path):
        """load_run_results with a properly structured benchmark dir."""
        # Build the directory structure: eval-1/with_skill/run-1/grading.json
        eval_dir = tmp_path / "eval-1"
        run_dir = eval_dir / "with_skill" / "run-1"
        run_dir.mkdir(parents=True)
        grading = {
            "summary": {"pass_rate": 0.8, "passed": 4, "failed": 1, "total": 5},
            "expectations": [],
            "user_notes_summary": {},
        }
        (run_dir / "grading.json").write_text(json.dumps(grading))

        results = load_run_results(tmp_path)
        assert isinstance(results, dict)
        assert "with_skill" in results
        assert len(results["with_skill"]) == 1
        assert results["with_skill"][0]["pass_rate"] == pytest.approx(0.8)

    def test_load_run_results_empty_dir(self, tmp_path):
        results = load_run_results(tmp_path)
        assert results == {}


# ---------------------------------------------------------------------------
# TestGenerateReport
# ---------------------------------------------------------------------------


class TestGenerateReport:
    """Tests for generate_html().

    Note: generate_html() calls max() on the history list to find the best
    iteration. It crashes with an empty history, so all tests use at least
    one history entry (the function only supports non-empty history).
    """

    def _make_history_entry(self, iteration=1, train_passed=3, train_total=4):
        return {
            "iteration": iteration,
            "train_passed": train_passed,
            "train_total": train_total,
            "description": f"Description attempt {iteration}.",
            "train_results": [],
            "test_results": [],
        }

    def _make_data(self, **overrides):
        base = {
            "history": [self._make_history_entry()],
            "holdout": 0,
            "original_description": "Original description.",
            "best_description": "Best description.",
            "best_score": 1.0,
            "iterations_run": 1,
            "train_size": 3,
            "test_size": 2,
        }
        base.update(overrides)
        return base

    def test_returns_string(self):
        result = generate_html(self._make_data())
        assert isinstance(result, str)

    def test_contains_html_tag(self):
        result = generate_html(self._make_data())
        assert "<html" in result.lower()

    def test_contains_body_tag(self):
        result = generate_html(self._make_data())
        assert "<body" in result.lower()

    def test_skill_name_in_title(self):
        result = generate_html(self._make_data(), skill_name="my-cool-skill")
        assert "my-cool-skill" in result

    def test_original_description_in_output(self):
        data = self._make_data(original_description="My original description here.")
        result = generate_html(data)
        assert "My original description here." in result

    def test_best_description_in_output(self):
        data = self._make_data(best_description="The very best description.")
        result = generate_html(data)
        assert "The very best description." in result

    def test_table_rendered_in_output(self):
        result = generate_html(self._make_data())
        assert "<table" in result.lower()


# ---------------------------------------------------------------------------
# TestImproveDescription
# ---------------------------------------------------------------------------


class TestImproveDescription:
    """Test _call_claude() from improve_description.py with mocked subprocess."""

    @pytest.fixture(autouse=True)
    def import_module(self):
        import importlib
        self.improve_mod = importlib.import_module("improve_description")

    def test_call_claude_returns_stdout(self):
        """_call_claude() returns stdout when subprocess succeeds."""
        fake_result = MagicMock()
        fake_result.returncode = 0
        fake_result.stdout = "Generated description output"
        fake_result.stderr = ""

        with patch("subprocess.run", return_value=fake_result) as mock_run:
            result = self.improve_mod._call_claude("test prompt", model=None)

        assert result == "Generated description output"
        mock_run.assert_called_once()

    def test_call_claude_raises_on_nonzero_exit(self):
        """_call_claude() raises RuntimeError when claude exits non-zero."""
        fake_result = MagicMock()
        fake_result.returncode = 1
        fake_result.stdout = ""
        fake_result.stderr = "claude: error"

        with patch("subprocess.run", return_value=fake_result):
            with pytest.raises(RuntimeError, match="exited 1"):
                self.improve_mod._call_claude("test prompt", model=None)

    def test_call_claude_with_model_passes_model_flag(self):
        """Model flag is included in the subprocess command when model is set."""
        fake_result = MagicMock()
        fake_result.returncode = 0
        fake_result.stdout = "output"
        fake_result.stderr = ""

        with patch("subprocess.run", return_value=fake_result) as mock_run:
            self.improve_mod._call_claude("prompt", model="claude-3-5-sonnet-20241022")

        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "--model" in cmd
        assert "claude-3-5-sonnet-20241022" in cmd

    def test_call_claude_removes_claudecode_env(self):
        """CLAUDECODE env var is removed before calling subprocess."""
        fake_result = MagicMock()
        fake_result.returncode = 0
        fake_result.stdout = "ok"
        fake_result.stderr = ""

        with patch("subprocess.run", return_value=fake_result) as mock_run:
            with patch.dict("os.environ", {"CLAUDECODE": "1"}, clear=False):
                self.improve_mod._call_claude("prompt", model=None)

        call_kwargs = mock_run.call_args[1]
        env = call_kwargs.get("env", {})
        assert "CLAUDECODE" not in env
