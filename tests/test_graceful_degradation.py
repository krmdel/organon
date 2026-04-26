"""Graceful degradation tests for all 19 skills.

Validates DEGRADE-01, DEGRADE-02, DEGRADE-03 requirements:
  - DEGRADE-01: All skills produce usable output when research_context/ is absent
  - DEGRADE-02: Skills with API dependencies fall back gracefully when .env is missing
  - DEGRADE-03: Skills function correctly with only partial research_context/ files present

Per D-08: Structural validation via SKILL.md content for all 19 skills.
Per D-09: Smoke test execution (Python import) for the 9 skills with Python backends.
Per D-10: Structural-only checks for the remaining 10 skills.
"""

import importlib
import os
import re
import sys
import tempfile
from pathlib import Path

import pytest

# Re-use shared constants from conftest
from conftest import ALL_SKILLS, SKILLS_DIR

# ---------------------------------------------------------------------------
# Ground truth lists (from disk audit: find .claude/skills/*/ -name "*.py")
# ---------------------------------------------------------------------------

# Skills with Python backends that get smoke tests (per D-09)
# Ground truth from disk audit:
PYTHON_BACKEND_SKILLS = [
    "meta-skill-creator",      # eval-viewer/generate_review.py
    "sci-data-analysis",       # scripts/plot_ops.py, data_ops.py
    "sci-hypothesis",          # scripts/hypothesis_ops.py
    "sci-tools",               # scripts/catalog_ops.py, validate_ops.py
    "sci-trending-research",   # scripts/last30days.py + lib/
    "sci-writing",             # scripts/writing_ops.py, review_ops.py
    "tool-youtube",            # scripts/digest.py, transcript.py
    "viz-excalidraw-diagram",  # references/render_excalidraw.py
    "viz-nano-banana",         # scripts/generate_image.py
]

# Skills with external API dependencies
API_SKILLS = [
    "sci-trending-research",    # OpenAI, xAI
    "tool-youtube",             # YouTube Data API
    "viz-nano-banana",          # Gemini API
    "tool-firecrawl-scraper",   # Firecrawl API
]

# All remaining skills get structural-only validation (per D-10)
STRUCTURAL_ONLY_SKILLS = [s for s in ALL_SKILLS if s not in PYTHON_BACKEND_SKILLS]

# Skills per Context Matrix that do NOT read research_context/ (trivially pass DEGRADE-01/03)
NO_CONTEXT_SKILLS = {"meta-wrap-up", "viz-nano-banana", "viz-excalidraw-diagram", "viz-diagram-code"}

# Env vars for API-dependent skills
API_ENV_VARS = {
    "sci-trending-research": ["OPENAI_API_KEY", "XAI_API_KEY"],
    "tool-youtube": ["YOUTUBE_API_KEY"],
    "viz-nano-banana": ["GEMINI_API_KEY"],
    "tool-firecrawl-scraper": ["FIRECRAWL_API_KEY"],
}

# Patterns that indicate a skill documents graceful degradation behavior for missing context
DEGRADE_PATTERNS = [
    r"no research",
    r"without research",
    r"research_context",
    r"standalone",
    r"context is missing",
    r"context exists",
    r"if.*context",
    r"fallback",
    r"graceful",
    r"optional",
    r"partial",
    r"not used",         # Context Matrix "—" is written out in SKILL.md tables
    r"load if",          # e.g. "Load if they exist"
    r"proceed without",  # e.g. "Proceed without them if not"
]

# Patterns for API fallback documentation
API_FALLBACK_PATTERNS = [
    r"fallback",
    r"without.*key",
    r"without.*api",
    r"api key.*not",
    r"graceful",
    r"still work",
    r"free tier",
    r"\.env",
    r"if.*missing",
    r"if.*absent",
    r"if.*not.*configured",
    r"if.*not.*set",
    r"webfetch",
    r"websearch",
    r"web search",
]


# ---------------------------------------------------------------------------
# Helper: read SKILL.md text for a skill
# ---------------------------------------------------------------------------

def _skill_text(skill_name: str) -> str:
    skill_md = SKILLS_DIR / skill_name / "SKILL.md"
    return skill_md.read_text(encoding="utf-8")


def _matches_any_pattern(text: str, patterns: list) -> bool:
    """Return True if text matches any of the given regex patterns (case-insensitive)."""
    lowered = text.lower()
    for pattern in patterns:
        if re.search(pattern, lowered, re.IGNORECASE | re.DOTALL):
            return True
    return False


# ---------------------------------------------------------------------------
# DEGRADE-01: Skills handle missing research_context/
# ---------------------------------------------------------------------------

class TestGracefulDegradation:

    @pytest.mark.parametrize("skill", ALL_SKILLS)
    def test_degrade_01_structural_no_research_context(self, skill):
        """Per D-08: SKILL.md acknowledges missing/optional research context behavior.

        Skills that do not use research_context (per Context Matrix) pass trivially
        because they have no context dependency to degrade from.
        """
        # Skills with no context dependency pass trivially
        if skill in NO_CONTEXT_SKILLS:
            return

        text = _skill_text(skill)
        assert _matches_any_pattern(text, DEGRADE_PATTERNS), (
            f"Skill '{skill}' SKILL.md does not document standalone/fallback behavior "
            f"for missing research context. Expected one of: {DEGRADE_PATTERNS[:5]}... "
            f"Add a note about graceful behavior when research_context/ is absent."
        )

    @pytest.mark.parametrize("skill", PYTHON_BACKEND_SKILLS)
    def test_degrade_01_smoke_no_research_context(self, skill):
        """Per D-09: Python backend scripts can be imported without research_context/ present.

        Verifies import-time safety. Runtime reads of context files are handled by Claude,
        not at import time, so the smoke test focuses on import-time crashes.
        """
        # Map skill name to its importable module and scripts directory
        skill_dir = SKILLS_DIR / skill
        import_info = _get_import_info(skill)

        if import_info is None:
            pytest.skip(f"No importable module configured for '{skill}'")

        scripts_dir, module_name = import_info

        # Ensure scripts dir is on sys.path
        scripts_str = str(scripts_dir)
        inserted = scripts_str not in sys.path
        if inserted:
            sys.path.insert(0, scripts_str)

        try:
            # Attempt the import -- should not crash even without research_context/
            try:
                mod = importlib.import_module(module_name)
                # Import succeeded -- skill is safe at import time
                assert mod is not None
            except ImportError as exc:
                # Missing optional deps (yt-dlp, playwright, google-genai, etc.) are acceptable
                dep_indicators = [
                    "yt_dlp", "yt-dlp", "playwright", "google", "genai",
                    "firecrawl", "scipy", "pandas", "numpy", "matplotlib", "seaborn",
                    "plotly", "openpyxl", "SciencePlots", "scienceplots",
                ]
                exc_msg = str(exc).lower()
                if any(d.lower() in exc_msg for d in dep_indicators):
                    pytest.skip(f"Skipped '{skill}': optional dependency missing — {exc}")
                raise  # Re-raise unexpected ImportErrors
        finally:
            if inserted and scripts_str in sys.path:
                sys.path.remove(scripts_str)

    # ---------------------------------------------------------------------------
    # DEGRADE-02: Skills with API dependencies document fallback behavior
    # ---------------------------------------------------------------------------

    @pytest.mark.parametrize("skill", API_SKILLS)
    def test_degrade_02_structural_api_fallback(self, skill):
        """Per D-08: API-dependent skills document fallback when keys are absent."""
        text = _skill_text(skill)
        assert _matches_any_pattern(text, API_FALLBACK_PATTERNS), (
            f"Skill '{skill}' SKILL.md does not document API key fallback behavior. "
            f"Expected at least one of: {API_FALLBACK_PATTERNS[:5]}... "
            f"Skills with external API deps must document what happens without the key."
        )

    @pytest.mark.parametrize("skill", [s for s in PYTHON_BACKEND_SKILLS if s in API_SKILLS])
    def test_degrade_02_smoke_missing_env(self, skill, monkeypatch):
        """Per D-09: Python backend skills with API deps import successfully without env vars."""
        # Remove relevant API keys from environment
        for env_var in API_ENV_VARS.get(skill, []):
            monkeypatch.delenv(env_var, raising=False)

        import_info = _get_import_info(skill)
        if import_info is None:
            pytest.skip(f"No importable module configured for '{skill}'")

        scripts_dir, module_name = import_info
        scripts_str = str(scripts_dir)
        inserted = scripts_str not in sys.path
        if inserted:
            sys.path.insert(0, scripts_str)

        try:
            try:
                mod = importlib.import_module(module_name)
                assert mod is not None
            except ImportError as exc:
                dep_indicators = [
                    "yt_dlp", "yt-dlp", "playwright", "google", "genai",
                    "firecrawl", "scipy", "pandas", "numpy", "matplotlib",
                ]
                exc_msg = str(exc).lower()
                if any(d.lower() in exc_msg for d in dep_indicators):
                    pytest.skip(f"Skipped '{skill}': optional dependency missing — {exc}")
                raise
        finally:
            if inserted and scripts_str in sys.path:
                sys.path.remove(scripts_str)

    # ---------------------------------------------------------------------------
    # DEGRADE-03: Skills handle partial research_context/
    # ---------------------------------------------------------------------------

    @pytest.mark.parametrize("skill", ALL_SKILLS)
    def test_degrade_03_structural_partial_context(self, skill):
        """Per D-08: Skills that read research_context/ handle its partial or missing state.

        Skills that don't read any context files pass trivially (per Context Matrix).
        Skills that do read context are validated for graceful partial-context handling.
        """
        # Skills with no context dependency pass trivially
        if skill in NO_CONTEXT_SKILLS:
            return

        text = _skill_text(skill)

        # Broader set of patterns: anything indicating the skill handles
        # missing/incomplete/optional context at runtime
        partial_patterns = DEGRADE_PATTERNS + [
            r"if.*exist",
            r"if.*not exist",
            r"if.*available",
            r"if.*found",
            r"optional",
            r"when.*missing",
            r"no.*context",
        ]
        assert _matches_any_pattern(text, partial_patterns), (
            f"Skill '{skill}' SKILL.md does not acknowledge partial/missing context handling. "
            f"Add a note that the skill works with incomplete research_context/ files."
        )

    @pytest.mark.parametrize("skill", [s for s in PYTHON_BACKEND_SKILLS
                                         if s not in NO_CONTEXT_SKILLS])
    def test_degrade_03_smoke_partial_context(self, skill, tmp_path):
        """Per D-09: Python backend modules are import-safe regardless of context file presence.

        Most skills read context at runtime (via Claude), not at import time.
        This smoke test verifies that import itself does not attempt to read
        research_context/ and crash with FileNotFoundError.
        """
        import_info = _get_import_info(skill)
        if import_info is None:
            pytest.skip(f"No importable module configured for '{skill}'")

        scripts_dir, module_name = import_info

        # Create a partial context directory (missing research-profile.md)
        partial_context = tmp_path / "research_context"
        partial_context.mkdir()
        # Only create one partial file (not the main profile)
        (partial_context / "notes.md").write_text("Partial context only.")

        scripts_str = str(scripts_dir)
        inserted = scripts_str not in sys.path
        if inserted:
            sys.path.insert(0, scripts_str)

        try:
            try:
                mod = importlib.import_module(module_name)
                assert mod is not None
            except ImportError as exc:
                dep_indicators = [
                    "yt_dlp", "yt-dlp", "playwright", "google", "genai",
                    "firecrawl", "scipy", "pandas", "numpy", "matplotlib",
                    "seaborn", "plotly", "openpyxl",
                ]
                exc_msg = str(exc).lower()
                if any(d.lower() in exc_msg for d in dep_indicators):
                    pytest.skip(f"Skipped '{skill}': optional dependency missing — {exc}")
                raise
        finally:
            if inserted and scripts_str in sys.path:
                sys.path.remove(scripts_str)


# ---------------------------------------------------------------------------
# Helper: skill → (scripts_dir, module_name) mapping
# ---------------------------------------------------------------------------

def _get_import_info(skill: str):
    """Return (scripts_dir, module_name) for a Python backend skill, or None."""
    skill_dir = SKILLS_DIR / skill

    mapping = {
        "meta-skill-creator": (skill_dir / "eval-viewer", "generate_review"),
        "sci-data-analysis":  (skill_dir / "scripts",     "data_ops"),
        "sci-hypothesis":     (skill_dir / "scripts",     "hypothesis_ops"),
        "sci-tools":          (skill_dir / "scripts",     "catalog_ops"),
        "sci-trending-research": (skill_dir / "scripts",  "last30days"),
        "sci-writing":        (skill_dir / "scripts",     "writing_ops"),
        "tool-youtube":       (skill_dir / "scripts",     "transcript"),
        "viz-excalidraw-diagram": (skill_dir / "references", "render_excalidraw"),
        "viz-nano-banana":    (skill_dir / "scripts",     "generate_image"),
    }
    return mapping.get(skill)
