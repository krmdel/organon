"""Tests for scripts/preview-md.py — the reusable markdown-with-Mermaid preview utility.

Covers:
1. Mermaid label linter — flags unsafe unquoted labels, ignores safe ones
2. HTML builder — produces self-contained output with <base href>, mermaid scripts, raw markdown embedded
3. Title extraction from YAML frontmatter
4. IDE detection cascade (with a monkeypatched PATH so the test doesn't depend on the user's machine)
5. CLI smoke — --lint-only exit codes, --no-open safety
"""

from __future__ import annotations

import importlib.util
import sys
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = ROOT / "scripts" / "preview-md.py"


@pytest.fixture(scope="module")
def pmd():
    """Import preview-md.py as a module despite the dash in its filename."""
    spec = importlib.util.spec_from_file_location("preview_md", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["preview_md"] = mod
    spec.loader.exec_module(mod)
    return mod


# =============================================================================
# 1. Linter
# =============================================================================


class TestMermaidLinter:
    def test_flags_unquoted_asterisk(self, pmd):
        md = """# Doc

```mermaid
flowchart TB
    A[sci-* skills]
    B[OK label]
```
"""
        warnings = pmd.lint_markdown(md)
        assert any("sci-*" in w and "A" in w for w in warnings), warnings

    def test_flags_unquoted_slash(self, pmd):
        md = """```mermaid
flowchart
    P[projects/data/]
```"""
        warnings = pmd.lint_markdown(md)
        assert any("projects/data" in w for w in warnings), warnings

    def test_flags_unquoted_question_mark_in_diamond(self, pmd):
        md = """```mermaid
flowchart
    X{is it ready?}
```"""
        warnings = pmd.lint_markdown(md)
        assert any("is it ready?" in w for w in warnings), warnings

    def test_flags_unquoted_br_tag(self, pmd):
        md = """```mermaid
flowchart
    N[SOUL.md<br/>contract]
```"""
        warnings = pmd.lint_markdown(md)
        assert any("SOUL.md" in w for w in warnings), warnings

    def test_ignores_properly_quoted_labels(self, pmd):
        md = """```mermaid
flowchart
    A["sci-* skills"]
    B[plain_safe_label]
    C["projects/data/"]
    D{"is it ready?"}
```"""
        assert pmd.lint_markdown(md) == []

    def test_ignores_content_outside_mermaid_fence(self, pmd):
        md = """# Title

A plain paragraph with `code? and [brackets]` that should not be linted.

```python
def foo():
    return [1, 2, 3]
```
"""
        assert pmd.lint_markdown(md) == []

    def test_flags_multiple_across_blocks(self, pmd):
        md = """```mermaid
flowchart
    A[sci-*]
```

Text.

```mermaid
flowchart
    B[tool-*]
```"""
        warnings = pmd.lint_markdown(md)
        # One warning per block
        assert len(warnings) == 2
        assert any("diagram #1" in w for w in warnings)
        assert any("diagram #2" in w for w in warnings)


# =============================================================================
# 2. HTML builder
# =============================================================================


class TestHTMLBuilder:
    def test_builds_html_with_base_href_and_marked_script(self, pmd, tmp_path):
        md = tmp_path / "doc.md"
        md.write_text("# Hello\n\nBody.\n")
        html = pmd.build_html(md)
        assert "<base href=" in html
        assert f"file://{tmp_path.resolve()}/" in html
        assert "marked.min.js" in html
        assert "mermaid.min.js" in html
        # Raw markdown must be embedded as JSON string
        assert "# Hello" in html

    def test_extracts_title_from_frontmatter(self, pmd):
        md = '---\ntitle: "My Doc"\nauthor: x\n---\n\n# Body\n'
        title, body = pmd.extract_title(md)
        assert title == "My Doc"
        assert body.startswith("# Body")

    def test_title_default_when_no_frontmatter(self, pmd):
        title, body = pmd.extract_title("# Plain")
        assert title == "Markdown preview"
        assert body == "# Plain"

    def test_title_default_when_frontmatter_has_no_title_key(self, pmd):
        md = "---\nauthor: x\n---\n\n# Body\n"
        title, body = pmd.extract_title(md)
        assert title == "Markdown preview"
        assert body.startswith("# Body")


# =============================================================================
# 3. IDE detection cascade
# =============================================================================


class TestIDEDetection:
    def test_respects_editor_env_when_known_ide(self, pmd, monkeypatch, tmp_path):
        fake_cursor = tmp_path / "cursor"
        fake_cursor.write_text("#!/bin/sh\necho fake\n")
        fake_cursor.chmod(0o755)
        monkeypatch.setenv("EDITOR", str(fake_cursor))
        monkeypatch.setenv("PATH", str(tmp_path) + ":" + "/usr/bin")
        opener = pmd.detect_ide_opener()
        assert opener is not None
        assert "cursor" in opener[0]

    def test_ignores_editor_env_when_non_ide(self, pmd, monkeypatch, tmp_path):
        fake_vim = tmp_path / "vim"
        fake_vim.write_text("#!/bin/sh\n")
        fake_vim.chmod(0o755)
        monkeypatch.setenv("EDITOR", str(fake_vim))
        # Clear PATH so no real cursor/code is found
        monkeypatch.setenv("PATH", "/nonexistent")
        # Also temporarily rename /Applications paths to not-found
        # (We cannot, so this test only verifies no crash — the returned opener
        # may still come from the macOS app fallback if Cursor is installed.)
        opener = pmd.detect_ide_opener()
        # Either None (no IDE) or a real IDE path — either is acceptable; the
        # key assertion is that $EDITOR=vim was NOT honoured.
        if opener is not None:
            assert "vim" not in opener[0]

    def test_headless_detection_on_linux_without_display(self, pmd, monkeypatch):
        monkeypatch.setattr(pmd.platform, "system", lambda: "Linux")
        monkeypatch.delenv("DISPLAY", raising=False)
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        monkeypatch.delenv("CI", raising=False)
        assert pmd.is_headless() is True

    def test_headless_detection_on_linux_with_display(self, pmd, monkeypatch):
        monkeypatch.setattr(pmd.platform, "system", lambda: "Linux")
        monkeypatch.setenv("DISPLAY", ":0")
        monkeypatch.delenv("CI", raising=False)
        assert pmd.is_headless() is False

    def test_headless_detection_when_ci_env_set(self, pmd, monkeypatch):
        monkeypatch.setenv("CI", "true")
        assert pmd.is_headless() is True


# =============================================================================
# 4. CLI smoke
# =============================================================================


class TestCLI:
    def test_lint_only_clean_exits_zero(self, tmp_path):
        md = tmp_path / "clean.md"
        md.write_text("""# Clean

```mermaid
flowchart
    A["OK"]
    B["also OK"]
```
""")
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(md), "--lint-only"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr

    def test_lint_only_with_warnings_exits_one(self, tmp_path):
        md = tmp_path / "dirty.md"
        md.write_text("""# Dirty

```mermaid
flowchart
    A[sci-* unquoted]
```
""")
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(md), "--lint-only"],
            capture_output=True, text=True,
        )
        assert result.returncode == 1
        assert "sci-*" in result.stderr

    def test_no_open_produces_html(self, tmp_path):
        md = tmp_path / "doc.md"
        md.write_text("# Hello\n\nBody with ```mermaid\nflowchart\n    A[OK]\n```\n")
        out = tmp_path / "out.html"
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(md),
             "--output", str(out), "--no-open"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr
        assert out.exists()
        assert out.stat().st_size > 1000  # real HTML, not empty
        html = out.read_text()
        assert "<base href=" in html
        assert "mermaid" in html

    def test_missing_file_exits_two(self, tmp_path):
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(tmp_path / "nope.md"), "--no-open"],
            capture_output=True, text=True,
        )
        assert result.returncode == 2
        assert "not found" in result.stderr.lower()
