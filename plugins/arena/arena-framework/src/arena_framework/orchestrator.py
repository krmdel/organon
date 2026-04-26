"""arena-attack-problem orchestrator.

Composes all Phase 1–3 primitives into a resumable, user-gated pipeline:

  recon -> rigor_scan -> literature (agent) -> hypothesize (council synth) ->
  attack_loop -> submit_gate -> retrospective

Each phase:
- Checks whether it's already complete (phase-marker file exists in workspace).
- Runs if not complete or if ``force_rerun`` includes this phase.
- Saves a marker on completion for resume.

User gates are emitted as ``GateRequest`` objects; the caller (CLI or agent)
decides how to present them. In tests we inject a ``UserGate`` stub that
auto-approves. In real use the gate uses ``AskUserQuestion`` or equivalent.

The attack loop itself is problem-specific and injected: the orchestrator
hands the loop the hypothesis graph + primitives library and lets it
return a `SubmissionCandidate`. A default stub that just echoes the best
competitor score is provided for tests.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

from .hypothesis_graph import HypothesisGraph
from .hypothesize import CouncilOutputs, HypothesizeResult, save_hypotheses, synthesize
from .recon import Recon, ReconArtifacts
from .retrospective import RetrospectiveResult, SessionSummary, run_retrospective, save_retrospective
from .rigor_gate import RigorVerdict


class Phase(str, Enum):
    RECON = "recon"
    HYPOTHESIZE = "hypothesize"
    ATTACK = "attack"
    SUBMIT = "submit"
    RETROSPECTIVE = "retrospective"


@dataclass
class GateRequest:
    """One user-approval point. Emitted, not blocking — caller decides."""

    phase: Phase
    prompt: str
    default_approved: bool = True


@dataclass
class GateResponse:
    approved: bool
    notes: str = ""


UserGate = Callable[[GateRequest], GateResponse]


def auto_approve(_req: GateRequest) -> GateResponse:
    """Default gate: approves everything. Used in tests. Real use injects
    a CLI-based or AskUserQuestion-based gate."""
    return GateResponse(approved=True, notes="auto-approved")


@dataclass
class SubmissionCandidate:
    config: Any
    arena_score: float
    rigorous_score: Optional[float]
    verdict: str  # "rigorous" | "exploit" | "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)


AttackLoop = Callable[
    [HypothesisGraph, ReconArtifacts, dict[str, Any]], SubmissionCandidate
]


def default_attack_loop(
    graph: HypothesisGraph,
    recon: ReconArtifacts,
    config: dict[str, Any],
) -> SubmissionCandidate:
    """Placeholder attack loop — returns the best competitor solution
    unmodified. Real attacks inject a problem-specific loop that actually
    uses the primitives library to search.

    This is a LOUD stub: it emits a warning to stderr and stamps
    ``verdict="echo-leader-stub"`` so downstream gates (submit,
    retrospective) can tell a real attack candidate apart from the
    placeholder. Before it was a SILENT stub that simply returned
    ``verdict="unknown"`` with ``source="echo-leader"`` — easy to mistake
    for a real attack result, especially on discrete-construction
    problems where ``continuous_attack.classify_problem`` returns
    "unknown" and the orchestrator silently falls through to this stub.
    """
    import sys  # noqa: PLC0415
    problem_title = (recon.problem or {}).get("title", recon.slug or "?")
    eval_mode = (recon.problem or {}).get("evaluationMode", "?")
    print(
        f"[arena-framework] default_attack_loop is a stub — it does not "
        f"search, it echoes the leaderboard #1 score back as a "
        f"SubmissionCandidate with verdict='echo-leader-stub'. Inject a "
        f"problem-specific AttackLoop via AttackOrchestrator(attack_loop=...) "
        f"to actually attack problem {problem_title!r} "
        f"(evaluationMode={eval_mode!r}, hypotheses={len(graph.nodes())}).",
        file=sys.stderr,
    )
    if not recon.top_solutions:
        return SubmissionCandidate(
            config=[],
            arena_score=float("inf"),
            rigorous_score=None,
            verdict="echo-leader-stub",
            metadata={"source": "echo-leader", "reason": "no top_solutions"},
        )
    best = recon.top_solutions[0]
    return SubmissionCandidate(
        config=best.get("data", {}),
        arena_score=float(best.get("score", 0.0)),
        rigorous_score=None,
        verdict="echo-leader-stub",
        metadata={
            "source": "echo-leader",
            "problem_title": problem_title,
            "evaluation_mode": eval_mode,
            "hypotheses_count": len(graph.nodes()),
            "note": (
                "No problem-specific AttackLoop was injected. Submit gate "
                "should reject this candidate."
            ),
        },
    )


# ---------------------------------------------------------------------------
# Workspace + phase tracking
# ---------------------------------------------------------------------------


@dataclass
class OrchestratorResult:
    slug: str
    workspace: Path
    phases_completed: list[Phase]
    recon_artifacts: Optional[ReconArtifacts] = None
    hypothesis_graph: Optional[HypothesisGraph] = None
    submission_candidate: Optional[SubmissionCandidate] = None
    submitted: bool = False
    retrospective: Optional[RetrospectiveResult] = None
    gate_decisions: dict[Phase, GateResponse] = field(default_factory=dict)


class AttackOrchestrator:
    """Resumable, user-gated attack pipeline for one arena problem."""

    def __init__(
        self,
        slug: str,
        workspace: Path,
        *,
        recon: Optional[Recon] = None,
        council_outputs: Optional[CouncilOutputs] = None,
        attack_loop: AttackLoop = default_attack_loop,
        user_gate: UserGate = auto_approve,
        patterns_dir: Optional[Path] = None,
        fixtures_dir: Optional[Path] = None,
        use_continuous_attack: bool = False,
        continuous_attack_budget: Optional[Any] = None,
        continuous_attack_config: Optional[dict[str, Any]] = None,
        continuous_attack_evaluator: Optional[Callable[[Any], float]] = None,
    ) -> None:
        self.slug = slug
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.recon = recon or Recon(slug, cache_dir=self.workspace)
        self.council_outputs = council_outputs
        self.attack_loop = attack_loop
        self.user_gate = user_gate
        self.patterns_dir = patterns_dir
        self.fixtures_dir = fixtures_dir
        self.use_continuous_attack = use_continuous_attack
        self.continuous_attack_budget = continuous_attack_budget
        self.continuous_attack_config = continuous_attack_config
        self.continuous_attack_evaluator = continuous_attack_evaluator

    # ---- continuous-attack dispatch (U14/orchestrator) ----

    def _try_continuous_attack(
        self, recon_art: ReconArtifacts
    ) -> Optional[SubmissionCandidate]:
        """Dispatch through ``continuous_attack.attack()`` when the flag is set.

        Returns ``None`` — caller falls back to ``self.attack_loop`` — when:
          * the continuous_attack package can't be imported,
          * :func:`classify_problem` returns ``"unknown"``,
          * :func:`attack` raises (no recipe registered, recipe error, etc.).

        Lazy-imports preserve the orchestrator's heavy-deps invariant
        (no scipy / numpy at module load).
        """
        try:
            from .continuous_attack import (  # noqa: PLC0415 - lazy
                attack as _cx_attack,
                classify_problem,
            )
            from .primitives.budget import Budget as _Budget  # noqa: PLC0415
        except ImportError:
            return None

        cls, diag = classify_problem(
            recon_art.problem, recon_art.top_solutions
        )
        if cls == "unknown":
            return None

        budget = self.continuous_attack_budget or _Budget(wall_clock_s=60.0)
        try:
            result = _cx_attack(
                recon_art.problem,
                budget=budget,
                evaluator=self.continuous_attack_evaluator,
                top_solutions=recon_art.top_solutions,
                config=self.continuous_attack_config,
                validate=False,
            )
        except Exception:
            return None

        metadata = dict(result.primitive_metadata or {})
        return SubmissionCandidate(
            config=result.best_state,
            arena_score=float(result.best_score),
            rigorous_score=None,
            verdict="unknown",
            metadata={
                "source": "continuous_attack",
                "recipe_name": result.recipe_name,
                "problem_class": result.problem_class,
                "classified_as": metadata.get("classified_as", cls),
                "dispatched_to": metadata.get("dispatched_to", cls),
                "classification_reasons": list(diag.get("reasons", [])),
                "n_iterations": result.n_iterations,
                "n_evaluations": result.n_evaluations,
                "wall_time_s": result.wall_time_s,
                "n_restarts": result.n_restarts,
                "n_basin_hops": result.n_basin_hops,
            },
        )

    # ---- phase markers ----

    def _marker_path(self, phase: Phase) -> Path:
        return self.workspace / ".phases" / f"{phase.value}.done"

    def _is_complete(self, phase: Phase) -> bool:
        return self._marker_path(phase).exists()

    def _mark_complete(self, phase: Phase) -> None:
        p = self._marker_path(phase)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch()

    # ---- main driver ----

    def run(
        self,
        *,
        force_rerun: Optional[set[Phase]] = None,
        stop_at: Optional[Phase] = None,
    ) -> OrchestratorResult:
        """Run phases in order, skipping completed ones. Stop after
        ``stop_at`` if provided."""
        force_rerun = force_rerun or set()
        phases_completed: list[Phase] = []
        gate_decisions: dict[Phase, GateResponse] = {}
        recon_art: Optional[ReconArtifacts] = None
        graph: Optional[HypothesisGraph] = None
        candidate: Optional[SubmissionCandidate] = None
        submitted = False
        retro: Optional[RetrospectiveResult] = None

        def _maybe_stop(phase: Phase) -> bool:
            return stop_at is not None and phase == stop_at

        # -- RECON --
        if Phase.RECON in force_rerun or not self._is_complete(Phase.RECON):
            recon_art = self.recon.run()
            self.recon.save(recon_art, self.workspace)
            gate = self.user_gate(
                GateRequest(
                    phase=Phase.RECON,
                    prompt=(
                        f"Recon complete for `{self.slug}`. "
                        f"Top-K: {len(recon_art.top_solutions)}, "
                        f"exploits flagged: {len(recon_art.exploit_entries())}. "
                        "Proceed to hypothesize?"
                    ),
                )
            )
            gate_decisions[Phase.RECON] = gate
            if not gate.approved:
                return OrchestratorResult(
                    slug=self.slug,
                    workspace=self.workspace,
                    phases_completed=phases_completed,
                    recon_artifacts=recon_art,
                    gate_decisions=gate_decisions,
                )
            self._mark_complete(Phase.RECON)
            phases_completed.append(Phase.RECON)
            if _maybe_stop(Phase.RECON):
                return OrchestratorResult(
                    slug=self.slug, workspace=self.workspace,
                    phases_completed=phases_completed,
                    recon_artifacts=recon_art,
                    gate_decisions=gate_decisions,
                )

        # -- HYPOTHESIZE --
        if Phase.HYPOTHESIZE in force_rerun or not self._is_complete(Phase.HYPOTHESIZE):
            council = self.council_outputs or CouncilOutputs.from_recon_dir(self.workspace)
            hypo_result: HypothesizeResult = synthesize(council)
            save_hypotheses(hypo_result, self.workspace / "HYPOTHESES.md")
            graph = hypo_result.graph
            gate = self.user_gate(
                GateRequest(
                    phase=Phase.HYPOTHESIZE,
                    prompt=(
                        f"Hypothesis graph built: {len(graph.nodes())} nodes, "
                        f"warnings: {hypo_result.warnings}. Proceed to attack?"
                    ),
                )
            )
            gate_decisions[Phase.HYPOTHESIZE] = gate
            if not gate.approved:
                return OrchestratorResult(
                    slug=self.slug, workspace=self.workspace,
                    phases_completed=phases_completed,
                    recon_artifacts=recon_art,
                    hypothesis_graph=graph,
                    gate_decisions=gate_decisions,
                )
            self._mark_complete(Phase.HYPOTHESIZE)
            phases_completed.append(Phase.HYPOTHESIZE)
            if _maybe_stop(Phase.HYPOTHESIZE):
                return OrchestratorResult(
                    slug=self.slug, workspace=self.workspace,
                    phases_completed=phases_completed,
                    recon_artifacts=recon_art, hypothesis_graph=graph,
                    gate_decisions=gate_decisions,
                )

        # -- ATTACK --
        if Phase.ATTACK in force_rerun or not self._is_complete(Phase.ATTACK):
            if recon_art is None:
                recon_art = self.recon.run()
            if graph is None and (self.workspace / "HYPOTHESES.md").exists():
                graph = HypothesisGraph.load(self.workspace / "HYPOTHESES.md")
            candidate = None
            if self.use_continuous_attack:
                candidate = self._try_continuous_attack(recon_art)
            if candidate is None:
                candidate = self.attack_loop(graph or HypothesisGraph(), recon_art, {})
            (self.workspace / "attack_candidate.json").write_text(
                json.dumps(asdict(candidate), default=str, indent=2)
            )
            self._mark_complete(Phase.ATTACK)
            phases_completed.append(Phase.ATTACK)
            if _maybe_stop(Phase.ATTACK):
                return OrchestratorResult(
                    slug=self.slug, workspace=self.workspace,
                    phases_completed=phases_completed,
                    recon_artifacts=recon_art,
                    hypothesis_graph=graph,
                    submission_candidate=candidate,
                    gate_decisions=gate_decisions,
                )

        # -- SUBMIT --
        if Phase.SUBMIT in force_rerun or not self._is_complete(Phase.SUBMIT):
            if candidate is None:
                cp = self.workspace / "attack_candidate.json"
                if cp.exists():
                    d = json.loads(cp.read_text())
                    candidate = SubmissionCandidate(**d)
            if candidate is None:
                raise RuntimeError("submit phase reached with no attack_candidate.json")

            prompt = (
                f"Submit candidate? arena={candidate.arena_score:.10g} "
                f"verdict={candidate.verdict}"
                + (f" rigorous={candidate.rigorous_score:.6g}" if candidate.rigorous_score is not None else "")
            )
            gate = self.user_gate(
                GateRequest(phase=Phase.SUBMIT, prompt=prompt, default_approved=False)
            )
            gate_decisions[Phase.SUBMIT] = gate
            submitted = gate.approved
            # We DO NOT actually submit here. The orchestrator only
            # authorises. A real submit path runs `SubmitGate.submit()`
            # with `allow_exploit=candidate.verdict == "exploit"` + an
            # explicit arena_client — wiring that is Slice 18b (live
            # integration) and requires real creds.
            self._mark_complete(Phase.SUBMIT)
            phases_completed.append(Phase.SUBMIT)

        # -- RETROSPECTIVE --
        if Phase.RETROSPECTIVE in force_rerun or not self._is_complete(Phase.RETROSPECTIVE):
            if graph is None and (self.workspace / "HYPOTHESES.md").exists():
                graph = HypothesisGraph.load(self.workspace / "HYPOTHESES.md")
            if graph is not None:
                summary = SessionSummary(
                    slug=self.slug,
                    final_arena_score=candidate.arena_score if candidate else None,
                    final_rigorous_score=candidate.rigorous_score if candidate else None,
                    final_verdict=candidate.verdict if candidate else None,
                )
                if self.patterns_dir and self.fixtures_dir:
                    retro = run_retrospective(
                        graph,
                        summary,
                        patterns_dir=self.patterns_dir,
                        fixtures_dir=self.fixtures_dir,
                    )
                    save_retrospective(retro, self.workspace / "RETROSPECTIVE.md")
            self._mark_complete(Phase.RETROSPECTIVE)
            phases_completed.append(Phase.RETROSPECTIVE)

        return OrchestratorResult(
            slug=self.slug,
            workspace=self.workspace,
            phases_completed=phases_completed,
            recon_artifacts=recon_art,
            hypothesis_graph=graph,
            submission_candidate=candidate,
            submitted=submitted,
            retrospective=retro,
            gate_decisions=gate_decisions,
        )
