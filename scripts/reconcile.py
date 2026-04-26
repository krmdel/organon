#!/usr/bin/env python3
"""Reconcile skills on disk against the catalog and CLAUDE.md registry.

CLAUDE.md Reconciliation describes this contract: detect drift between
.claude/skills/ (source of truth), .claude/skills/_catalog/catalog.json,
and the Skill Registry table in CLAUDE.md, and report it. The intended
flow is that /lets-go or SessionStart hooks invoke this script and
Claude surfaces drift before any other work begins.

Usage:
    python3 scripts/reconcile.py            # human-readable report
    python3 scripts/reconcile.py --json     # machine-readable report
    python3 scripts/reconcile.py --strict   # exit 1 on any drift

Exit codes:
    0 — no drift (or drift present but not --strict)
    1 — drift present and --strict, OR an IO/parse error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PROJECT_ROOT / ".claude" / "skills"
CATALOG_PATH = SKILLS_DIR / "_catalog" / "catalog.json"
CLAUDE_MD = PROJECT_ROOT / "CLAUDE.md"

SKIP_DIRS = {"_catalog"}

# Skills intentionally excluded from the public repo via .gitignore but
# may exist locally (or be referenced in catalog.json / CLAUDE.md). The
# reconcile contract treats them as "not subject to drift" rather than
# either side of the consistency check, so neither a missing folder
# (CI clone) nor a missing registry row (local edit) trips drift.
GITIGNORED_SKILLS = {"tool-substack", "tool-social-publisher"}


@dataclass
class Drift:
    on_disk_not_catalog: list[str] = field(default_factory=list)
    catalog_not_on_disk: list[str] = field(default_factory=list)
    on_disk_not_claude_md: list[str] = field(default_factory=list)
    claude_md_not_on_disk: list[str] = field(default_factory=list)
    name_folder_mismatches: list[str] = field(default_factory=list)

    def total(self) -> int:
        return sum(len(getattr(self, f.name)) for f in [
            *[f for f in type(self).__dataclass_fields__.values()]
        ])

    def empty(self) -> bool:
        return self.total() == 0


def disk_skills() -> set[str]:
    """Every direct subdirectory of .claude/skills/ that isn't in the
    skip list or a hidden folder."""
    if not SKILLS_DIR.exists():
        return set()
    return {
        p.name for p in SKILLS_DIR.iterdir()
        if p.is_dir() and p.name not in SKIP_DIRS and not p.name.startswith(".")
    }


def catalog_skills() -> set[str]:
    if not CATALOG_PATH.exists():
        return set()
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return set(data.get("skills", {}).keys()) | set(data.get("core_skills", []))


def claude_md_skills() -> set[str]:
    """Scrape the CLAUDE.md Skill Registry for the first-column skill
    names. The registry uses GitHub-flavored markdown tables; we look
    for rows inside the `## Skill Registry` section whose first cell
    looks like a kebab-case skill name."""
    if not CLAUDE_MD.exists():
        return set()
    text = CLAUDE_MD.read_text(encoding="utf-8")

    # Narrow to the Skill Registry section so we don't pick up incidental
    # code fences with skill names mentioned elsewhere.
    start = text.find("## Skill Registry")
    if start < 0:
        return set()
    end = text.find("\n## ", start + 1)
    section = text[start:end] if end > 0 else text[start:]

    skills: set[str] = set()
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        # Strip leading/trailing pipes, split.
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells:
            continue
        first = cells[0]
        # Header row and separator row aren't skills.
        if first.lower() == "skill" or set(first) <= set("- "):
            continue
        # Strip backticks around the name if present.
        first = first.strip("`")
        if re.fullmatch(r"(sci|ops|viz|meta|tool)-[a-z][a-z0-9-]*", first):
            skills.add(first)
    return skills


def name_folder_mismatches(disk: set[str]) -> list[str]:
    """For each disk skill, parse its SKILL.md frontmatter and check
    whether the `name:` field matches the folder name."""
    mismatches: list[str] = []
    for name in disk:
        skill_md = SKILLS_DIR / name / "SKILL.md"
        if not skill_md.exists():
            continue
        text = skill_md.read_text(encoding="utf-8")
        m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
        if not m:
            continue
        block = m.group(1)
        nm = re.search(r"^name:\s*(.+)$", block, re.MULTILINE)
        if nm and nm.group(1).strip() != name:
            mismatches.append(f"{name} (yaml name={nm.group(1).strip()})")
    return mismatches


def compute_drift() -> Drift:
    disk = disk_skills() - GITIGNORED_SKILLS
    catalog = catalog_skills() - GITIGNORED_SKILLS
    claude = claude_md_skills() - GITIGNORED_SKILLS

    return Drift(
        on_disk_not_catalog=sorted(disk - catalog),
        catalog_not_on_disk=sorted(catalog - disk),
        on_disk_not_claude_md=sorted(disk - claude),
        claude_md_not_on_disk=sorted(claude - disk),
        name_folder_mismatches=sorted(name_folder_mismatches(disk)),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    parser.add_argument("--strict", action="store_true",
                        help="Exit 1 on any drift (default: exit 0 and let the caller decide)")
    args = parser.parse_args()

    try:
        drift = compute_drift()
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"reconcile: error computing drift: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({
            "total": drift.total(),
            "clean": drift.empty(),
            "drift": asdict(drift),
        }, indent=2))
    else:
        if drift.empty():
            print("✓ Skills are in sync: disk ↔ catalog.json ↔ CLAUDE.md registry.")
        else:
            print("⚠ Skill drift detected:")
            sections = [
                ("New on disk, missing from catalog.json", drift.on_disk_not_catalog),
                ("In catalog.json, missing on disk",        drift.catalog_not_on_disk),
                ("On disk, missing from CLAUDE.md registry", drift.on_disk_not_claude_md),
                ("In CLAUDE.md registry, missing on disk",   drift.claude_md_not_on_disk),
                ("YAML name does not match folder",          drift.name_folder_mismatches),
            ]
            for label, items in sections:
                if items:
                    print(f"\n  {label}:")
                    for item in items:
                        print(f"    - {item}")
            print("\nTo fix: add missing rows, remove stale rows, or rename folders to match.")

    if args.strict and not drift.empty():
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
