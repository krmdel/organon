"""End-to-end workflow scenario tests — simulates multi-skill user journeys.

These tests verify that the skill ecosystem supports complete scientific
workflows, not just individual skill invocations. Each test class represents
a realistic user scenario that chains multiple skills together.

Note: These are structural/integration tests. They verify the skill files,
dependencies, and routing exist to support each workflow — they don't
execute the actual LLM-driven skill logic (that requires a live Claude session).
"""

import re
from pathlib import Path

import pytest

SKILLS_DIR = Path(__file__).resolve().parent.parent / ".claude" / "skills"
CLAUDE_MD = Path(__file__).resolve().parent.parent / "CLAUDE.md"


def skill_text(skill_name: str) -> str:
    """Read full SKILL.md text for a skill."""
    return (SKILLS_DIR / skill_name / "SKILL.md").read_text()


def skill_references(skill_name: str) -> list[str]:
    """List reference files for a skill."""
    ref_dir = SKILLS_DIR / skill_name / "references"
    if not ref_dir.exists():
        return []
    return [f.name for f in ref_dir.iterdir() if f.is_file()]


# ---------------------------------------------------------------------------
# Scenario 1: Hypothesis Generation from Data
# User: "I have patient data — what hypotheses can I generate?"
# Flow: sci-data-analysis → sci-hypothesis → sci-writing
# ---------------------------------------------------------------------------


class TestScenarioHypothesisFromData:
    """
    User loads data, finds patterns, generates hypotheses, then drafts a paper.
    """

    def test_data_analysis_exists(self):
        assert (SKILLS_DIR / "sci-data-analysis" / "SKILL.md").exists()

    def test_data_analysis_detects_patterns(self):
        text = skill_text("sci-data-analysis")
        assert "pattern" in text.lower() or "correlation" in text.lower()

    def test_hypothesis_reads_data_analysis_output(self):
        """sci-hypothesis should be able to consume sci-data-analysis output."""
        text = skill_text("sci-hypothesis")
        assert "data" in text.lower() and "pattern" in text.lower()

    def test_hypothesis_generates_testable_hypotheses(self):
        text = skill_text("sci-hypothesis")
        assert "testable" in text.lower() or "generate" in text.lower()

    def test_hypothesis_has_experiment_design(self):
        text = skill_text("sci-hypothesis")
        assert "experiment" in text.lower() and "design" in text.lower()

    def test_writing_can_draft_from_hypothesis(self):
        """sci-writing should be able to draft a paper section from hypothesis results."""
        text = skill_text("sci-writing")
        assert "draft" in text.lower()
        # Writing reads data analysis outputs
        assert "sci-data-analysis" in text

    def test_chain_dependencies_satisfied(self):
        """All skills in the chain should exist."""
        for skill in ["sci-data-analysis", "sci-hypothesis", "sci-writing"]:
            assert (SKILLS_DIR / skill / "SKILL.md").exists()


# ---------------------------------------------------------------------------
# Scenario 2: Article Summarization
# User: "Summarize this paper" or "Find and summarize papers on X"
# Flow: sci-literature-research → sci-communication (lay summary or blog)
# ---------------------------------------------------------------------------


class TestScenarioArticleSummarization:
    """
    User searches for papers, gets summaries, then creates accessible content.
    """

    def test_literature_can_search_papers(self):
        text = skill_text("sci-literature-research")
        assert "search" in text.lower() and "paper" in text.lower()

    def test_literature_can_summarize(self):
        text = skill_text("sci-literature-research")
        assert "summar" in text.lower()  # summary/summarize

    def test_literature_exports_bibtex(self):
        text = skill_text("sci-literature-research")
        assert "bibtex" in text.lower() or "bib" in text.lower()

    def test_communication_accepts_paper_source(self):
        """sci-communication should accept papers as input for repurposing."""
        text = skill_text("sci-communication")
        assert "paper" in text.lower() or "manuscript" in text.lower()

    def test_communication_has_lay_summary_mode(self):
        text = skill_text("sci-communication")
        assert "lay-summary" in text.lower() or "lay summary" in text.lower()

    def test_communication_has_blog_mode(self):
        text = skill_text("sci-communication")
        assert "blog" in text.lower()

    def test_lay_summary_format_defined(self):
        """The other-formats.md should define lay summary specifications."""
        ref_dir = SKILLS_DIR / "sci-communication" / "references"
        text = (ref_dir / "other-formats.md").read_text()
        assert "lay summary" in text.lower()
        assert "grade" in text.lower() or "reading level" in text.lower()


# ---------------------------------------------------------------------------
# Scenario 3: Trending Research → Blog/Tutorial
# User: "What's hot in genomics? Write me a blog post about the top trend"
# Flow: sci-trending-research → sci-communication (blog or tutorial)
# ---------------------------------------------------------------------------


class TestScenarioTrendingToBlog:
    """
    User checks trends, then creates outreach content about a trending topic.
    """

    def test_trending_produces_brief(self):
        text = skill_text("sci-trending-research")
        assert "brief" in text.lower() and "save" in text.lower()

    def test_trending_brief_has_findings(self):
        ref_dir = SKILLS_DIR / "sci-trending-research" / "references"
        template = (ref_dir / "brief-template.md").read_text()
        assert "Key Findings" in template or "key findings" in template.lower()

    def test_trending_routes_to_communication(self):
        """Step 6 should suggest routing to sci-communication."""
        text = skill_text("sci-trending-research")
        assert "sci-communication" in text

    def test_communication_accepts_concept_input(self):
        """User can describe a trending concept without providing a paper."""
        text = skill_text("sci-communication")
        assert "concept" in text.lower() or "topic" in text.lower()

    def test_communication_blog_format_complete(self):
        ref_dir = SKILLS_DIR / "sci-communication" / "references"
        blog = (ref_dir / "blog-format.md").read_text()
        # Should have structure, specs, accuracy gate
        assert "## Structure" in blog or "## structure" in blog.lower()
        assert "1000" in blog  # ~1000 words target
        assert "accuracy" in blog.lower()


# ---------------------------------------------------------------------------
# Scenario 4: Trending Research Summarization
# User: "Summarize what's trending in AI for drug discovery"
# Flow: sci-trending-research (synthesis) → user reads brief
# ---------------------------------------------------------------------------


class TestScenarioTrendingSummarization:
    """
    User wants a synthesis of current trends — not a paper, just the landscape.
    """

    def test_trending_has_synthesis_step(self):
        text = skill_text("sci-trending-research")
        assert "synthesize" in text.lower() or "synthesis" in text.lower()

    def test_trending_methodology_weights_sources(self):
        ref_dir = SKILLS_DIR / "sci-trending-research" / "references"
        synth = (ref_dir / "synthesis-guide.md").read_text()
        assert "weight" in synth.lower() or "engagement" in synth.lower()

    def test_trending_methodology_cross_validates(self):
        ref_dir = SKILLS_DIR / "sci-trending-research" / "references"
        synth = (ref_dir / "synthesis-guide.md").read_text()
        assert "cross" in synth.lower()  # cross-platform validation

    def test_trending_covers_multiple_platforms(self):
        text = skill_text("sci-trending-research")
        platforms = ["reddit", "twitter", "x", "preprint", "biorxiv", "arxiv"]
        found = sum(1 for p in platforms if p in text.lower())
        assert found >= 3, f"Trending covers only {found} platforms (expected ≥3)"

    def test_trending_has_query_types(self):
        text = skill_text("sci-trending-research")
        for qtype in ["BREAKTHROUGHS", "METHODS", "DEBATES", "GENERAL"]:
            assert qtype in text, f"Missing query type: {qtype}"


# ---------------------------------------------------------------------------
# Scenario 5: Paper Preparation (full manuscript workflow)
# User: "Help me write my paper from start to finish"
# Flow: sci-literature-research → sci-data-analysis → sci-writing → figures
# ---------------------------------------------------------------------------


class TestScenarioPaperPreparation:
    """
    Full paper writing workflow from literature to formatted manuscript.
    """

    def test_writing_has_all_sections(self):
        text = skill_text("sci-writing")
        for section in ["introduction", "methods", "results", "discussion", "abstract"]:
            assert section.lower() in text.lower(), f"Missing section: {section}"

    def test_writing_has_citation_formatting(self):
        text = skill_text("sci-writing")
        assert "citation" in text.lower() and "format" in text.lower()

    def test_writing_reads_literature_output(self):
        text = skill_text("sci-writing")
        assert "sci-literature-research" in text or ".bib" in text

    def test_writing_reads_data_analysis_output(self):
        text = skill_text("sci-writing")
        assert "sci-data-analysis" in text

    def test_writing_has_peer_review(self):
        text = skill_text("sci-writing")
        assert "peer review" in text.lower() or "review mode" in text.lower()

    def test_writing_offers_figure_generation(self):
        text = skill_text("sci-writing")
        assert "Figure Proposal Gate" in text or "Figure Generation" in text

    def test_writing_routes_to_data_plots(self):
        text = skill_text("sci-writing")
        assert "sci-data-analysis" in text and "plot" in text.lower()

    def test_writing_routes_to_illustrations(self):
        text = skill_text("sci-writing")
        assert "viz-nano-banana" in text

    def test_writing_routes_to_flow_diagrams(self):
        text = skill_text("sci-writing")
        assert "viz-excalidraw-diagram" in text

    def test_section_guides_reference_exists(self):
        assert (
            SKILLS_DIR / "sci-writing" / "references" / "section-guides.md"
        ).exists()

    def test_citation_styles_available(self):
        text = skill_text("sci-writing")
        for style in ["apa", "nature", "ieee"]:
            assert style.lower() in text.lower(), f"Missing citation style: {style}"


# ---------------------------------------------------------------------------
# Scenario 6: Tutorial with Illustrations
# User: "Write a tutorial on CRISPR-Cas9 gene editing with diagrams"
# Flow: sci-communication (tutorial) + viz-nano-banana + viz-excalidraw
# ---------------------------------------------------------------------------


class TestScenarioTutorialWithIllustrations:
    """
    Tutorial creation with inline visual generation.
    """

    def test_communication_has_tutorial_mode(self):
        text = skill_text("sci-communication")
        assert "tutorial" in text.lower()

    def test_tutorial_format_has_structure(self):
        ref_dir = SKILLS_DIR / "sci-communication" / "references"
        tutorial = (ref_dir / "tutorial-format.md").read_text()
        required_sections = [
            "what you'll learn",
            "prerequisite",
            "step",
            "example",
            "pitfall",
        ]
        text_lower = tutorial.lower()
        for section in required_sections:
            assert section in text_lower, f"Tutorial format missing: {section}"

    def test_tutorial_mentions_visual_placement(self):
        ref_dir = SKILLS_DIR / "sci-communication" / "references"
        tutorial = (ref_dir / "tutorial-format.md").read_text()
        assert "visual" in tutorial.lower() or "diagram" in tutorial.lower()

    def test_communication_viz_step_exists(self):
        """Step 3 should be visual generation."""
        text = skill_text("sci-communication")
        assert "Visual Generation" in text or "visual generation" in text.lower()

    def test_viz_nano_banana_has_scientific_illustrations(self):
        text = skill_text("viz-nano-banana")
        scientific_terms = ["scientific", "pathway", "cell", "molecular", "experimental"]
        found = sum(1 for t in scientific_terms if t in text.lower())
        assert found >= 2, "viz-nano-banana lacks scientific illustration support"

    def test_viz_excalidraw_supports_protocols(self):
        text = skill_text("viz-excalidraw-diagram")
        assert "protocol" in text.lower() or "workflow" in text.lower()

    def test_communication_declares_viz_dependencies(self):
        text = skill_text("sci-communication")
        assert "viz-nano-banana" in text
        assert "viz-excalidraw-diagram" in text
        assert "sci-data-analysis" in text


# ---------------------------------------------------------------------------
# Scenario 7: Blog Post from Multiple Sources
# User: "Write a blog post about CRISPR — use these URLs and my recent paper"
# Flow: tool-firecrawl (URLs) + sci-communication (blog) + viz
# ---------------------------------------------------------------------------


class TestScenarioBlogFromMultipleSources:
    """
    Blog post that synthesizes multiple input types.
    """

    def test_communication_accepts_urls(self):
        text = skill_text("sci-communication")
        assert "url" in text.lower()

    def test_communication_accepts_pasted_text(self):
        text = skill_text("sci-communication")
        assert "pasted" in text.lower() or "paste" in text.lower()

    def test_communication_accepts_multiple_sources(self):
        text = skill_text("sci-communication")
        assert "multiple" in text.lower() or "synthesize" in text.lower()

    def test_communication_has_accuracy_gate(self):
        text = skill_text("sci-communication")
        assert "accuracy" in text.lower()

    def test_communication_has_humanizer_gate_for_blogs(self):
        text = skill_text("sci-communication")
        assert "humanizer" in text.lower()
        # Should apply to blog specifically
        assert "blog" in text.lower()

    def test_blog_format_prevents_overclaiming(self):
        ref_dir = SKILLS_DIR / "sci-communication" / "references"
        blog = (ref_dir / "blog-format.md").read_text()
        hedging_checks = ["suggests", "proves", "flagged"]
        found = sum(1 for h in hedging_checks if h in blog.lower())
        assert found >= 2, "Blog format lacks hedging verification"

    def test_firecrawl_skill_exists(self):
        """Firecrawl is needed for URL extraction."""
        assert (SKILLS_DIR / "tool-firecrawl-scraper" / "SKILL.md").exists()


# ---------------------------------------------------------------------------
# Scenario 8: Social Thread from Research Finding
# User: "Turn my latest finding into a Twitter thread"
# Flow: sci-communication (social) with accuracy gate
# ---------------------------------------------------------------------------


class TestScenarioSocialThread:
    """
    Social media thread from research — must maintain accuracy.
    """

    def test_communication_has_social_mode(self):
        text = skill_text("sci-communication")
        assert "social" in text.lower()

    def test_social_format_has_thread_structure(self):
        ref_dir = SKILLS_DIR / "sci-communication" / "references"
        social = (ref_dir / "social-formats.md").read_text()
        assert "thread" in social.lower()
        assert "hook" in social.lower()

    def test_social_format_has_char_limits(self):
        ref_dir = SKILLS_DIR / "sci-communication" / "references"
        social = (ref_dir / "social-formats.md").read_text()
        assert "280" in social  # Twitter char limit

    def test_social_format_has_accuracy_gate(self):
        ref_dir = SKILLS_DIR / "sci-communication" / "references"
        social = (ref_dir / "social-formats.md").read_text()
        assert "accuracy" in social.lower()

    def test_social_includes_caveat_tweet(self):
        ref_dir = SKILLS_DIR / "sci-communication" / "references"
        social = (ref_dir / "social-formats.md").read_text()
        assert "caveat" in social.lower() or "limitation" in social.lower()


# ---------------------------------------------------------------------------
# CLAUDE.md Consistency Tests
# ---------------------------------------------------------------------------


class TestClaudeMdConsistency:
    """Verify CLAUDE.md is consistent with the actual skill ecosystem."""

    @pytest.fixture(autouse=True)
    def load_claude_md(self):
        self.claude_md = CLAUDE_MD.read_text()

    def test_no_marketing_skills_in_registry(self):
        removed = [
            "mkt-brand-voice", "mkt-content-repurposing", "mkt-copywriting",
            "mkt-icp", "mkt-positioning", "mkt-ugc-scripts", "viz-ugc-heygen",
        ]
        for skill in removed:
            assert f"`{skill}`" not in self.claude_md, (
                f"CLAUDE.md still references removed skill: {skill}"
            )

    def test_sci_communication_in_registry(self):
        assert "`sci-communication`" in self.claude_md

    def test_sci_trending_research_in_registry(self):
        assert "`sci-trending-research`" in self.claude_md

    def test_no_str_trending_reference(self):
        assert "str-trending-research" not in self.claude_md

    def test_disambiguation_has_communication(self):
        """Science skill disambiguation should include sci-communication."""
        assert "sci-communication" in self.claude_md
        # Should appear in the numbered priority list
        lines = self.claude_md.split("\n")
        disambiguation_lines = [
            l for l in lines
            if "sci-communication" in l and re.match(r"\d+\.", l.strip())
        ]
        assert len(disambiguation_lines) >= 1, (
            "sci-communication not in disambiguation priority list"
        )

    def test_disambiguation_has_trending(self):
        lines = self.claude_md.split("\n")
        trending_lines = [
            l for l in lines
            if "sci-trending-research" in l and re.match(r"\d+\.", l.strip())
        ]
        assert len(trending_lines) >= 1, (
            "sci-trending-research not in disambiguation priority list"
        )

    def test_context_matrix_has_all_sci_skills(self):
        sci_skills = [
            "sci-data-analysis", "sci-hypothesis", "sci-literature-research",
            "sci-writing", "sci-communication", "sci-tools", "sci-research-mgmt",
            "sci-trending-research",
        ]
        for skill in sci_skills:
            assert f"`{skill}`" in self.claude_md, (
                f"Context matrix missing {skill}"
            )

    def test_skill_categories_no_mkt(self):
        """Skill categories should not include mkt prefix."""
        # Find the categories table
        in_categories = False
        for line in self.claude_md.split("\n"):
            if "Skill Categories" in line:
                in_categories = True
            if in_categories and "| `mkt`" in line:
                pytest.fail("Skill categories still includes mkt prefix")
            if in_categories and line.startswith("---"):
                break
