"""Tests for skill reference files — verifies completeness, consistency,
and scientific (not marketing) framing of reference documents.

Covers:
- sci-communication: all format references exist and have accuracy gates
- sci-writing: section guides, review checklist, no repurpose-formats.md
- sci-trending-research: methodology reframed for science
- viz skills: referenced as dependencies where needed
"""

from pathlib import Path

import pytest

SKILLS_DIR = Path(__file__).resolve().parent.parent / ".claude" / "skills"


# ---------------------------------------------------------------------------
# sci-communication Reference Tests
# ---------------------------------------------------------------------------


class TestCommunicationReferences:
    """Verify sci-communication has all required reference files."""

    REF_DIR = SKILLS_DIR / "sci-communication" / "references"

    def test_references_dir_exists(self):
        assert self.REF_DIR.is_dir()

    def test_blog_format_exists(self):
        assert (self.REF_DIR / "blog-format.md").exists()

    def test_tutorial_format_exists(self):
        assert (self.REF_DIR / "tutorial-format.md").exists()

    def test_social_formats_exists(self):
        assert (self.REF_DIR / "social-formats.md").exists()

    def test_other_formats_exists(self):
        assert (self.REF_DIR / "other-formats.md").exists()

    @pytest.mark.parametrize("ref_file", [
        "blog-format.md",
        "tutorial-format.md",
        "social-formats.md",
        "other-formats.md",
    ])
    def test_accuracy_gate_in_all_formats(self, ref_file):
        """Every format reference must include an accuracy preservation gate."""
        text = (self.REF_DIR / ref_file).read_text()
        assert "accuracy" in text.lower(), (
            f"{ref_file} missing accuracy preservation gate"
        )

    def test_blog_has_citation_simplification(self):
        text = (self.REF_DIR / "blog-format.md").read_text()
        assert "citation simplification" in text.lower() or "simplified version" in text.lower()

    def test_blog_has_visual_placement(self):
        text = (self.REF_DIR / "blog-format.md").read_text()
        assert "visual" in text.lower() or "diagram" in text.lower() or "illustration" in text.lower()

    def test_tutorial_has_prerequisites(self):
        text = (self.REF_DIR / "tutorial-format.md").read_text()
        assert "prerequisite" in text.lower()

    def test_tutorial_has_worked_example(self):
        text = (self.REF_DIR / "tutorial-format.md").read_text()
        assert "worked example" in text.lower() or "example" in text.lower()

    def test_tutorial_has_common_pitfalls(self):
        text = (self.REF_DIR / "tutorial-format.md").read_text()
        assert "pitfall" in text.lower() or "common mistake" in text.lower()

    def test_tutorial_has_visual_placement(self):
        text = (self.REF_DIR / "tutorial-format.md").read_text()
        assert "visual" in text.lower() or "diagram" in text.lower()

    def test_social_has_twitter_format(self):
        text = (self.REF_DIR / "social-formats.md").read_text()
        assert "twitter" in text.lower() or "thread" in text.lower()
        assert "280" in text, "Twitter format should mention 280 char limit"

    def test_social_has_linkedin_format(self):
        text = (self.REF_DIR / "social-formats.md").read_text()
        assert "linkedin" in text.lower()

    def test_other_has_lay_summary(self):
        text = (self.REF_DIR / "other-formats.md").read_text()
        assert "lay summary" in text.lower()

    def test_other_has_press_release(self):
        text = (self.REF_DIR / "other-formats.md").read_text()
        assert "press release" in text.lower()

    def test_other_has_newsletter(self):
        text = (self.REF_DIR / "other-formats.md").read_text()
        assert "newsletter" in text.lower()

    def test_other_has_poster_abstract(self):
        text = (self.REF_DIR / "other-formats.md").read_text()
        assert "poster" in text.lower() or "conference" in text.lower()

    @pytest.mark.parametrize("ref_file", [
        "blog-format.md",
        "tutorial-format.md",
        "social-formats.md",
        "other-formats.md",
    ])
    def test_no_marketing_language(self, ref_file):
        """Reference files should not contain marketing terminology."""
        text = (self.REF_DIR / ref_file).read_text().lower()
        marketing_terms = [
            "brand voice", "buyer persona", "ideal customer", "sales funnel",
            "conversion rate", "call to action for sales", "lead magnet",
            "value proposition", "usp",
        ]
        for term in marketing_terms:
            assert term not in text, (
                f"{ref_file} contains marketing term: '{term}'"
            )


# ---------------------------------------------------------------------------
# sci-writing Reference Tests
# ---------------------------------------------------------------------------


class TestWritingReferences:
    """Verify sci-writing references are correct post-cleanup."""

    REF_DIR = SKILLS_DIR / "sci-writing" / "references"

    def test_section_guides_exists(self):
        assert (self.REF_DIR / "section-guides.md").exists()

    def test_academic_conventions_exists(self):
        assert (self.REF_DIR / "academic-conventions.md").exists()

    def test_review_checklist_exists(self):
        assert (self.REF_DIR / "review-checklist.md").exists()

    def test_repurpose_formats_removed(self):
        """repurpose-formats.md should be GONE — moved to sci-communication."""
        assert not (self.REF_DIR / "repurpose-formats.md").exists(), (
            "repurpose-formats.md should have been removed from sci-writing"
        )

    def test_section_guides_covers_all_sections(self):
        text = (self.REF_DIR / "section-guides.md").read_text().lower()
        for section in ["introduction", "methods", "results", "discussion", "abstract"]:
            assert section in text, f"section-guides.md missing {section}"

    def test_review_checklist_has_criteria(self):
        text = (self.REF_DIR / "review-checklist.md").read_text()
        # Should have multiple evaluation criteria
        assert text.count("##") >= 3, "Review checklist seems too sparse"


# ---------------------------------------------------------------------------
# sci-trending-research Reference Tests
# ---------------------------------------------------------------------------


class TestTrendingReferences:
    """Verify sci-trending-research references are science-framed."""

    REF_DIR = SKILLS_DIR / "sci-trending-research" / "references"

    def test_brief_template_exists(self):
        assert (self.REF_DIR / "brief-template.md").exists()

    def test_research_methodology_exists(self):
        assert (self.REF_DIR / "research-methodology.md").exists()

    def test_synthesis_guide_exists(self):
        assert (self.REF_DIR / "synthesis-guide.md").exists()

    def test_methodology_has_academic_subreddits(self):
        text = (self.REF_DIR / "research-methodology.md").read_text()
        academic_subs = ["r/science", "r/bioinformatics", "r/MachineLearning"]
        found = sum(1 for sub in academic_subs if sub in text)
        assert found >= 2, "Methodology should reference academic subreddits"

    def test_methodology_has_preprint_searches(self):
        text = (self.REF_DIR / "research-methodology.md").read_text().lower()
        assert "biorxiv" in text or "arxiv" in text

    def test_synthesis_has_research_implications(self):
        text = (self.REF_DIR / "synthesis-guide.md").read_text()
        assert "Research Implications" in text or "research implications" in text.lower()

    def test_synthesis_no_content_angles(self):
        text = (self.REF_DIR / "synthesis-guide.md").read_text()
        assert "Content Angle Extraction" not in text, (
            "Synthesis guide still has marketing 'Content Angle Extraction'"
        )

    def test_brief_template_no_content_angles(self):
        text = (self.REF_DIR / "brief-template.md").read_text()
        assert "Content Angles" not in text

    def test_brief_template_has_research_implications(self):
        text = (self.REF_DIR / "brief-template.md").read_text()
        assert "Research Implications" in text or "research implications" in text.lower()

    def test_methodology_has_science_query_types(self):
        text = (self.REF_DIR / "research-methodology.md").read_text()
        # Should use science query types, not marketing ones
        assert "BREAKTHROUGHS" in text or "METHODS" in text or "DEBATES" in text


# ---------------------------------------------------------------------------
# Viz Skill Reference Tests
# ---------------------------------------------------------------------------


class TestVizSkillsForScience:
    """Verify viz skills support scientific use cases."""

    def test_nano_banana_has_scientific_style(self):
        text = (SKILLS_DIR / "viz-nano-banana" / "SKILL.md").read_text().lower()
        assert "scientific" in text, "viz-nano-banana missing scientific style"

    def test_nano_banana_has_pathway_diagrams(self):
        text = (SKILLS_DIR / "viz-nano-banana" / "SKILL.md").read_text().lower()
        assert "pathway" in text or "cell diagram" in text or "molecular" in text

    def test_excalidraw_has_protocol_diagrams(self):
        text = (SKILLS_DIR / "viz-excalidraw-diagram" / "SKILL.md").read_text().lower()
        assert "protocol" in text or "workflow" in text
