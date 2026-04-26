"""Comprehensive framework test suite — verifies ALL skills are functional and properly chained.

Tests every skill's:
1. Structure (SKILL.md, references, scripts exist)
2. Python operations (actual function calls with real data)
3. Bash scripts (executable, correct behavior)
4. Cross-skill dependencies (referenced skills exist and are compatible)
5. CLAUDE.md consistency (registry, matrix, routing)
6. Output conventions (file naming, directory structure)

Scenario: BiomarkerX immunotherapy study — synthetic clinical data flowing through
the entire skill ecosystem from hypothesis to presentation.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
import yaml

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / ".claude" / "skills"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
OUTPUT = Path(__file__).resolve().parent / "e2e_output" / "framework_test"
CLAUDE_MD = ROOT / "CLAUDE.md"

# Import skill scripts
for scripts_dir in [
    SKILLS_DIR / "sci-data-analysis" / "scripts",
    SKILLS_DIR / "sci-hypothesis" / "scripts",
    SKILLS_DIR / "sci-writing" / "scripts",
    SKILLS_DIR / "sci-tools" / "scripts",
]:
    sys.path.insert(0, str(scripts_dir))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def setup_output():
    OUTPUT.mkdir(parents=True, exist_ok=True)


@pytest.fixture(scope="session")
def output_dir():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    return OUTPUT


@pytest.fixture(scope="module")
def repro_patch(output_dir):
    """Patch the reproducibility logger."""
    ledger = output_dir / "test_ledger.jsonl"
    p = patch("repro.repro_logger.LEDGER_PATH", ledger)
    p.start()
    yield
    p.stop()


@pytest.fixture(scope="module")
def clinical_df(repro_patch):
    from data_ops import load_and_profile
    df, _ = load_and_profile(str(FIXTURES / "e2e_clinical_data.csv"))
    return df


def load_skill_frontmatter(skill_name: str) -> dict:
    skill_md = SKILLS_DIR / skill_name / "SKILL.md"
    text = skill_md.read_text()
    match = re.match(r"^---\n(.*?\n)---", text, re.DOTALL)
    if not match:
        return {}
    return yaml.safe_load(match.group(1))


ALL_SKILLS = sorted([
    d.name for d in SKILLS_DIR.iterdir()
    if d.is_dir() and not d.name.startswith("_")
])


# ===================================================================
# PART 1: Structural Integrity — Every skill is well-formed
# ===================================================================


class TestSkillStructure:
    """Every skill has valid SKILL.md, matching name, and required files."""

    @pytest.mark.parametrize("skill", ALL_SKILLS)
    def test_skill_md_exists(self, skill):
        assert (SKILLS_DIR / skill / "SKILL.md").exists()

    @pytest.mark.parametrize("skill", ALL_SKILLS)
    def test_name_matches_folder(self, skill):
        fm = load_skill_frontmatter(skill)
        assert fm.get("name") == skill, f"name='{fm.get('name')}' != folder='{skill}'"

    @pytest.mark.parametrize("skill", ALL_SKILLS)
    def test_description_under_1024(self, skill):
        fm = load_skill_frontmatter(skill)
        desc = fm.get("description", "")
        assert len(desc) <= 1024, f"{skill} description is {len(desc)} chars"

    @pytest.mark.parametrize("skill", ALL_SKILLS)
    def test_no_stale_marketing_refs(self, skill):
        text = (SKILLS_DIR / skill / "SKILL.md").read_text().lower()
        stale = ["mkt-brand-voice", "mkt-content-repurposing", "mkt-copywriting",
                 "mkt-icp", "mkt-positioning", "mkt-ugc-scripts", "viz-ugc-heygen",
                 "str-trending-research", "tool-stitch", "viz-stitch"]
        for term in stale:
            assert term not in text, f"{skill} references removed skill: {term}"

    @pytest.mark.parametrize("skill", ALL_SKILLS)
    def test_referenced_dependencies_exist(self, skill):
        """Every skill listed in dependencies table must be installed."""
        text = (SKILLS_DIR / skill / "SKILL.md").read_text()
        # Find dependency table rows — match backtick-wrapped names in first column
        dep_matches = re.findall(r"\|\s*`([a-z]+-[a-z-]+)`\s*\|", text)
        for dep in dep_matches:
            # Skip non-skill values that might match the regex
            if not any(dep.startswith(p) for p in ["sci-", "viz-", "tool-", "meta-", "ops-"]):
                continue
            assert (SKILLS_DIR / dep).exists(), (
                f"{skill} depends on '{dep}' which is not installed"
            )


class TestBashScripts:
    """All bash scripts are executable and have valid syntax."""

    SCRIPTS = [
        "sci-data-analysis/scripts/setup.sh",
        "sci-hypothesis/scripts/setup.sh",
        "sci-writing/scripts/setup.sh",
        "sci-tools/scripts/setup.sh",
        "tool-youtube/scripts/setup.sh",
        "viz-diagram-code/scripts/setup.sh",
        "viz-diagram-code/scripts/render_diagram.sh",
        "viz-presentation/scripts/setup.sh",
        "viz-presentation/scripts/render_presentation.sh",
        "sci-research-mgmt/scripts/search_notes.sh",
    ]

    @pytest.mark.parametrize("script", SCRIPTS)
    def test_script_exists(self, script):
        assert (SKILLS_DIR / script).exists()

    @pytest.mark.parametrize("script", SCRIPTS)
    def test_script_executable(self, script):
        path = SKILLS_DIR / script
        assert os.access(str(path), os.X_OK), f"{script} is not executable"

    @pytest.mark.parametrize("script", SCRIPTS)
    def test_script_valid_syntax(self, script):
        path = SKILLS_DIR / script
        result = subprocess.run(
            ["bash", "-n", str(path)], capture_output=True, text=True
        )
        assert result.returncode == 0, f"{script} has syntax errors: {result.stderr}"


class TestReferenceFiles:
    """All reference files mentioned in SKILL.md exist."""

    @pytest.mark.parametrize("skill", ALL_SKILLS)
    def test_references_dir_if_mentioned(self, skill):
        text = (SKILLS_DIR / skill / "SKILL.md").read_text()
        if "references/" in text:
            ref_dir = SKILLS_DIR / skill / "references"
            assert ref_dir.exists(), f"{skill} mentions references/ but dir missing"
            assert len(list(ref_dir.iterdir())) > 0, f"{skill}/references/ is empty"


# ===================================================================
# PART 2: Python Operations — Every skill's code works
# ===================================================================


class TestDataAnalysisOps:
    """sci-data-analysis Python scripts work correctly."""

    def test_load_csv(self, clinical_df):
        assert clinical_df.shape == (30, 9)

    def test_ttest(self, clinical_df, repro_patch):
        from data_ops import run_statistical_test
        result = run_statistical_test(
            clinical_df, "ttest_ind",
            columns={"value_col": "biomarker_level", "group_col": "group"}
        )
        assert result["p_value"] < 0.001
        assert abs(result["effect_size"]) > 1.0

    def test_chi_square(self, clinical_df, repro_patch):
        from data_ops import run_statistical_test
        result = run_statistical_test(
            clinical_df, "chi_square",
            columns={"col_a": "response", "col_b": "group"}
        )
        assert result["p_value"] < 0.01

    def test_pearson(self, clinical_df, repro_patch):
        from data_ops import run_statistical_test
        result = run_statistical_test(
            clinical_df, "pearson",
            columns={"col_a": "biomarker_level", "col_b": "survival_months"}
        )
        assert result["statistic"] > 0.5

    def test_plot_generation(self, clinical_df, output_dir):
        ledger = output_dir / "test_ledger.jsonl"
        with patch("repro.repro_logger.LEDGER_PATH", ledger):
            from plot_ops import generate_dual_plot
            paths = generate_dual_plot(
                clinical_df, "scatter", "biomarker_level", "survival_months",
                base_path=str(output_dir / "test_scatter"),
                title="Test Plot", xlabel="X", ylabel="Y", hue_col="group"
            )
        # generate_dual_plot returns dict with 'static' (list) and 'interactive' (str)
        if isinstance(paths, dict):
            all_files = paths.get("static", []) + [paths.get("interactive", "")]
        elif isinstance(paths, list):
            all_files = paths
        else:
            all_files = [paths]
        all_files = [f for f in all_files if f]
        assert len(all_files) >= 2, f"Expected multiple output files, got {all_files}"
        for p in all_files:
            assert Path(p).exists(), f"Plot file not found: {p}"

    def test_box_plot(self, clinical_df, output_dir, repro_patch):
        from plot_ops import generate_dual_plot
        paths = generate_dual_plot(
            clinical_df, "box", "group", "biomarker_level",
            base_path=str(output_dir / "test_box")
        )
        assert len(paths) >= 2

    def test_report_generation(self, clinical_df, repro_patch):
        from data_ops import run_statistical_test, generate_report
        result = run_statistical_test(
            clinical_df, "ttest_ind",
            columns={"value_col": "biomarker_level", "group_col": "group"}
        )
        report = generate_report(result, "ttest_ind")
        assert "t-test" in report.lower() or "t(" in report.lower()
        assert len(report) > 50


class TestHypothesisOps:
    """sci-hypothesis Python scripts work correctly."""

    def test_pattern_analysis(self, output_dir):
        ledger = output_dir / "test_ledger.jsonl"
        with patch("repro.repro_logger.LEDGER_PATH", ledger):
            from hypothesis_ops import analyze_patterns
            result = analyze_patterns(str(FIXTURES / "e2e_clinical_data.csv"))
        assert "correlations" in result
        assert "group_differences" in result
        assert len(result["group_differences"]) > 0

    def test_power_analysis(self):
        from hypothesis_ops import ttest_power_analysis
        result = ttest_power_analysis(effect_size=1.0, alpha=0.05, power=0.8)
        assert "n1" in result
        assert result["n1"] > 0

    def test_evidence_classification(self):
        from hypothesis_ops import classify_evidence
        result = classify_evidence(
            p_value=0.001, effect_size=1.5,
            ci_lower=0.8, ci_upper=2.2
        )
        assert "verdict" in result
        assert "strong" in result["verdict"].lower()

    def test_experiment_design(self, repro_patch):
        from hypothesis_ops import design_experiment
        result = design_experiment(
            hypothesis="BiomarkerX predicts response",
            effect_size=1.0, test_type="ttest"
        )
        assert "sample_size" in result
        assert "hypothesis" in result

    def test_hypothesis_report(self):
        from hypothesis_ops import generate_hypothesis_report
        report = generate_hypothesis_report({
            "hypothesis": "Test hypothesis",
            "p_value": 0.001, "effect_size": 1.5,
            "ci_lower": 0.8, "ci_upper": 2.2,
            "rationale": "Strong signal", "verdict": "supported"
        })
        assert len(report) > 50

    def test_experiment_report(self, repro_patch):
        from hypothesis_ops import design_experiment, generate_experiment_report
        design = design_experiment(
            hypothesis="Test", effect_size=1.0, test_type="ttest"
        )
        report = generate_experiment_report(design)
        assert len(report) > 50


class TestWritingOps:
    """sci-writing Python scripts work correctly."""

    def test_parse_bibtex(self):
        from writing_ops import parse_bib_file
        entries = parse_bib_file(str(FIXTURES / "e2e_references.bib"))
        assert len(entries) == 4
        keys = [e["key"] for e in entries]
        assert "Chen2024" in keys

    def test_format_apa(self):
        from writing_ops import parse_bib_file, format_citation
        entries = parse_bib_file(str(FIXTURES / "e2e_references.bib"))
        formatted = format_citation(entries[0], "apa")
        assert "2024" in formatted
        assert len(formatted) > 20

    def test_format_nature(self):
        from writing_ops import parse_bib_file, format_citation
        entries = parse_bib_file(str(FIXTURES / "e2e_references.bib"))
        formatted = format_citation(entries[0], "nature")
        assert len(formatted) > 10

    def test_bibliography(self):
        from writing_ops import parse_bib_file, format_bibliography
        entries = parse_bib_file(str(FIXTURES / "e2e_references.bib"))
        bib = format_bibliography(entries, "apa")
        assert "Chen" in bib
        assert "Wang" in bib
        assert len(bib) > 200

    def test_citation_replacement(self):
        from writing_ops import parse_bib_file, replace_citation_markers
        entries = parse_bib_file(str(FIXTURES / "e2e_references.bib"))
        draft = "Results are consistent with prior work [@Chen2024] and [@Wang2023]."
        formatted, warnings = replace_citation_markers(draft, entries, "apa")
        assert "[@Chen2024]" not in formatted
        assert "[@Wang2023]" not in formatted
        assert len(warnings) == 0

    def test_review_report(self, output_dir):
        sys.path.insert(0, str(SKILLS_DIR / "sci-writing" / "scripts"))
        import importlib
        import review_ops
        importlib.reload(review_ops)
        # Create a temp manuscript file
        ms = output_dir / "test_manuscript.md"
        ms.write_text("# Introduction\n\nThis study examines BiomarkerX.\n")
        findings = [
            {"criterion": "originality", "score": 7, "comments": "Novel approach"},
            {"criterion": "methodology", "score": 8, "comments": "Sound design"},
            {"criterion": "clarity", "score": 6, "comments": "Needs editing"},
        ]
        report = review_ops.generate_review_report(str(ms), findings)
        assert len(report) > 50


class TestCatalogOps:
    """sci-tools catalog operations work."""

    def test_import(self):
        from catalog_ops import search_catalog
        # Just verify import works — actual search needs the catalog file
        assert callable(search_catalog)


# ===================================================================
# PART 3: Rendering Tools — Bash scripts produce output
# ===================================================================


class TestMarpRendering:
    """viz-presentation renders Marp slides."""

    def test_setup_script(self):
        result = subprocess.run(
            ["bash", str(SKILLS_DIR / "viz-presentation" / "scripts" / "setup.sh")],
            capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 0
        assert "marp" in result.stdout.lower() or "OK" in result.stdout

    def test_render_presentation(self, output_dir):
        # Create a minimal test presentation
        test_md = output_dir / "test_slides.md"
        test_md.write_text("---\nmarp: true\n---\n\n# Test Slide\n\nContent\n\n---\n\n# Slide 2\n\nMore content\n")

        result = subprocess.run(
            ["bash", str(SKILLS_DIR / "viz-presentation" / "scripts" / "render_presentation.sh"),
             str(test_md), "pdf"],
            capture_output=True, text=True, timeout=60
        )
        pdf_path = test_md.with_suffix(".pdf")
        assert pdf_path.exists(), f"PDF not created. stderr: {result.stderr}"
        assert pdf_path.stat().st_size > 1000


class TestMermaidSetup:
    """viz-diagram-code setup and rendering."""

    @pytest.mark.skipif(
        os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true",
        reason="setup.sh runs npm install -g which needs elevated permissions in CI"
    )
    def test_setup_script(self):
        result = subprocess.run(
            ["bash", str(SKILLS_DIR / "viz-diagram-code" / "scripts" / "setup.sh")],
            capture_output=True, text=True, timeout=120
        )
        assert result.returncode == 0


# ===================================================================
# PART 4: Cross-Skill Chaining — Skills reference each other correctly
# ===================================================================


class TestSkillChaining:
    """Verify skills that depend on each other are properly connected."""

    def test_writing_routes_blog_to_communication(self):
        text = (SKILLS_DIR / "sci-writing" / "SKILL.md").read_text()
        assert "sci-communication" in text

    def test_communication_depends_on_viz_skills(self):
        text = (SKILLS_DIR / "sci-communication" / "SKILL.md").read_text()
        assert "viz-nano-banana" in text
        assert "viz-diagram-code" in text
        assert "sci-data-analysis" in text

    def test_writing_depends_on_viz_skills(self):
        text = (SKILLS_DIR / "sci-writing" / "SKILL.md").read_text()
        assert "viz-nano-banana" in text
        assert "viz-diagram-code" in text

    def test_presentation_depends_on_viz_skills(self):
        text = (SKILLS_DIR / "viz-presentation" / "SKILL.md").read_text()
        assert "viz-diagram-code" in text

    def test_trending_routes_to_hypothesis(self):
        text = (SKILLS_DIR / "sci-trending-research" / "SKILL.md").read_text()
        assert "sci-hypothesis" in text

    def test_trending_routes_to_communication(self):
        text = (SKILLS_DIR / "sci-trending-research" / "SKILL.md").read_text()
        assert "sci-communication" in text

    def test_trending_routes_to_writing(self):
        text = (SKILLS_DIR / "sci-trending-research" / "SKILL.md").read_text()
        assert "sci-writing" in text

    def test_literature_uses_correct_trending_name(self):
        text = (SKILLS_DIR / "sci-literature-research" / "SKILL.md").read_text()
        assert "str-trending-research" not in text, "Still references old skill name"

    def test_hypothesis_chains_from_data_analysis(self):
        text = (SKILLS_DIR / "sci-hypothesis" / "SKILL.md").read_text()
        assert "data" in text.lower() and "pattern" in text.lower()

    def test_communication_accepts_multiple_sources(self):
        text = (SKILLS_DIR / "sci-communication" / "SKILL.md").read_text()
        for source in ["Paper", "Concept", "URL", "Pasted text"]:
            assert source in text or source.lower() in text.lower()


# ===================================================================
# PART 5: CLAUDE.md Consistency
# ===================================================================


class TestClaudeMdConsistency:
    """CLAUDE.md matches the actual skill ecosystem."""

    @pytest.fixture(autouse=True)
    def load(self):
        self.text = CLAUDE_MD.read_text()

    def test_no_removed_skills(self):
        removed = ["mkt-brand-voice", "mkt-content-repurposing", "mkt-copywriting",
                    "mkt-icp", "mkt-positioning", "mkt-ugc-scripts", "viz-ugc-heygen",
                    "str-trending-research", "tool-stitch", "viz-stitch", "str-ai-seo"]
        for skill in removed:
            assert skill not in self.text, f"CLAUDE.md still references {skill}"

    # Skills excluded from the public repo via .gitignore — may exist on
    # disk locally without a CLAUDE.md row, or vice versa in CI.
    _GITIGNORED_SKILLS = {"tool-substack", "tool-social-publisher"}

    def test_all_installed_skills_in_registry(self):
        for skill in ALL_SKILLS:
            if skill in self._GITIGNORED_SKILLS:
                continue
            assert f"`{skill}`" in self.text, f"{skill} not in CLAUDE.md"

    def test_disambiguation_covers_all_sci_skills(self):
        sci_skills = [
            s for s in ALL_SKILLS
            if s.startswith("sci-") and s not in self._GITIGNORED_SKILLS
        ]
        for skill in sci_skills:
            assert skill in self.text, f"{skill} missing from disambiguation"

    def test_no_mkt_category(self):
        assert "| `mkt`" not in self.text


# ===================================================================
# PART 6: Full Pipeline Integration
# ===================================================================


class TestFullPipeline:
    """Chain all skills: data → hypothesis → writing → communication → presentation."""

    def test_stage1_data_analysis(self, clinical_df, output_dir, repro_patch):
        """Load data, run all stat tests, generate plots."""
        from data_ops import run_statistical_test
        from plot_ops import generate_dual_plot

        bio = run_statistical_test(clinical_df, "ttest_ind",
            columns={"value_col": "biomarker_level", "group_col": "group"})
        assert bio["p_value"] < 0.001

        chi = run_statistical_test(clinical_df, "chi_square",
            columns={"col_a": "response", "col_b": "group"})
        assert chi["p_value"] < 0.01

        corr = run_statistical_test(clinical_df, "pearson",
            columns={"col_a": "biomarker_level", "col_b": "survival_months"})
        assert corr["statistic"] > 0.7

        paths = generate_dual_plot(clinical_df, "scatter",
            "biomarker_level", "survival_months",
            base_path=str(output_dir / "pipeline_scatter"),
            hue_col="group")
        assert len(paths) >= 2
        self.__class__.stats = {"bio": bio, "chi": chi, "corr": corr}
        self.__class__.plot_paths = paths

    def test_stage2_hypothesis(self, repro_patch):
        """Generate hypotheses from the data patterns."""
        from hypothesis_ops import (
            analyze_patterns, classify_evidence,
            ttest_power_analysis, design_experiment,
        )

        patterns = analyze_patterns(str(FIXTURES / "e2e_clinical_data.csv"))
        assert len(patterns["group_differences"]) > 0

        stats = getattr(self.__class__, "stats", None)
        if stats:
            ev = classify_evidence(
                p_value=stats["bio"]["p_value"],
                effect_size=stats["bio"]["effect_size"],
                ci_lower=stats["bio"]["ci_95"][0],
                ci_upper=stats["bio"]["ci_95"][1],
            )
            assert "verdict" in ev

        power = ttest_power_analysis(effect_size=1.5)
        assert power["n1"] > 0

        design = design_experiment(
            hypothesis="BiomarkerX predicts response",
            effect_size=1.0, test_type="ttest"
        )
        assert "sample_size" in design

    def test_stage3_manuscript(self, output_dir):
        """Format citations for the manuscript."""
        from writing_ops import (
            parse_bib_file, format_bibliography, replace_citation_markers,
        )

        entries = parse_bib_file(str(FIXTURES / "e2e_references.bib"))
        bib = format_bibliography(entries, "apa")
        assert len(bib) > 200

        draft = "Findings align with prior work [@Chen2024] and [@Kim2023]."
        formatted, warnings = replace_citation_markers(draft, entries, "apa")
        assert "[@" not in formatted
        assert len(warnings) == 0

        # Save manuscript fragment
        (output_dir / "manuscript_test.md").write_text(
            f"# Test Manuscript\n\n{formatted}\n\n{bib}"
        )
        assert (output_dir / "manuscript_test.md").exists()

    def test_stage4_blog_structure(self):
        """Verify blog format reference has required sections."""
        ref = SKILLS_DIR / "sci-communication" / "references" / "blog-format.md"
        text = ref.read_text()
        assert "## Structure" in text or "## structure" in text.lower()
        assert "accuracy" in text.lower()
        assert "citation simplification" in text.lower() or "simplified" in text.lower()

    def test_stage5_tutorial_structure(self):
        """Verify tutorial format reference has required sections."""
        ref = SKILLS_DIR / "sci-communication" / "references" / "tutorial-format.md"
        text = ref.read_text()
        assert "prerequisite" in text.lower()
        assert "pitfall" in text.lower()
        assert "code" in text.lower()

    def test_stage6_diagram_creation(self, output_dir):
        """Create a Mermaid diagram file."""
        mmd = output_dir / "test_diagram.mmd"
        mmd.write_text(
            "%%{init: {'theme': 'neutral'}}%%\n"
            "flowchart TB\n"
            "    A[Data] --> B[Analysis]\n"
            "    B --> C[Results]\n"
        )
        assert mmd.exists()
        content = mmd.read_text()
        assert "flowchart" in content

    def test_stage7_presentation_creation(self, output_dir):
        """Create and render a Marp presentation."""
        pres = output_dir / "test_presentation.md"
        pres.write_text(
            "---\nmarp: true\nmath: katex\n---\n\n"
            "# BiomarkerX Study\n\n"
            "- Key finding: $p < 0.001$\n"
            "- Effect size: $d = 3.64$\n\n"
            "---\n\n"
            "## Results\n\n"
            "Treatment group showed significantly higher biomarker levels.\n"
        )
        assert pres.exists()

        # Render to PDF
        result = subprocess.run(
            ["bash", str(SKILLS_DIR / "viz-presentation" / "scripts" / "render_presentation.sh"),
             str(pres), "pdf"],
            capture_output=True, text=True, timeout=60
        )
        pdf = pres.with_suffix(".pdf")
        assert pdf.exists(), f"PDF render failed: {result.stderr}"

    def test_stage8_all_outputs_exist(self, output_dir):
        """Verify the full pipeline produced all expected files."""
        files = {f.name for f in output_dir.iterdir() if f.is_file()}
        expected_patterns = [
            "pipeline_scatter",   # Plot from stage 1
            "manuscript_test",    # Manuscript from stage 3
            "test_diagram.mmd",   # Diagram from stage 6
            "test_presentation",  # Presentation from stage 7
        ]
        for pattern in expected_patterns:
            matches = [f for f in files if pattern in f]
            assert len(matches) > 0, f"Missing output matching '{pattern}'"


# ===================================================================
# PART 7: Personalization — Context files work
# ===================================================================


class TestPersonalization:
    """Verify personalization infrastructure is functional."""

    def test_soul_md_exists(self):
        soul = ROOT / "context" / "SOUL.md"
        assert soul.exists()
        text = soul.read_text()
        assert "scientific" in text.lower() or "research" in text.lower()
        assert "marketing" not in text.lower()

    def test_user_md_exists(self):
        assert (ROOT / "context" / "USER.md").exists()

    def test_learnings_exists(self):
        learnings = ROOT / "context" / "learnings.md"
        assert learnings.exists()

    def test_learnings_has_active_skill_sections(self):
        text = (ROOT / "context" / "learnings.md").read_text()
        expected = ["sci-writing", "sci-data-analysis", "sci-literature-research"]
        for skill in expected:
            assert f"## {skill}" in text, f"learnings.md missing ## {skill}"

    def test_learnings_no_stale_sections(self):
        text = (ROOT / "context" / "learnings.md").read_text()
        stale = ["mkt-brand-voice", "mkt-copywriting", "mkt-icp",
                 "viz-ugc-heygen", "tool-stitch", "viz-stitch-design"]
        for skill in stale:
            assert f"## {skill}" not in text, f"learnings.md still has stale ## {skill}"

    def test_research_profile_location(self):
        """Research profile path referenced by sci-* skills should be consistent."""
        for skill in ALL_SKILLS:
            if not skill.startswith("sci-"):
                continue
            text = (SKILLS_DIR / skill / "SKILL.md").read_text()
            if "research-profile" in text:
                assert "research_context/research-profile.md" in text or "research-profile.md" in text


# ===================================================================
# PART 8: API Key Graceful Degradation
# ===================================================================


class TestGracefulDegradation:
    """Skills with API key dependencies have documented fallbacks."""

    API_SKILLS = {
        "viz-nano-banana": "GEMINI_API_KEY",
        "sci-trending-research": "OPENAI_API_KEY",
        "tool-firecrawl-scraper": "FIRECRAWL_API_KEY",
        "tool-youtube": "YOUTUBE_API_KEY",
    }

    @pytest.mark.parametrize("skill,key", list(API_SKILLS.items()))
    def test_api_key_documented(self, skill, key):
        text = (SKILLS_DIR / skill / "SKILL.md").read_text()
        assert key in text, f"{skill} doesn't document {key}"

    @pytest.mark.parametrize("skill,key", list(API_SKILLS.items()))
    def test_fallback_documented(self, skill, key):
        text = (SKILLS_DIR / skill / "SKILL.md").read_text().lower()
        fallback_terms = ["fallback", "without", "missing", "not found",
                         "no api key", "not configured", "if missing"]
        has_fallback = any(term in text for term in fallback_terms)
        assert has_fallback, f"{skill} has no documented fallback for missing {key}"
