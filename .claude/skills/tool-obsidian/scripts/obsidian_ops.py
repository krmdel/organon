"""Obsidian vault integration for Organon.

Optional passthrough skill: writes markdown notes into a local Obsidian
vault folder so the user's knowledge graph can index them. Obsidian itself
provides search, backlinks, tags, and the graph view — this script just
writes well-formed .md files with frontmatter and wikilinks.

Vault detection order:
  1. $OBSIDIAN_VAULT env var (override)
  2. ~/Library/Application Support/obsidian/obsidian.json vault registry (macOS)
  3. Common paths: ~/Documents/Obsidian, ~/Obsidian, ~/Vaults

If no vault is found, every write command exits with a clear message —
the rest of the framework continues to work normally.

Layout under <vault>/organon/:
    data-notes/    observations from sci-data-analysis
    paper-notes/   literature notes from sci-literature-research
    daily/         daily session summaries (YYYY-MM-DD.md)
    experiments/   hypothesis / experiment notes
    drafts/        manuscript drafts in progress
    inbox/         unsorted / quick capture
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import quote

CATEGORIES = {
    "data-notes",
    "paper-notes",
    "daily",
    "experiments",
    "drafts",
    "inbox",
}
DEFAULT_CATEGORY = "inbox"
SUBFOLDER = "organon"

MACOS_REGISTRY = Path.home() / "Library" / "Application Support" / "obsidian" / "obsidian.json"


def _from_env() -> Path | None:
    raw = os.environ.get("OBSIDIAN_VAULT", "").strip()
    if not raw:
        return None
    p = Path(os.path.expanduser(raw))
    return p if p.is_dir() else None


def _from_registry() -> Path | None:
    if not MACOS_REGISTRY.is_file():
        return None
    try:
        data = json.loads(MACOS_REGISTRY.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    vaults = data.get("vaults", {})
    if not vaults:
        return None
    # Pick the most-recently-opened (Obsidian stores `ts` per vault)
    sorted_vaults = sorted(
        vaults.items(),
        key=lambda kv: kv[1].get("ts", 0),
        reverse=True,
    )
    for _vault_id, meta in sorted_vaults:
        path = meta.get("path")
        if path and Path(path).is_dir():
            return Path(path)
    return None


def _from_common_paths() -> Path | None:
    candidates = [
        Path.home() / "Documents" / "Obsidian",
        Path.home() / "Obsidian",
        Path.home() / "Vaults",
    ]
    for c in candidates:
        if c.is_dir():
            # Pick first subdirectory that looks like a vault (contains .obsidian)
            for child in sorted(c.iterdir()):
                if child.is_dir() and (child / ".obsidian").is_dir():
                    return child
            # Or treat the folder itself as vault if it has .obsidian
            if (c / ".obsidian").is_dir():
                return c
    return None


def find_vault() -> Path | None:
    """Return the active Obsidian vault path, or None if not detected."""
    return _from_env() or _from_registry() or _from_common_paths()


def ensure_staging_root() -> Path:
    vault = find_vault()
    if vault is None:
        raise SystemExit(
            "ERROR: Obsidian vault not detected. Set OBSIDIAN_VAULT=/path/to/vault "
            "in .env, or install Obsidian and open a vault. Scientific-os will "
            "keep working without Obsidian — this skill is optional."
        )
    staging = vault / SUBFOLDER
    staging.mkdir(exist_ok=True)
    return staging


def slugify(title: str) -> str:
    """Convert a note title to a safe filename."""
    s = title.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    return s.strip("-") or "untitled"


def build_frontmatter(
    title: str,
    tags: list[str] | None = None,
    links: list[str] | None = None,
    source: str | None = None,
) -> str:
    lines = ["---", f"title: {title}", f"created: {date.today().isoformat()}"]
    if tags:
        clean = [t.lstrip("#") for t in tags if t]
        lines.append(f"tags: [{', '.join(clean)}]")
    if source:
        lines.append(f"source: {source}")
    if links:
        lines.append("links:")
        for l in links:
            lines.append(f"  - \"[[{l}]]\"")
    lines.append("---")
    return "\n".join(lines) + "\n"


def write_note(
    title: str,
    body: str,
    category: str = DEFAULT_CATEGORY,
    tags: list[str] | None = None,
    links: list[str] | None = None,
    source: str | None = None,
    overwrite: bool = False,
) -> Path:
    if category not in CATEGORIES:
        raise SystemExit(
            f"ERROR: unknown category '{category}'. Choose from: {sorted(CATEGORIES)}"
        )

    staging_root = ensure_staging_root()
    cat_dir = staging_root / category
    cat_dir.mkdir(exist_ok=True)

    fname = slugify(title) + ".md"
    dest = cat_dir / fname
    if dest.exists() and not overwrite:
        counter = 1
        while True:
            candidate = cat_dir / f"{slugify(title)}-{counter}.md"
            if not candidate.exists():
                dest = candidate
                break
            counter += 1

    fm = build_frontmatter(title, tags=tags, links=links, source=source)
    header = f"# {title}\n\n"
    content = fm + "\n" + header + body.rstrip() + "\n"
    dest.write_text(content)
    return dest


def append_to_note(note_path: Path, body: str, heading: str | None = None) -> Path:
    if not note_path.exists():
        raise SystemExit(f"ERROR: note not found: {note_path}")
    existing = note_path.read_text()
    if not existing.endswith("\n"):
        existing += "\n"
    block = ""
    if heading:
        block += f"\n## {heading}\n\n"
    else:
        block += "\n"
    block += body.rstrip() + "\n"
    note_path.write_text(existing + block)
    return note_path


def daily_note_path() -> Path:
    staging = ensure_staging_root()
    daily_dir = staging / "daily"
    daily_dir.mkdir(exist_ok=True)
    return daily_dir / f"{date.today().isoformat()}.md"


def append_daily(body: str, heading: str | None = None) -> Path:
    path = daily_note_path()
    if not path.exists():
        # Seed the daily note with a minimal frontmatter
        title = date.today().isoformat()
        fm = build_frontmatter(title, tags=["daily"])
        path.write_text(fm + f"\n# {title}\n")
    return append_to_note(path, body, heading=heading)


def status() -> dict:
    vault = find_vault()
    if vault is None:
        return {
            "installed": False,
            "error": "Obsidian vault not detected — skill is optional, framework unaffected",
            "vault_root": None,
            "staging_root": None,
        }
    staging = vault / SUBFOLDER
    return {
        "installed": True,
        "vault_root": str(vault),
        "vault_name": vault.name,
        "staging_root": str(staging) if staging.is_dir() else None,
        "staging_exists": staging.is_dir(),
        "detection_source": (
            "env" if _from_env() else
            "registry" if _from_registry() else
            "common-paths"
        ),
    }


def list_notes(category: str | None = None) -> list[dict]:
    vault = find_vault()
    if vault is None:
        return []
    staging = vault / SUBFOLDER
    if not staging.is_dir():
        return []
    search_dirs = [staging / category] if category else [staging / c for c in CATEGORIES]
    entries: list[dict] = []
    for d in search_dirs:
        if not d.is_dir():
            continue
        for note in sorted(d.glob("*.md")):
            stat = note.stat()
            entries.append({
                "category": d.name,
                "name": note.name,
                "size_bytes": stat.st_size,
                "path": str(note),
                "obsidian_uri": obsidian_uri(note, vault),
            })
    return entries


def search_notes(query: str, category: str | None = None) -> list[dict]:
    """Filesystem grep across note contents — case-insensitive."""
    vault = find_vault()
    if vault is None:
        return []
    staging = vault / SUBFOLDER
    if not staging.is_dir():
        return []
    search_dirs = [staging / category] if category else [staging / c for c in CATEGORIES]
    q = query.lower()
    results: list[dict] = []
    for d in search_dirs:
        if not d.is_dir():
            continue
        for note in d.glob("*.md"):
            try:
                text = note.read_text()
            except OSError:
                continue
            if q in text.lower() or q in note.name.lower():
                # Find the first matching line for a snippet
                snippet = ""
                for line in text.splitlines():
                    if q in line.lower():
                        snippet = line.strip()[:120]
                        break
                results.append({
                    "category": d.name,
                    "name": note.name,
                    "path": str(note),
                    "snippet": snippet,
                    "obsidian_uri": obsidian_uri(note, find_vault()),
                })
    return results


def obsidian_uri(note_path: Path, vault: Path | None = None) -> str:
    """Return an obsidian:// URI that opens the note in Obsidian."""
    vault = vault or find_vault()
    if vault is None:
        return ""
    try:
        rel = note_path.relative_to(vault)
    except ValueError:
        rel = Path(note_path.name)
    return f"obsidian://open?vault={quote(vault.name)}&file={quote(str(rel.with_suffix('')))}"


def main() -> int:
    parser = argparse.ArgumentParser(prog="obsidian_ops", description="Obsidian vault integration")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_status = sub.add_parser("status", help="Show vault mount + staging root status")
    p_status.add_argument("--json", action="store_true")

    p_write = sub.add_parser("write", help="Create a new note in the vault")
    p_write.add_argument("title", help="Note title")
    p_write.add_argument("--body", default=None, help="Note body (markdown)")
    p_write.add_argument("--from-file", default=None, help="Read body from file")
    p_write.add_argument("--category", choices=sorted(CATEGORIES), default=DEFAULT_CATEGORY)
    p_write.add_argument("--tags", default=None, help="Comma-separated tags")
    p_write.add_argument("--link-to", default=None, help="Comma-separated note titles to [[link]]")
    p_write.add_argument("--source", default=None, help="Source reference (URL, DOI, file path)")
    p_write.add_argument("--overwrite", action="store_true")
    p_write.add_argument("--json", action="store_true")

    p_append = sub.add_parser("append", help="Append to an existing note")
    p_append.add_argument("note", help="Path to note (relative to vault or absolute)")
    p_append.add_argument("--body", default=None)
    p_append.add_argument("--from-file", default=None)
    p_append.add_argument("--heading", default=None, help="Optional ## heading to insert")

    p_daily = sub.add_parser("daily", help="Append to today's daily note")
    p_daily.add_argument("--body", default=None)
    p_daily.add_argument("--from-file", default=None)
    p_daily.add_argument("--heading", default=None)

    p_list = sub.add_parser("list", help="List staged notes")
    p_list.add_argument("--category", choices=sorted(CATEGORIES), default=None)
    p_list.add_argument("--json", action="store_true")

    p_search = sub.add_parser("search", help="Filesystem search across staged notes")
    p_search.add_argument("query")
    p_search.add_argument("--category", choices=sorted(CATEGORIES), default=None)
    p_search.add_argument("--json", action="store_true")

    p_link = sub.add_parser("link", help="Return obsidian:// URI for a note")
    p_link.add_argument("note", help="Path to the note")

    args = parser.parse_args()

    if args.cmd == "status":
        s = status()
        if args.json:
            print(json.dumps(s, indent=2))
        else:
            if not s["installed"]:
                print(f"✗ {s['error']}")
                return 1
            print(f"✓ Obsidian vault: {s['vault_root']}")
            print(f"  detected via: {s['detection_source']}")
            print(f"  staging root: {s['staging_root'] or '(not created yet)'}")
        return 0

    if args.cmd == "write":
        body = args.body
        if args.from_file:
            body = Path(args.from_file).read_text()
        if body is None:
            body = sys.stdin.read() if not sys.stdin.isatty() else ""
        tags = [t.strip() for t in args.tags.split(",")] if args.tags else None
        links = [l.strip() for l in args.link_to.split(",")] if args.link_to else None
        dest = write_note(
            args.title, body or "(empty)",
            category=args.category, tags=tags, links=links,
            source=args.source, overwrite=args.overwrite,
        )
        result = {
            "staged": str(dest),
            "category": dest.parent.name,
            "size_bytes": dest.stat().st_size,
            "obsidian_uri": obsidian_uri(dest),
        }
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"✓ note written → {dest}")
            print(f"  category: {result['category']}")
            print(f"  size:     {result['size_bytes']:,} bytes")
            print(f"  open in obsidian: {result['obsidian_uri']}")
        return 0

    if args.cmd == "append":
        body = args.body
        if args.from_file:
            body = Path(args.from_file).read_text()
        if body is None:
            body = sys.stdin.read() if not sys.stdin.isatty() else ""
        note_path = Path(args.note)
        if not note_path.is_absolute():
            # Treat as vault-relative
            vault = find_vault()
            if vault is None:
                raise SystemExit("ERROR: Obsidian vault not detected")
            note_path = vault / args.note
        append_to_note(note_path, body or "", heading=args.heading)
        print(f"✓ appended → {note_path}")
        return 0

    if args.cmd == "daily":
        body = args.body
        if args.from_file:
            body = Path(args.from_file).read_text()
        if body is None:
            body = sys.stdin.read() if not sys.stdin.isatty() else ""
        path = append_daily(body or "", heading=args.heading)
        print(f"✓ appended to daily note → {path}")
        print(f"  open in obsidian: {obsidian_uri(path)}")
        return 0

    if args.cmd == "list":
        entries = list_notes(category=args.category)
        if args.json:
            print(json.dumps(entries, indent=2))
        else:
            if not entries:
                print("(no staged notes)")
                return 0
            by_cat: dict[str, list[dict]] = {}
            for e in entries:
                by_cat.setdefault(e["category"], []).append(e)
            for cat in sorted(by_cat):
                print(f"\n{cat}/ ({len(by_cat[cat])} notes)")
                for e in by_cat[cat]:
                    print(f"  {e['name']:<50} {e['size_bytes']:>6} bytes")
        return 0

    if args.cmd == "search":
        results = search_notes(args.query, category=args.category)
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            if not results:
                print(f"(no matches for '{args.query}')")
                return 0
            print(f"{len(results)} match{'es' if len(results) != 1 else ''}:")
            for r in results:
                print(f"  {r['category']}/{r['name']}")
                if r["snippet"]:
                    print(f"    → {r['snippet']}")
        return 0

    if args.cmd == "link":
        print(obsidian_uri(Path(args.note)))
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
