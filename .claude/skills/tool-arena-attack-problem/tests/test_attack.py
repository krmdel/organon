"""Unit tests for arena-attack-problem skill.

Covers:
- extract_refs: arXiv ID, DOI, named-reference detection + render
- overview.render_overview: all 5 agents present / 3 of 5 / 0 of 5
- attack.run_stage: dispatch + subcommand error handling
- CLI smoke: `attack.py --help` exits 0
- Skill contract: SKILL.md frontmatter ≤ 1024 chars, body ≤ 200 lines
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPTS = SKILL_DIR / "scripts"
REPO_ROOT = SKILL_DIR.parent.parent.parent
FRAMEWORK_SRC = REPO_ROOT / "projects" / "arena-framework" / "src"

sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(FRAMEWORK_SRC))

import attack  # noqa: E402
from extract_refs import extract_references, render_references_md  # noqa: E402
from overview import render_overview  # noqa: E402

from arena_framework.hypothesis_graph import HypothesisGraph, HypothesisNode  # noqa: E402
from arena_framework.hypothesize import CouncilOutputs  # noqa: E402


# ---------------------------------------------------------------------------
# extract_refs
# ---------------------------------------------------------------------------


class TestExtractRefs:
    def test_arxiv_id_detection(self):
        problem = {"description": "See arXiv:1706.00567 and hep-th/9901001 for background."}
        refs = extract_references(problem)
        ids = {r["id"] for r in refs if r["kind"] == "arxiv"}
        assert "1706.00567" in ids
        assert "hep-th/9901001" in ids

    def test_doi_detection(self):
        problem = {"description": "See 10.1007/s00208-017-1517-3 or https://doi.org/10.1145/3531146.3533172."}
        refs = extract_references(problem)
        dois = {r["id"] for r in refs if r["kind"] == "doi"}
        assert any("10.1007/s00208-017-1517-3" in d for d in dois)
        assert any("10.1145/3531146.3533172" in d for d in dois)

    def test_named_reference_detection(self):
        problem = {"description": "Cohn and Gonçalves (2017) proved the uncertainty principle."}
        refs = extract_references(problem)
        named = [r for r in refs if r["kind"] == "named"]
        assert any("Cohn" in r["id"] for r in named)

    def test_deduplicates_across_sources(self):
        problem = {"description": "arXiv:1706.00567"}
        discussions = [{"body": "See arXiv:1706.00567 again"}]
        refs = extract_references(problem, discussions)
        arxiv_ids = [r["id"] for r in refs if r["kind"] == "arxiv"]
        assert arxiv_ids.count("1706.00567") == 1

    def test_empty_problem_no_refs(self):
        refs = extract_references({}, [])
        assert refs == []

    def test_render_references_md_with_refs(self):
        refs = [
            {"kind": "arxiv", "id": "1706.00567", "source": "problem"},
            {"kind": "doi", "id": "10.1007/x", "source": "problem"},
            {"kind": "named", "id": "Cohn 2017", "source": "discussions"},
        ]
        md = render_references_md("test-slug", refs)
        assert "# test-slug" in md
        assert "## arXiv IDs" in md
        assert "## DOIs" in md
        assert "## Named references" in md
        assert "## Hydration recipe for arena-literature-agent" in md

    def test_render_references_md_empty_has_fallback(self):
        md = render_references_md("test-slug", [])
        assert "No references auto-extracted" in md
        assert "broad WebSearch" in md

    def test_discussions_reply_blob_scanned(self):
        discussions = [
            {
                "title": "T",
                "replies": [{"content": "Please see DOI 10.1234/foobar for proof."}],
            }
        ]
        refs = extract_references({}, discussions)
        dois = [r["id"] for r in refs if r["kind"] == "doi"]
        assert any("10.1234/foobar" in d for d in dois)


# ---------------------------------------------------------------------------
# overview.render_overview
# ---------------------------------------------------------------------------


class _FakeRecon:
    def __init__(self, slug="demo", leaderboard=None, problem=None):
        self.slug = slug
        self.problem = problem or {
            "title": "Demo Problem",
            "slug": slug,
            "scoring": "minimize",
            "minImprovement": 1e-5,
            "description": "Find the smallest configuration.",
        }
        self.leaderboard = leaderboard or [
            {"agent_name": "AgentA", "score": 0.5, "submissions": 3},
            {"agent_name": "AgentB", "score": 0.6, "submissions": 2},
        ]


def _build_graph_with_nodes() -> HypothesisGraph:
    g = HypothesisGraph()
    for i, pri in enumerate([1, 3, 5, 7, 9, 11], start=1):
        g.add_node(HypothesisNode(
            id=f"H{i}",
            statement=f"Hypothesis {i}",
            kill_criterion=f"kill {i}",
            priority=pri,
            provenance=["arena-literature-agent"],
        ))
    return g


class TestOverview:
    def test_all_required_sections_present(self, tmp_path):
        ws = tmp_path / "w"
        ws.mkdir()
        (ws / "literature").mkdir()
        (ws / "recon").mkdir()

        (ws / "literature" / "LITERATURE.md").write_text(
            "# L\n## Published bounds\n| B | V |\n|---|---|\n| upper | 1.5 |\n\n"
            "## Open questions\n- Q1?\n- Q2?\n"
        )
        (ws / "recon" / "COMPETITOR_FORENSICS.md").write_text(
            "## Per-rank structural diffs\ndiff body\n\n"
            "## Methodology signals from discussions\nsig body\n"
        )
        (ws / "recon" / "APPLICABLE_PATTERNS.md").write_text(
            "## Applicable patterns (ranked)\n| Pattern | Conf |\n|---|---|\n| `k-climb` | HIGH |\n"
        )
        (ws / "recon" / "RIGOR_REPORT.md").write_text(
            "## Exploit line\nk = 15\n"
        )
        (ws / "recon" / "CRITIQUE.md").write_text(
            "## Missing hypotheses\n### Hmissing — one-line\n- **Priority:** 3\n"
        )
        outputs = CouncilOutputs.from_recon_dir(ws)
        graph = _build_graph_with_nodes()
        md = render_overview(
            workspace=ws,
            recon=_FakeRecon(),
            graph=graph,
            provenance={f"H{i}": ["arena-literature-agent"] for i in range(1, 7)},
            council_outputs=outputs,
            warnings=[],
        )

        for header in (
            "## Problem",
            "## SOTA snapshot",
            "## Published bounds",
            "## Competitor forensics",
            "## Hypothesis graph (top-5)",
            "## Proposed attack directions",
            "## Open questions",
            "## Agent coverage",
        ):
            assert header in md, f"missing required header: {header!r}"

    def test_graceful_degradation_no_agent_outputs(self, tmp_path):
        ws = tmp_path / "w"
        ws.mkdir()
        outputs = CouncilOutputs.from_recon_dir(ws)  # all None
        md = render_overview(
            workspace=ws,
            recon=_FakeRecon(),
            graph=HypothesisGraph(),
            provenance={},
            council_outputs=outputs,
            warnings=["literature agent output missing"],
        )
        assert "## Problem" in md
        assert "## Agent coverage" in md
        assert "MISSING" in md  # all 5 agents flagged missing
        assert "literature agent output missing" in md

    def test_top_five_sorted_by_priority(self, tmp_path):
        ws = tmp_path / "w"
        ws.mkdir()
        outputs = CouncilOutputs.from_recon_dir(ws)
        graph = _build_graph_with_nodes()  # 6 nodes, priorities 1..11
        md = render_overview(
            workspace=ws,
            recon=_FakeRecon(),
            graph=graph,
            provenance={},
            council_outputs=outputs,
            warnings=[],
        )
        # H1 (priority 1) should appear before H5 (priority 9) in the rendering
        idx_h1 = md.find("### H1")
        idx_h5 = md.find("### H5")
        assert 0 <= idx_h1 < idx_h5
        # H6 (priority 11) should be beyond top-5; not appear under Hypothesis graph section
        section = md.split("## Hypothesis graph (top-5)")[1].split("##")[0]
        assert "### H6" not in section


# ---------------------------------------------------------------------------
# attack.run_stage dispatch
# ---------------------------------------------------------------------------


class TestDispatch:
    def test_unknown_stage_raises(self):
        with pytest.raises(ValueError, match="unknown stage"):
            attack.run_stage("nonexistent")

    def test_hypothesize_stage_writes_draft(self, tmp_path):
        ws = tmp_path / "w"
        ws.mkdir()
        (ws / "recon").mkdir()
        (ws / "literature").mkdir()
        # Seed one literature file with an open question
        (ws / "literature" / "LITERATURE.md").write_text(
            "## Open questions\n- What is the bound?\n"
        )
        rc = attack.run_stage("hypothesize", workspace=str(ws))
        assert rc == 0
        assert (ws / "HYPOTHESES_DRAFT.md").is_file()
        assert (ws / ".phases" / "hypothesize.done").is_file()

    def test_overview_stage_requires_recon_at_minimum(self, tmp_path):
        ws = tmp_path / "w"
        ws.mkdir()
        (ws / "recon").mkdir()
        (ws / "literature").mkdir()
        rc = attack.run_stage("overview", workspace=str(ws))
        assert rc == 0
        assert (ws / "OVERVIEW.md").is_file()
        assert (ws / "HYPOTHESES.md").is_file()


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------


class TestCLI:
    def test_help_exits_zero(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "attack.py"), "--help"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0
        for sub in ("recon", "hypothesize", "overview", "attack"):
            assert sub in result.stdout

    def test_unknown_subcommand_nonzero(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "attack.py"), "nope"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode != 0


# ---------------------------------------------------------------------------
# Skill contract
# ---------------------------------------------------------------------------


class TestSkillContract:
    def test_frontmatter_under_1024_chars(self):
        skill_md = (SKILL_DIR / "SKILL.md").read_text()
        # Frontmatter is between the first two "---" markers.
        parts = skill_md.split("---", 2)
        assert len(parts) >= 3
        frontmatter = parts[1]
        assert len(frontmatter) < 1024, \
            f"frontmatter is {len(frontmatter)} chars, must be < 1024"

    def test_body_under_200_lines(self):
        skill_md = (SKILL_DIR / "SKILL.md").read_text().splitlines()
        assert len(skill_md) <= 200, f"SKILL.md is {len(skill_md)} lines, must be ≤ 200"

    def test_references_folder_nonempty(self):
        refs = SKILL_DIR / "references"
        assert refs.is_dir()
        md_files = list(refs.glob("*.md"))
        assert len(md_files) >= 1

    def test_spawn_agents_doc_covers_all_five(self):
        doc = (SKILL_DIR / "references" / "spawn-agents.md").read_text()
        for a in (
            "arena-literature-agent", "arena-historian-agent",
            "arena-pattern-scout-agent", "arena-rigor-agent",
            "arena-critic-agent",
        ):
            assert a in doc
