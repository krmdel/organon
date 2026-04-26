"""Cold-start path for brand-new arena problems (Upgrade U5).

Composes U1 (evaluator registry) + U2 (router) + U3 (critic loop) + U4
(parallel runner + seed generator) for the no-fixture case.

When the orchestrator is invoked with a slug that has no fixture:

1. Router classifies Class A or B and emits a ranked primitive stack.
2. arena-literature-agent fires with elevated budget (handled by the
   orchestrator's hypothesize phase).
3. Cold-start seed pool is built from THREE candidates:
   a. Random valid candidate (from problem spec defaults)
   b. Best-competitor-scaled (leaderboard #1 × 1.0001 if scoring=minimize)
   c. Router's primary-primitive default state
4. Each round: fan out via parallel_runner (U4); critic loop (U3) gates the
   result; additive directives feed the next round's seed pool.

Exposes an ``attack_loop_cold_start`` callable conforming to the
``arena_framework.orchestrator.AttackLoop`` signature, so it drops into the
existing orchestrator without glue code.
"""

from __future__ import annotations

import copy
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from .attack_loops._critic_loop import (
    CriticContext,
    decide_directive,
    load_previous_directives,
    run_critic_round,
)
from .hypothesis_graph import HypothesisGraph
from .orchestrator import SubmissionCandidate
from .parallel_runner import ParallelRunResult, SeedSpec, parallel_run
from .primitives.budget import Budget, PrimitiveResult
from .recon import ReconArtifacts, default_evaluator_registry
from .router import RoutingDecision, route
from .seed_generator import (
    HistoryEntry,
    append_history,
    generate_diverse_rng,
    generate_opro_proposals,
    generate_perturbations,
)


# ---------------------------------------------------------------------------
# Seeding strategies
# ---------------------------------------------------------------------------


def _extract_best_competitor_solution(
    recon: ReconArtifacts,
) -> Optional[dict[str, Any]]:
    if not recon.top_solutions:
        return None
    sol = recon.top_solutions[0]
    return sol.get("data", sol)


def _random_valid_candidate(
    recon: ReconArtifacts, rng: random.Random
) -> Optional[dict[str, Any]]:
    """Generate a valid random candidate from the problem schema.

    Uses a simple default for each known schema key. Not trying to be smart —
    just to provide a baseline that the evaluator won't reject.
    """
    prob = recon.problem or {}
    schema = prob.get("solutionSchema") or {}
    sample = _extract_best_competitor_solution(recon)
    if sample is None:
        return None
    candidate: dict[str, Any] = {}
    for key, val in sample.items():
        candidate[key] = _randomize_field(val, rng)
    return candidate


def _randomize_field(val: Any, rng: random.Random) -> Any:
    """Produce a near-competitor-shaped random value for a single field."""
    if isinstance(val, list):
        if not val:
            return []
        first = val[0]
        if isinstance(first, (list, tuple)):
            return [
                [rng.uniform(-1.0, 1.0) for _ in inner] for inner in val
            ]
        if isinstance(first, int):
            return [rng.randint(0, max(1, int(first))) for _ in val]
        if isinstance(first, float):
            return [rng.uniform(0.0, 1.0) for _ in val]
        return list(val)
    if isinstance(val, dict):
        return {k: _randomize_field(v, rng) for k, v in val.items()}
    if isinstance(val, float):
        return rng.uniform(0.0, 1.0)
    if isinstance(val, int):
        return rng.randint(0, max(1, val))
    return val


def _scaled_competitor_candidate(
    recon: ReconArtifacts, scale: float = 1.0001
) -> Optional[dict[str, Any]]:
    """Scale all numeric fields of the best competitor solution by ``scale``.

    Useful when the arena verifier has a strict ``> threshold`` test that a
    1.0001× multiplicative nudge can exploit (the PNT 2026-04-16 win
    technique)."""
    sol = _extract_best_competitor_solution(recon)
    if sol is None:
        return None
    return _scale_numeric(sol, scale)


def _scale_numeric(obj: Any, factor: float) -> Any:
    if isinstance(obj, (int, float)):
        return obj * factor
    if isinstance(obj, list):
        return [_scale_numeric(x, factor) for x in obj]
    if isinstance(obj, dict):
        return {k: _scale_numeric(v, factor) for k, v in obj.items()}
    return obj


def _router_default_candidate(
    decision: RoutingDecision, recon: ReconArtifacts
) -> Optional[dict[str, Any]]:
    """The router's top primitive's ``default_params`` interpreted as a seed
    state. For most problems this is just the best competitor unmodified —
    the router is advising the *attack method*, not the initial state. But
    some primitives (e.g. smooth_max_beta) expect a warm-start and this is
    where that wiring happens if we know a better start than the competitor.
    """
    # For now: echo best competitor. Primitive-specific overrides can wire
    # here later (e.g. "map_elites_evolve" → seed from a Singer construction).
    return _extract_best_competitor_solution(recon)


# ---------------------------------------------------------------------------
# Cold-start config
# ---------------------------------------------------------------------------


@dataclass
class ColdStartConfig:
    """Knobs controlling the cold-start attack. All have defaults; override
    via the orchestrator's ``attack_loop_config`` dict."""

    n_seeds_per_round: int = 8
    max_rounds: int = 6
    seed_rng: int = 42
    scoring: str = "minimize"
    min_improvement: float = 1e-5
    history_path: Optional[Path] = None
    round_dir: Optional[Path] = None
    scale_factor: float = 1.0001
    routing_decision: Optional[RoutingDecision] = None
    opro_threshold: int = 8


# ---------------------------------------------------------------------------
# Inner single-seed attack shim
# ---------------------------------------------------------------------------


def _score_candidate(
    slug: str, candidate: dict[str, Any]
) -> tuple[float, dict[str, Any]]:
    """Score a candidate via the registry's rigorous_evaluator (preferred)
    or arena_evaluator (fallback). Returns (score, diagnostic)."""
    registry = default_evaluator_registry()
    entry = registry.get(slug)
    if entry is None:
        return float("inf"), {"verdict_hint": "no_evaluator"}
    try:
        cfg = entry["config_extractor"]({"data": candidate})
    except Exception as exc:
        return float("inf"), {"verdict_hint": "config_extract_failed", "error": str(exc)}
    try:
        rig = entry["rigorous_evaluator"](cfg)
        if isinstance(rig, tuple) and len(rig) == 2:
            return float(rig[0]), dict(rig[1])
        return float(rig), {}
    except Exception:
        try:
            arena = entry["arena_evaluator"](cfg)
            return float(arena), {"verdict_hint": "arena_only_scored"}
        except Exception as exc:
            return float("inf"), {
                "verdict_hint": "both_evaluators_failed",
                "error": str(exc),
            }


def _attack_shim(
    seed: int, budget: Budget, **config: Any
) -> PrimitiveResult:
    """Pure-eval child: score a candidate. No optimization inside — the
    cold-start round is about *fan out + aggregate*; the real optimization
    comes from the seed diversity + the critic loop's directives.
    """
    slug = config["slug"]
    candidate = config["candidate"]
    score, diag = _score_candidate(slug, candidate)
    return PrimitiveResult(
        best_score=score,
        best_state=candidate,
        n_iterations=1,
        n_evaluations=1,
        wall_time_s=0.0,
        primitive_metadata=diag,
    )


# ---------------------------------------------------------------------------
# Cold-start attack loop
# ---------------------------------------------------------------------------


def attack_loop_cold_start(
    graph: HypothesisGraph,
    recon: ReconArtifacts,
    config: dict[str, Any],
) -> SubmissionCandidate:
    """Cold-start attack loop conforming to the ``AttackLoop`` signature.

    Config keys (all optional, see ``ColdStartConfig`` for defaults):
      n_seeds_per_round, max_rounds, scoring, min_improvement,
      history_path (Path), round_dir (Path), scale_factor, routing_decision.
    """
    cfg = ColdStartConfig(
        n_seeds_per_round=int(config.get("n_seeds_per_round", 8)),
        max_rounds=int(config.get("max_rounds", 6)),
        seed_rng=int(config.get("seed_rng", 42)),
        scoring=str(config.get("scoring", recon.problem.get("scoring", "minimize"))),
        min_improvement=float(
            config.get("min_improvement", recon.problem.get("minImprovement", 1e-5))
        ),
        history_path=_as_path(config.get("history_path")),
        round_dir=_as_path(config.get("round_dir")),
        scale_factor=float(config.get("scale_factor", 1.0001)),
        routing_decision=config.get("routing_decision"),
        opro_threshold=int(config.get("opro_threshold", 8)),
    )

    if cfg.routing_decision is None:
        cfg.routing_decision = route(
            recon.problem,
            top_solutions=recon.top_solutions,
            leaderboard=recon.leaderboard,
        )

    rng = random.Random(cfg.seed_rng)
    slug = recon.slug

    # Round 0: build 3-candidate seed pool
    initial_seeds: list[SeedSpec] = []
    rand = _random_valid_candidate(recon, rng)
    if rand is not None:
        initial_seeds.append(
            SeedSpec(
                seed=cfg.seed_rng,
                config={"slug": slug, "candidate": rand},
                tag="cold-random",
            )
        )
    scaled = _scaled_competitor_candidate(recon, cfg.scale_factor)
    if scaled is not None:
        initial_seeds.append(
            SeedSpec(
                seed=cfg.seed_rng + 1,
                config={"slug": slug, "candidate": scaled},
                tag=f"cold-scaled-{cfg.scale_factor}",
            )
        )
    router_state = _router_default_candidate(cfg.routing_decision, recon)
    if router_state is not None:
        initial_seeds.append(
            SeedSpec(
                seed=cfg.seed_rng + 2,
                config={"slug": slug, "candidate": router_state},
                tag="cold-router-default",
            )
        )

    if not initial_seeds:
        return SubmissionCandidate(
            config={}, arena_score=float("inf"), rigorous_score=None,
            verdict="unknown",
            metadata={"cold_start_error": "no seed candidates built"},
        )

    best_candidate: Optional[dict[str, Any]] = None
    best_score = float("inf") if cfg.scoring == "minimize" else float("-inf")
    best_diag: dict[str, Any] = {}
    round_history: list[HistoryEntry] = []
    all_directives: list[dict[str, Any]] = []

    current_pool = initial_seeds

    for round_n in range(cfg.max_rounds):
        pool_budget = Budget(wall_clock_s=60.0)
        result = parallel_run(
            _attack_shim,
            current_pool,
            budget=pool_budget,
            minimize=(cfg.scoring == "minimize"),
            per_child_budget_fraction=1.0,
        )

        # Update global best from this round
        if result.best_child and result.best_child.result is not None:
            round_score = result.best_child.result.best_score
            if _is_better(round_score, best_score, cfg.scoring):
                best_score = round_score
                best_candidate = result.best_child.result.best_state
                best_diag = result.best_child.result.primitive_metadata

        # Log history
        entry = HistoryEntry(
            params={
                "round_n": round_n,
                "n_seeds": len(current_pool),
                "seed_tags": [s.tag for s in current_pool],
            },
            score=(
                result.best_child.result.best_score
                if result.best_child and result.best_child.result
                else float("inf")
            ),
            seed=cfg.seed_rng + round_n,
            metadata=dict(best_diag),
        )
        round_history.append(entry)
        if cfg.history_path is not None:
            append_history(cfg.history_path, entry)

        # Critic loop
        latest_verdict = _verdict_from_diag(best_diag, best_score)
        ctx = CriticContext(
            round_n=round_n,
            problem_slug=slug,
            scoring=cfg.scoring,
            min_improvement=cfg.min_improvement,
            best_known_score=best_score,
            threshold_score=_leaderboard_threshold(recon),
            latest_candidate={"rel_noise": 0.01},
            latest_diagnostic=best_diag,
            latest_score=best_score,
            latest_verdict=latest_verdict,
            history=round_history,
            previous_directives=all_directives,
        )
        directive = run_critic_round(ctx, round_dir=cfg.round_dir)
        all_directives.append(directive.to_dict())

        if directive.verdict == "accept":
            break
        if directive.verdict == "stop":
            break

        # Build next round's pool: best_known + directive-conditioned new seeds
        next_seeds: list[SeedSpec] = []
        if best_candidate is not None:
            next_seeds.append(
                SeedSpec(
                    seed=cfg.seed_rng + 1000 * (round_n + 1),
                    config={"slug": slug, "candidate": best_candidate},
                    tag=f"best-round-{round_n}",
                )
            )

        new_k = cfg.n_seeds_per_round - len(next_seeds)
        if len(round_history) >= cfg.opro_threshold:
            opro = generate_opro_proposals(
                history=round_history,
                n=new_k,
                problem_goal=cfg.scoring,
                base_seed=cfg.seed_rng + 5000 * (round_n + 1),
            )
            for s in opro:
                next_seeds.append(
                    SeedSpec(
                        seed=s.seed,
                        config={
                            "slug": slug,
                            "candidate": _candidate_from_opro(s.config, best_candidate),
                        },
                        tag=s.tag,
                    )
                )
        else:
            noise = float(
                directive.parameters.get("new_rel_noise", 0.01)
            )
            if best_candidate is not None:
                perturbed = generate_perturbations(
                    n=new_k,
                    base_state=best_candidate,
                    noise_schedule=[noise] * new_k,
                    base_seed=cfg.seed_rng + 3000 * (round_n + 1),
                )
                for s in perturbed:
                    next_seeds.append(
                        SeedSpec(
                            seed=s.seed,
                            config={
                                "slug": slug,
                                "candidate": _perturbed_candidate(
                                    best_candidate, s.config["rel_noise"], rng
                                ),
                            },
                            tag=s.tag,
                        )
                    )
            else:
                diverse = generate_diverse_rng(
                    n=new_k, base_seed=cfg.seed_rng + 7000 * (round_n + 1),
                )
                for s in diverse:
                    cand = _random_valid_candidate(recon, rng)
                    if cand:
                        next_seeds.append(
                            SeedSpec(
                                seed=s.seed,
                                config={"slug": slug, "candidate": cand},
                                tag=s.tag,
                            )
                        )

        if not next_seeds:
            break
        current_pool = next_seeds

    # Emit SubmissionCandidate
    if best_candidate is None:
        return SubmissionCandidate(
            config={}, arena_score=float("inf"), rigorous_score=None,
            verdict="unknown",
            metadata={"cold_start_status": "no valid candidate"},
        )

    verdict = _verdict_from_diag(best_diag, best_score)
    arena_score = best_score
    rigorous_score: Optional[float] = None
    if verdict == "rigorous":
        rigorous_score = best_score

    return SubmissionCandidate(
        config=best_candidate,
        arena_score=float(arena_score),
        rigorous_score=rigorous_score,
        verdict=verdict,
        metadata={
            "cold_start": True,
            "rounds_run": len(round_history),
            "routing_class": cfg.routing_decision.problem_class,
            "final_directive": all_directives[-1] if all_directives else None,
            "diagnostic": best_diag,
        },
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _as_path(x: Any) -> Optional[Path]:
    if x is None:
        return None
    return Path(x)


def _is_better(new: float, old: float, scoring: str) -> bool:
    if scoring == "minimize":
        return new < old
    return new > old


def _leaderboard_threshold(recon: ReconArtifacts) -> Optional[float]:
    if not recon.leaderboard:
        return None
    top = recon.leaderboard[0]
    s = top.get("score", top.get("bestScore"))
    try:
        return float(s) if s is not None else None
    except (TypeError, ValueError):
        return None


def _verdict_from_diag(diag: dict[str, Any], score: float) -> str:
    hint = diag.get("verdict_hint", "")
    if "exploit" in hint:
        return "exploit"
    if "rigorous" in hint or "integer" in hint:
        return "rigorous"
    return "unknown"


def _candidate_from_opro(
    opro_cfg: dict[str, Any], fallback: Optional[dict[str, Any]]
) -> dict[str, Any]:
    """OPRO returns abstract param proposals; for cold-start we need a
    candidate dict matching the solution schema. Fall back to ``fallback``
    (typically the best-known candidate) and apply the OPRO params as
    perturbation hints (e.g. the proposer's ``scale_factor`` gets applied
    to the fallback's numeric fields).
    """
    params = opro_cfg.get("params", {}) or {}
    if fallback is None:
        return params
    if "scale_factor" in params:
        return _scale_numeric(fallback, float(params["scale_factor"]))
    return fallback


def _perturbed_candidate(
    base: dict[str, Any], rel_noise: float, rng: random.Random
) -> dict[str, Any]:
    """Apply multiplicative Gaussian noise to numeric fields of ``base``."""

    def _perturb(v: Any) -> Any:
        if isinstance(v, (int, float)):
            return v * (1.0 + rng.gauss(0.0, rel_noise))
        if isinstance(v, list):
            return [_perturb(x) for x in v]
        if isinstance(v, dict):
            return {k: _perturb(w) for k, w in v.items()}
        return v

    return _perturb(copy.deepcopy(base))
