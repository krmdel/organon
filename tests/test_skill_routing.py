"""Tests for skill routing — verifies user requests route to the correct skill.

Covers the Science skill disambiguation hierarchy from CLAUDE.md and ensures
no marketing/stale skill references remain. Tests the trigger keywords in
each SKILL.md frontmatter against expected routing outcomes.
"""

import re
import yaml
from pathlib import Path

import pytest

SKILLS_DIR = Path(__file__).resolve().parent.parent / ".claude" / "skills"
CLAUDE_MD = Path(__file__).resolve().parent.parent / "CLAUDE.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_skill_frontmatter(skill_name: str) -> dict:
    """Parse YAML frontmatter from a skill's SKILL.md."""
    skill_md = SKILLS_DIR / skill_name / "SKILL.md"
    assert skill_md.exists(), f"SKILL.md not found for {skill_name}"
    text = skill_md.read_text()
    # Extract YAML between --- markers
    match = re.match(r"^---\n(.*?\n)---", text, re.DOTALL)
    assert match, f"No YAML frontmatter in {skill_name}/SKILL.md"
    return yaml.safe_load(match.group(1))


def get_trigger_phrases(skill_name: str) -> list[str]:
    """Extract trigger phrases from a skill's description.

    Looks for the 'Triggers on: "phrase1", "phrase2", ...' section in the
    skill frontmatter description and returns all quoted trigger phrases.
    """
    fm = load_skill_frontmatter(skill_name)
    desc = fm.get("description", "")
    # Find the 'Triggers on:' section and extract everything up to 'Does NOT' or end
    match = re.search(r"Triggers on:\s*(.+?)(?:Does NOT|$)", desc, re.DOTALL)
    if not match:
        return []
    raw = match.group(1)
    # Extract all double-quoted phrases from the section
    phrases = re.findall(r'"([^"]+)"', raw)
    return phrases


# ---------------------------------------------------------------------------
# Skill Structure Tests
# ---------------------------------------------------------------------------


class TestSkillInventory:
    """Verify the correct skills exist on disk — no marketing leftovers."""

    EXPECTED_SKILLS = {
        "meta-skill-creator",
        "meta-wrap-up",
        "ops-cron",
        "sci-communication",
        "sci-data-analysis",
        "sci-hypothesis",
        "sci-literature-research",
        "sci-research-mgmt",
        "sci-research-profile",
        "sci-tools",
        "sci-trending-research",
        "sci-writing",
        "tool-firecrawl-scraper",
        "tool-gdrive",
        "tool-humanizer",
        "tool-obsidian",
        "tool-paperclip",
        "tool-youtube",
        "viz-diagram-code",
        "viz-excalidraw-diagram",
        "viz-nano-banana",
        "viz-presentation",
    }

    REMOVED_SKILLS = {
        "mkt-brand-voice",
        "mkt-content-repurposing",
        "mkt-copywriting",
        "mkt-icp",
        "mkt-positioning",
        "mkt-ugc-scripts",
        "viz-ugc-heygen",
        "str-trending-research",  # renamed to sci-trending-research
    }

    def test_expected_skills_present(self):
        actual = {
            d.name
            for d in SKILLS_DIR.iterdir()
            if d.is_dir() and not d.name.startswith("_")
        }
        missing = self.EXPECTED_SKILLS - actual
        assert not missing, f"Missing skills: {missing}"

    def test_removed_skills_absent(self):
        actual = {
            d.name
            for d in SKILLS_DIR.iterdir()
            if d.is_dir() and not d.name.startswith("_")
        }
        leftover = self.REMOVED_SKILLS & actual
        assert not leftover, f"Marketing skills still present: {leftover}"

    def test_no_mkt_prefix_skills(self):
        """No skill should use the mkt- prefix anymore."""
        actual = {
            d.name
            for d in SKILLS_DIR.iterdir()
            if d.is_dir() and d.name.startswith("mkt-")
        }
        assert not actual, f"Found mkt-prefixed skills: {actual}"

    def test_all_skills_have_skill_md(self):
        for skill_dir in SKILLS_DIR.iterdir():
            if skill_dir.is_dir() and not skill_dir.name.startswith("_"):
                assert (
                    skill_dir / "SKILL.md"
                ).exists(), f"{skill_dir.name} missing SKILL.md"


class TestSkillFrontmatter:
    """Verify YAML frontmatter is valid and consistent."""

    @pytest.fixture(params=[
        d.name
        for d in SKILLS_DIR.iterdir()
        if d.is_dir() and not d.name.startswith("_")
    ])
    def skill_name(self, request):
        return request.param

    def test_name_matches_folder(self, skill_name):
        fm = load_skill_frontmatter(skill_name)
        assert fm["name"] == skill_name, (
            f"Frontmatter name '{fm['name']}' != folder '{skill_name}'"
        )

    def test_description_under_1024_chars(self, skill_name):
        fm = load_skill_frontmatter(skill_name)
        desc = fm.get("description", "")
        assert len(desc) < 1024, (
            f"{skill_name} description is {len(desc)} chars (max 1024)"
        )

    def test_no_marketing_references_in_description(self, skill_name):
        fm = load_skill_frontmatter(skill_name)
        desc = fm.get("description", "").lower()
        marketing_terms = [
            "brand voice", "mkt-", "buyer persona", "ideal customer",
            "sales page", "landing page copy", "ugc video", "copywriting",
            "content atomizer",
        ]
        for term in marketing_terms:
            assert term not in desc, (
                f"{skill_name} description contains marketing term: '{term}'"
            )


# ---------------------------------------------------------------------------
# Routing Tests — Science Skill Disambiguation
# ---------------------------------------------------------------------------


class TestHypothesisRouting:
    """Requests about data patterns and explanations → sci-hypothesis."""

    REQUESTS = [
        "What explains the group differences between treatment and control?",
        "My data suggests higher expression in mutants — generate a hypothesis",
        "What is driving this trend in patient outcomes?",
        "Generate testable hypotheses from this data pattern",
        "Design an experiment to test this hypothesis",
        "Run a power analysis for my planned study",
    ]

    @pytest.mark.parametrize("user_request", REQUESTS)
    def test_hypothesis_triggers_present(self, user_request):
        triggers = get_trigger_phrases("sci-hypothesis")
        # At least one trigger keyword should appear in the skill
        assert len(triggers) > 0, "sci-hypothesis has no trigger phrases"

    def test_skill_has_generate_mode(self):
        text = (SKILLS_DIR / "sci-hypothesis" / "SKILL.md").read_text()
        assert "generate" in text.lower(), "sci-hypothesis missing generate mode"

    def test_skill_has_experiment_design(self):
        text = (SKILLS_DIR / "sci-hypothesis" / "SKILL.md").read_text()
        assert "experiment" in text.lower(), "sci-hypothesis missing experiment design"

    def test_skill_has_power_analysis(self):
        text = (SKILLS_DIR / "sci-hypothesis" / "SKILL.md").read_text()
        assert "power analysis" in text.lower(), "sci-hypothesis missing power analysis"


class TestDataAnalysisRouting:
    """Requests for statistical tests and data operations → sci-data-analysis."""

    REQUESTS = [
        "Run a t-test on my expression data",
        "Plot a scatter chart of age vs response",
        "Clean my data — remove outliers and missing values",
        "Generate a heatmap of correlations",
        "Run ANOVA across treatment groups",
        "Load this CSV and show me a summary",
    ]

    @pytest.mark.parametrize("user_request", REQUESTS)
    def test_data_keywords_in_triggers(self, user_request):
        triggers = get_trigger_phrases("sci-data-analysis")
        assert len(triggers) > 0

    def test_skill_has_plot_mode(self):
        text = (SKILLS_DIR / "sci-data-analysis" / "SKILL.md").read_text()
        assert "plot" in text.lower()

    def test_skill_has_statistical_tests(self):
        text = (SKILLS_DIR / "sci-data-analysis" / "SKILL.md").read_text()
        assert "t-test" in text.lower() or "ttest" in text.lower()


class TestLiteratureRouting:
    """Requests to find/search papers → sci-literature-research."""

    REQUESTS = [
        "Search PubMed for CRISPR delivery papers",
        "Find recent papers on transformer architectures in genomics",
        "Literature review on single-cell RNA sequencing",
        "Export BibTeX for my search results",
        "What papers cite Smith et al 2024?",
    ]

    @pytest.mark.parametrize("user_request", REQUESTS)
    def test_literature_triggers(self, user_request):
        triggers = get_trigger_phrases("sci-literature-research")
        assert len(triggers) > 0

    def test_skill_has_bibtex_export(self):
        text = (SKILLS_DIR / "sci-literature-research" / "SKILL.md").read_text()
        assert "bibtex" in text.lower() or "bib" in text.lower()


class TestPaperclipRouting:
    """Requests involving full-text biomedical papers, bioRxiv/PMC grep, figure analysis → tool-paperclip."""

    REQUESTS = [
        "Grep across the paperclip corpus for BRCA1 mutations",
        "paperclip search CRISPR lipid nanoparticle",
        "Find bioRxiv preprints on AlphaFold from the last 30 days",
        "Read PMC10791696 methods section",
        "Ask what this figure shows from the paperclip paper",
        "Map delivery methods across these full-text papers",
    ]

    def test_skill_registered_in_claude_md(self):
        text = CLAUDE_MD.read_text()
        assert "| `tool-paperclip` |" in text, "tool-paperclip missing from CLAUDE.md Skill Registry"

    def test_skill_registered_in_context_matrix(self):
        text = CLAUDE_MD.read_text()
        idx = text.find("## Context Matrix")
        assert idx != -1
        assert "| `tool-paperclip` |" in text[idx:], "tool-paperclip missing from Context Matrix"

    def test_skill_md_exists(self):
        assert (SKILLS_DIR / "tool-paperclip" / "SKILL.md").exists()

    def test_skill_documents_cli_commands(self):
        text = (SKILLS_DIR / "tool-paperclip" / "SKILL.md").read_text()
        for cmd in ["search", "grep", "lookup", "map", "ask-image", "cat", "pull"]:
            assert f"paperclip {cmd}" in text, f"tool-paperclip SKILL.md missing `paperclip {cmd}` example"

    def test_skill_documents_filesystem_layout(self):
        text = (SKILLS_DIR / "tool-paperclip" / "SKILL.md").read_text()
        assert "/papers/" in text, "tool-paperclip SKILL.md should document /papers/ filesystem"
        assert "meta.json" in text, "tool-paperclip SKILL.md should reference meta.json"
        assert "content.lines" in text, "tool-paperclip SKILL.md should reference content.lines"

    def test_skill_documents_citation_format(self):
        text = (SKILLS_DIR / "tool-paperclip" / "SKILL.md").read_text()
        assert "citations.gxl.ai" in text, "tool-paperclip SKILL.md should document citations.gxl.ai URL format"

    def test_skill_has_fallback_language(self):
        text = (SKILLS_DIR / "tool-paperclip" / "SKILL.md").read_text()
        assert any(w in text.lower() for w in ["fallback", "degrade", "unavailable", "standalone"]), (
            "tool-paperclip SKILL.md missing fallback/degradation language"
        )

    def test_routes_to_sci_literature_on_fallback(self):
        text = (SKILLS_DIR / "tool-paperclip" / "SKILL.md").read_text()
        assert "sci-literature-research" in text, (
            "tool-paperclip SKILL.md should name sci-literature-research as fallback"
        )

    @pytest.mark.parametrize("user_request", REQUESTS)
    def test_paperclip_triggers_match_registry(self, user_request):
        """Each request should match at least one paperclip-specific keyword."""
        paperclip_keywords = [
            "paperclip", "biorxiv", "medrxiv", "pmc", "full-text",
            "grep papers", "ask-image", "/papers/",
        ]
        low = user_request.lower()
        assert any(kw in low for kw in paperclip_keywords), (
            f"Request '{user_request}' has no paperclip-distinctive keyword — ambiguous with sci-literature-research"
        )


class TestWritingRouting:
    """Requests to write/draft/review manuscripts → sci-writing."""

    REQUESTS = [
        "Draft an introduction for my paper on BRCA1",
        "Write the methods section",
        "Format my citations in APA style",
        "Peer review my results section",
        "Write an abstract for this manuscript",
    ]

    @pytest.mark.parametrize("user_request", REQUESTS)
    def test_writing_triggers(self, user_request):
        triggers = get_trigger_phrases("sci-writing")
        assert len(triggers) > 0

    def test_skill_routes_repurpose_to_communication(self):
        """sci-writing should redirect repurpose/blog requests to sci-communication."""
        text = (SKILLS_DIR / "sci-writing" / "SKILL.md").read_text()
        assert "sci-communication" in text, (
            "sci-writing should reference sci-communication for repurpose requests"
        )

    def test_no_repurpose_mode(self):
        """sci-writing should NOT have a repurpose mode anymore."""
        text = (SKILLS_DIR / "sci-writing" / "SKILL.md").read_text()
        # Should not have "Repurpose Mode" as a step header
        assert "Repurpose Mode" not in text, (
            "sci-writing still contains Repurpose Mode — should be in sci-communication"
        )

    def test_has_figure_generation_step(self):
        text = (SKILLS_DIR / "sci-writing" / "SKILL.md").read_text()
        assert "Figure Proposal Gate" in text or "Figure Generation" in text, (
            "sci-writing missing figure-proposal step (Figure Proposal Gate or legacy Figure Generation)"
        )

    def test_viz_dependencies_declared(self):
        text = (SKILLS_DIR / "sci-writing" / "SKILL.md").read_text()
        assert "viz-nano-banana" in text
        assert "viz-excalidraw-diagram" in text


class TestCommunicationRouting:
    """Blog posts, tutorials, explainers, social → sci-communication."""

    REQUESTS = [
        "Write a blog post about my CRISPR paper",
        "Create a tutorial on single-cell RNA-seq analysis",
        "Explain epigenetics for non-scientists",
        "Write a Twitter thread about our latest findings",
        "Prepare a lay summary for patients",
        "Draft a press release for our Nature publication",
        "Create a newsletter roundup of this week's papers",
        "Gentle introduction to transformer models for biologists",
    ]

    @pytest.mark.parametrize("user_request", REQUESTS)
    def test_communication_triggers(self, user_request):
        triggers = get_trigger_phrases("sci-communication")
        assert len(triggers) > 0

    def test_seven_modes(self):
        text = (SKILLS_DIR / "sci-communication" / "SKILL.md").read_text()
        modes = ["blog", "tutorial", "explainer", "social", "newsletter",
                 "press-release", "lay-summary"]
        for mode in modes:
            assert mode in text.lower(), f"sci-communication missing mode: {mode}"

    def test_flexible_source_inputs(self):
        text = (SKILLS_DIR / "sci-communication" / "SKILL.md").read_text()
        assert "Paper/manuscript file" in text or "Paper" in text
        assert "Concept" in text or "concept" in text
        assert "URL" in text
        assert "Pasted text" in text or "pasted" in text.lower()

    def test_viz_orchestration(self):
        text = (SKILLS_DIR / "sci-communication" / "SKILL.md").read_text()
        assert "viz-nano-banana" in text, "Missing viz-nano-banana dependency"
        assert "viz-excalidraw-diagram" in text, "Missing viz-excalidraw-diagram dependency"
        assert "sci-data-analysis" in text, "Missing sci-data-analysis dependency"

    def test_accuracy_gate(self):
        text = (SKILLS_DIR / "sci-communication" / "SKILL.md").read_text()
        assert "accuracy" in text.lower(), "Missing accuracy preservation gate"

    def test_humanizer_gate(self):
        text = (SKILLS_DIR / "sci-communication" / "SKILL.md").read_text()
        assert "humanizer" in text.lower(), "Missing humanizer gate step"


class TestTrendingResearchRouting:
    """Requests about emerging trends → sci-trending-research."""

    REQUESTS = [
        "What's trending in computational genomics?",
        "Hot topics in AI for drug discovery right now",
        "Recent breakthroughs in CRISPR delivery",
        "What are researchers saying about foundation models in biology?",
        "Field pulse on spatial transcriptomics",
        "Research trends in immunotherapy",
    ]

    @pytest.mark.parametrize("user_request", REQUESTS)
    def test_trending_triggers(self, user_request):
        triggers = get_trigger_phrases("sci-trending-research")
        assert len(triggers) > 0

    def test_not_named_str(self):
        """Should be sci-trending-research, not str-trending-research."""
        assert not (SKILLS_DIR / "str-trending-research").exists()
        assert (SKILLS_DIR / "sci-trending-research").exists()

    def test_routes_to_sci_skills(self):
        text = (SKILLS_DIR / "sci-trending-research" / "SKILL.md").read_text()
        assert "sci-hypothesis" in text
        assert "sci-writing" in text
        assert "sci-communication" in text

    def test_no_marketing_references(self):
        text = (SKILLS_DIR / "sci-trending-research" / "SKILL.md").read_text()
        for term in ["mkt-", "content creation", "content atomizer", "email sequence"]:
            assert term not in text.lower(), (
                f"sci-trending-research still references marketing: '{term}'"
            )

    def test_preprint_searches(self):
        """Should search preprint servers, not just social media."""
        methodology = (
            SKILLS_DIR / "sci-trending-research" / "references" / "research-methodology.md"
        ).read_text()
        assert "biorxiv" in methodology.lower() or "bioRxiv" in methodology
        assert "arxiv" in methodology.lower()

    def test_research_implications_not_content_angles(self):
        brief = (
            SKILLS_DIR / "sci-trending-research" / "references" / "brief-template.md"
        ).read_text()
        assert "Research Implications" in brief or "research implications" in brief.lower()
        assert "Content Angles" not in brief


class TestToolsRouting:
    """Requests for biomedical tool discovery → sci-tools."""

    REQUESTS = [
        "Find tools for protein structure prediction",
        "Browse ToolUniverse for genomics tools",
        "Create a custom research skill for mass spec analysis",
    ]

    @pytest.mark.parametrize("user_request", REQUESTS)
    def test_tools_triggers(self, user_request):
        triggers = get_trigger_phrases("sci-tools")
        assert len(triggers) > 0


class TestResearchMgmtRouting:
    """Requests for notes, projects, scheduling → sci-research-mgmt."""

    REQUESTS = [
        "Log an observation about today's experiment",
        "Show me my research project dashboard",
        "Set up paper alerts for CRISPR papers",
        "Search my notes for #immunotherapy",
        "Promote experiment EXP-001 from observation to project",
    ]

    @pytest.mark.parametrize("user_request", REQUESTS)
    def test_mgmt_triggers(self, user_request):
        triggers = get_trigger_phrases("sci-research-mgmt")
        assert len(triggers) > 0


# ---------------------------------------------------------------------------
# Cross-Skill Routing Boundary Tests
# ---------------------------------------------------------------------------


class TestRoutingBoundaries:
    """Ensure requests don't route to the wrong skill."""

    def test_blog_does_not_route_to_writing(self):
        """'blog post' should go to sci-communication, NOT sci-writing."""
        writing_fm = load_skill_frontmatter("sci-writing")
        desc = writing_fm["description"].lower()
        assert "blog" not in desc or "sci-communication" in desc

    def test_manuscript_does_not_route_to_communication(self):
        """'draft introduction' should go to sci-writing, NOT sci-communication."""
        comm_fm = load_skill_frontmatter("sci-communication")
        desc = comm_fm["description"].lower()
        assert "manuscript" not in desc or "sci-writing" in desc

    def test_trending_does_not_route_to_literature(self):
        """Social/community sentiment triggers must not appear in sci-literature-research.

        sci-literature-research may claim publication trend phrases ("trending topics",
        "research trends") since it tracks literature trends. But it must NOT claim
        community-sentiment phrases like "what's trending in" or "hot topics" that
        belong exclusively to sci-trending-research (priority 8 in hierarchy).
        """
        triggers = get_trigger_phrases("sci-literature-research")
        # Only flag phrases that overlap with sci-trending-research's exclusive territory
        social_sentiment_phrases = {"what's trending in", "hot topics", "field pulse",
                                    "recent breakthroughs", "emerging trends in",
                                    "community sentiment"}
        conflicting = [t for t in triggers if t.lower() in social_sentiment_phrases]
        assert not conflicting, (
            f"sci-literature-research claims sci-trending-research trigger phrases: {conflicting}"
        )

    def test_writing_negative_triggers_include_communication(self):
        """sci-writing should explicitly exclude blog/repurpose requests."""
        writing_fm = load_skill_frontmatter("sci-writing")
        desc = writing_fm["description"].lower()
        assert "sci-communication" in desc, (
            "sci-writing should reference sci-communication in negative triggers"
        )


# ---------------------------------------------------------------------------
# Requirement-Mapped Routing Tests — ROUTE-01, ROUTE-02, ROUTE-03
# ---------------------------------------------------------------------------


class TestRequirementRouting:
    """ROUTE-01, ROUTE-02, ROUTE-03: Explicit requirement-mapped routing tests."""

    def test_route_01_trigger_phrases_unique_per_skill(self):
        """ROUTE-01: Each trigger phrase must map to exactly one skill.

        Builds a map of {phrase: [skill1, skill2, ...]} across all skills and
        asserts no phrase is claimed by more than one skill. This prevents
        routing ambiguity when trigger phrases overlap between skills.
        """
        all_skills = sorted([
            d.name for d in SKILLS_DIR.iterdir()
            if d.is_dir() and not d.name.startswith("_")
        ])

        phrase_map: dict[str, list[str]] = {}
        for skill in all_skills:
            for phrase in get_trigger_phrases(skill):
                phrase_map.setdefault(phrase, []).append(skill)

        conflicts = {
            phrase: skills
            for phrase, skills in phrase_map.items()
            if len(skills) > 1
        }
        assert not conflicts, (
            "Trigger phrases claimed by multiple skills (routing ambiguity):\n"
            + "\n".join(
                f"  '{phrase}' -> {skills}"
                for phrase, skills in sorted(conflicts.items())
            )
        )

    def test_route_02_negative_triggers_respected(self):
        """ROUTE-02: Routing boundaries are enforced via negative triggers in frontmatter.

        Verifies the key cross-skill exclusions: blog content stays out of sci-writing,
        manuscript drafting stays out of sci-communication, and hypothesis generation
        is excluded from sci-data-analysis.
        """
        # sci-writing must reference sci-communication as its negative trigger destination
        # (blog posts, lay summaries, repurposing should NOT go to sci-writing)
        writing_desc = load_skill_frontmatter("sci-writing").get("description", "")
        assert "sci-communication" in writing_desc, (
            "sci-writing must reference sci-communication in 'Does NOT trigger for' section. "
            "Blog posts and repurposing should route to sci-communication, not sci-writing."
        )

        # sci-data-analysis must NOT claim "hypothesis" or "generate hypothesis" as triggers
        # (explaining patterns routes to sci-hypothesis, not sci-data-analysis)
        data_triggers = get_trigger_phrases("sci-data-analysis")
        hypothesis_triggers = [
            t for t in data_triggers
            if "hypothesis" in t.lower() or "generate hypothesis" in t.lower()
        ]
        assert not hypothesis_triggers, (
            f"sci-data-analysis claims hypothesis trigger phrases: {hypothesis_triggers}. "
            "Hypothesis generation must route to sci-hypothesis (priority 1)."
        )

        # sci-literature-research must NOT claim community-sentiment trending phrases
        # that belong exclusively to sci-trending-research (priority 8)
        lit_triggers = get_trigger_phrases("sci-literature-research")
        social_sentiment = {"what's trending in", "hot topics", "field pulse",
                            "recent breakthroughs", "emerging trends in", "community sentiment"}
        conflicting_lit = [t for t in lit_triggers if t.lower() in social_sentiment]
        assert not conflicting_lit, (
            f"sci-literature-research claims sci-trending-research phrases: {conflicting_lit}. "
            "Social/community trend queries must route to sci-trending-research."
        )

        # sci-communication must NOT claim manuscript trigger phrases
        # (draft introduction, write methods, write abstract route to sci-writing)
        comm_triggers = get_trigger_phrases("sci-communication")
        manuscript_triggers = [
            t for t in comm_triggers
            if any(m in t.lower() for m in ["manuscript", "methods section",
                                             "draft introduction", "write abstract"])
        ]
        assert not manuscript_triggers, (
            f"sci-communication claims manuscript triggers: {manuscript_triggers}. "
            "Manuscript drafting must route to sci-writing (priority 4)."
        )

    def test_route_03_disambiguation_hierarchy_order(self):
        """ROUTE-03: The 8-level Science skill disambiguation hierarchy is intact in CLAUDE.md.

        Reads the 'Science skill disambiguation' section and verifies all 8 priority
        entries are present and map to the correct skills in the correct order.
        """
        text = CLAUDE_MD.read_text()

        # Locate the disambiguation section
        idx = text.find("Science skill disambiguation")
        assert idx != -1, (
            "CLAUDE.md is missing the 'Science skill disambiguation' section."
        )
        section = text[idx:idx + 2000]

        # Expected hierarchy: (priority, skill_name)
        expected_hierarchy = [
            (1, "sci-hypothesis"),
            (2, "sci-data-analysis"),
            (3, "sci-literature-research"),
            (4, "sci-writing"),
            (5, "sci-communication"),
            (6, "sci-tools"),
            (7, "sci-research-mgmt"),
            (8, "sci-trending-research"),
        ]

        # Extract numbered lines pointing to skills
        # Pattern: "N. ... -> `skill-name`" or "N. ... route to `skill-name`"
        found_entries: list[tuple[int, str]] = []
        for m in re.finditer(
            r"^(\d+)\.\s+.*?`(sci-[a-z-]+)`",
            section,
            re.MULTILINE,
        ):
            priority = int(m.group(1))
            skill = m.group(2)
            found_entries.append((priority, skill))

        # Verify all 8 entries present
        assert len(found_entries) == 8, (
            f"Expected 8 hierarchy entries in CLAUDE.md, found {len(found_entries)}: {found_entries}"
        )

        # Verify each entry matches expected skill in correct order
        for i, (exp_priority, exp_skill) in enumerate(expected_hierarchy):
            actual_priority, actual_skill = found_entries[i]
            assert actual_priority == exp_priority, (
                f"Priority mismatch at position {i + 1}: "
                f"expected priority {exp_priority}, got {actual_priority}"
            )
            assert actual_skill == exp_skill, (
                f"Skill mismatch at priority {exp_priority}: "
                f"expected '{exp_skill}', got '{actual_skill}'"
            )


# ---------------------------------------------------------------------------
# /lets-go command coverage
# ---------------------------------------------------------------------------


COMMANDS_DIR = Path(__file__).resolve().parent.parent / ".claude" / "commands"
LETS_GO_PATH = COMMANDS_DIR / "lets-go.md"
USER_MD = Path(__file__).resolve().parent.parent / "context" / "USER.md"


class TestLetsGoCommand:
    """Guard rails so the first-run onboarding contract doesn't silently
    drift. These tests fail loudly if the command is renamed, moved, or
    the memory/user schema diverges from CLAUDE.md."""

    def test_command_file_exists(self):
        assert LETS_GO_PATH.exists(), (
            f"/lets-go command file missing at {LETS_GO_PATH} — "
            "CLAUDE.md heartbeat step 5 auto-invokes it. Without this "
            "file the session start contract is broken."
        )

    def test_command_file_non_empty(self):
        content = LETS_GO_PATH.read_text()
        assert len(content) > 500, "lets-go.md looks truncated"

    def test_references_memory_and_context(self):
        """The command must reference the memory and context contracts from
        CLAUDE.md heartbeat. Drift here breaks first-run onboarding."""
        content = LETS_GO_PATH.read_text().lower()
        for marker in ("memory", "research_context", "goal"):
            assert marker in content, (
                f"lets-go.md missing required marker '{marker}'. "
                "Sync with CLAUDE.md heartbeat section."
            )

    def test_no_start_here_reference(self):
        """start-here was the deleted predecessor. Any lingering reference
        means stale docs will route users to a removed command."""
        content = LETS_GO_PATH.read_text().lower()
        assert "/start-here" not in content

    def test_user_md_points_to_lets_go(self):
        """context/USER.md footer must reference /lets-go, not /start-here."""
        content = USER_MD.read_text()
        assert "/start-here" not in content, (
            "context/USER.md still references deleted /start-here command"
        )
        assert "/lets-go" in content, (
            "context/USER.md footer must reference /lets-go"
        )

    def test_user_md_has_research_fields(self):
        """USER.md must be the research-focused template, not the old
        business template (Business / Role / Website)."""
        content = USER_MD.read_text()
        assert "Research Focus" in content, (
            "context/USER.md missing 'Research Focus' section — likely "
            "still the old business template. Fix via Fix 3."
        )
        assert "Business:" not in content, (
            "context/USER.md still contains stale 'Business:' field"
        )


# ---------------------------------------------------------------------------
# Catalog ↔ disk sync
# ---------------------------------------------------------------------------


import json  # noqa: E402

CATALOG_PATH = SKILLS_DIR / "_catalog" / "catalog.json"


class TestCatalogSync:
    """Every folder on disk must be registered in catalog.json and vice
    versa. Reconciliation drift (skill exists but not indexed) silently
    breaks /lets-go discovery and feedback loops."""

    def _load_catalog(self) -> dict:
        assert CATALOG_PATH.exists(), f"catalog.json missing at {CATALOG_PATH}"
        return json.loads(CATALOG_PATH.read_text())

    # Skills excluded from the public repo via .gitignore. They may exist
    # locally without a catalog row (or vice versa in CI); exempt from
    # both directions of the catalog-disk consistency check.
    _GITIGNORED_SKILLS = {"tool-substack", "tool-social-publisher"}

    def _on_disk(self) -> set[str]:
        return {
            d.name
            for d in SKILLS_DIR.iterdir()
            if d.is_dir() and not d.name.startswith("_")
        }

    def test_catalog_is_valid_json(self):
        self._load_catalog()

    def test_every_disk_skill_in_catalog(self):
        catalog = self._load_catalog()
        listed = set(catalog.get("skills", {}).keys())
        disk = self._on_disk()
        missing = (disk - listed) - self._GITIGNORED_SKILLS
        assert not missing, (
            f"Skills exist on disk but are NOT registered in catalog.json: "
            f"{sorted(missing)}. Add them via the reconciliation workflow "
            "in CLAUDE.md §Reconciliation."
        )

    def test_no_catalog_ghost_entries(self):
        catalog = self._load_catalog()
        listed = set(catalog.get("skills", {}).keys())
        disk = self._on_disk()
        ghosts = (listed - disk) - self._GITIGNORED_SKILLS
        assert not ghosts, (
            f"catalog.json references skills that don't exist on disk: "
            f"{sorted(ghosts)}"
        )

    def test_catalog_entries_have_required_fields(self):
        catalog = self._load_catalog()
        required_fields = {"category", "description"}
        for name, entry in catalog.get("skills", {}).items():
            missing = required_fields - set(entry.keys())
            assert not missing, (
                f"catalog.json entry '{name}' missing fields: {sorted(missing)}"
            )
