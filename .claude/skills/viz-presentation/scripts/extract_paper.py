#!/usr/bin/env python3
"""
Extract a PDF paper into (markdown text + figures + tables + asset index).

Primary backend: Docling (strong layout + figure extraction).
Fallback backend: PyMuPDF (fitz) — works everywhere Python runs.

Usage:
    python3 extract_paper.py input.pdf output_dir/

Produces:
    output_dir/paper.md           # full text as markdown
    output_dir/assets/fig-*.png   # extracted figures
    output_dir/assets/tbl-*.png   # extracted tables (fallback: screenshots of table regions)
    output_dir/assets.json        # asset index: {id, type, caption, page, path}

Exit codes:
    0 success (either backend)
    2 no PDF / unreadable PDF
    3 both backends failed

The asset index is what the SKILL uses to match figures to slides.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


def _log(msg: str) -> None:
    print(f"[extract_paper] {msg}", file=sys.stderr)


def _sizing_hint(w: int, h: int) -> str:
    """Suggest a Marp size directive based on aspect ratio.

    Default slide is 1280x720 with ~140px chrome → ~540px content height, ~1160px width.
    Target: max 470px tall in the body to leave room for title + caption.
    """
    if not (w and h):
        return "h:440 center"
    aspect = w / h
    if aspect >= 2.5:
        return "w:900 center"       # wide banner (architecture, pipeline)
    if aspect >= 1.5:
        return "h:420 center"       # standard landscape (bar charts, line plots)
    if aspect >= 0.9:
        return "h:460 center"       # near-square (heatmaps, SHAP)
    return "h:470 center"           # portrait/tall — likely needs its own slide, bullets off


def _write_index(out_dir: Path, paper_md: str, assets: list[dict]) -> None:
    (out_dir / "paper.md").write_text(paper_md, encoding="utf-8")
    (out_dir / "assets.json").write_text(
        json.dumps({"assets": assets}, indent=2), encoding="utf-8"
    )


def _try_docling(pdf: Path, out_dir: Path) -> bool:
    try:
        from docling.document_converter import DocumentConverter
    except ImportError:
        _log("docling not installed (optional) — trying fallback")
        return False

    try:
        _log("using Docling backend")
        converter = DocumentConverter()
        result = converter.convert(str(pdf))
        doc = result.document

        md = doc.export_to_markdown()

        assets_dir = out_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        assets: list[dict] = []
        fig_idx = 0
        tbl_idx = 0

        for pic in getattr(doc, "pictures", []) or []:
            fig_idx += 1
            asset_id = f"fig-{fig_idx:02d}"
            img = None
            for attr in ("image", "get_image"):
                try:
                    img = getattr(pic, attr)
                    if callable(img):
                        img = img()
                    if img is not None:
                        break
                except Exception:
                    pass
            asset_path = assets_dir / f"{asset_id}.png"
            w = h = None
            if img is not None:
                try:
                    img.save(asset_path)
                    w, h = img.size
                except Exception as e:
                    _log(f"could not save {asset_id}: {e}")
                    continue
            caption = ""
            for attr in ("caption", "text"):
                val = getattr(pic, attr, None)
                if isinstance(val, str) and val.strip():
                    caption = val.strip()
                    break
            page = getattr(pic, "page", None) or getattr(pic, "page_no", None)
            assets.append(
                {
                    "id": asset_id,
                    "type": "figure",
                    "caption": caption,
                    "page": page,
                    "path": str(asset_path.relative_to(out_dir)),
                    "width": w,
                    "height": h,
                    "aspect": round(w / h, 2) if (w and h) else None,
                    "sizing_hint": _sizing_hint(w, h) if (w and h) else None,
                }
            )

        for tbl in getattr(doc, "tables", []) or []:
            tbl_idx += 1
            asset_id = f"tbl-{tbl_idx:02d}"
            caption = ""
            for attr in ("caption", "text"):
                val = getattr(tbl, attr, None)
                if isinstance(val, str) and val.strip():
                    caption = val.strip()
                    break
            page = getattr(tbl, "page", None) or getattr(tbl, "page_no", None)
            md_table = ""
            try:
                md_table = tbl.export_to_markdown()
            except Exception:
                pass
            asset_path = assets_dir / f"{asset_id}.md"
            if md_table:
                asset_path.write_text(md_table, encoding="utf-8")
            assets.append(
                {
                    "id": asset_id,
                    "type": "table",
                    "caption": caption,
                    "page": page,
                    "path": str(asset_path.relative_to(out_dir)) if md_table else "",
                }
            )

        _write_index(out_dir, md, assets)
        _log(f"docling: {fig_idx} figures, {tbl_idx} tables extracted")
        return True
    except Exception as e:
        _log(f"docling backend failed: {e}")
        return False


def _try_pymupdf(pdf: Path, out_dir: Path) -> bool:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        _log("PyMuPDF not installed — cannot fall back")
        return False

    try:
        _log("using PyMuPDF fallback backend")
        doc = fitz.open(str(pdf))
        assets_dir = out_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        md_parts: list[str] = []
        assets: list[dict] = []
        fig_idx = 0

        for page_no, page in enumerate(doc, start=1):
            text = page.get_text("text") or ""
            md_parts.append(text)

            for img_ref in page.get_images(full=True):
                xref = img_ref[0]
                try:
                    pix = fitz.Pixmap(doc, xref)
                    if pix.n - pix.alpha >= 4:
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    fig_idx += 1
                    asset_id = f"fig-{fig_idx:02d}"
                    asset_path = assets_dir / f"{asset_id}.png"
                    w, h = pix.width, pix.height
                    pix.save(str(asset_path))
                    pix = None

                    caption = _guess_caption_near_image(text, fig_idx)
                    assets.append(
                        {
                            "id": asset_id,
                            "type": "figure",
                            "caption": caption,
                            "page": page_no,
                            "path": str(asset_path.relative_to(out_dir)),
                            "width": w,
                            "height": h,
                            "aspect": round(w / h, 2) if (w and h) else None,
                            "sizing_hint": _sizing_hint(w, h) if (w and h) else None,
                        }
                    )
                except Exception as e:
                    _log(f"page {page_no} image xref {xref} failed: {e}")

        md = "\n\n".join(md_parts)
        _write_index(out_dir, md, assets)
        _log(f"pymupdf: {fig_idx} figures extracted (no structured tables)")
        return True
    except Exception as e:
        _log(f"pymupdf fallback failed: {e}")
        return False


def _guess_caption_near_image(page_text: str, fig_num: int) -> str:
    """Best-effort caption lookup — finds 'Figure N.' style captions in page text."""
    patterns = [
        rf"Figure\s+{fig_num}[.:]\s*([^\n]{{0,200}})",
        rf"Fig\.\s*{fig_num}[.:]\s*([^\n]{{0,200}})",
    ]
    for pat in patterns:
        m = re.search(pat, page_text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: extract_paper.py input.pdf output_dir/", file=sys.stderr)
        return 2

    pdf = Path(sys.argv[1]).expanduser().resolve()
    out_dir = Path(sys.argv[2]).expanduser().resolve()

    if not pdf.is_file():
        _log(f"not a file: {pdf}")
        return 2
    if pdf.suffix.lower() != ".pdf":
        _log(f"not a PDF: {pdf}")
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)

    if _try_docling(pdf, out_dir):
        _log(f"wrote {out_dir}/paper.md and assets.json")
        return 0
    if _try_pymupdf(pdf, out_dir):
        _log(f"wrote {out_dir}/paper.md and assets.json (fallback mode)")
        return 0

    _log("both backends failed. install one: `uv pip install docling` or `pip install pymupdf`")
    return 3


if __name__ == "__main__":
    sys.exit(main())
