"""Skill validation suite for the sci-tools ecosystem.

Validates YAML frontmatter, folder naming conventions, trigger phrase conflicts,
and output path conventions for newly created skills. Provides scientific defaults
for custom skill creation.

Used by: sci-tools SKILL.md (create mode validation step)
"""

import glob
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import yaml
except ImportError:
    yaml = None  # Fallback to regex parsing if yaml not available

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SKILLS_DIR = PROJECT_ROOT / ".claude" / "skills"

# Valid category prefixes from CLAUDE.md Skill Categories table
VALID_CATEGORIES = {"mkt", "str", "ops", "viz", "acc", "meta", "tool", "sci"}

# Folder naming pattern: {category}-{name} in kebab-case
FOLDER_PATTERN = re.compile(r"^[a-z]+-[a-z][a-z0-9-]*$")


def _extract_frontmatter(content: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract YAML frontmatter block from SKILL.md content.

    Returns (frontmatter_text, error_message).
    """
    fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not fm_match:
        return None, "Missing YAML frontmatter"
    return fm_match.group(1), None


def _parse_frontmatter(fm_text: str) -> Tuple[Optional[dict], Optional[str]]:
    """Parse YAML frontmatter text into a dict.

    Returns (parsed_dict, error_message).
    """
    if yaml is not None:
        try:
            parsed = yaml.safe_load(fm_text)
            if not isinstance(parsed, dict):
                return None, "Invalid YAML frontmatter: not a mapping"
            return parsed, None
        except yaml.YAMLError as e:
            return None, f"Invalid YAML frontmatter: {e}"
    else:
        # Fallback: regex parsing for name, description, and category
        # Handles inline, folded (>), and literal (|) YAML scalar styles
        parsed = {}
        for key in ("name", "description", "category"):
            # Match the key line
            key_match = re.search(rf"^{key}:\s*(.*)$", fm_text, re.MULTILINE)
            if not key_match:
                continue
            first_line = key_match.group(1).strip()

            if first_line in (">", "|", ">-", "|-"):
                # Multiline: collect indented continuation lines
                rest = fm_text[key_match.end():]
                cont_lines = []
                started = False
                for line in rest.split("\n"):
                    if line and (line[0] == " " or line[0] == "\t"):
                        cont_lines.append(line.strip())
                        started = True
                    elif line.strip() == "" and started:
                        cont_lines.append("")
                    elif line.strip() == "" and not started:
                        # Skip leading empty lines (e.g. after block indicator)
                        continue
                    else:
                        break
                # Remove trailing empty lines
                while cont_lines and cont_lines[-1] == "":
                    cont_lines.pop()
                joiner = " " if first_line.startswith(">") else "\n"
                parsed[key] = joiner.join(cont_lines)
            elif first_line:
                # Inline value (strip quotes if present)
                parsed[key] = first_line.strip("\"'")
            # else: key exists but no value -- skip
        return parsed, None


def validate_skill(skill_dir: str) -> Tuple[List[str], List[str]]:
    """Validate a skill directory for ecosystem compatibility.

    Checks:
    1. SKILL.md exists
    2. YAML frontmatter present
    3. Frontmatter parses correctly
    4. Required 'name' field
    5. Required 'description' field
    6. Name matches folder name
    7. Folder follows {category}-{name} kebab-case pattern
    8. Output path convention (warning only)

    Args:
        skill_dir: Path to the skill directory.

    Returns:
        Tuple of (errors, warnings) where each is a list of strings.
    """
    errors: List[str] = []
    warnings: List[str] = []

    # Check 1: SKILL.md exists
    skill_md_path = os.path.join(skill_dir, "SKILL.md")
    if not os.path.exists(skill_md_path):
        errors.append("Missing SKILL.md")
        return errors, warnings

    with open(skill_md_path, "r") as f:
        content = f.read()

    # Check 2: Extract YAML frontmatter
    fm_text, fm_error = _extract_frontmatter(content)
    if fm_error:
        errors.append(fm_error)
        return errors, warnings

    # Check 3: Parse frontmatter
    fm, parse_error = _parse_frontmatter(fm_text)
    if parse_error:
        errors.append(parse_error)
        return errors, warnings

    # Check 4: Required 'name' field
    if "name" not in fm:
        errors.append("Missing 'name' in frontmatter")

    # Check 5: Required 'description' field
    if "description" not in fm:
        errors.append("Missing 'description' in frontmatter")

    # Check 6: Name matches folder name
    folder_name = os.path.basename(os.path.normpath(skill_dir))
    if fm.get("name") and fm["name"] != folder_name:
        errors.append(
            f"Frontmatter name '{fm['name']}' != folder name '{folder_name}'"
        )

    # Check 7: Folder naming convention
    if not FOLDER_PATTERN.match(folder_name):
        errors.append(
            f"Folder name '{folder_name}' must be {{category}}-{{name}} in kebab-case"
        )

    # Check 8: Output path convention (warning)
    if "projects/" in content:
        expected_prefix = f"projects/{folder_name}/"
        if expected_prefix not in content:
            warnings.append(
                f"Output path should use 'projects/{folder_name}/' "
                f"(found 'projects/' reference but not the expected pattern)"
            )

    return errors, warnings


def check_trigger_conflicts(
    skill_dir: str, trigger_phrases: Optional[List[str]] = None
) -> List[Dict[str, str]]:
    """Check if trigger phrases conflict with existing skills.

    Scans all installed skills' SKILL.md descriptions for overlapping
    trigger phrases. Returns conflicts with suggestions for resolution.

    Args:
        skill_dir: Path to the skill being checked.
        trigger_phrases: Explicit list of trigger phrases. If None,
            extracted from the skill's SKILL.md description.

    Returns:
        List of dicts with keys: phrase, conflicts_with, suggestion.
    """
    skill_name = os.path.basename(os.path.normpath(skill_dir))

    # Extract trigger phrases from SKILL.md if not provided
    if trigger_phrases is None:
        trigger_phrases = _extract_triggers_from_skill(skill_dir)

    if not trigger_phrases:
        return []

    conflicts: List[Dict[str, str]] = []

    # Scan all existing skills
    for skill_md_path in glob.glob(str(SKILLS_DIR / "*/SKILL.md")):
        existing_dir = os.path.dirname(skill_md_path)
        existing_name = os.path.basename(existing_dir)

        # Skip self and catalog/internal directories
        if existing_name == skill_name or existing_name.startswith("_"):
            continue

        try:
            with open(skill_md_path, "r") as f:
                content = f.read()
        except (OSError, IOError):
            continue

        # Extract description from frontmatter
        fm_text, _ = _extract_frontmatter(content)
        if not fm_text:
            continue

        fm, _ = _parse_frontmatter(fm_text)
        if not fm or "description" not in fm:
            continue

        existing_desc = str(fm["description"]).lower()

        # Check each trigger phrase
        for phrase in trigger_phrases:
            if phrase.lower() in existing_desc:
                conflicts.append(
                    {
                        "phrase": phrase,
                        "conflicts_with": existing_name,
                        "suggestion": f'Prepend "scientific " or "research " to distinguish: '
                        f'"scientific {phrase}" or "research {phrase}"',
                    }
                )

    return conflicts


def _extract_triggers_from_skill(skill_dir: str) -> List[str]:
    """Extract trigger phrases from a skill's SKILL.md description field.

    Looks for patterns like 'Triggers on: "phrase1", "phrase2"' in the
    description frontmatter field.
    """
    skill_md_path = os.path.join(skill_dir, "SKILL.md")
    if not os.path.exists(skill_md_path):
        return []

    with open(skill_md_path, "r") as f:
        content = f.read()

    fm_text, _ = _extract_frontmatter(content)
    if not fm_text:
        return []

    fm, _ = _parse_frontmatter(fm_text)
    if not fm or "description" not in fm:
        return []

    desc = str(fm["description"])

    # Extract quoted phrases after "Triggers on:"
    triggers_match = re.search(r"Triggers on:\s*(.+?)(?:\.|$)", desc, re.DOTALL)
    if triggers_match:
        trigger_text = triggers_match.group(1)
        # Extract quoted strings
        phrases = re.findall(r'"([^"]+)"', trigger_text)
        if phrases:
            return phrases

    return []


def get_scientific_defaults() -> dict:
    """Return pre-filled defaults for new scientific skills.

    These defaults are applied when a scientist creates a custom skill
    via the sci-tools create mode. They ensure consistency with existing
    sci-* skills and include reproducibility logging.

    Returns:
        Dict with keys: category_prefix, output_path_prefix, context_needs,
        has_reproducibility_logging, reproducibility_step, learnings_section.
    """
    return {
        "category_prefix": "sci-",
        "output_path_prefix": "projects/sci-",
        "context_needs": [
            {
                "file": "research_context/research-profile.md",
                "load_level": "full",
                "purpose": "Field and interests for personalization",
            }
        ],
        "has_reproducibility_logging": True,
        "reproducibility_step": (
            "Log operation to reproducibility ledger via "
            "repro.repro_logger.log_operation()"
        ),
        "learnings_section": "## {skill-name}",
    }
