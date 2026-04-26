#!/usr/bin/env python3
"""Session-wide memory search for Organon.

Searches across ALL session memory files (context/memory/*.md), not just
today + yesterday. Supports keyword search, date range filter, skill filter,
project filter, and combinations.

Memory file format (one file per day, multiple sessions):
    ## Session N
    ### Project (optional)
    project-name
    ### Goal
    one-line goal
    ### Deliverables
    - path/file — description
    ### Decisions
    - decision and rationale
    ### Open threads
    - unfinished items

Two modes:
    search:        --query, --date-from, --date-to, --skill, --project
    rebuild-index: regenerates context/memory/index.json from .md files

Usage:
    python3 scripts/memory-search.py --query "CRISPR"
    python3 scripts/memory-search.py --skill sci-communication
    python3 scripts/memory-search.py --rebuild-index
    python3 scripts/memory-search.py --query "OpenClaw" --json
"""

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MEMORY_DIR = PROJECT_ROOT / "context" / "memory"
INDEX_PATH = MEMORY_DIR / "index.json"

# Skill name pattern: category-skillname (e.g., sci-writing, viz-nano-banana)
SKILL_PATTERN = re.compile(r"\b((?:sci|viz|tool|meta|ops|gsd)-[a-z0-9-]+)\b")
# Date pattern in filename: 2026-04-09.md
DATE_FILENAME = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")


def parse_session_blocks(text: str, date_str: str) -> list[dict]:
    """Parse a memory file into structured session blocks."""
    sessions = []
    # Split on "## Session N" headers
    parts = re.split(r"^## Session (\d+)\s*$", text, flags=re.MULTILINE)
    # parts[0] is content before any session (often empty or header)
    # then alternating: number, body, number, body, ...
    for i in range(1, len(parts), 2):
        session_num = int(parts[i])
        body = parts[i + 1] if i + 1 < len(parts) else ""

        session = {
            "date": date_str,
            "session": session_num,
            "project": _extract_section(body, "Project"),
            "goal": _extract_section(body, "Goal"),
            "deliverables": _extract_list(body, "Deliverables"),
            "decisions": _extract_list(body, "Decisions"),
            "open_threads": _extract_list(body, "Open threads"),
        }
        # Mine skills from deliverables (file paths) and goal text
        skills = set()
        scan_text = " ".join([
            session["goal"] or "",
            " ".join(session["deliverables"]),
            " ".join(session["decisions"]),
        ])
        for match in SKILL_PATTERN.findall(scan_text):
            skills.add(match)
        # Also check deliverable paths for projects/{skill-name}/ patterns
        for d in session["deliverables"]:
            m = re.search(r"projects/([a-z]+-[a-z0-9-]+)/", d)
            if m:
                # Map output folder to skill (sci-communication folder ↔ sci-communication skill)
                folder = m.group(1)
                skills.add(folder)

        session["skills"] = sorted(skills)
        sessions.append(session)

    return sessions


def _extract_section(body: str, name: str) -> str | None:
    """Extract a single-line section value (### Name → next non-empty line)."""
    pattern = re.compile(rf"^### {re.escape(name)}\s*$", re.MULTILINE)
    m = pattern.search(body)
    if not m:
        return None
    after = body[m.end():].lstrip("\n")
    # Stop at next ### header or end
    next_header = re.search(r"^###\s", after, re.MULTILINE)
    if next_header:
        chunk = after[: next_header.start()]
    else:
        chunk = after
    chunk = chunk.strip()
    if not chunk:
        return None
    # Return first non-empty line for single-value fields
    return chunk.split("\n")[0].strip()


def _extract_list(body: str, name: str) -> list[str]:
    """Extract a bulleted list section."""
    pattern = re.compile(rf"^### {re.escape(name)}\s*$", re.MULTILINE)
    m = pattern.search(body)
    if not m:
        return []
    after = body[m.end():]
    next_header = re.search(r"^###\s", after, re.MULTILINE)
    if next_header:
        chunk = after[: next_header.start()]
    else:
        chunk = after
    items = []
    for line in chunk.strip().split("\n"):
        line = line.strip()
        if line.startswith("-"):
            items.append(line.lstrip("- ").strip())
    return items


def iter_memory_files() -> Iterator[tuple[str, Path]]:
    """Yield (date_str, path) for every memory file, sorted oldest to newest."""
    if not MEMORY_DIR.exists():
        return
    for path in sorted(MEMORY_DIR.glob("*.md")):
        m = DATE_FILENAME.match(path.name)
        if m:
            yield m.group(1), path


def load_all_sessions() -> list[dict]:
    """Parse every memory file and return a flat list of session dicts."""
    sessions = []
    for date_str, path in iter_memory_files():
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        sessions.extend(parse_session_blocks(text, date_str))
    return sessions


def session_matches(
    session: dict,
    query: str | None,
    date_from: date | None,
    date_to: date | None,
    skill: str | None,
    project: str | None,
) -> bool:
    """Apply all filters to a session. AND semantics."""
    sess_date = datetime.strptime(session["date"], "%Y-%m-%d").date()
    if date_from and sess_date < date_from:
        return False
    if date_to and sess_date > date_to:
        return False
    if skill and skill not in session["skills"]:
        return False
    if project:
        proj = (session.get("project") or "").lower()
        if project.lower() not in proj:
            return False
    if query:
        haystack = " ".join(filter(None, [
            session.get("goal") or "",
            session.get("project") or "",
            " ".join(session["deliverables"]),
            " ".join(session["decisions"]),
            " ".join(session["open_threads"]),
        ])).lower()
        if query.lower() not in haystack:
            return False
    return True


def find_snippet(session: dict, query: str | None, max_len: int = 200) -> str:
    """Return a contextual snippet for display, ideally containing the query."""
    candidates = [
        session.get("goal") or "",
        session.get("project") or "",
        " ".join(session["deliverables"]),
        " ".join(session["decisions"]),
    ]
    if query:
        q = query.lower()
        for c in candidates:
            if q in c.lower():
                idx = c.lower().find(q)
                start = max(0, idx - 40)
                end = min(len(c), idx + len(query) + 100)
                snippet = c[start:end]
                return snippet[:max_len]
    # Fallback: goal
    return (session.get("goal") or "")[:max_len]


def format_human(matches: list[dict], query: str | None) -> str:
    """Render matches as a human-readable list, newest first."""
    if not matches:
        return "No matching sessions found."
    matches.sort(key=lambda s: (s["date"], s["session"]), reverse=True)
    lines = [f"Found {len(matches)} matching session(s):", ""]
    for s in matches:
        skills = ", ".join(s["skills"]) if s["skills"] else "—"
        proj = s.get("project") or ""
        lines.append(f"📅 {s['date']} — Session {s['session']}" + (f" [{proj}]" if proj else ""))
        lines.append(f"   Goal: {s.get('goal') or '(no goal recorded)'}")
        lines.append(f"   Skills: {skills}")
        snippet = find_snippet(s, query)
        if snippet:
            lines.append(f"   Context: {snippet}")
        lines.append("")
    return "\n".join(lines)


def _atomic_write_json(path: Path, payload: dict) -> None:
    """Write `payload` to `path` atomically with an advisory flock.

    Two concurrent rebuilds (two sessions, or a session + a cron job)
    would otherwise race on index.json. fcntl.flock serialises them on
    POSIX; os.replace makes the final swap atomic so readers never see
    a half-written file. On Windows fcntl is missing — we fall back to
    just the os.replace swap, which is still atomic per NT semantics
    but not mutually exclusive.
    """
    import os as _os
    import tempfile

    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")

    lock_fh = open(lock_path, "w")
    try:
        try:
            import fcntl  # POSIX only
            fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
        except ImportError:
            pass  # Windows — degrade gracefully to os.replace atomicity only.

        # Write to sibling tempfile, then atomic rename.
        fd, tmp = tempfile.mkstemp(
            prefix=path.name + ".",
            suffix=".tmp",
            dir=str(path.parent),
        )
        try:
            with _os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
                f.flush()
                _os.fsync(f.fileno())
            _os.replace(tmp, path)
        except Exception:
            try:
                _os.unlink(tmp)
            except FileNotFoundError:
                pass
            raise
    finally:
        lock_fh.close()
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def rebuild_index() -> dict:
    """Regenerate context/memory/index.json from all memory files."""
    sessions = load_all_sessions()
    index_sessions = []
    for s in sessions:
        index_sessions.append({
            "date": s["date"],
            "session": s["session"],
            "goal": s.get("goal"),
            "project": s.get("project"),
            "skills": s["skills"],
            "deliverables_count": len(s["deliverables"]),
        })
    payload = {
        "sessions": index_sessions,
        "last_rebuilt": datetime.now().strftime("%Y-%m-%d"),
        "total": len(index_sessions),
    }
    _atomic_write_json(INDEX_PATH, payload)
    return payload


def main():
    parser = argparse.ArgumentParser(
        description="Search session memory across all dates."
    )
    parser.add_argument("--query", help="Keyword to search across all session fields")
    parser.add_argument("--date-from", help="Earliest session date (YYYY-MM-DD)")
    parser.add_argument("--date-to", help="Latest session date (YYYY-MM-DD)")
    parser.add_argument("--skill", help="Filter by skill name (e.g., sci-writing)")
    parser.add_argument("--project", help="Filter by project name (substring match)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--rebuild-index", action="store_true", help="Regenerate index.json")
    args = parser.parse_args()

    if args.rebuild_index:
        payload = rebuild_index()
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"Index rebuilt: {payload['total']} sessions across "
                  f"{len(set(s['date'] for s in payload['sessions']))} days.")
            print(f"Saved to {INDEX_PATH}")
        return

    date_from = (
        datetime.strptime(args.date_from, "%Y-%m-%d").date() if args.date_from else None
    )
    date_to = (
        datetime.strptime(args.date_to, "%Y-%m-%d").date() if args.date_to else None
    )

    sessions = load_all_sessions()
    matches = [
        s for s in sessions
        if session_matches(s, args.query, date_from, date_to, args.skill, args.project)
    ]

    if args.json:
        print(json.dumps(matches, indent=2))
    else:
        print(format_human(matches, args.query))


if __name__ == "__main__":
    main()
