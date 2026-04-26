"""Google Drive desktop integration for Organon.

Relies on the Google Drive desktop app's local sync folder instead of the
Drive REST API. Zero OAuth, zero API keys — files copied into the sync
folder are uploaded by the desktop app automatically.

Layout under <Drive root>/organon/:
    data/          CSVs and datasets from sci-data-analysis
    figures/       PNGs, SVGs from viz-* skills
    manuscripts/   Markdown/PDF drafts from sci-writing
    presentations/ PDFs/PPTX from viz-presentation
    papers/        References and PDFs from sci-literature-research
    notes/         Everything else
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

CATEGORY_MAP = {
    ".csv": "data",
    ".xlsx": "data",
    ".xls": "data",
    ".parquet": "data",
    ".json": "data",
    ".tsv": "data",
    ".png": "figures",
    ".jpg": "figures",
    ".jpeg": "figures",
    ".svg": "figures",
    ".tif": "figures",
    ".tiff": "figures",
    ".pdf": "manuscripts",
    ".md": "manuscripts",
    ".docx": "manuscripts",
    ".tex": "manuscripts",
    ".pptx": "presentations",
    ".key": "presentations",
    ".bib": "papers",
}

DEFAULT_SUBFOLDER = "organon"


def find_drive_root() -> Path | None:
    """Return the 'My Drive' path for the logged-in Google Drive desktop app.

    Returns None if Google Drive desktop is not installed or not mounted.
    """
    candidates: list[Path] = []

    # macOS CloudStorage (modern)
    cloud_storage = Path.home() / "Library" / "CloudStorage"
    if cloud_storage.is_dir():
        for entry in cloud_storage.iterdir():
            if entry.name.startswith("GoogleDrive-"):
                my_drive = entry / "My Drive"
                if my_drive.is_dir():
                    candidates.append(my_drive)

    # Legacy symlink / Windows / Linux
    for alt in [
        Path.home() / "Google Drive" / "My Drive",
        Path.home() / "Google Drive",
        Path.home() / "GoogleDrive" / "My Drive",
    ]:
        if alt.is_dir():
            candidates.append(alt)

    return candidates[0] if candidates else None


def ensure_staging_root() -> Path:
    """Return the organon subfolder inside My Drive, creating it if needed."""
    root = find_drive_root()
    if root is None:
        raise SystemExit(
            "ERROR: Google Drive desktop not detected. Install it from "
            "https://www.google.com/drive/download/ and sign in, then re-run."
        )
    staging = root / DEFAULT_SUBFOLDER
    staging.mkdir(exist_ok=True)
    return staging


def categorize(path: Path) -> str:
    return CATEGORY_MAP.get(path.suffix.lower(), "notes")


def stage(src: Path, category: str | None = None, rename: str | None = None) -> Path:
    if not src.exists():
        raise SystemExit(f"ERROR: source not found: {src}")
    if src.is_dir():
        raise SystemExit(f"ERROR: directories not yet supported (pass individual files): {src}")

    staging_root = ensure_staging_root()
    cat = category or categorize(src)
    dest_dir = staging_root / cat
    dest_dir.mkdir(exist_ok=True)

    dest_name = rename or src.name
    dest = dest_dir / dest_name
    if dest.exists():
        stem, ext = Path(dest_name).stem, Path(dest_name).suffix
        ts = int(time.time())
        dest = dest_dir / f"{stem}_{ts}{ext}"
        counter = 1
        while dest.exists():
            dest = dest_dir / f"{stem}_{ts}_{counter}{ext}"
            counter += 1

    shutil.copy2(src, dest)
    return dest


def status() -> dict:
    root = find_drive_root()
    if root is None:
        return {
            "installed": False,
            "error": "Google Drive desktop not detected",
            "drive_root": None,
            "staging_root": None,
        }
    staging = root / DEFAULT_SUBFOLDER
    return {
        "installed": True,
        "drive_root": str(root),
        "staging_root": str(staging) if staging.is_dir() else None,
        "staging_exists": staging.is_dir(),
    }


def list_staged(category: str | None = None) -> list[dict]:
    root = find_drive_root()
    if root is None:
        return []
    staging = root / DEFAULT_SUBFOLDER
    if not staging.is_dir():
        return []
    search_roots = [staging / category] if category else [
        staging / c for c in set(CATEGORY_MAP.values()) | {"notes"}
    ]
    entries: list[dict] = []
    for sr in search_roots:
        if not sr.is_dir():
            continue
        for f in sorted(sr.iterdir()):
            if f.is_file():
                stat = f.stat()
                entries.append({
                    "category": sr.name,
                    "name": f.name,
                    "size_bytes": stat.st_size,
                    "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                    "path": str(f),
                })
    return entries


def share_link(local_path: Path) -> str:
    """Return a Finder/browser URL for the file. Desktop app generates actual
    share links only via right-click; this opens the containing folder.
    """
    return f"file://{local_path.resolve()}"


# ---------------------------------------------------------------------------
# E3 — audit bundle staging
# ---------------------------------------------------------------------------

_AUDIT_PATTERNS = ("*.bib", "*.citations.json", "*-audit.md")


def _find_audit_artifacts(md_path: Path) -> list[Path]:
    """Return sorted list of audit artefacts adjacent to the markdown file.

    Searches the same directory for: *.bib, *.citations.json, *-audit.md.
    Does NOT include the markdown file itself.
    """
    found: list[Path] = []
    for pattern in _AUDIT_PATTERNS:
        found.extend(sorted(md_path.parent.glob(pattern)))
    return sorted(set(found))


def stage_audit_bundle(md_path: Path) -> dict:
    """Stage a markdown file together with its adjacent audit artefacts.

    Creates a sibling folder named ``{stem}_audit`` under the manuscripts
    Drive category and copies the .md + every *.bib, *.citations.json, and
    *-audit.md found next to the markdown.

    Returns a dict with keys:
        bundle_dir  — absolute Drive path of the ``{stem}_audit/`` folder
        staged      — list of dicts {src, dest, size_bytes}
        skipped     — list of src paths that could not be read
    """
    if not md_path.exists():
        raise SystemExit(f"ERROR: source not found: {md_path}")
    if md_path.suffix.lower() != ".md":
        raise SystemExit(f"ERROR: stage-bundle expects a .md file, got: {md_path}")

    staging_root = ensure_staging_root()
    bundle_dir = staging_root / "manuscripts" / f"{md_path.stem}_audit"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    artefacts = [md_path] + _find_audit_artifacts(md_path)
    staged: list[dict] = []
    skipped: list[str] = []

    for src in artefacts:
        dest = bundle_dir / src.name
        if dest.exists():
            stem, ext = src.stem, src.suffix
            ts = int(time.time())
            dest = bundle_dir / f"{stem}_{ts}{ext}"
        try:
            shutil.copy2(src, dest)
            staged.append({"src": str(src), "dest": str(dest), "size_bytes": dest.stat().st_size})
        except OSError as exc:
            skipped.append(str(src))

    return {"bundle_dir": str(bundle_dir), "staged": staged, "skipped": skipped}


def main() -> int:
    parser = argparse.ArgumentParser(prog="gdrive_ops", description="Google Drive desktop integration")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_status = sub.add_parser("status", help="Show Drive mount + staging root status")
    p_status.add_argument("--json", action="store_true")

    p_stage = sub.add_parser("stage", help="Copy a local file into the Drive staging folder")
    p_stage.add_argument("file", help="Local file to stage")
    p_stage.add_argument("--category", help="Override auto-categorization", default=None)
    p_stage.add_argument("--rename", help="Rename the file on upload", default=None)
    p_stage.add_argument("--json", action="store_true")

    p_list = sub.add_parser("list", help="List staged files")
    p_list.add_argument("--category", default=None)
    p_list.add_argument("--json", action="store_true")

    p_bundle = sub.add_parser(
        "stage-bundle",
        help="Stage a .md file together with its adjacent audit artefacts (E3)",
    )
    p_bundle.add_argument("file", help="Markdown file whose audit bundle to stage")
    p_bundle.add_argument("--json", action="store_true")

    p_link = sub.add_parser("link", help="Print the file:// URL for a staged path")
    p_link.add_argument("path")

    args = parser.parse_args()

    if args.cmd == "status":
        s = status()
        if args.json:
            print(json.dumps(s, indent=2))
        else:
            if not s["installed"]:
                print(f"✗ {s['error']}")
                return 1
            print(f"✓ Google Drive desktop: {s['drive_root']}")
            print(f"  staging root:          {s['staging_root'] or '(not created yet)'}")
        return 0

    if args.cmd == "stage":
        dest = stage(Path(args.file), category=args.category, rename=args.rename)
        if args.json:
            print(json.dumps({"staged": str(dest), "size_bytes": dest.stat().st_size}))
        else:
            print(f"✓ staged → {dest}")
            print(f"  category: {dest.parent.name}")
            print(f"  size:     {dest.stat().st_size:,} bytes")
            print(f"  link:     {share_link(dest)}")
        return 0

    if args.cmd == "list":
        entries = list_staged(category=args.category)
        if args.json:
            print(json.dumps(entries, indent=2))
        else:
            if not entries:
                print("(no staged files)")
                return 0
            by_cat: dict[str, list[dict]] = {}
            for e in entries:
                by_cat.setdefault(e["category"], []).append(e)
            for cat in sorted(by_cat):
                print(f"\n{cat}/ ({len(by_cat[cat])} files)")
                for e in by_cat[cat]:
                    size_kb = e["size_bytes"] / 1024
                    print(f"  {e['name']:<50} {size_kb:>8.1f} KB  {e['mtime']}")
        return 0

    if args.cmd == "stage-bundle":
        result = stage_audit_bundle(Path(args.file))
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            n = len(result["staged"])
            print(f"✓ staged {n} file(s) → {result['bundle_dir']}/")
            for item in result["staged"]:
                size_kb = item["size_bytes"] / 1024
                print(f"  {Path(item['src']).name:<50} {size_kb:>8.1f} KB")
            if result["skipped"]:
                print(f"  ⚠ skipped ({len(result['skipped'])}): {', '.join(Path(p).name for p in result['skipped'])}")
        return 0 if not result["skipped"] else 1

    if args.cmd == "link":
        print(share_link(Path(args.path)))
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
