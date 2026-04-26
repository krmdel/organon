"""Tests for research profile schema validation.

Validates the profile-schema.md template structure and tests that
research profile files with complete and partial data are correctly parsed.
"""

import re
from pathlib import Path

import pytest

# Locate the repo root and schema file
REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / ".claude" / "skills" / "sci-research-profile" / "references" / "profile-schema.md"

REQUIRED_SECTIONS = ["## Core Identity", "## Research Focus", "## Preferences", "## Tool Ecosystem"]

CORE_IDENTITY_FIELDS = ["Name", "Institution", "Department", "Career Stage"]

VALID_CAREER_STAGES = [
    "PhD Student",
    "Postdoc",
    "Assistant Prof",
    "Associate Prof",
    "Full Prof",
    "Industry Researcher",
    "Research Scientist",
    "Other",
]


def parse_profile(content: str) -> dict:
    """Parse a research-profile.md string into a dict of section -> field -> value.

    Each H2 section becomes a top-level key. Within each section, lines matching
    '- **Label:** value' become key-value pairs. Active Questions (numbered lists)
    are collected as a list under the 'Active Questions' key.

    Args:
        content: The markdown content of a research profile file.

    Returns:
        A dict mapping section names to dicts of field names to values.
    """
    sections = {}
    current_section = None
    current_fields = {}

    for line in content.split("\n"):
        # Detect H2 section headers
        if line.startswith("## "):
            if current_section is not None:
                sections[current_section] = current_fields
            current_section = line.strip()
            current_fields = {}
            continue

        # Detect field lines: - **Label:** value
        field_match = re.match(r"^- \*\*(.+?):\*\*\s*(.*)", line)
        if field_match and current_section is not None:
            field_name = field_match.group(1)
            field_value = field_match.group(2).strip()
            current_fields[field_name] = field_value
            continue

        # Detect numbered list items (Active Questions)
        numbered_match = re.match(r"^\s+\d+\.\s+(.*)", line)
        if numbered_match and current_section is not None:
            questions = current_fields.get("Active Questions", [])
            if isinstance(questions, str):
                questions = []
            questions.append(numbered_match.group(1).strip())
            current_fields["Active Questions"] = questions

    # Don't forget the last section
    if current_section is not None:
        sections[current_section] = current_fields

    return sections


class TestSchemaStructure:
    """Tests that validate the profile-schema.md file itself."""

    def test_schema_file_exists(self):
        """profile-schema.md must exist at the expected path."""
        assert SCHEMA_PATH.exists(), f"Schema file not found at {SCHEMA_PATH}"

    def test_schema_has_all_sections(self):
        """profile-schema.md must contain all four required H2 sections."""
        content = SCHEMA_PATH.read_text()
        for section in REQUIRED_SECTIONS:
            assert section in content, f"Missing section: {section}"

    def test_core_identity_fields(self):
        """Core Identity section must contain Name, Institution, Department, Career Stage."""
        content = SCHEMA_PATH.read_text()
        # Extract the template block from the schema
        for field in CORE_IDENTITY_FIELDS:
            assert f"**{field}:**" in content, f"Missing Core Identity field: {field}"

    def test_career_stage_valid_values(self):
        """Career Stage field must list all 8 valid career stage values."""
        content = SCHEMA_PATH.read_text()
        for stage in VALID_CAREER_STAGES:
            assert stage in content, f"Missing career stage value: {stage}"


class TestProfileParsing:
    """Tests that validate parsing of research profile content."""

    COMPLETE_PROFILE = """\
# Research Profile

## Core Identity
- **Name:** Jane Smith
- **Institution:** MIT
- **Department:** Computer Science
- **Career Stage:** Assistant Prof

## Research Focus
- **Primary Field:** Machine Learning
- **Subfields:** NLP, Computer Vision
- **Keywords:** transformers, attention, multimodal
- **Active Questions:**
  1. How do vision-language models generalize?
  2. Can we reduce transformer training costs by 10x?

## Preferences
- **Preferred Journals:** Nature Machine Intelligence, JMLR
- **Citation Style:** APA
- **Writing Conventions:** active voice, Oxford comma, American English

## Tool Ecosystem
- **Languages:** Python, Julia
- **Statistical Tools:** scipy, PyTorch, JAX
- **Databases:** HuggingFace Hub, Papers With Code
- **Other:** Docker, Weights & Biases
"""

    PARTIAL_PROFILE = """\
# Research Profile

## Core Identity
- **Name:** John Doe
- **Institution:** Not specified
- **Department:** Not specified
- **Career Stage:** PhD Student

## Research Focus
- **Primary Field:** Biology
- **Subfields:** Not specified
- **Keywords:** Not specified
- **Active Questions:**

## Preferences
- **Preferred Journals:** Not specified
- **Citation Style:** Not specified
- **Writing Conventions:** Not specified

## Tool Ecosystem
- **Languages:** R
- **Statistical Tools:** Not specified
- **Databases:** Not specified
- **Other:** Not specified
"""

    def test_complete_profile_valid(self):
        """A profile with all fields filled must parse successfully with all sections populated."""
        parsed = parse_profile(self.COMPLETE_PROFILE)
        for section in REQUIRED_SECTIONS:
            assert section in parsed, f"Missing section in parsed output: {section}"
            assert len(parsed[section]) > 0, f"Section {section} has no fields"

        # Verify specific values
        assert parsed["## Core Identity"]["Name"] == "Jane Smith"
        assert parsed["## Core Identity"]["Career Stage"] == "Assistant Prof"
        assert parsed["## Research Focus"]["Primary Field"] == "Machine Learning"
        assert isinstance(parsed["## Research Focus"]["Active Questions"], list)
        assert len(parsed["## Research Focus"]["Active Questions"]) == 2

    def test_partial_profile_valid(self):
        """A profile with 'Not specified' fields must still parse successfully (graceful degradation)."""
        parsed = parse_profile(self.PARTIAL_PROFILE)
        # All four sections must exist
        for section in REQUIRED_SECTIONS:
            assert section in parsed, f"Missing section in partial profile: {section}"

        # Fields with 'Not specified' are still present as string values
        assert parsed["## Core Identity"]["Institution"] == "Not specified"
        assert parsed["## Preferences"]["Citation Style"] == "Not specified"

        # Some fields have real values
        assert parsed["## Core Identity"]["Name"] == "John Doe"
        assert parsed["## Core Identity"]["Career Stage"] == "PhD Student"
        assert parsed["## Tool Ecosystem"]["Languages"] == "R"
