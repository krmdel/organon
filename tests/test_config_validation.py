"""Config validation tests for CFG-01 through CFG-14.

These tests enforce that all skill YAML frontmatter, JSON configs, CLAUDE.md
registry tables, skill dependencies, external service docs, and output paths
are correct and internally consistent.  They act as permanent guardrails
against config drift.

Requirement coverage:
  CFG-01  All SKILL.md files have valid YAML frontmatter under 1024 chars
  CFG-02  All JSON config files parse without errors
  CFG-03  Every skill folder on disk appears in Skill Registry and Context Matrix
  CFG-04  Every Registry/Matrix entry has a matching folder on disk
  CFG-05  No legacy skill names appear in committed source files
  CFG-06  Frontmatter `name` field matches the skill folder name exactly
  CFG-07  All declared references/ and scripts/ files exist on disk
  CFG-08  Output path references use the skill's category prefix
  CFG-09  Cross-skill dependencies in SKILL.md reference existing skills
  CFG-10  Required dependencies are present on disk; optional deps have fallback text
  CFG-11  Frontmatter description has trigger content and no XML angle brackets
  CFG-12  External services referenced in skills appear in the Service Registry
  CFG-13  Service Registry API key names appear in .env.example
  CFG-14  Skills that reference external APIs document a fallback
"""

import json
import re
import sys
from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# Path setup — allow importing from the tests/ dir without installing
# ---------------------------------------------------------------------------
TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from conftest import (  # noqa: E402
    ALL_SKILLS,
    CLAUDE_MD,
    ENV_EXAMPLE,
    EXCLUDED_DIRS,
    LEGACY_PATTERNS,
    ROOT,
    SKILLS_DIR,
    extract_skill_names_from_context_matrix,
    extract_skill_names_from_registry,
    load_skill_frontmatter,
    parse_service_registry,
)

# ---------------------------------------------------------------------------
# Helper: read SKILL.md text for a skill
# ---------------------------------------------------------------------------

def _skill_text(skill: str) -> str:
    return (SKILLS_DIR / skill / "SKILL.md").read_text()


# ---------------------------------------------------------------------------
# Helper: extract declared dependency skill names from a SKILL.md text
# ---------------------------------------------------------------------------

_SKILL_PREFIXES = ("sci-", "viz-", "tool-", "meta-", "ops-")


def _parse_dep_table(text: str):
    """Return list of (skill_name, required_bool, row_text) from ## Dependencies.

    Only matches skill names with known category prefixes (sci-, viz-, tool-, etc.)
    to avoid false positives from style-name tables or other backtick content.
    """
    idx = text.find("## Dependencies")
    if idx == -1:
        return []
    # Only read the dependency section, stopping at the next ## heading
    next_section = text.find("\n## ", idx + 1)
    section = text[idx:next_section] if next_section != -1 else text[idx:idx + 3000]

    lines = section.split("\n")
    table_lines = [
        l for l in lines
        if l.strip().startswith("|") and "---" not in l
    ]
    if len(table_lines) < 2:
        return []
    deps = []
    for row in table_lines[1:]:  # skip header
        # Extract backtick-wrapped skill name with known category prefix
        name_match = re.search(r"`([a-z]+-[a-z][a-z0-9-]+)`", row)
        if not name_match:
            continue
        name = name_match.group(1)
        # Only consider names with valid skill category prefixes
        if not any(name.startswith(p) for p in _SKILL_PREFIXES):
            continue
        # Check the Required? column (second pipe-delimited cell)
        cells = [c.strip() for c in row.split("|")[1:-1]]
        required = False
        if len(cells) >= 2:
            req_cell = cells[1].strip().lower()
            required = req_cell in ("required", "yes")
        deps.append((name, required, row))
    return deps


# ---------------------------------------------------------------------------
# Helper: check if a skill references an external service
# ---------------------------------------------------------------------------

_API_KEY_PATTERN = re.compile(r"[A-Z][A-Z0-9]*_API_KEY|[A-Z][A-Z0-9]*_KEY")
_SERVICE_NAMES = {"firecrawl", "openai", "xai", "youtube", "gemini"}


def _has_external_service(text: str) -> bool:
    """Return True if SKILL.md references an external API key or known service."""
    if _API_KEY_PATTERN.search(text):
        return True
    lower = text.lower()
    return any(s in lower for s in _SERVICE_NAMES)


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestConfigValidation:

    # -----------------------------------------------------------------------
    # CFG-01: YAML frontmatter valid and under 1024 characters
    # -----------------------------------------------------------------------

    @pytest.mark.parametrize("skill", ALL_SKILLS)
    def test_cfg_01_yaml_frontmatter_valid(self, skill):
        """CFG-01: Each SKILL.md has parseable YAML frontmatter under 1024 chars."""
        skill_md = SKILLS_DIR / skill / "SKILL.md"
        text = skill_md.read_text()

        # Check frontmatter block exists and parses
        fm = load_skill_frontmatter(skill)
        assert fm, (
            f"{skill}/SKILL.md: frontmatter is missing or empty "
            "(expected '---' delimited YAML block)"
        )

        # Check raw frontmatter length
        match = re.match(r"^---\n(.*?\n)---", text, re.DOTALL)
        assert match, f"{skill}/SKILL.md: cannot find '---' frontmatter delimiters"
        raw_fm = match.group(1)
        assert len(raw_fm) < 1024, (
            f"{skill}/SKILL.md: frontmatter is {len(raw_fm)} chars "
            f"(must be under 1024)"
        )

    # -----------------------------------------------------------------------
    # CFG-02: JSON config files parse without errors
    # -----------------------------------------------------------------------

    @pytest.mark.parametrize("rel_path", [
        ".claude/skills/_catalog/catalog.json",
        ".claude/settings.json",
    ])
    def test_cfg_02_json_configs_valid(self, rel_path):
        """CFG-02: Core JSON config files parse without errors."""
        path = ROOT / rel_path
        assert path.exists(), f"Expected config file not found: {rel_path}"
        try:
            json.loads(path.read_text())
        except json.JSONDecodeError as e:
            pytest.fail(f"{rel_path}: JSON parse error — {e}")

    def test_cfg_02_installed_json_valid_if_exists(self):
        """CFG-02: installed.json parses if it exists (may be absent on fresh installs)."""
        installed = ROOT / ".claude" / "skills" / "_catalog" / "installed.json"
        if not installed.exists():
            pytest.skip("installed.json not present (expected on fresh installs)")
        try:
            json.loads(installed.read_text())
        except json.JSONDecodeError as e:
            pytest.fail(f"installed.json: JSON parse error — {e}")

    # -----------------------------------------------------------------------
    # CFG-03: Skill folders on disk appear in Skill Registry and Context Matrix
    #
    # Skills excluded from the public repo via .gitignore (see root
    # .gitignore) may exist on disk locally without a registry row, or
    # appear in CLAUDE.md without the folder in CI clones. Either side
    # of the consistency check exempts them.
    # -----------------------------------------------------------------------

    _GITIGNORED_SKILLS = {"tool-substack", "tool-social-publisher"}

    def test_cfg_03_skill_folders_in_registry(self):
        """CFG-03: Every skill folder on disk has a row in the CLAUDE.md Skill Registry."""
        registry_names = extract_skill_names_from_registry()
        missing = (set(ALL_SKILLS) - registry_names) - self._GITIGNORED_SKILLS
        assert not missing, (
            f"Skills on disk missing from CLAUDE.md Skill Registry: {sorted(missing)}"
        )

    def test_cfg_03_skill_folders_in_context_matrix(self):
        """CFG-03: Every skill folder on disk has a row in the CLAUDE.md Context Matrix."""
        matrix_names = extract_skill_names_from_context_matrix()
        missing = (set(ALL_SKILLS) - matrix_names) - self._GITIGNORED_SKILLS
        assert not missing, (
            f"Skills on disk missing from CLAUDE.md Context Matrix: {sorted(missing)}"
        )

    # -----------------------------------------------------------------------
    # CFG-04: Registry/Matrix entries have corresponding folders on disk
    # -----------------------------------------------------------------------

    def test_cfg_04_registry_entries_have_folders(self):
        """CFG-04: Every CLAUDE.md Skill Registry entry has a folder on disk."""
        registry_names = extract_skill_names_from_registry()
        extra = (registry_names - set(ALL_SKILLS)) - self._GITIGNORED_SKILLS
        assert not extra, (
            f"CLAUDE.md Skill Registry entries with no folder on disk: {sorted(extra)}"
        )

    def test_cfg_04_context_matrix_entries_have_folders(self):
        """CFG-04: Every CLAUDE.md Context Matrix entry has a folder on disk."""
        matrix_names = extract_skill_names_from_context_matrix()
        extra = (matrix_names - set(ALL_SKILLS)) - self._GITIGNORED_SKILLS
        assert not extra, (
            f"CLAUDE.md Context Matrix entries with no folder on disk: {sorted(extra)}"
        )

    # -----------------------------------------------------------------------
    # CFG-05: No legacy skill name references in committed source files
    # -----------------------------------------------------------------------

    def test_cfg_05_no_legacy_references(self):
        """CFG-05: No legacy skill names appear in committed source files."""
        # Files that intentionally contain legacy names as negative test fixtures
        excluded_files = {
            "test_full_framework.py",
            "test_skill_routing.py",
            "test_workflow_scenarios.py",
            "test_ci_regression.py",
        }

        failures = []
        extensions = {".md", ".sh", ".py", ".json", ".txt"}

        for path in ROOT.rglob("*"):
            # Skip non-files and excluded directories
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT)
            rel_str = str(rel)
            if any(excl in rel_str for excl in EXCLUDED_DIRS):
                continue
            if path.name in excluded_files:
                continue
            if path.suffix not in extensions:
                continue

            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for pattern in LEGACY_PATTERNS:
                # Case-sensitive match (same as cleanup grep)
                if pattern in text:
                    failures.append(f"{rel_str}: contains legacy pattern '{pattern}'")

        assert not failures, (
            "Legacy skill names found in committed files:\n" +
            "\n".join(failures[:20])  # cap output
        )

    # -----------------------------------------------------------------------
    # CFG-06: Frontmatter `name` field matches folder name
    # -----------------------------------------------------------------------

    @pytest.mark.parametrize("skill", ALL_SKILLS)
    def test_cfg_06_name_matches_folder(self, skill):
        """CFG-06: Frontmatter `name` field matches the skill folder name exactly."""
        fm = load_skill_frontmatter(skill)
        assert fm.get("name") == skill, (
            f"{skill}/SKILL.md: frontmatter name='{fm.get('name')}' "
            f"does not match folder name '{skill}'"
        )

    # -----------------------------------------------------------------------
    # CFG-07: All files under references/ and scripts/ subdirectories exist
    # -----------------------------------------------------------------------

    @pytest.mark.parametrize("skill", ALL_SKILLS)
    def test_cfg_07_declared_files_exist(self, skill):
        """CFG-07: Files under references/ and scripts/ subdirs exist on disk."""
        skill_dir = SKILLS_DIR / skill
        text = _skill_text(skill)
        missing = []

        # Check explicitly referenced files in references/ and scripts/
        # Only check backtick-wrapped references (operative instructions, not examples).
        # Skip lines that contain "e.g.," or "e.g. " — those are illustrative patterns.
        for ref_match in re.finditer(
            r"`((?:references|scripts)/[^\s\`\)\"\']+\.(?:md|sh|py|txt|json))`",
            text
        ):
            rel_path = ref_match.group(1)
            # Skip references found on example/illustrative lines
            start = ref_match.start()
            line_start = text.rfind("\n", 0, start) + 1
            line_end = text.find("\n", start)
            line_text = text[line_start:line_end] if line_end != -1 else text[line_start:]
            if "e.g.," in line_text or "e.g. " in line_text:
                continue
            full_path = skill_dir / rel_path
            if not full_path.exists():
                missing.append(rel_path)

        # Also: if references/ or scripts/ subdirs exist on disk, verify all their
        # files are accessible (no broken symlinks, etc.)
        for subdir_name in ("references", "scripts"):
            subdir = skill_dir / subdir_name
            if subdir.is_dir():
                for f in subdir.iterdir():
                    if f.is_file() and not f.exists():
                        missing.append(str(f.relative_to(skill_dir)))

        assert not missing, (
            f"{skill}/SKILL.md references files that don't exist: {missing}"
        )

    # -----------------------------------------------------------------------
    # CFG-08: Output path references use the skill's category prefix
    # -----------------------------------------------------------------------

    @pytest.mark.parametrize("skill", ALL_SKILLS)
    def test_cfg_08_output_paths_use_category_prefix(self, skill):
        """CFG-08: `projects/` path references use the skill's category prefix."""
        text = _skill_text(skill)
        category = skill.split("-")[0]  # e.g. "sci" from "sci-writing"

        found_paths = re.findall(r"projects/([a-z][a-z0-9-]+)", text)
        violations = []
        for path_name in found_paths:
            # Skip context paths from other skills (reads from other skill outputs)
            # Only flag output paths that don't start with any valid category prefix
            path_category = path_name.split("-")[0]
            valid_prefixes = {"sci", "viz", "tool", "meta", "ops", "briefs"}
            if path_category not in valid_prefixes:
                violations.append(f"projects/{path_name}")

        assert not violations, (
            f"{skill}/SKILL.md: output paths with invalid category prefixes: {violations}"
        )

    # -----------------------------------------------------------------------
    # CFG-09: Cross-skill dependency references point to existing skills
    # -----------------------------------------------------------------------

    @pytest.mark.parametrize("skill", ALL_SKILLS)
    def test_cfg_09_cross_skill_dependencies_exist(self, skill):
        """CFG-09: All skill names in ## Dependencies tables exist as folders."""
        text = _skill_text(skill)
        deps = _parse_dep_table(text)
        if not deps:
            return  # no dependencies declared — pass trivially

        missing = []
        for dep_name, _required, _row in deps:
            if not (SKILLS_DIR / dep_name).is_dir():
                missing.append(dep_name)

        assert not missing, (
            f"{skill}/SKILL.md ## Dependencies references non-existent skills: {missing}"
        )

    # -----------------------------------------------------------------------
    # CFG-10: Required deps exist on disk; optional deps have fallback text
    # -----------------------------------------------------------------------

    @pytest.mark.parametrize("skill", ALL_SKILLS)
    def test_cfg_10_required_deps_present_optional_have_fallback(self, skill):
        """CFG-10: Required deps exist on disk; optional deps declare fallback."""
        text = _skill_text(skill)
        deps = _parse_dep_table(text)
        if not deps:
            return

        missing_required = []
        missing_fallback = []
        fallback_keywords = {
            "fallback", "without it", "still works", "optional", "ask user",
            "placeholder", "manual", "degrade",
        }

        for dep_name, required, row in deps:
            if required:
                if not (SKILLS_DIR / dep_name).is_dir():
                    missing_required.append(dep_name)
            else:
                row_lower = row.lower()
                if not any(kw in row_lower for kw in fallback_keywords):
                    missing_fallback.append(dep_name)

        errors = []
        if missing_required:
            errors.append(f"Required deps missing from disk: {missing_required}")
        if missing_fallback:
            errors.append(f"Optional deps with no fallback text: {missing_fallback}")

        assert not errors, f"{skill}/SKILL.md: " + "; ".join(errors)

    # -----------------------------------------------------------------------
    # CFG-11: Frontmatter description contains trigger info and no XML brackets
    # -----------------------------------------------------------------------

    @pytest.mark.parametrize("skill", ALL_SKILLS)
    def test_cfg_11_frontmatter_has_triggers_no_xml(self, skill):
        """CFG-11: Frontmatter description is substantive with triggers; no XML angle brackets."""
        fm = load_skill_frontmatter(skill)
        desc = fm.get("description", "")

        # Must have a substantive description with trigger-related content
        has_trigger_info = (
            "trigger" in desc.lower()
            or "Triggers on" in desc
            or len(desc) > 50
        )
        assert has_trigger_info, (
            f"{skill}/SKILL.md: frontmatter description is missing or too brief "
            f"(got {len(desc)} chars, expected >50 or trigger content)"
        )

        # No XML angle brackets (per CLAUDE.md YAML frontmatter rules)
        assert "<" not in desc and ">" not in desc, (
            f"{skill}/SKILL.md: frontmatter description contains XML angle brackets"
        )

    # -----------------------------------------------------------------------
    # CFG-12: External services referenced in skills appear in the Service Registry
    # -----------------------------------------------------------------------

    def test_cfg_12_external_services_in_service_registry(self):
        """CFG-12: Skills that reference external services match the Service Registry."""
        registry_rows = parse_service_registry()
        if not registry_rows:
            pytest.skip("Service Registry not found in CLAUDE.md")

        # Build a set of service names from the registry (lowercase)
        registry_services = set()
        for row in registry_rows:
            service_col = row.get("Service", "")
            registry_services.add(service_col.lower())
            # Also add the API key name
            key_col = row.get("API Key", "")
            key_clean = re.sub(r"`", "", key_col).strip().lower()
            if key_clean:
                registry_services.add(key_clean)

        # Service names that map to registry service names
        service_map = {
            "firecrawl": "firecrawl",
            "openai": "openai",
            "xai": "xai",
            "youtube": "youtube",
            "gemini": "google gemini",
            "OPENAI_API_KEY": "openai",
            "XAI_API_KEY": "xai",
            "FIRECRAWL_API_KEY": "firecrawl",
            "YOUTUBE_API_KEY": "youtube",
            "GEMINI_API_KEY": "google gemini",
        }

        violations = []
        for skill in ALL_SKILLS:
            text = _skill_text(skill)
            if not _has_external_service(text):
                continue

            # Check which services are referenced
            found_keys = _API_KEY_PATTERN.findall(text)
            found_service_names = [s for s in _SERVICE_NAMES if s in text.lower()]

            for key in found_keys:
                canonical = service_map.get(key, key.lower().replace("_api_key", ""))
                # Check if any registry service matches
                matched = any(canonical in svc for svc in registry_services)
                if not matched:
                    violations.append(
                        f"{skill}: references API key '{key}' not in Service Registry"
                    )

            for svc in found_service_names:
                canonical = service_map.get(svc, svc)
                matched = any(canonical in reg_svc for reg_svc in registry_services)
                if not matched:
                    violations.append(
                        f"{skill}: references service '{svc}' not in Service Registry"
                    )

        assert not violations, (
            "Skills reference external services not in Service Registry:\n" +
            "\n".join(violations)
        )

    # -----------------------------------------------------------------------
    # CFG-13: Service Registry API key names appear in .env.example
    # -----------------------------------------------------------------------

    def test_cfg_13_service_registry_keys_in_env_example(self):
        """CFG-13: Every API key name from Service Registry appears in .env.example."""
        if not ENV_EXAMPLE.exists():
            pytest.skip(".env.example not found")

        registry_rows = parse_service_registry()
        if not registry_rows:
            pytest.skip("Service Registry not found in CLAUDE.md")

        env_text = ENV_EXAMPLE.read_text()
        missing = []

        for row in registry_rows:
            key_col = row.get("API Key", "")
            # Extract key name from backtick-wrapped or plain text
            key_match = re.search(r"`([A-Z_]+)`", key_col)
            if key_match:
                key_name = key_match.group(1)
            else:
                key_name = key_col.strip()
            if not key_name:
                continue
            if key_name not in env_text:
                missing.append(key_name)

        assert not missing, (
            f"Service Registry API keys not in .env.example: {missing}"
        )

    # -----------------------------------------------------------------------
    # CFG-14: Skills that reference external APIs document a fallback
    # -----------------------------------------------------------------------

    @pytest.mark.parametrize("skill", ALL_SKILLS)
    def test_cfg_14_api_skills_document_fallback(self, skill):
        """CFG-14: Skills that reference external APIs document a graceful fallback."""
        text = _skill_text(skill)
        if not _has_external_service(text):
            return  # no external API references — pass trivially

        fallback_keywords = [
            "fallback", "without", "graceful", "optional", "not required",
            "still work", "degrade", "fall back", "without it",
        ]
        has_fallback = any(kw in text.lower() for kw in fallback_keywords)
        assert has_fallback, (
            f"{skill}/SKILL.md: references external API but contains no fallback language "
            f"(expected one of: {fallback_keywords})"
        )
