#!/usr/bin/env python3
"""Export a markdown file to DOCX (always) and PDF (if a supported engine exists).

Pipeline:
    1. Scan for ```mermaid fences; pre-render each to a PNG via `mmdc`
       (mermaid-cli), swap the fence with an image ref in a staged .md.
    2. Run pandoc on the staged .md:
       - `.docx` always (pandoc native, no extra engine needed)
       - `.pdf` via the first available engine: weasyprint, tectonic,
         xelatex, pdflatex. If none, skip PDF with a clear message.
    3. Report absolute paths for every artifact produced.

Outputs land next to the source .md unless `--out-dir` is given:
    <stem>.docx
    <stem>.pdf         (if a PDF engine is available)
    figures/mermaid-N.png   (one per diagram)

Usage:
    scripts/export-md.py docs/whitepaper.md              # docx + pdf next to source
    scripts/export-md.py docs/whitepaper.md --out-dir build/
    scripts/export-md.py docs/whitepaper.md --docx-only  # skip PDF even if engine exists
    scripts/export-md.py docs/whitepaper.md --formats docx,pdf
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


MERMAID_FENCE_RE = re.compile(r"^```mermaid\s*\n(.*?)^```", re.DOTALL | re.MULTILINE)

# Pandoc's own --pdf-engine values. weasyprint is lightest (HTML/CSS, no
# LaTeX) but needs system libs (pango) on macOS. tectonic is a
# self-contained LaTeX; xelatex/pdflatex need a full TeX distribution.
PANDOC_PDF_ENGINES = ("weasyprint", "tectonic", "xelatex", "pdflatex")

# Chromium-class browser binaries, probed in order. Used as a pandoc-free
# PDF fallback: render to HTML then print-to-pdf via headless chrome.
# Works on any box that has a modern browser — no LaTeX, no pango.
CHROMIUM_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "google-chrome",
    "chromium",
    "chromium-browser",
    "msedge",
    "brave-browser",
)


REPO_ROOT = Path(__file__).resolve().parent.parent
VENV_BIN = REPO_ROOT / ".venv" / "bin"

# ---------------------------------------------------------------------------
# E4 — pre-export citation gate
# ---------------------------------------------------------------------------

_CITATION_MARKER_RE = re.compile(r"\[@[A-Za-z][A-Za-z0-9_-]*\]")
_EXPORT_LEDGER = Path.home() / ".scientific-os" / "export-ledger.jsonl"


def _write_export_ledger(entry: dict) -> None:
    _EXPORT_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with _EXPORT_LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _run_export_gate(md_path: Path) -> tuple[bool, str]:
    """Run citation gate before export. Same logic as substack gate.

    Returns (blocked, status_summary). Gracefully degrades if verify_ops
    is unavailable.
    """
    text = md_path.read_text(encoding="utf-8")
    has_markers = bool(_CITATION_MARKER_RE.search(text))
    bib_candidates = list(md_path.parent.glob("*.bib"))
    bib_path = str(bib_candidates[0]) if bib_candidates else None

    if not has_markers and not bib_path:
        return False, ""

    sci_writing_scripts = REPO_ROOT / ".claude" / "skills" / "sci-writing" / "scripts"
    if str(sci_writing_scripts) not in sys.path:
        sys.path.insert(0, str(sci_writing_scripts))
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    try:
        from verify_ops import run_verification, VerificationError  # type: ignore[import]
    except ImportError as e:
        # Phase 8: an unavailable verify_ops on the export path used to fall
        # through to a clean pass with a stderr WARNING — turning a broken
        # venv into a silent disable of the export gate. Now: refuse the
        # export unless SCI_OS_ALLOW_UNGATED=1 is set, in which case the
        # bypass is logged to the export ledger.
        msg = (
            f"[export-md] BLOCKED: verify_ops unavailable ({e}). "
            "The citation gate cannot run, so the export is refused. "
            "Fix the import error (likely a broken venv or missing repro/ "
            "dependency) and retry. To bypass in an emergency, set "
            "SCI_OS_ALLOW_UNGATED=1 — the bypass is logged to "
            f"{_EXPORT_LEDGER}."
        )
        if os.environ.get("SCI_OS_ALLOW_UNGATED", "").strip().lower() in ("1", "true", "yes"):
            try:
                _write_export_ledger({
                    "ts": datetime.datetime.utcnow().isoformat() + "Z",
                    "outcome": "ungated_bypass",
                    "path": str(md_path),
                    "reason": f"verify_ops ImportError: {e}",
                })
            except Exception:
                pass
            print(
                f"[export-md] SCI_OS_ALLOW_UNGATED=1 — proceeding "
                f"WITHOUT citation gate (logged to {_EXPORT_LEDGER}).",
                file=sys.stderr,
            )
            return False, "ungated_bypass"
        print(msg, file=sys.stderr)
        return True, "verify_ops_unavailable"

    print("[export-md] running citation verification gate…", file=sys.stderr)
    try:
        result = run_verification(
            manuscript_path=str(md_path),
            bib_path=bib_path,
            apply_fixes=False,
        )
    except VerificationError as e:
        msg = f"[export-md] GATE BLOCKED: {e}"
        print(msg, file=sys.stderr)
        return True, str(e)

    blocked = result.get("blocked", False)
    summary = result.get("summary", {})
    status = f"CRITICAL={summary.get('critical',0)} MAJOR={summary.get('major',0)}"

    if blocked:
        findings = result.get("findings", [])
        crits = [f for f in findings if f.get("severity") == "critical"]
        print(
            f"\n[export-md] EXPORT BLOCKED — citation gate FAILED ({status})",
            file=sys.stderr,
        )
        for f in crits[:5]:
            print(f"  • [{f.get('criterion','')}] {f.get('finding','')}", file=sys.stderr)
        print(
            "\n  Fix citations above, or bypass with --force (logged to ledger).\n",
            file=sys.stderr,
        )
    else:
        print(f"[export-md] citation gate passed ({status})", file=sys.stderr)

    return blocked, status


def which(binary: str) -> str | None:
    """Find a binary on PATH, falling back to the repo's .venv/bin/.

    This lets users install PDF engines into the repo venv (e.g.
    `uv pip install --python .venv/bin/python weasyprint`) without
    needing to activate it first."""
    p = shutil.which(binary)
    if p:
        return p
    venv_candidate = VENV_BIN / binary
    if venv_candidate.exists():
        return str(venv_candidate)
    return None


def pre_render_mermaid(md_text: str, figures_dir: Path) -> str:
    """For each ```mermaid fence, write the body to a temp file, run mmdc,
    and splice a `![](figures/mermaid-N.png)` image reference in its place.

    Returns the rewritten markdown. If mmdc is not on PATH, returns the
    text unchanged and prints a warning to stderr (fences will render as
    code blocks in the output, which is still legible).
    """
    if which("mmdc") is None:
        print(
            "[export-md] warn: mmdc not on PATH — mermaid fences will be "
            "rendered as code blocks rather than images. Install with "
            "`npm install -g @mermaid-js/mermaid-cli`.",
            file=sys.stderr,
        )
        return md_text

    figures_dir.mkdir(parents=True, exist_ok=True)
    counter = {"i": 0}

    def _render(match: re.Match) -> str:
        counter["i"] += 1
        i = counter["i"]
        src = match.group(1).rstrip()
        mmd_path = figures_dir / f"mermaid-{i}.mmd"
        png_path = figures_dir / f"mermaid-{i}.png"
        mmd_path.write_text(src, encoding="utf-8")
        try:
            # -w 1600 widens the render canvas so wide flowcharts keep
            # their rows intact instead of wrapping to a narrower box.
            # -s 2 doubles the device pixel ratio so PNGs stay crisp when
            # scaled up to A4 page width (~180mm ≈ 2100px at 300dpi).
            subprocess.run(
                [
                    "mmdc", "-i", str(mmd_path), "-o", str(png_path),
                    "-b", "white", "-w", "1600", "-s", "2",
                ],
                check=True, capture_output=True, text=True, timeout=60,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as err:
            msg = getattr(err, "stderr", "") or str(err)
            print(
                f"[export-md] warn: mmdc failed on diagram #{i}: "
                f"{msg[:200]}. Leaving fence as code block.",
                file=sys.stderr,
            )
            return match.group(0)
        finally:
            mmd_path.unlink(missing_ok=True)
        return f"![Mermaid diagram {i}]({png_path.relative_to(figures_dir.parent).as_posix()})\n"

    return MERMAID_FENCE_RE.sub(_render, md_text)


def detect_pandoc_pdf_engine() -> str | None:
    """Return the first available pandoc-supported PDF engine, or None."""
    for engine in PANDOC_PDF_ENGINES:
        if which(engine):
            return engine
    return None


def detect_chromium() -> str | None:
    """Return the first Chromium-class browser found, or None.

    We probe explicit .app bundle paths (macOS) and common Linux names.
    This is the pandoc-free PDF path: HTML → chrome --print-to-pdf.
    """
    for cand in CHROMIUM_CANDIDATES:
        if "/" in cand:
            if Path(cand).exists():
                return cand
        else:
            p = shutil.which(cand)
            if p:
                return p
    return None


def render_html_from_md(md_path: Path, staged_md: str, out_dir: Path) -> Path:
    """Build a self-contained HTML file for a staged markdown (with
    mermaid already pre-rendered to PNGs). Used as the input to
    Chromium print-to-pdf. We re-use the preview-md builder so the
    layout matches what the user sees in the browser preview."""
    import json as _json

    title = md_path.stem
    # Strip YAML frontmatter so it doesn't leak into the body
    body = staged_md
    if body.startswith("---"):
        end = body.find("\n---", 3)
        if end != -1:
            body = body[end + 4:].lstrip()

    base_href = f"file://{md_path.parent.resolve()}/"
    html_path = out_dir / f"{md_path.stem}._chromium.html"
    raw_json = _json.dumps(body)

    # Publication-quality print CSS:
    # - @page rule sets A4 with tight margins and explicitly empty
    #   headers / footers (removes any print-UA-injected title bar
    #   inside the page box — Chromium's top-of-page URL + date line
    #   comes from the *browser* print header, disabled below via a
    #   separate CLI flag)
    # - Image and diagram break rules prevent ugly splits mid-figure
    # - Root font size slightly smaller for print density
    html = (
        "<!DOCTYPE html><html><head>"
        '<meta charset="utf-8">'
        f'<base href="{base_href}">'
        f"<title>{title}</title>"
        '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/github-markdown-css@5/github-markdown-light.min.css">'
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        # EB Garamond: static-weight Google Font, LaTeX-book feel, full
        # ligature coverage. Avoids the variable-axis (opsz) subsetting
        # quirk in Chromium's --print-to-pdf that strips space glyphs from
        # the PDF text layer (PDF displays fine but copy-paste loses word
        # boundaries). JetBrains Mono is also static-weight for the same
        # reason.
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
        'family=EB+Garamond:ital,wght@0,400;0,500;0,600;0,700;1,400;1,600'
        '&family=JetBrains+Mono:wght@400;500&display=swap">'
        '<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>'
        "<style>"
        "@page { size: A4; margin: 18mm 16mm 20mm 16mm;"
        "        @top-left { content: ''; } @top-center { content: ''; } @top-right { content: ''; }"
        "        @bottom-left { content: ''; } @bottom-center { content: counter(page); } @bottom-right { content: ''; } }"
        "html,body { background: #fff; }"
        # Source Serif 4 is an Adobe open-source academic serif with full
        # ligature coverage (fi, fl, ffi) and opsz metadata — the closest
        # free web match to Latin Modern / LaTeX paper typography.
        "body { max-width: 900px; margin: 2em auto; padding: 0 2em;"
        "       font-family: 'EB Garamond', 'Charter', 'Iowan Old Style',"
        "                    Georgia, 'Times New Roman', serif;"
        "       font-feature-settings: 'liga' 1, 'kern' 1, 'lnum' 1;"
        "       font-size: 12pt; line-height: 1.45; color: #1f2328;"
        "       font-variant-ligatures: common-ligatures; }"
        "p, li { text-align: justify; hyphens: auto; -webkit-hyphens: auto; }"
        # A4 usable height after 18mm top + 20mm bottom margins is ~259mm.
        # Cap figures at 220mm so caption + surrounding whitespace also fit
        # on the page. Tall portrait flowcharts (e.g. routing cascade) used
        # to overflow past the bottom margin without this rule.
        "img { display: block; margin: 1em auto; max-width: 100%; max-height: 220mm;"
        "      width: auto; height: auto; object-fit: contain;"
        "      page-break-inside: avoid; break-inside: avoid; }"
        "h1 { border-bottom: 2px solid #eaecef; padding-bottom: .3em; page-break-after: avoid; break-after: avoid; }"
        ".title-block { text-align: center; margin: 1.5em 0 1.2em; }"
        ".title-block h1 { border-bottom: none; padding-bottom: 0; margin-bottom: 0.15em;"
        "                   font-size: 2.6em; font-weight: 600; letter-spacing: 0.01em; }"
        ".title-block .subtitle { text-align: center; color: #57606a; font-style: italic;"
        "                          font-size: 1.25em; margin-top: 0; hyphens: none; }"
        "h2, h3, h4 { page-break-after: avoid; break-after: avoid; }"
        "h2 { border-bottom: 1px solid #eaecef; padding-bottom: .3em; margin-top: 1.8em; margin-bottom: 0.4em; }"
        "h3 { margin-top: 1.2em; margin-bottom: 0.3em; }"
        "h4 { margin-top: 1em; margin-bottom: 0.2em; }"
        "h3 + p, h4 + p, h2 + p { margin-top: 0.2em; }"
        "pre { background: #f6f8fa; padding: 1em; border-radius: 6px; overflow-x: auto;"
        "      page-break-inside: avoid; break-inside: avoid; font-size: 0.85em;"
        "      font-family: 'JetBrains Mono', ui-monospace, Menlo, Consolas, monospace;"
        "      text-align: left; hyphens: none; }"
        "code { font-size: 0.88em; font-family: 'JetBrains Mono', ui-monospace, Menlo, Consolas, monospace; }"
        "h1, h2, h3, h4, h5, h6 { font-family: 'EB Garamond', Georgia, serif;"
        "                          font-weight: 600; letter-spacing: 0; }"
        "table { page-break-inside: avoid; break-inside: avoid; }"
        "figure, .figure, blockquote { page-break-inside: avoid; break-inside: avoid; }"
        "p.caption { color: #57606a; font-size: 0.95em; text-align: center;"
        "            margin-top: -0.4em; font-style: italic; hyphens: none; }"
        "@media print { body { max-width: none; margin: 0; padding: 0; } }"
        "</style></head><body class='markdown-body'>"
        "<article id='content'></article>"
        "<script>"
        f"const raw = {raw_json};"
        "marked.setOptions({breaks:false,gfm:true});"
        "const root = document.getElementById('content');"
        "root.innerHTML = marked.parse(raw);"
        # A paragraph is a figure caption only when its entire text content
        # is wrapped in a single <em>. CSS :first-child/:last-child ignore
        # text nodes, so any inline italic turned the surrounding paragraph
        # into a centered caption. Detect via JS using textContent equality.
        "root.querySelectorAll('p').forEach(p => {"
        "  const ems = p.querySelectorAll('em');"
        "  if (ems.length === 1 &&"
        "      p.textContent.trim() === ems[0].textContent.trim()) {"
        "    p.classList.add('caption');"
        "  }"
        "});"
        "</script></body></html>"
    )
    html_path.write_text(html, encoding="utf-8")
    return html_path


def chromium_print_to_pdf(html_path: Path, pdf_path: Path, chromium: str) -> bool:
    """Run Chromium headless --print-to-pdf. Return True on success.

    Flags used:
    - --headless=new         : modern headless mode (old one deprecated)
    - --no-pdf-header-footer : drop the browser's default page header
                               (URL + date-time) and footer (page-n/N +
                               document title). Without this flag the
                               PDF looks like a printed web page, not a
                               publication.
    - --print-to-pdf-no-header : older alias of the above (both kept
                                 so it works across Chromium builds
                                 that only accept one or the other)
    - --virtual-time-budget   : advance the page clock so async
                                marked.js rendering completes before
                                the print snapshot.
    """
    cmd = [
        chromium,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--no-pdf-header-footer",
        "--print-to-pdf-no-header",
        "--hide-scrollbars",
        f"--print-to-pdf={pdf_path}",
        "--virtual-time-budget=20000",  # wait for marked.js + Google Fonts
        f"file://{html_path.resolve()}",
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120)
        return pdf_path.exists() and pdf_path.stat().st_size > 0
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as err:
        msg = getattr(err, "stderr", "") or str(err)
        print(f"[export-md] warn: chromium print-to-pdf failed: {msg[:300]}", file=sys.stderr)
        return False


def export(
    md_path: Path,
    out_dir: Path,
    formats: list[str],
) -> dict[str, Path]:
    """Run the full export. Returns {format: output_path} for each artifact
    actually produced. Missing engines cause that format to be silently
    skipped (with a stderr note)."""
    if which("pandoc") is None:
        print(
            "[export-md] error: pandoc is not installed. Install via "
            "`brew install pandoc` (macOS) or your package manager.",
            file=sys.stderr,
        )
        sys.exit(2)

    out_dir.mkdir(parents=True, exist_ok=True)
    source = md_path.read_text(encoding="utf-8")

    # Pre-render Mermaid
    figures_dir = out_dir / "figures"
    staged_md = pre_render_mermaid(source, figures_dir)
    staged_path = out_dir / f"{md_path.stem}._staged.md"
    staged_path.write_text(staged_md, encoding="utf-8")

    artifacts: dict[str, Path] = {}

    # Resource paths: pandoc needs to resolve relative image paths from
    # the staged file's location; adding the source dir too supports
    # existing `assets/hero.png` style refs.
    resource_paths = f"{out_dir}:{md_path.parent}"

    try:
        if "docx" in formats:
            docx_out = out_dir / f"{md_path.stem}.docx"
            cmd = [
                "pandoc", str(staged_path),
                "-o", str(docx_out),
                f"--resource-path={resource_paths}",
                "--standalone",
            ]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            artifacts["docx"] = docx_out

        if "pdf" in formats:
            pdf_out = out_dir / f"{md_path.stem}.pdf"
            pdf_produced = False

            # Path 1: pandoc with a pandoc-supported engine (weasyprint /
            # tectonic / xelatex / pdflatex). Cleanest output when the
            # engine is available with all its system deps.
            engine = detect_pandoc_pdf_engine()
            if engine:
                cmd = [
                    "pandoc", str(staged_path),
                    "-o", str(pdf_out),
                    f"--resource-path={resource_paths}",
                    f"--pdf-engine={engine}",
                    "--standalone",
                ]
                try:
                    subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=180)
                    pdf_produced = True
                    artifacts["pdf"] = pdf_out
                except subprocess.CalledProcessError as err:
                    stderr = err.stderr or ""
                    print(
                        f"[export-md] note: pandoc+{engine} failed "
                        f"(likely missing system deps). Falling back to "
                        f"headless Chromium. stderr snippet: {stderr[-200:]}",
                        file=sys.stderr,
                    )

            # Path 2: headless Chromium on an HTML rendering — universal
            # fallback. Works on any box with a modern browser. No LaTeX,
            # no pango, no extra Python packages.
            if not pdf_produced:
                chromium = detect_chromium()
                if chromium:
                    html_path = render_html_from_md(md_path, staged_md, out_dir)
                    try:
                        if chromium_print_to_pdf(html_path, pdf_out, chromium):
                            artifacts["pdf"] = pdf_out
                            pdf_produced = True
                    finally:
                        html_path.unlink(missing_ok=True)

            if not pdf_produced:
                print(
                    "[export-md] note: PDF skipped. No working engine. "
                    "Install one of: (a) Chrome / Chromium / Edge / Brave "
                    "(any modern browser — Organon will drive it headlessly), "
                    "(b) weasyprint via `brew install pango gdk-pixbuf libffi "
                    "&& uv pip install --python .venv/bin/python weasyprint`, "
                    "or (c) tectonic via `brew install tectonic`. DOCX was "
                    "still produced and is a full-fidelity substitute.",
                    file=sys.stderr,
                )
    finally:
        staged_path.unlink(missing_ok=True)

    return artifacts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export markdown to DOCX and PDF (with Mermaid pre-rendering)."
    )
    parser.add_argument("file", type=Path, help="Source markdown file")
    parser.add_argument(
        "--out-dir", type=Path, default=None,
        help="Output directory (default: same as source)",
    )
    parser.add_argument(
        "--formats", default="docx,pdf",
        help="Comma-separated formats to produce (default: docx,pdf)",
    )
    parser.add_argument(
        "--docx-only", action="store_true",
        help="Shortcut for --formats docx",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Bypass citation gate on CRITICAL findings (bypass logged to ~/.scientific-os/export-ledger.jsonl)",
    )
    args = parser.parse_args()

    if not args.file.exists():
        print(f"[export-md] file not found: {args.file}", file=sys.stderr)
        return 2

    md_path = args.file.resolve()
    out_dir = args.out_dir if args.out_dir else args.file.parent
    formats = ["docx"] if args.docx_only else [f.strip() for f in args.formats.split(",") if f.strip()]

    # E4 — pre-export citation gate
    blocked, gate_summary = _run_export_gate(md_path)
    if blocked:
        _write_export_ledger({
            "ts": datetime.datetime.utcnow().isoformat() + "Z",
            "action": "export",
            "file": str(md_path),
            "formats": formats,
            "override": "--force" if args.force else "refused",
            "gate_summary": gate_summary,
            "md5": hashlib.md5(md_path.read_bytes()).hexdigest(),
        })
        if not args.force:
            return 1
        print("[export-md] --force: bypass logged to ledger, continuing.", file=sys.stderr)

    artifacts = export(md_path, out_dir.resolve(), formats)

    if not artifacts:
        print("[export-md] no artifacts produced.", file=sys.stderr)
        return 1

    print("[export-md] produced:")
    for fmt, path in artifacts.items():
        print(f"  {fmt.upper():4s} {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
