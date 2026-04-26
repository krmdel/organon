"""Tests for scripts/export-md.py — covers regressions that would otherwise
ship broken to end users.

Focus:
1. Chromium print-to-pdf invocation must suppress the browser's default
   page header (URL + date/time) and footer (page n/N + title). Without
   the right flags, PDFs look like screenshots of a browser tab instead
   of publication-quality documents.
2. HTML render used for print contains the @page CSS rules that clean
   up margins and hide UA-injected header/footer regions.
3. Mermaid fence detection picks up fences and leaves non-mermaid code
   untouched.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import unittest.mock as mock
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = ROOT / "scripts" / "export-md.py"


@pytest.fixture(scope="module")
def emd():
    spec = importlib.util.spec_from_file_location("export_md", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["export_md"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestChromiumPrintToPDF:
    """The Chromium CLI invocation must carry the flags that produce a
    clean publication-quality PDF. Missing flags → PDF has browser
    print headers (URL + date-time) and footers (page n/N + title)."""

    def test_flags_suppress_browser_header_and_footer(self, emd, tmp_path):
        """Real regression: a PDF without --no-pdf-header-footer shows the
        HTML file URL and the print date on every page — unusable for OSS
        release. Both aliases (--no-pdf-header-footer and
        --print-to-pdf-no-header) must be present because Chromium builds
        vary on which they honour."""
        html = tmp_path / "x.html"
        html.write_text("<html><body>hi</body></html>")
        pdf = tmp_path / "x.pdf"
        captured: dict[str, list[str]] = {}

        def _fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            # Simulate Chromium writing the PDF so success path runs.
            pdf.write_bytes(b"%PDF-fake")
            return mock.Mock(returncode=0)

        with mock.patch.object(emd.subprocess, "run", _fake_run):
            ok = emd.chromium_print_to_pdf(html, pdf, "/fake/chromium")

        assert ok is True
        cmd = captured["cmd"]
        assert "--no-pdf-header-footer" in cmd, (
            "missing --no-pdf-header-footer; PDFs will have URL+date header"
        )
        assert "--print-to-pdf-no-header" in cmd, (
            "missing --print-to-pdf-no-header alias; some Chromium builds ignore --no-pdf-header-footer"
        )
        assert "--headless=new" in cmd, "must use modern headless mode"
        assert any(a.startswith("--print-to-pdf=") for a in cmd), (
            "must use --print-to-pdf to actually produce a PDF"
        )
        assert any(a.startswith("--virtual-time-budget=") for a in cmd), (
            "must wait for marked.js async render before snapshot"
        )

    def test_failure_returns_false_with_warning(self, emd, tmp_path, capsys):
        html = tmp_path / "x.html"
        html.write_text("<html></html>")
        pdf = tmp_path / "x.pdf"

        def _boom(cmd, **kwargs):
            raise subprocess.CalledProcessError(
                returncode=1, cmd=cmd, output=b"", stderr=b"fake chromium crash"
            )

        with mock.patch.object(emd.subprocess, "run", _boom):
            ok = emd.chromium_print_to_pdf(html, pdf, "/fake/chromium")

        assert ok is False
        err = capsys.readouterr().err
        assert "chromium print-to-pdf failed" in err


class TestPrintHTMLTemplate:
    """The HTML handed to Chromium must include the @page CSS rules that
    produce clean margins and hide UA-injected header/footer regions.
    Relying on Chromium CLI flags alone is fragile — the @page rules are
    belt-and-braces."""

    def test_html_contains_page_rules(self, emd, tmp_path):
        md = tmp_path / "doc.md"
        md.write_text("# Hello\n\nBody.\n")
        html_path = emd.render_html_from_md(md, md.read_text(), tmp_path)
        html = html_path.read_text()

        # @page rule with margins
        assert "@page" in html, "missing @page CSS rule"
        assert re.search(r"@page\s*\{[^}]*margin", html), (
            "@page rule must set page margins"
        )
        # Empty @top-* rules to neutralise UA-injected print header
        assert "@top-center" in html or "@top-left" in html, (
            "missing @top-* rule — UA print header may leak through"
        )
        # Page break protection for figures and code blocks
        assert "page-break-inside" in html or "break-inside" in html, (
            "missing break-inside rule — figures/tables may split across pages"
        )


class TestMermaidFenceDetection:
    """Pre-render Mermaid fences to PNG only targets mermaid blocks; leaves
    other code blocks alone."""

    def test_detects_mermaid_fence(self, emd):
        md = "pre\n\n```mermaid\nflowchart\n    A[ok]\n```\n\npost\n"
        assert emd.MERMAID_FENCE_RE.search(md) is not None

    def test_ignores_python_fence(self, emd):
        md = "```python\nprint('hi')\n```\n"
        assert emd.MERMAID_FENCE_RE.search(md) is None

    def test_ignores_plain_fence(self, emd):
        md = "```\nplain preformatted\n```\n"
        assert emd.MERMAID_FENCE_RE.search(md) is None
