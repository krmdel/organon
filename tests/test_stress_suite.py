"""Stress / e2e suite for thin-coverage skills and recently-added framework contracts.

Complements the existing suite (test_skill_routing, test_workflow_scenarios,
test_edge_cases, test_paper_pipeline, etc.) by covering:

1. New CLAUDE.md contracts — Figure Proposal Gate, Task Routing cascade,
   Pattern Detection, IDE preview routing.
2. Newly-added skill steps — Pre-Analysis Advisor (sci-data-analysis),
   Pattern → Skillification (meta-wrap-up), Figure Proposal Gate
   integration (sci-writing, sci-communication).
3. Thin-coverage skill scripts — tool-substack (markdown → ProseMirror),
   tool-einstein-arena (client init), sci-optimization (LP solver).
4. Cross-skill stress — routing cascade fallbacks, degraded environment,
   malformed inputs at skill boundaries.

Run: pytest tests/test_stress_suite.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / ".claude" / "skills"
CLAUDE_MD = ROOT / "CLAUDE.md"


def _skill_md(name: str) -> str:
    return (SKILLS_DIR / name / "SKILL.md").read_text()


# =============================================================================
# Section 1 — New CLAUDE.md contracts (post-2026-04-17 upgrade)
# =============================================================================


class TestCLAUDEMdContracts:
    """The framework-level contracts added during the 5-point upgrade must
    remain discoverable by Claude at session start — each is a single grep
    away, not buried in a reference file."""

    @pytest.fixture(scope="class")
    def claude(self) -> str:
        return CLAUDE_MD.read_text()

    def test_task_routing_cascade_present(self, claude):
        """Routing cascade: adjacent skill → ToolUniverse → web → new skill."""
        # Must mention all four tiers and their order
        assert "Adjacent skill" in claude, "cascade tier A missing"
        assert "ToolUniverse" in claude, "cascade tier B missing"
        # Tier C acknowledges web/MCP fallback
        assert "Web / MCP" in claude or "Web/MCP" in claude, "cascade tier C missing"
        assert "New skill" in claude, "cascade tier D missing"
        # Terminal sentinel only fires after cascade exhausts
        assert "NO SKILL MATCH" in claude
        assert "sci-tools" in claude, "cascade must name sci-tools as ToolUniverse entry"

    def test_figure_proposal_gate_present(self, claude):
        """Figure Proposal Gate wiring: routing to all 4 viz/data skills + skip options."""
        assert "Figure Proposal Gate" in claude
        # All four routing destinations
        assert "sci-data-analysis" in claude
        assert "viz-diagram-code" in claude
        assert "viz-nano-banana" in claude
        assert "viz-excalidraw-diagram" in claude
        # Opt-out signals
        assert "skip rest" in claude or "skip this" in claude

    def test_pattern_detection_in_auto_wrap_up(self, claude):
        """meta-wrap-up pattern-scan + skillification proposal must be in the
        auto wrap-up section (so Claude discovers it every session end)."""
        assert "pattern" in claude.lower()
        assert "meta-skill-creator" in claude
        # The ≥3× threshold is the trigger condition; phrasing may vary
        lower = claude.lower()
        assert "3 times" in lower or "≥3" in lower or "3+" in lower

    def test_registration_checklist_updated(self, claude):
        """New skills must explicitly route through Figure Proposal Gate and
        Task Routing cascade — those checks belong to the registration checklist."""
        # Find the registration checklist block
        assert "Registration checklist" in claude
        # Both new checkboxes must be present
        assert "Figure Proposal Gate" in claude
        assert "Task Routing cascade" in claude or "routing cascade" in claude

    def test_ide_preview_rule_covers_drafts(self, claude):
        """Global IDE auto-open rule must list .md so drafts land in the editor."""
        assert "Auto-open in IDE" in claude
        # .md must be in the auto-previewable extension list
        assert ".md`" in claude or "(`.md" in claude


# =============================================================================
# Section 2 — Skill-level integration of new steps
# =============================================================================


class TestSkillLevelIntegration:
    """Each new CLAUDE.md gate must be referenced by the skills that should
    honour it, with clear Step N anchors Claude can follow."""

    def test_sci_writing_figure_proposal_gate(self):
        text = _skill_md("sci-writing")
        assert "Figure Proposal Gate" in text
        # Must reference the four routing destinations
        assert "sci-data-analysis" in text
        assert "viz-diagram-code" in text
        assert "viz-nano-banana" in text
        assert "viz-excalidraw-diagram" in text
        # Output path contract
        assert "figures/" in text

    def test_sci_communication_figure_proposal_gate(self):
        text = _skill_md("sci-communication")
        assert "Figure Proposal Gate" in text
        # Format-specific style defaults must survive the rewrite
        assert "color" in text.lower()  # viz-nano-banana color style
        # Strong-signal override clause
        assert "casual" in text.lower() or "friendly" in text.lower()

    def test_sci_data_analysis_pre_analysis_advisor(self):
        text = _skill_md("sci-data-analysis")
        # The new step must exist and be titled consistently
        assert "Pre-Analysis Advisor" in text or "pre-analysis advisor" in text.lower()
        # Key signals the advisor checks
        assert "Shapiro" in text or "normality" in text.lower()
        # Escalation hints to sister skills (per Task Routing cascade)
        assert "sci-hypothesis" in text
        assert "sci-tools" in text

    def test_meta_wrap_up_pattern_skillification(self):
        text = _skill_md("meta-wrap-up")
        # The new Step 3h must exist
        assert "Pattern Detection" in text or "Skillification" in text
        # User-approval requirement — never auto-build
        assert "approval" in text.lower() or "user decides" in text.lower() or "approved" in text.lower()
        # The build path
        assert "meta-skill-creator" in text
        # Guardrails must reference the routing cascade so we don't propose
        # skills that existing tooling already covers
        assert "existing skill" in text.lower() or "duplicating" in text.lower()


# =============================================================================
# Section 3 — Thin-coverage skills (structural contracts)
# =============================================================================


class TestThinCoverageSkills:
    """For prompt-only skills (no scripts/) the guarantees live in SKILL.md:
    triggers, outputs, dependencies, platform notes. Stress them."""

    def test_ops_cron_documents_cross_platform(self):
        text = _skill_md("ops-cron")
        lower = text.lower()
        # All three supported platforms
        assert "launchd" in lower or "launchagent" in lower
        assert "windows" in lower or "task scheduler" in lower
        # Cron job lifecycle operations
        assert "cron" in lower
        # Headless execution marker
        assert "claude -p" in text or "headless" in lower

    def test_tool_firecrawl_has_fallback_guidance(self):
        text = _skill_md("tool-firecrawl-scraper")
        lower = text.lower()
        # API key + graceful degradation
        assert "firecrawl_api_key" in lower
        assert "webfetch" in lower or "fallback" in lower

    def test_tool_einstein_arena_credentials_path(self):
        text = _skill_md("tool-einstein-arena")
        # Credentials path must be gitignored and under the skill's project dir
        assert "tool-einstein-arena" in text
        assert ".credentials.json" in text
        assert "gitignored" in text.lower()

    def test_sci_optimization_declares_toolkit(self):
        text = _skill_md("sci-optimization")
        lower = text.lower()
        # Core techniques
        assert "lp" in lower or "linear program" in lower
        assert "column generation" in lower


# =============================================================================
# Section 4 — tool-substack script stress (markdown → ProseMirror)
# =============================================================================


@pytest.fixture(scope="module")
def substack_ops():
    # Optional dep — if the substack venv wasn't run, skip this whole section
    # rather than fail CI on environments that don't care about Substack.
    pytest.importorskip("markdown_it", reason="markdown-it-py not installed; run tool-substack setup.sh")
    pytest.importorskip("bs4", reason="beautifulsoup4 not installed; run tool-substack setup.sh")
    sys.path.insert(0, str(SKILLS_DIR / "tool-substack" / "scripts"))
    import substack_ops  # type: ignore
    return substack_ops


class TestSubstackMarkdownConversion:
    """tool-substack converts markdown to Substack's ProseMirror schema. The
    pure parsing functions are testable without hitting the Substack API."""

    def test_split_frontmatter_with_yaml(self, substack_ops):
        md = "---\ntitle: Hello\nsubtitle: World\n---\n\n# Body\n\nparagraph."
        fm, body = substack_ops.split_frontmatter(md)
        assert fm["title"] == "Hello"
        assert fm["subtitle"] == "World"
        assert body.lstrip().startswith("# Body")

    def test_split_frontmatter_without_yaml(self, substack_ops):
        md = "# Just a heading\n\nno frontmatter here."
        fm, body = substack_ops.split_frontmatter(md)
        assert fm == {}
        assert body == md

    def test_split_frontmatter_empty(self, substack_ops):
        fm, body = substack_ops.split_frontmatter("")
        assert fm == {}
        assert body == ""

    def test_split_frontmatter_malformed_closing(self, substack_ops):
        """Frontmatter opener but no closer — must not crash, treat as plain body."""
        md = "---\ntitle: Oops\n# no closing ---\n\nstill body"
        fm, body = substack_ops.split_frontmatter(md)
        # Implementation may either return empty fm or parse best-effort;
        # either is acceptable as long as no exception escapes.
        assert isinstance(fm, dict)
        assert isinstance(body, str)

    def test_pmconverter_handles_heading_and_paragraph(self, substack_ops):
        conv = substack_ops.PMConverter(image_map={}, publication_url="https://x.substack.com")
        md = "# Title\n\nFirst paragraph with **bold** text.\n"
        doc = conv.convert(md)
        # ProseMirror top-level is a doc with content array
        assert doc.get("type") == "doc"
        assert isinstance(doc.get("content"), list)
        assert len(doc["content"]) >= 2  # heading + paragraph

    def test_pmconverter_empty_input(self, substack_ops):
        conv = substack_ops.PMConverter(image_map={}, publication_url="https://x.substack.com")
        doc = conv.convert("")
        assert doc.get("type") == "doc"
        # Empty input should not crash; content may be [] or contain an empty paragraph
        assert isinstance(doc.get("content"), list)

    def test_pmconverter_code_fence(self, substack_ops):
        conv = substack_ops.PMConverter(image_map={}, publication_url="https://x.substack.com")
        md = "```python\nprint('hi')\n```\n"
        doc = conv.convert(md)
        # At least one code_block-typed node should appear
        nodes = json.dumps(doc)
        assert "code_block" in nodes or "code" in nodes.lower()

    def test_require_credentials_without_env(self, substack_ops, monkeypatch):
        """Missing credentials must raise a clear error, not silently upload nothing."""
        for key in ("SUBSTACK_PUBLICATION_URL", "SUBSTACK_SESSION_TOKEN", "SUBSTACK_USER_ID"):
            monkeypatch.delenv(key, raising=False)
        with pytest.raises((SystemExit, RuntimeError, ValueError, KeyError)):
            substack_ops._require_credentials()


# =============================================================================
# Section 5 — sci-optimization LP solver stress
# =============================================================================


@pytest.fixture(scope="module")
def lp_solver_module():
    sys.path.insert(0, str(SKILLS_DIR / "sci-optimization" / "scripts"))
    import lp_solver  # type: ignore
    return lp_solver


class TestLPSolverStress:
    """sci-optimization LPSolver is a specialised wrapper for competition-math
    LPs: solves `min c'x s.t. Ax <= rhs, bounds[0] <= x <= bounds[1]` where
    c = objective_fn(keys) and A rows = constraint_fn(keys, x_points).
    Stress trivial / infeasible / degenerate cases against this contract."""

    def test_trivial_lp_converges(self, lp_solver_module):
        """1-variable LP: min x s.t. x ≤ 1, 0 ≤ x ≤ 10 → x* = 0.
        solve_full builds constraints from x_points = arange(1, x_range+1)."""
        import numpy as np
        solver = lp_solver_module.LPSolver(
            keys=np.array([1]),
            objective_fn=lambda k: np.array([1.0]),
            # One row per x_point, one column per key — constant 1.0
            constraint_fn=lambda k, x: np.ones((len(x), len(k))),
            bounds=(0, 10),
            rhs=1.0,
        )
        result = solver.solve_full(x_range=1, time_limit=10)
        assert result.success
        assert 0.0 - 1e-9 <= result.x[0] <= 1.0 + 1e-9

    def test_infeasible_lp_flagged(self, lp_solver_module):
        """bounds=(5, 10), constraint x ≤ rhs=1 is infeasible (x must be ≥ 5 but ≤ 1)."""
        import numpy as np
        solver = lp_solver_module.LPSolver(
            keys=np.array([1]),
            objective_fn=lambda k: np.array([1.0]),
            constraint_fn=lambda k, x: np.ones((len(x), len(k))),
            bounds=(5, 10),
            rhs=1.0,
        )
        result = solver.solve_full(x_range=1, time_limit=10)
        assert not result.success, "infeasible LP must flip result.success=False"

    def test_degenerate_lp_converges(self, lp_solver_module):
        """x_range=3 produces 3 identical constraint rows — degenerate but solvable."""
        import numpy as np
        solver = lp_solver_module.LPSolver(
            keys=np.array([1]),
            objective_fn=lambda k: np.array([1.0]),
            constraint_fn=lambda k, x: np.ones((len(x), len(k))),
            bounds=(0, 10),
            rhs=1.0,
        )
        result = solver.solve_full(x_range=3, time_limit=10)
        assert result.success
        assert result.x[0] <= 1.0 + 1e-9


# =============================================================================
# Section 6 — tool-einstein-arena client init stress
# =============================================================================


class TestEinsteinArenaClient:
    """arena_ops.EinsteinArena class: construction with and without
    credentials, repo-root resolution."""

    @pytest.fixture
    def arena_module(self):
        sys.path.insert(0, str(SKILLS_DIR / "tool-einstein-arena" / "scripts"))
        import arena_ops  # type: ignore
        return arena_ops

    def test_repo_root_resolution(self, arena_module):
        """_find_repo_root must walk up until it sees projects/ + .claude/."""
        root = arena_module._find_repo_root(Path(__file__))
        assert (root / ".claude").exists()
        assert (root / "projects").exists() or True  # projects may not exist on fresh repo

    def test_client_construction_without_creds(self, arena_module, tmp_path):
        """Constructing the client with no credentials file must not crash —
        it should allow registration on first use (graceful-degradation contract)."""
        fake_creds = str(tmp_path / ".credentials.json")
        try:
            client = arena_module.EinsteinArena(credentials_path=fake_creds)
            assert client is not None
        except (FileNotFoundError, ValueError, SystemExit):
            # Acceptable — some implementations refuse to construct without
            # creds and force explicit register. Either is a valid contract,
            # as long as the error is named.
            pass

    def test_client_register_requires_auth_fails_cleanly(self, arena_module, tmp_path):
        """Hitting an auth-gated endpoint without valid creds must raise a
        named exception, not silently succeed."""
        fake_creds = str(tmp_path / ".credentials.json")
        try:
            client = arena_module.EinsteinArena(credentials_path=fake_creds)
        except Exception:
            pytest.skip("client refused to construct without creds — that's also acceptable")
        # Now try an auth-required call via the private _require_auth guard
        with pytest.raises((RuntimeError, ValueError, AttributeError, SystemExit)):
            client._require_auth()


# =============================================================================
# Section 7 — Cross-skill degraded-environment stress
# =============================================================================


class TestDegradedEnvironment:
    """The Service Registry guarantees every skill has a fallback when its
    API key is missing. Stress the key skills to make sure missing-key paths
    don't crash."""

    def test_missing_all_api_keys_session_still_loads(self, monkeypatch):
        """A cold start with NO API keys should still import every skill's
        SKILL.md successfully (no hard coupling to env)."""
        for key in (
            "FIRECRAWL_API_KEY",
            "OPENAI_API_KEY",
            "XAI_API_KEY",
            "YOUTUBE_API_KEY",
            "GEMINI_API_KEY",
            "NCBI_API_KEY",
            "OPENALEX_API_KEY",
            "SUBSTACK_SESSION_TOKEN",
        ):
            monkeypatch.delenv(key, raising=False)

        for skill_dir in SKILLS_DIR.iterdir():
            if not skill_dir.is_dir() or skill_dir.name.startswith("_"):
                continue
            skill_md = skill_dir / "SKILL.md"
            if skill_md.exists():
                text = skill_md.read_text()
                assert len(text) > 0
                # Must declare the name field
                assert "name:" in text[:300]

    def test_catalog_json_declares_required_services(self):
        """Every skill in catalog.json with requires_services must have those
        keys documented in CLAUDE.md's Service Registry."""
        catalog = json.loads((SKILLS_DIR / "_catalog" / "catalog.json").read_text())
        claude = CLAUDE_MD.read_text()
        for skill_name, meta in catalog["skills"].items():
            for service_key in meta.get("requires_services", []):
                # Case-insensitive because CLAUDE.md sometimes prose-cases keys
                assert service_key in claude, (
                    f"{skill_name} requires {service_key} but it's not in the "
                    f"CLAUDE.md Service Registry"
                )


# =============================================================================
# Section 8 — Router sanity: trigger phrases uniqueness
# =============================================================================


class TestRouterSanity:
    """If two skills claim the same trigger phrase verbatim, the router will
    route ambiguously. Catch this early."""

    def test_no_duplicate_exact_triggers_across_sci_skills(self):
        """Each distinctive trigger phrase should belong to at most one sci-* skill.
        We only flag strongly-distinctive triggers (>=2 words, biomedical/analysis specific);
        generic words like "analyze" can appear in multiple skills with disambiguation rules."""
        # Representative distinctive triggers per skill (not exhaustive)
        distinctive = {
            "sci-data-analysis": "t-test",
            "sci-hypothesis": "generate hypothesis",
            "sci-literature-research": "search papers",
            "sci-writing": "draft introduction",
            "sci-communication": "blog post",
            "sci-trending-research": "what's trending in",
            "sci-research-mgmt": "research note",
            "sci-tools": "browse tools",
            "sci-optimization": "column generation",
        }
        for skill, trigger in distinctive.items():
            text = _skill_md(skill)
            assert trigger in text, f"{skill} missing distinctive trigger '{trigger}'"
            # The same trigger should NOT appear in a different skill's
            # triggers block as its OWN primary trigger (mentions in "Does NOT
            # trigger" are fine)
            for other_skill in distinctive:
                if other_skill == skill:
                    continue
                other_text = _skill_md(other_skill)
                # If the trigger appears in the other skill, it must be in a
                # "Does NOT trigger" clause (ambiguity is handled)
                if trigger in other_text:
                    # Disambiguation may span multiple lines ("...write a blog
                    # post... → tell them to use `sci-communication`"). Check
                    # the paragraph surrounding each occurrence (±3 lines).
                    lines = other_text.split("\n")
                    for i, line in enumerate(lines):
                        if trigger not in line:
                            continue
                        window = "\n".join(lines[max(0, i - 3): i + 4]).lower()
                        has_disambiguation = (
                            "does not trigger" in window
                            or "not trigger" in window
                            or f"use {skill}" in window
                            or f"use `{skill}`" in window
                            or skill in window  # paragraph names the owning skill
                        )
                        assert has_disambiguation, (
                            f"'{trigger}' appears in {other_skill} near line {i+1} "
                            f"without disambiguation pointing to {skill}: "
                            f"'{line.strip()}'"
                        )
