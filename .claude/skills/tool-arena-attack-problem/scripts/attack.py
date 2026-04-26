#!/usr/bin/env python3
"""arena-attack-problem -- autonomous Einstein Arena attack pipeline entry point.

Subcommands:
    recon        Fetch problem + leaderboard + top-K + discussions + extract references
    hypothesize  Synthesise 4 agent artifacts into HYPOTHESES_DRAFT.md
    overview     Re-synthesise with CRITIQUE.md + render OVERVIEW.md
    attack       Run the AttackOrchestrator ATTACK phase
    submit       Run the SUBMIT gate (user-approved)
    retrospective Post-campaign learning

Each subcommand is idempotent and writes markers under {workspace}/.phases/ so
a partially-run campaign can resume exactly where it left off.

Agent spawning (Stages 2 + 4 of the playbook) is done by Claude via the Agent
tool -- this script handles all non-agent work.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

SKILL_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SKILL_DIR.parent.parent.parent
FRAMEWORK_SRC = REPO_ROOT / "plugins" / "arena" / "arena-framework" / "src"
ARENA_SKILL_SCRIPTS = REPO_ROOT / ".claude" / "skills" / "tool-einstein-arena" / "scripts"
PLAYBOOK_TEMPLATE = (
    REPO_ROOT / ".claude" / "skills" / "tool-einstein-arena" / "assets" / "playbook-template.md"
)

if str(FRAMEWORK_SRC) not in sys.path:
    sys.path.insert(0, str(FRAMEWORK_SRC))
if str(ARENA_SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(ARENA_SKILL_SCRIPTS))
if str(SKILL_DIR / "scripts") not in sys.path:
    sys.path.insert(0, str(SKILL_DIR / "scripts"))


# ---------------------------------------------------------------------------
# Stage 1: RECON
# ---------------------------------------------------------------------------


def cmd_recon(args: argparse.Namespace) -> int:
    from arena_framework.recon import Recon  # noqa: PLC0415

    workspace = Path(args.workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "recon").mkdir(exist_ok=True)
    (workspace / "literature").mkdir(exist_ok=True)
    (workspace / "solutions").mkdir(exist_ok=True)

    if args.offline:
        recon = Recon(args.slug, cache_dir=workspace)
        art = recon.run()
    else:
        recon = Recon(args.slug)
        art = recon.run_live(output_dir=workspace)
    recon.save(art, workspace)

    # Reference paper extraction (Gap 5)
    from extract_refs import extract_references, render_references_md  # noqa: PLC0415

    refs = extract_references(art.problem, art.discussions)
    (workspace / "literature" / "REFERENCES.md").write_text(
        render_references_md(args.slug, refs)
    )

    # Bootstrap PLAYBOOK.md if absent
    playbook = workspace / "PLAYBOOK.md"
    if not playbook.exists() and PLAYBOOK_TEMPLATE.is_file():
        header = f"<!-- recon-slug: {args.slug} -->\n"
        playbook.write_text(header + PLAYBOOK_TEMPLATE.read_text())

    _mark_phase(workspace, "recon")

    print(f"[recon] workspace: {workspace}")
    print(f"[recon]   problem: {art.problem.get('title', args.slug)}")
    print(f"[recon]   leaderboard entries: {len(art.leaderboard)}")
    print(f"[recon]   top-K solutions: {len(art.top_solutions)}")
    print(f"[recon]   discussion threads: {len(art.discussions)}")
    print(f"[recon]   references extracted: {len(refs)}")
    print(f"[recon]   exploits flagged: {len(art.exploit_entries())}")
    print(f"[recon] next: spawn the 5 research agents in parallel "
          f"(see references/spawn-agents.md)")
    return 0


# ---------------------------------------------------------------------------
# Stage 3: HYPOTHESIZE -- compose 4 pre-critic agents into draft graph
# ---------------------------------------------------------------------------


def cmd_hypothesize(args: argparse.Namespace) -> int:
    from arena_framework.hypothesize import (  # noqa: PLC0415
        CouncilOutputs,
        save_hypotheses,
        synthesize,
    )

    workspace = Path(args.workspace).resolve()
    outputs = CouncilOutputs.from_recon_dir(workspace)
    result = synthesize(outputs)

    draft_path = workspace / "HYPOTHESES_DRAFT.md"
    save_hypotheses(result, draft_path)
    (workspace / "recon" / "SYNTHESIS_WARNINGS.json").write_text(
        json.dumps(result.warnings, indent=2)
    )

    print(f"[hypothesize] draft nodes: {len(result.graph.nodes())}")
    print(f"[hypothesize] warnings: {result.warnings}")
    print(f"[hypothesize] wrote: {draft_path}")
    print(f"[hypothesize] next: spawn arena-critic-agent on the draft "
          f"(see references/spawn-agents.md §Stage 4)")
    _mark_phase(workspace, "hypothesize")
    return 0


# ---------------------------------------------------------------------------
# Stage 5: OVERVIEW -- re-synthesise with critic + render rich briefing
# ---------------------------------------------------------------------------


def cmd_overview(args: argparse.Namespace) -> int:
    from arena_framework.hypothesize import (  # noqa: PLC0415
        CouncilOutputs,
        save_hypotheses,
        synthesize,
    )
    from arena_framework.recon import Recon  # noqa: PLC0415
    from overview import render_overview  # noqa: PLC0415

    workspace = Path(args.workspace).resolve()
    outputs = CouncilOutputs.from_recon_dir(workspace)
    result = synthesize(outputs)

    save_hypotheses(result, workspace / "HYPOTHESES.md")

    # Offline-load the recon artifacts from workspace. Pass {} to disable the
    # default rigor registry so unknown-slug test workspaces don't explode.
    art = None
    if _has_recon_files(workspace):
        slug_from_problem = json.loads(
            (workspace / "problem.json").read_text()
        ).get("slug", workspace.name)
        try:
            art = Recon(slug_from_problem, cache_dir=workspace,
                        evaluator_registry={}).run()
        except Exception:
            art = None

    overview_md = render_overview(
        workspace=workspace,
        recon=art,
        graph=result.graph,
        provenance=result.provenance_by_node,
        council_outputs=outputs,
        warnings=result.warnings,
    )
    (workspace / "OVERVIEW.md").write_text(overview_md)

    print(f"[overview] hypothesis graph: {len(result.graph.nodes())} nodes")
    print(f"[overview] agents present: "
          f"{sum(1 for p in [outputs.literature, outputs.historian, outputs.pattern_scout, outputs.critic, outputs.rigor] if p and p.exists())}/5")
    print(f"[overview] wrote: {workspace / 'OVERVIEW.md'}")
    print(f"[overview] next: present OVERVIEW.md summary and AskUserQuestion "
          f"to proceed to attack / modify / abort")
    _mark_phase(workspace, "overview")
    return 0


# ---------------------------------------------------------------------------
# Stage 6: ATTACK (stub -- delegated to AttackOrchestrator in live use)
# ---------------------------------------------------------------------------


def cmd_attack(args: argparse.Namespace) -> int:
    from arena_framework.orchestrator import (  # noqa: PLC0415
        AttackOrchestrator,
        Phase,
        GateRequest,
        GateResponse,
    )
    from arena_framework.recon import Recon  # noqa: PLC0415

    workspace = Path(args.workspace).resolve()

    def _gate(req: GateRequest) -> GateResponse:
        if req.phase == Phase.SUBMIT:
            return GateResponse(approved=False, notes="submit deferred to cmd_submit")
        return GateResponse(approved=True, notes="auto-approved by arena-attack-problem")

    orch = AttackOrchestrator(
        slug=args.slug,
        workspace=workspace,
        recon=Recon(args.slug, cache_dir=workspace),
        user_gate=_gate,
    )
    # Jump past recon + hypothesize -- those were handled by prior stages.
    _mark_phase(workspace, "recon", skip_parent=True)
    _mark_phase(workspace, "hypothesize", skip_parent=True)
    result = orch.run(stop_at=Phase.ATTACK)
    print(f"[attack] phases completed this run: {[p.value for p in result.phases_completed]}")
    return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mark_phase(workspace: Path, phase: str, *, skip_parent: bool = False) -> None:
    phase_dir = workspace / ".phases"
    phase_dir.mkdir(parents=True, exist_ok=True)
    (phase_dir / f"{phase}.done").touch()


def _has_recon_files(workspace: Path) -> bool:
    return (workspace / "problem.json").is_file()


# ---------------------------------------------------------------------------
# Stage-by-stage artifact expectations (used by ``verify`` subcommand)
# ---------------------------------------------------------------------------

STAGE_EXPECTATIONS: dict[str, list[str]] = {
    "recon": [
        "problem.json",
        "leaderboard.json",
        "best_solutions.json",
        "discussions.json",
        "literature/REFERENCES.md",
    ],
    "agents": [  # Stage 2 — 4 parallel agent outputs
        "literature/LITERATURE.md",
        "recon/COMPETITOR_FORENSICS.md",
        "recon/APPLICABLE_PATTERNS.md",
        "recon/RIGOR_REPORT.md",
    ],
    "hypothesize": [
        "HYPOTHESES_DRAFT.md",
        "recon/SYNTHESIS_WARNINGS.json",
    ],
    "critic": [  # Stage 4 — critic agent output
        "recon/CRITIQUE.md",
    ],
    "overview": [
        "HYPOTHESES.md",
        "OVERVIEW.md",
    ],
}


def cmd_verify(args: argparse.Namespace) -> int:
    """Stage-artifact audit: print which expected files exist for a stage.

    Exits non-zero if any expected artifact is missing. Call after every
    Claude-driven Agent spawn (Stages 2 and 4) to catch the "agent returned
    content inline but never called Write" failure mode. Example:

        python3 attack.py verify --workspace W --stage agents
    """
    workspace = Path(args.workspace).resolve()
    expected = STAGE_EXPECTATIONS.get(args.stage)
    if expected is None:
        print(f"[verify] unknown stage {args.stage!r}; choose from "
              f"{sorted(STAGE_EXPECTATIONS)}", file=sys.stderr)
        return 2

    present: list[str] = []
    missing: list[str] = []
    for rel in expected:
        path = workspace / rel
        (present if path.is_file() else missing).append(rel)

    print(f"[verify] stage={args.stage} workspace={workspace}")
    for rel in present:
        print(f"[verify]   OK  {rel}")
    for rel in missing:
        print(f"[verify]   MISS {rel}")
    if missing:
        print(f"[verify] {len(missing)}/{len(expected)} artifacts missing — "
              f"common cause: subagent returned content inline but never "
              f"called the Write tool. Re-spawn or write the content "
              f"directly from the returned message.", file=sys.stderr)
        return 1
    print(f"[verify] {len(present)}/{len(expected)} artifacts OK")
    return 0


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

SUBCOMMANDS = {
    "recon": cmd_recon,
    "hypothesize": cmd_hypothesize,
    "overview": cmd_overview,
    "attack": cmd_attack,
    "verify": cmd_verify,
}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="arena-attack-problem",
        description="Autonomous Einstein Arena attack pipeline (7 stages).",
    )
    sub = p.add_subparsers(dest="subcommand", required=True)

    r = sub.add_parser("recon", help="Fetch problem + references (Stage 1)")
    r.add_argument("--slug", required=True)
    r.add_argument("--workspace", required=True)
    r.add_argument("--offline", action="store_true",
                   help="Use cached JSON from workspace instead of live fetch")

    h = sub.add_parser("hypothesize", help="Compose agent outputs into draft graph (Stage 3)")
    h.add_argument("--workspace", required=True)

    o = sub.add_parser("overview", help="Re-synth with critic + render OVERVIEW.md (Stage 5)")
    o.add_argument("--workspace", required=True)

    a = sub.add_parser("attack", help="Run AttackOrchestrator attack phase (Stage 6)")
    a.add_argument("--slug", required=True)
    a.add_argument("--workspace", required=True)

    v = sub.add_parser(
        "verify",
        help=("Audit stage artifacts (catch inline-return subagent failures "
              "before they propagate)"),
    )
    v.add_argument("--workspace", required=True)
    v.add_argument(
        "--stage",
        required=True,
        choices=sorted(STAGE_EXPECTATIONS),
        help="Stage whose expected artifacts should exist on disk",
    )

    return p


def run_stage(stage: str, **kwargs: Any) -> int:
    """Library entrypoint for tests. Builds a Namespace from kwargs."""
    if stage not in SUBCOMMANDS:
        raise ValueError(f"unknown stage: {stage!r} (expected {sorted(SUBCOMMANDS)})")
    ns = argparse.Namespace(**kwargs)
    return SUBCOMMANDS[stage](ns)


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.subcommand not in SUBCOMMANDS:
        parser.error(f"unknown subcommand {args.subcommand!r}")
    return SUBCOMMANDS[args.subcommand](args)


if __name__ == "__main__":
    sys.exit(main())
