#!/usr/bin/env python3
"""Validate every SKILL.md's YAML frontmatter against CLAUDE.md rules.

CLAUDE.md mandates: frontmatter < 1024 chars, YAML `name:` matches the
containing folder name, folder name matches category-prefix convention.
This script is run by CI and by the reconciliation loop on SessionStart
so drift is caught before it lands in main.

Usage:
    python3 scripts/validate_skill_frontmatter.py
    python3 scripts/validate_skill_frontmatter.py --json

Exit codes:
    0 — all skills pass
    1 — at least one skill has a validation error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PROJECT_ROOT / ".claude" / "skills"

FRONTMATTER_MAX_BYTES = 1024
# Category prefixes from CLAUDE.md § Skill Categories. A folder name
# must start with one of these or be in SKIP_DIRS.
ALLOWED_CATEGORIES = {"sci", "ops", "viz", "meta", "tool"}
# Directories that live under .claude/skills/ but are NOT skills in the
# registry sense.
SKIP_DIRS = {"_catalog"}


@dataclass
class Finding:
    skill: str
    level: str  # "error" or "warning"
    issue: str
    detail: Optional[str] = None


def parse_frontmatter(md_text: str) -> tuple[str, dict]:
    """Return the raw frontmatter block (without fences) and parsed YAML.

    Raises ValueError if the file lacks a frontmatter block or the YAML
    fails to parse.
    """
    match = re.match(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", md_text, re.DOTALL)
    if not match:
        raise ValueError("no YAML frontmatter block")
    raw = match.group(1)
    try:
        parsed = yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"YAML parse error: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("frontmatter is not a mapping")
    return raw, parsed


def validate_skill(skill_dir: Path) -> list[Finding]:
    findings: list[Finding] = []
    name = skill_dir.name
    skill_md = skill_dir / "SKILL.md"

    if not skill_md.exists():
        findings.append(Finding(name, "error", "SKILL.md missing"))
        return findings

    text = skill_md.read_text(encoding="utf-8")

    try:
        raw, parsed = parse_frontmatter(text)
    except ValueError as exc:
        findings.append(Finding(name, "error", "frontmatter parse failed", str(exc)))
        return findings

    # Byte-length check — CLAUDE.md specifies a hard ceiling.
    raw_bytes = len(raw.encode("utf-8"))
    if raw_bytes >= FRONTMATTER_MAX_BYTES:
        findings.append(
            Finding(
                name,
                "error",
                "frontmatter exceeds 1024-byte ceiling",
                f"{raw_bytes} bytes",
            )
        )

    # `name:` field must match the folder.
    yaml_name = parsed.get("name")
    if yaml_name != name:
        findings.append(
            Finding(
                name,
                "error",
                "YAML name does not match folder",
                f"yaml={yaml_name!r} folder={name!r}",
            )
        )

    # Category prefix check.
    prefix = name.split("-", 1)[0] if "-" in name else name
    if prefix not in ALLOWED_CATEGORIES:
        findings.append(
            Finding(
                name,
                "warning",
                f"folder prefix '{prefix}' not in {sorted(ALLOWED_CATEGORIES)}",
            )
        )

    # Description field is required for routing.
    if not parsed.get("description"):
        findings.append(Finding(name, "error", "missing description field"))

    return findings


def validate_all() -> list[Finding]:
    findings: list[Finding] = []
    for child in sorted(SKILLS_DIR.iterdir()):
        if not child.is_dir() or child.name in SKIP_DIRS or child.name.startswith("."):
            continue
        findings.extend(validate_skill(child))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    args = parser.parse_args()

    findings = validate_all()
    errors = [f for f in findings if f.level == "error"]
    warnings = [f for f in findings if f.level == "warning"]

    if args.json:
        print(json.dumps(
            {
                "total_findings": len(findings),
                "errors": len(errors),
                "warnings": len(warnings),
                "findings": [asdict(f) for f in findings],
            },
            indent=2,
        ))
    else:
        if not findings:
            print("OK — every SKILL.md passes frontmatter validation.")
        else:
            for f in findings:
                tag = "ERROR" if f.level == "error" else "warn "
                line = f"[{tag}] {f.skill}: {f.issue}"
                if f.detail:
                    line += f" ({f.detail})"
                print(line)
            print(f"\n{len(errors)} error(s), {len(warnings)} warning(s)")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
