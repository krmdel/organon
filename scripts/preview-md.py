#!/usr/bin/env python3
"""Preview a markdown file with live Mermaid diagrams in the browser.

Packages two lessons learned the hard way during the Organon whitepaper
draft (2026-04-17):

1. **Mermaid label linter.** Mermaid v10+ treats unquoted `*`, `?`, `:`,
   `/`, `<br/>` inside node labels as syntax-breaking. The linter scans
   each ```mermaid fence and flags bare `[...]` or `{...}` labels
   containing trouble characters. Run with `--lint-only` to fail fast
   in CI, or just call the previewer and it will surface any renderer
   errors inline next to the diagram.

2. **Correct render pipeline.** Pre-replacing ```mermaid fences before
   marked.js parses the markdown is WRONG — marked treats the indented
   diagram body as a code block and mangles the source. The working
   pattern is: let marked parse the fence natively into
   `<pre><code class="language-mermaid">`, then post-process the DOM
   into `<div class="mermaid">` and call `mermaid.render()` explicitly.
   A `<base href>` pointing at the markdown's parent directory is set
   so relative asset paths (images, etc.) resolve correctly.

Usage:
    scripts/preview-md.py docs/my-doc.md                 # render + open browser
    scripts/preview-md.py docs/my-doc.md --output /tmp/x.html
    scripts/preview-md.py docs/my-doc.md --no-open       # just build, don't launch browser
    scripts/preview-md.py docs/my-doc.md --lint-only     # only check Mermaid safety
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Iterable


# ---------------------------------------------------------------------------
# IDE / browser opener cascade
# ---------------------------------------------------------------------------

# IDE binaries in preference order. Each is a command invoked as `{bin} {path}`
# which opens the file in a new tab. If none are found, we fall back to the
# browser. We also probe .app bundle paths on macOS since `cursor` / `code`
# may not be on PATH when running under Claude Code's restricted shell.
IDE_CANDIDATES = (
    "cursor",
    "code",
    "windsurf",
    "codium",
    "code-insiders",
)

# macOS .app bundle fallbacks — these launch the IDE but file-open may be
# slower because they go through `open -a`.
MACOS_IDE_APPS = (
    ("Cursor", "/Applications/Cursor.app/Contents/Resources/app/bin/cursor"),
    ("Visual Studio Code", "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"),
    ("Windsurf", "/Applications/Windsurf.app/Contents/Resources/app/bin/windsurf"),
)


def detect_ide_opener() -> list[str] | None:
    """Return an argv prefix that will open a file in the user's IDE, or None
    if no IDE is detected. Respects $EDITOR when it names a known IDE."""
    editor = os.environ.get("EDITOR", "").strip()
    if editor:
        # Crude check: if EDITOR names a known IDE binary (after stripping args)
        editor_bin = editor.split()[0]
        if Path(editor_bin).name in IDE_CANDIDATES:
            resolved = shutil.which(editor_bin) or editor_bin
            return [resolved]

    for cand in IDE_CANDIDATES:
        p = shutil.which(cand)
        if p:
            return [p]

    if platform.system() == "Darwin":
        for _, app_bin in MACOS_IDE_APPS:
            if Path(app_bin).exists():
                return [app_bin]

    return None


def is_headless() -> bool:
    """Return True when the current environment looks headless / CI.

    In headless environments we must not try to spawn a GUI browser — fail
    closed with a clear message instead. A DISPLAY variable on Linux, or
    running under SSH without forwarding, both count."""
    if os.environ.get("CI"):
        return True
    system = platform.system()
    if system == "Linux":
        return not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY")
    if system == "Windows":
        # Hard to detect cleanly; assume interactive
        return False
    # macOS: always has a display when a user is running the CLI
    return False


def open_in_ide(path: Path) -> bool:
    """Open `path` in the preferred IDE. Return True on success."""
    opener = detect_ide_opener()
    if not opener:
        return False
    try:
        subprocess.Popen(opener + [str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def open_in_browser(path: Path) -> bool:
    """Open `path` in the default browser. Return True on success."""
    if is_headless():
        return False
    try:
        return webbrowser.open(f"file://{path.resolve()}")
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Mermaid label linter
# ---------------------------------------------------------------------------

# Characters that can break Mermaid v10+ when they appear in an UNQUOTED node
# label: `* ? : / < > @ # $ %` and the HTML `<br/>` sequence. Slash is
# included because trailing / path-like slashes (e.g. `projects/`, `a/b/`)
# are particularly fragile across Mermaid parser versions.
# Safe alternatives: wrap the label in double quotes, e.g. `Foo["a/b"]`.
UNSAFE_CHARS = r"*?:<>@#$%/"


MERMAID_FENCE_RE = re.compile(r"^```mermaid\s*\n(.*?)^```", re.DOTALL | re.MULTILINE)

# Matches bracket nodes `Name[...]` and diamond decisions `Name{...}`
# where the label is NOT already wrapped in double quotes.
# Group 1: the opening bracket `[` or `{`
# Group 2: the label content (no closing bracket/brace, no leading `"`)
UNQUOTED_LABEL_RE = re.compile(
    r"(?<![\w])([A-Za-z][A-Za-z0-9_]*)\s*([\[\{])(?!\")([^\]\}\n]+)([\]\}])"
)


def lint_mermaid_block(block: str, block_idx: int, fence_line: int) -> list[str]:
    """Return a list of human-readable warnings for one Mermaid block.

    block: the raw text BETWEEN the ```mermaid and closing ``` fences
    block_idx: 1-based index of this block in the document
    fence_line: 1-based line number where the opening fence lives
    """
    warnings: list[str] = []
    for local_line_no, line in enumerate(block.splitlines(), start=1):
        stripped = line.strip()
        # Skip comments and blank lines
        if not stripped or stripped.startswith("%%"):
            continue
        for m in UNQUOTED_LABEL_RE.finditer(line):
            node_id, open_br, label, close_br = m.groups()
            if any(c in label for c in UNSAFE_CHARS) or "<br" in label:
                abs_line = fence_line + local_line_no
                pair = "{}".format("[...]" if open_br == "[" else "{...}")
                warnings.append(
                    f"  L{abs_line}: diagram #{block_idx}, node `{node_id}{open_br}{label}{close_br}` — "
                    f"contains unsafe char; wrap label in double quotes: `{node_id}{open_br}\"{label}\"{close_br}`"
                )
    return warnings


def lint_markdown(md_text: str) -> list[str]:
    """Scan the whole document's Mermaid blocks. Returns all warnings."""
    warnings: list[str] = []
    for block_idx, match in enumerate(MERMAID_FENCE_RE.finditer(md_text), start=1):
        block_body = match.group(1)
        # Line where the opening ```mermaid sits (1-based)
        fence_line = md_text.count("\n", 0, match.start()) + 1
        warnings.extend(lint_mermaid_block(block_body, block_idx, fence_line))
    return warnings


# ---------------------------------------------------------------------------
# HTML builder
# ---------------------------------------------------------------------------


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<base href="__BASE_HREF__">
<title>__TITLE__</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/github-markdown-css@5/github-markdown-light.min.css">
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>
  body { max-width: 960px; margin: 2em auto; padding: 0 2em; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }
  .markdown-body { box-sizing: border-box; }
  .mermaid { text-align: center; margin: 1.5em 0; padding: 1em; background: #fafbfc; border: 1px solid #eaecef; border-radius: 6px; overflow-x: auto; }
  .mermaid svg { max-width: 100%; height: auto; }
  pre code { font-size: 0.88em; }
  h1 { border-bottom: 2px solid #eaecef; padding-bottom: .3em; }
  h2 { border-bottom: 1px solid #eaecef; padding-bottom: .3em; margin-top: 2em; }
  p > em:first-child:last-child { color: #57606a; font-size: 0.95em; display: block; text-align: center; margin-top: -0.8em; }
  .mermaid-error { color: #b00020; background: #fff3f3; padding: 1em; border: 1px solid #f5c6cb; border-radius: 6px; font-family: monospace; font-size: 0.85em; white-space: pre-wrap; }
  img { max-width: 100%; height: auto; }
</style>
</head>
<body class="markdown-body">
<article id="content">Rendering...</article>
<script>
  const raw = __RAW_JSON__;
  marked.setOptions({ breaks: false, gfm: true });
  document.getElementById('content').innerHTML = marked.parse(raw);

  // Step 1: convert `<pre><code class="language-mermaid">` blocks into `<div class="mermaid">`
  // BEFORE running mermaid — pre-replacing the fences before marked mangles the source.
  document.querySelectorAll('pre code.language-mermaid').forEach((code, i) => {
    const src = code.textContent;
    const div = document.createElement('div');
    div.className = 'mermaid';
    div.id = 'mmd-' + i;
    div.textContent = src;
    code.closest('pre').replaceWith(div);
  });

  mermaid.initialize({
    startOnLoad: false,
    theme: 'default',
    securityLevel: 'loose',
    flowchart: { htmlLabels: true, curve: 'basis' }
  });

  // Step 2: render each diagram, surfacing errors inline so the user sees
  // which diagram and which line failed instead of a silent bomb icon.
  (async () => {
    const diagrams = document.querySelectorAll('.mermaid');
    for (let i = 0; i < diagrams.length; i++) {
      const el = diagrams[i];
      const src = el.textContent;
      try {
        const { svg } = await mermaid.render('mrender-' + i, src);
        el.innerHTML = svg;
      } catch (err) {
        el.className = 'mermaid-error';
        el.textContent = 'Mermaid error in diagram ' + (i + 1) + ':\\n' + (err.message || err) + '\\n\\nSource:\\n' + src;
      }
    }
  })();
</script>
</body>
</html>
"""


def extract_title(md: str) -> tuple[str, str]:
    """Return (title, body) — strips YAML frontmatter title if present."""
    title = "Markdown preview"
    if md.startswith("---"):
        end = md.find("\n---", 3)
        if end != -1:
            fm = md[3:end]
            m = re.search(r"title:\s*\"?([^\"\n]+)\"?", fm)
            if m:
                title = m.group(1).strip()
            md = md[end + 4:].lstrip()
    return title, md


def build_html(md_path: Path) -> str:
    text = md_path.read_text(encoding="utf-8")
    title, body = extract_title(text)
    base_href = f"file://{md_path.parent.resolve()}/"
    return (
        HTML_TEMPLATE
        .replace("__TITLE__", title)
        .replace("__BASE_HREF__", base_href)
        .replace("__RAW_JSON__", json.dumps(body))
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Preview a markdown file with live Mermaid diagrams.",
    )
    parser.add_argument("file", type=Path, help="Path to the markdown file")
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("/tmp/md-preview.html"),
        help="Output HTML path (default: /tmp/md-preview.html)",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Write the HTML but do not open anything (no IDE, no browser)",
    )
    parser.add_argument(
        "--browser",
        action="store_true",
        help="Force the HTML preview to open in the default browser even if an IDE is detected",
    )
    parser.add_argument(
        "--ide",
        action="store_true",
        help="Open the source .md directly in the IDE (markdown preview via IDE extension). "
             "Does not build the HTML preview.",
    )
    parser.add_argument(
        "--lint-only",
        action="store_true",
        help="Run the Mermaid label linter and exit (non-zero if warnings)",
    )
    parser.add_argument(
        "--no-lint",
        action="store_true",
        help="Skip the Mermaid label linter before rendering",
    )
    args = parser.parse_args()

    if not args.file.exists():
        print(f"[preview-md] file not found: {args.file}", file=sys.stderr)
        return 2

    md_text = args.file.read_text(encoding="utf-8")

    # Lint (unless explicitly skipped)
    warnings: list[str] = []
    if not args.no_lint:
        warnings = lint_markdown(md_text)

    if warnings:
        print(f"[preview-md] {len(warnings)} Mermaid label warning(s):", file=sys.stderr)
        for w in warnings:
            print(w, file=sys.stderr)

    if args.lint_only:
        return 1 if warnings else 0

    # --ide mode: just open the raw .md in the user's IDE and return.
    # The IDE's built-in markdown preview handles rendering (install.sh
    # bundles the Mermaid extension via setup-ide-previews.sh).
    if args.ide and not args.no_open:
        if open_in_ide(args.file):
            print(f"[preview-md] opened {args.file} in IDE")
            return 0
        print(
            "[preview-md] no IDE detected on PATH (tried cursor, code, windsurf, $EDITOR). "
            "Falling back to browser HTML preview.",
            file=sys.stderr,
        )

    html = build_html(args.file)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    print(f"[preview-md] wrote {args.output} ({len(html):,} bytes)")
    if warnings:
        print(
            f"[preview-md] note: {len(warnings)} lint warning(s) above — "
            f"diagrams may render but could be fragile. Fix now to prevent future regressions.",
            file=sys.stderr,
        )

    if args.no_open:
        return 0

    # Open cascade: IDE first (opens the HTML as an editor tab), browser as
    # fallback. Users can force browser with --browser. In headless
    # environments, skip opening entirely with a clear message.
    opened = False
    if not args.browser:
        opened = open_in_ide(args.output)
        if opened:
            print(f"[preview-md] opened in IDE: {args.output}")
    if not opened:
        if is_headless():
            print(
                f"[preview-md] headless environment detected — preview not opened. "
                f"HTML is at {args.output} — copy to a machine with a browser or IDE to view.",
                file=sys.stderr,
            )
        elif open_in_browser(args.output):
            print(f"[preview-md] opened in browser: {args.output}")
        else:
            print(
                f"[preview-md] could not open preview. HTML is at {args.output}.",
                file=sys.stderr,
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
