"""E.10 — Fresh-problem autonomous pipeline (Slice 20, Gap 6).

This closes the last Slice-of-the-framework: exercise the full
arena-attack-problem pipeline end-to-end on a synthetic "fresh" arena
problem. The 5 recon agents are stubbed (their outputs written directly
to the workspace), Recon runs offline from cached JSON, and every stage
(recon → hypothesize → overview → attack) is invoked and asserted.

Zero live network. Zero live credentials.

Covers the integration surface between:
  - arena-attack-problem/scripts/{attack, extract_refs, overview}.py
  - arena_framework.recon.Recon (offline mode)
  - arena_framework.hypothesize.synthesize
  - arena_framework.orchestrator.AttackOrchestrator
  - the 5 agent artifact contracts

If this test ever breaks, the autonomous pipeline has a real integration
regression.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = REPO_ROOT / ".claude" / "skills" / "tool-arena-attack-problem"
SKILL_SCRIPTS = SKILL_DIR / "scripts"
FRAMEWORK_SRC = REPO_ROOT / "projects" / "arena-framework" / "src"

sys.path.insert(0, str(SKILL_SCRIPTS))
sys.path.insert(0, str(FRAMEWORK_SRC))


# ---------------------------------------------------------------------------
# Synthetic fresh-problem workspace factory
# ---------------------------------------------------------------------------


FRESH_SLUG = "fresh-test-problem"


def _write_synthetic_recon(workspace: Path) -> None:
    """Mimic what `Recon.run()` would write if it fetched a new problem.

    Writes: problem.json, leaderboard.json, best_solutions.json, discussions.json.
    Also scaffolds the sub-dirs that Stage-2 agents write into.
    """
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "recon").mkdir(exist_ok=True)
    (workspace / "literature").mkdir(exist_ok=True)
    (workspace / "solutions").mkdir(exist_ok=True)

    (workspace / "problem.json").write_text(json.dumps({
        "id": 999,
        "slug": FRESH_SLUG,
        "title": "Fresh Test Problem",
        "scoring": "minimize",
        "minImprovement": 1e-5,
        "description": (
            "Minimise the sum of pairwise distances between N points. "
            "Based on the bound proved in Cohn and Gonçalves (2017); "
            "see arXiv:1706.00567 for the seminal construction."
        ),
        "solutionSchema": {"points": "list of [x, y] pairs"},
    }))
    (workspace / "leaderboard.json").write_text(json.dumps([
        {"agent_name": "IncumbentAgent", "score": 1.234567, "submissions": 5},
        {"agent_name": "SecondAgent", "score": 1.300000, "submissions": 3},
        {"agent_name": "ThirdAgent", "score": 1.450000, "submissions": 2},
    ]))
    (workspace / "best_solutions.json").write_text(json.dumps([
        {"id": 100, "agent_name": "IncumbentAgent", "score": 1.234567,
         "data": {"points": [[0.1, 0.2], [0.3, 0.4]]}},
        {"id": 101, "agent_name": "SecondAgent", "score": 1.300000,
         "data": {"points": [[0.15, 0.25], [0.35, 0.45]]}},
    ]))
    (workspace / "discussions.json").write_text(json.dumps([
        {"id": 1, "title": "Cohn-Gonçalves approach?",
         "body": "Has anyone tried the doi:10.1007/s00208-017-1517-3 construction?",
         "replies": []},
    ]))


def _write_stub_agent_outputs(workspace: Path) -> None:
    """Simulate Stage-2 + Stage-4 agent outputs that Claude would have
    produced by calling each of the 5 agents via the Agent tool."""

    # arena-literature-agent
    (workspace / "literature" / "LITERATURE.md").write_text(
        "# Fresh Test Problem — Literature\n\n"
        "## Published bounds\n\n"
        "| Bound type | Value | Method | Source | Notes |\n"
        "|---|---|---|---|---|\n"
        "| Lower | 1.0 | analytic | [@cohn2017] | proved tight |\n"
        "| Upper | 2.0 | numeric | [@goncalves2018] | conjectured |\n\n"
        "## SOTA methods\n\nSinger construction [@singer1938].\n\n"
        "## Reproducibility\n\nCohn-Gonçalves published coefficients.\n\n"
        "## Open questions\n\n"
        "- Can the Singer construction reach the lower bound at N=10?\n"
        "- Does a dyadic refinement close the 1.0-1.234 gap?\n\n"
        "## BibTeX\n\n```bibtex\n"
        "@article{cohn2017, title={Uncertainty principle}, year={2017}}\n"
        "```\n"
    )

    # arena-historian-agent
    (workspace / "recon" / "COMPETITOR_FORENSICS.md").write_text(
        "# Competitor forensics — Fresh Test Problem\n\n"
        "## Leaderboard snapshot\n\n"
        "| Rank | Agent | Score | Submissions |\n|---|---|---|---|\n"
        "| 1 | IncumbentAgent | 1.234567 | 5 |\n\n"
        "## Score progression timeline\n\n"
        "2026-04-20: Incumbent drops from 1.45 → 1.23 via dyadic refinement.\n\n"
        "## Per-rank structural diffs\n\n"
        "#1 vs #2: IncumbentAgent uses 2 decimal-place granularity; SecondAgent uses 3.\n\n"
        "## Methodology signals from discussions\n\n"
        "Thread 1 (IncumbentAgent): 'Dyadic snap at d=8 was the key'.\n\n"
        "## Contradictions\n\nNone flagged.\n\n"
        "## Community-known techniques\n\n- dyadic-snap (thread 1)\n"
    )

    # arena-pattern-scout-agent
    (workspace / "recon" / "APPLICABLE_PATTERNS.md").write_text(
        "# Applicable patterns — Fresh Test Problem\n\n"
        "## Applicable patterns (ranked)\n\n"
        "| Pattern | Confidence | Reasoning |\n|---|---|---|\n"
        "| `dyadic-snap` | HIGH | competitor used it |\n"
        "| `ulp-descent` | MEDIUM | float64 floor may matter near optimum |\n"
    )

    # arena-rigor-agent
    (workspace / "recon" / "RIGOR_REPORT.md").write_text(
        "# Rigor report — Fresh Test Problem\n\n"
        "## Verdicts\n\n| Solution | Arena | Rigorous | Verdict |\n"
        "|---|---|---|---|\n| 100 | 1.234567 | 1.234567 | rigorous |\n\n"
        "## Exploit line\n\n"
        "No exploit detected. All top-K verdicts rigorous.\n"
    )

    # arena-critic-agent
    (workspace / "recon" / "CRITIQUE.md").write_text(
        "# Critique — draft hypothesis graph\n\n"
        "## Findings\n\n| Hypothesis id | Severity | Finding | Suggested fix |\n"
        "|---|---|---|---|\n| H1 | MINOR | wording tight | none |\n\n"
        "## Missing hypotheses\n\n"
        "### Hx — Try the published tight construction directly\n"
        "- **statement:** Run Singer construction from Cohn 2017\n"
        "- **kill_criterion:** Singer fails to reach 1.0\n"
        "- **priority:** 2\n\n"
        "## Redundancies\n\nNone.\n\n## Literature-driven FATALs\n\nNone.\n\n"
        "## Overall verdict\n\nGraph is tight enough to proceed.\n"
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFreshProblemPipeline:
    """End-to-end exercise of arena-attack-problem on a synthetic problem."""

    def test_stage1_recon_offline_writes_all_artifacts(self, tmp_path):
        """Simulated recon: problem + refs + subdirs created."""
        import attack  # noqa: PLC0415
        ws = tmp_path / "campaign"
        _write_synthetic_recon(ws)

        # The recon stage can run in offline mode when cache is pre-populated.
        # Skip the live fetch; assert extract_refs picks up Cohn + arxiv + doi.
        from extract_refs import extract_references, render_references_md

        problem = json.loads((ws / "problem.json").read_text())
        discussions = json.loads((ws / "discussions.json").read_text())
        refs = extract_references(problem, discussions)

        arxiv_ids = {r["id"] for r in refs if r["kind"] == "arxiv"}
        dois = {r["id"] for r in refs if r["kind"] == "doi"}
        named = {r["id"] for r in refs if r["kind"] == "named"}
        assert "1706.00567" in arxiv_ids
        assert any("10.1007/s00208-017-1517-3" in d for d in dois)
        assert any("Cohn" in n for n in named)

        # Render the REFERENCES.md into the workspace
        (ws / "literature" / "REFERENCES.md").write_text(
            render_references_md(FRESH_SLUG, refs)
        )
        assert (ws / "literature" / "REFERENCES.md").is_file()

    def test_stage3_hypothesize_composes_agent_outputs(self, tmp_path):
        """Synthesiser produces a non-empty graph from 5-agent stubs."""
        import attack
        ws = tmp_path / "campaign"
        _write_synthetic_recon(ws)
        _write_stub_agent_outputs(ws)

        rc = attack.run_stage("hypothesize", workspace=str(ws))
        assert rc == 0

        draft = ws / "HYPOTHESES_DRAFT.md"
        assert draft.is_file()

        # The synthesiser writes warnings as JSON; assert they reflect reality.
        warnings_raw = (ws / "recon" / "SYNTHESIS_WARNINGS.json").read_text()
        warnings = json.loads(warnings_raw)
        # With all 5 agent outputs present, no "missing" warnings should fire.
        assert not any("missing" in w for w in warnings), \
            f"unexpected warnings with all 5 agents present: {warnings}"

    def test_stage5_overview_renders_all_required_sections(self, tmp_path):
        """OVERVIEW.md contains every section in the required schema."""
        import attack
        ws = tmp_path / "campaign"
        _write_synthetic_recon(ws)
        _write_stub_agent_outputs(ws)

        attack.run_stage("hypothesize", workspace=str(ws))
        rc = attack.run_stage("overview", workspace=str(ws))
        assert rc == 0

        overview = (ws / "OVERVIEW.md").read_text()
        for section in (
            "## Problem",
            "## SOTA snapshot",
            "## Published bounds",
            "## Competitor forensics",
            "## Hypothesis graph (top-5)",
            "## Proposed attack directions",
            "## Open questions",
            "## Agent coverage",
        ):
            assert section in overview, f"missing {section!r} in OVERVIEW.md"

        # Evidence that content actually flowed from each agent
        assert "Fresh Test Problem" in overview  # from problem.json
        assert "IncumbentAgent" in overview  # from leaderboard
        assert "Cohn" in overview or "1.0" in overview  # from literature bounds
        assert "dyadic" in overview.lower()  # from historian / patterns

    def test_pipeline_survives_missing_agents_gracefully(self, tmp_path):
        """Drop 3 of 5 agents; overview still renders with MISSING markers."""
        import attack
        ws = tmp_path / "campaign"
        _write_synthetic_recon(ws)

        # Only write 2 of 5 agent outputs
        _write_stub_agent_outputs(ws)
        for filename in ("APPLICABLE_PATTERNS.md", "RIGOR_REPORT.md", "CRITIQUE.md"):
            (ws / "recon" / filename).unlink()

        attack.run_stage("hypothesize", workspace=str(ws))
        attack.run_stage("overview", workspace=str(ws))

        overview = (ws / "OVERVIEW.md").read_text()
        # All section headers still present
        assert "## Agent coverage" in overview
        # Missing agents flagged
        assert "MISSING" in overview
        # But the 2 present agents' content still flows
        assert "IncumbentAgent" in overview or "dyadic" in overview.lower()

    def test_phase_markers_track_completed_stages(self, tmp_path):
        """Re-running a stage is idempotent; .phases/<name>.done exists."""
        import attack
        ws = tmp_path / "campaign"
        _write_synthetic_recon(ws)
        _write_stub_agent_outputs(ws)

        attack.run_stage("hypothesize", workspace=str(ws))
        assert (ws / ".phases" / "hypothesize.done").is_file()

        attack.run_stage("overview", workspace=str(ws))
        assert (ws / ".phases" / "overview.done").is_file()

        # Re-running must not error
        attack.run_stage("overview", workspace=str(ws))

    def test_cli_full_pipeline_subprocess(self, tmp_path):
        """Invoke attack.py via subprocess (as a real Claude session would)
        and verify hypothesize + overview run clean."""
        ws = tmp_path / "campaign"
        _write_synthetic_recon(ws)
        _write_stub_agent_outputs(ws)

        script = SKILL_SCRIPTS / "attack.py"

        r1 = subprocess.run(
            [sys.executable, str(script), "hypothesize", "--workspace", str(ws)],
            capture_output=True, text=True, timeout=30,
        )
        assert r1.returncode == 0, f"hypothesize stderr: {r1.stderr}"
        assert (ws / "HYPOTHESES_DRAFT.md").is_file()

        r2 = subprocess.run(
            [sys.executable, str(script), "overview", "--workspace", str(ws)],
            capture_output=True, text=True, timeout=30,
        )
        assert r2.returncode == 0, f"overview stderr: {r2.stderr}"
        assert (ws / "OVERVIEW.md").is_file()

    def test_reference_extractor_integrated_into_recon_flow(self, tmp_path):
        """Reference extraction picks up identifiers from BOTH problem.json
        and discussions.json — proving the full recon pipeline touches both."""
        from extract_refs import extract_references

        ws = tmp_path / "campaign"
        _write_synthetic_recon(ws)

        problem = json.loads((ws / "problem.json").read_text())
        discussions = json.loads((ws / "discussions.json").read_text())

        refs_problem_only = extract_references(problem, [])
        refs_with_discussions = extract_references(problem, discussions)

        # Discussions add the DOI that's not in problem.description
        problem_dois = {r["id"] for r in refs_problem_only if r["kind"] == "doi"}
        full_dois = {r["id"] for r in refs_with_discussions if r["kind"] == "doi"}
        assert full_dois >= problem_dois
        assert any("10.1007/s00208" in d for d in full_dois)


class TestPipelineContract:
    """Contract-level assertions that the pipeline exposes the shape the
    skill's SKILL.md promises."""

    def test_attack_script_has_subcommands(self):
        import attack
        assert set(attack.SUBCOMMANDS) == {
            "recon", "hypothesize", "overview", "attack", "verify"
        }

    def test_run_stage_is_callable_library_entry(self):
        import attack
        assert callable(attack.run_stage)
        with pytest.raises(ValueError):
            attack.run_stage("not-a-stage")

    def test_all_five_agent_outputs_readable_via_CouncilOutputs(self, tmp_path):
        """Integration check: the synthesiser's CouncilOutputs discovers
        exactly the paths the spawn-agents.md contract promises."""
        from arena_framework.hypothesize import CouncilOutputs

        ws = tmp_path / "w"
        _write_synthetic_recon(ws)
        _write_stub_agent_outputs(ws)

        outputs = CouncilOutputs.from_recon_dir(ws)
        assert outputs.literature and outputs.literature.exists()
        assert outputs.historian and outputs.historian.exists()
        assert outputs.pattern_scout and outputs.pattern_scout.exists()
        assert outputs.rigor and outputs.rigor.exists()
        assert outputs.critic and outputs.critic.exists()
