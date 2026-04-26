#!/usr/bin/env python3
"""Research profile evolution from session activity.

Called during meta-wrap-up Step 3g. Analyzes today's session memory plus
historical session data to:

  1. Always update the Research Activity Log (factual record, no approval needed)
  2. Propose new research keywords if a topic recurs across 2+ sessions
  3. Propose new active questions if a recurring theme emerges

Safety rules (from references/evolution-signals.md):
  - Never auto-modify Core Identity, Institution, Department, Career Stage
  - Activity Log: always updated
  - Keywords / Questions: proposed only, require user approval
  - No-op gracefully if research-profile.md doesn't exist

Usage:
  python3 scripts/profile-evolve.py [--date YYYY-MM-DD]
  python3 scripts/profile-evolve.py --json   # for tool consumption
"""

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROFILE_PATH = PROJECT_ROOT / "research_context" / "research-profile.md"
MEMORY_DIR = PROJECT_ROOT / "context" / "memory"
MEMORY_SEARCH = PROJECT_ROOT / "scripts" / "memory-search.py"

ACTIVITY_LOG_HEADER = "## Research Activity Log"

# Stop words to exclude when extracting topic keywords
STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "for", "to", "of", "in", "on",
    "at", "with", "by", "from", "about", "as", "is", "was", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "must", "can", "this",
    "that", "these", "those", "i", "you", "we", "they", "it", "me", "us",
    "them", "my", "your", "our", "their", "his", "her", "its", "any",
    "some", "all", "each", "every", "no", "not", "only", "own", "same",
    "than", "too", "very", "just", "into", "through", "during", "before",
    "after", "above", "below", "out", "up", "down", "over", "under",
    "again", "further", "then", "once", "here", "there", "when", "where",
    "why", "how", "what", "which", "who", "whom", "session", "goal",
    "deliverables", "decisions", "open", "threads", "based", "create",
    "make", "build", "use", "used", "using", "new", "via", "see",
    "details", "details:", "file", "files", "folder", "path",
}


def load_memory_for_date(target_date: str) -> dict | None:
    """Load and parse a single day's memory file."""
    path = MEMORY_DIR / f"{target_date}.md"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    return {"date": target_date, "raw": text}


def extract_topics(text: str, min_length: int = 4) -> list[str]:
    """Extract candidate topic keywords from session text.

    Pulls capitalized phrases and technical terms (anything that looks
    like a domain word). Excludes stopwords and short fragments.
    """
    # Find capitalized words and quoted phrases
    candidates = []
    # Capitalized multi-word phrases (e.g., "Local AI", "OpenClaw")
    for match in re.findall(r"\b([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)*)\b", text):
        if len(match) >= min_length:
            candidates.append(match.strip())
    # Quoted phrases
    for match in re.findall(r'"([^"]+)"', text):
        if len(match) >= min_length:
            candidates.append(match.strip())
    # Filter stopwords
    return [
        c for c in candidates
        if c.lower() not in STOPWORDS and not c.lower().startswith("session ")
    ]


def extract_skills_from_memory(text: str) -> list[str]:
    """Find all skill names referenced in a memory file."""
    pattern = re.compile(r"\b((?:sci|viz|tool|meta|ops)-[a-z0-9-]+)\b")
    return sorted(set(pattern.findall(text)))


def get_historical_topics(today_date: str) -> Counter:
    """Use memory-search.py --rebuild-index then load all sessions for topic counting."""
    if not MEMORY_SEARCH.exists():
        return Counter()
    try:
        # Get all sessions as JSON
        result = subprocess.run(
            ["python3", str(MEMORY_SEARCH), "--query", "", "--json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return Counter()
        sessions = json.loads(result.stdout) if result.stdout.strip() else []
    except Exception:
        return Counter()

    counter = Counter()
    for s in sessions:
        if s.get("date") == today_date:
            continue  # exclude today (we'll add it separately)
        text = " ".join(filter(None, [
            s.get("goal") or "",
            " ".join(s.get("deliverables", [])),
            " ".join(s.get("decisions", [])),
        ]))
        for topic in extract_topics(text):
            counter[topic] += 1
    return counter


def build_activity_row(today_date: str, today_memory: dict) -> str:
    """Generate one Activity Log table row for today."""
    text = today_memory["raw"]
    skills = extract_skills_from_memory(text)
    topics = extract_topics(text)
    # Pull goal from first session block
    goal_match = re.search(r"### Goal\s*\n([^\n]+)", text)
    goal = goal_match.group(1).strip() if goal_match else "(no goal)"
    if len(goal) > 60:
        goal = goal[:57] + "..."

    skills_str = ", ".join(skills) if skills else "—"
    # Take top 3 unique topics for brevity
    seen = set()
    unique_topics = []
    for t in topics:
        if t.lower() not in seen:
            seen.add(t.lower())
            unique_topics.append(t)
        if len(unique_topics) >= 3:
            break
    topics_str = ", ".join(unique_topics) if unique_topics else "—"

    return f"| {today_date} | {skills_str} | {topics_str} | {goal} |"


def update_activity_log(profile_text: str, new_row: str, today_date: str) -> str:
    """Append today's row to the Research Activity Log section.

    Idempotent: if today's date already has a row, replace it instead of appending.
    """
    if ACTIVITY_LOG_HEADER not in profile_text:
        # Append the section
        section = (
            f"\n\n{ACTIVITY_LOG_HEADER}\n\n"
            f"_Auto-updated by `scripts/profile-evolve.py` after each session._\n\n"
            f"| Date | Skills Used | Topics | Notes |\n"
            f"|------|-------------|--------|-------|\n"
            f"{new_row}\n"
        )
        return profile_text.rstrip() + section

    # Section exists — find it
    lines = profile_text.split("\n")
    out = []
    in_section = False
    today_row_replaced = False

    for line in lines:
        if line.strip() == ACTIVITY_LOG_HEADER:
            in_section = True
            out.append(line)
            continue
        if in_section and line.startswith("## ") and line.strip() != ACTIVITY_LOG_HEADER:
            # Hit next section — insert today's row before it if not already
            if not today_row_replaced:
                out.append(new_row)
                today_row_replaced = True
            in_section = False
        if in_section and line.startswith(f"| {today_date} |"):
            # Replace existing row for today
            out.append(new_row)
            today_row_replaced = True
            continue
        out.append(line)

    if in_section and not today_row_replaced:
        # Section was last in file
        out.append(new_row)

    return "\n".join(out)


def find_recurring_topics(historical: Counter, today_topics: list[str], min_count: int = 2) -> list[str]:
    """Identify topics that appear in 2+ historical sessions AND today."""
    today_set = {t.lower() for t in today_topics}
    recurring = []
    for topic, count in historical.most_common():
        if count >= (min_count - 1) and topic.lower() in today_set:
            recurring.append(topic)
    return recurring


def evolve(today_date: str, dry_run: bool = False) -> dict:
    """Main entry: update activity log, return proposals."""
    result = {
        "date": today_date,
        "profile_exists": PROFILE_PATH.exists(),
        "activity_log_updated": False,
        "proposed_keywords": [],
        "proposed_questions": [],
        "skipped_reason": None,
    }

    if not PROFILE_PATH.exists():
        result["skipped_reason"] = (
            "research_context/research-profile.md does not exist. "
            "Run sci-research-profile to create it first."
        )
        return result

    today_memory = load_memory_for_date(today_date)
    if not today_memory:
        result["skipped_reason"] = f"No memory file for {today_date}"
        return result

    today_topics = extract_topics(today_memory["raw"])
    historical = get_historical_topics(today_date)
    recurring = find_recurring_topics(historical, today_topics)

    # Propose recurring topics as new keywords (deduped)
    profile_text = PROFILE_PATH.read_text(encoding="utf-8")
    existing_keywords_match = re.search(r"Keywords[:\s]+([^\n]+)", profile_text, re.IGNORECASE)
    existing_keywords = set()
    if existing_keywords_match:
        existing_keywords = {
            k.strip().lower() for k in re.split(r"[,;]", existing_keywords_match.group(1))
        }
    result["proposed_keywords"] = [
        t for t in recurring if t.lower() not in existing_keywords
    ][:5]

    # Build activity row and update profile
    new_row = build_activity_row(today_date, today_memory)
    updated_text = update_activity_log(profile_text, new_row, today_date)

    if not dry_run and updated_text != profile_text:
        PROFILE_PATH.write_text(updated_text, encoding="utf-8")
        result["activity_log_updated"] = True

    return result


def show_activity_log() -> int:
    """Print the current Research Activity Log section. If research-profile.md
    is missing or has no Activity Log section yet, emit an explanatory
    empty-state message instead of silent empty output (L2).

    Returns the process exit code (0 for any reachable state, including
    empty — the absence of an Activity Log is a normal state on fresh
    profiles, not an error).
    """
    if not PROFILE_PATH.exists():
        print(
            "No research profile yet — run `sci-research-profile` to create "
            "one. The Activity Log will appear here after your first session."
        )
        return 0

    text = PROFILE_PATH.read_text(encoding="utf-8")
    if ACTIVITY_LOG_HEADER not in text:
        print(
            f"{ACTIVITY_LOG_HEADER} has not been created yet.\n"
            "The log is populated automatically by meta-wrap-up at the end "
            "of each session. Complete a session with at least one deliverable "
            "and the first row will appear here."
        )
        return 0

    # Extract the section and print it.
    lines = text.split("\n")
    in_section = False
    section_lines: list[str] = []
    for line in lines:
        if line.strip() == ACTIVITY_LOG_HEADER:
            in_section = True
            section_lines.append(line)
            continue
        if in_section and line.startswith("## ") and line.strip() != ACTIVITY_LOG_HEADER:
            break
        if in_section:
            section_lines.append(line)

    # Check whether the section has any actual data rows (ignore the
    # header row and separator).
    data_rows = [
        ln for ln in section_lines
        if ln.startswith("|") and not ln.startswith("| Date ") and "----" not in ln
    ]
    if not data_rows:
        print(
            f"{ACTIVITY_LOG_HEADER} exists but has no rows yet.\n"
            "meta-wrap-up will add the first row after your next session "
            "with a deliverable."
        )
        return 0

    print("\n".join(section_lines).rstrip())
    return 0


def main():
    parser = argparse.ArgumentParser(description="Evolve research profile from session activity")
    parser.add_argument("--date", help="Target date YYYY-MM-DD (default: today)")
    parser.add_argument("--dry-run", action="store_true", help="Don't write changes")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--show",
        action="store_true",
        help="Display the current Activity Log without evolving (for sci-research-profile 'show evolution').",
    )
    args = parser.parse_args()

    if args.show:
        raise SystemExit(show_activity_log())

    target_date = args.date or date.today().strftime("%Y-%m-%d")
    result = evolve(target_date, dry_run=args.dry_run)

    if args.json:
        print(json.dumps(result, indent=2))
        return

    if result["skipped_reason"]:
        print(f"Skipped: {result['skipped_reason']}")
        return

    if result["activity_log_updated"]:
        print(f"✓ Research Activity Log updated for {target_date}")
    else:
        print(f"Activity log already current for {target_date} (no change)")

    if result["proposed_keywords"]:
        print(f"\n💡 Proposed new keywords (recurring topics in 2+ sessions):")
        for k in result["proposed_keywords"]:
            print(f"  - {k}")
        print("\nReview and approve in meta-wrap-up.")
    else:
        print("\nNo new keywords proposed.")


if __name__ == "__main__":
    main()
