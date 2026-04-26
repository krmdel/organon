"""Evolution outer loop (Upgrade U6/4).

Ties program_db + mutator + signatures into the outer evolutionary search
loop described in HANDOFF.md §4 U6. One generation is:

1. **Select parents** — sample one parent per island via ``ProgramDB.sample_parent``
   (annealed softmax over clusters, inverse-length within cluster).
2. **Mutate** — request a child via the injected ``mutator_fn``. Identity
   fallbacks are counted but never break the loop.
3. **Evaluate** — run the injected ``evaluator`` against each child's code.
4. **Insert** — route each child into the DB under its signature; the DB
   bucketizes into clusters for MAP-Elites diversity preservation.
5. **Tick generation** on every island.

Periodically (every ``ProgramDB.reset_period`` generations across all
islands), the loop invokes ``reset_islands`` to wipe the bottom half and
reseed from the top.

The loop respects ``Budget`` — checks ``exhausted()`` at the top of every
generation AND after every evaluation (so a slow evaluator can trigger an
early exit mid-generation). Returns a populated ``EvolutionResult`` that
callers can diff against the DB's ``global_best`` for their own reporting.

The mutator and evaluator are injected (not imported inline) so tests can
run the full loop with deterministic stubs and no LLM / no subprocesses.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ..primitives.budget import Budget, BudgetClock
from .mutator import MutationResult, mutate as _default_mutate
from .program_db import Program, ProgramDB
from .signatures.base import Signature


# ---------------------------------------------------------------------------
# Evaluator contract
# ---------------------------------------------------------------------------


@dataclass
class EvaluationResult:
    """Output of ``evaluator(code)``. The loop inserts score+state into the DB.

    ``metadata`` flows through to the ``Program.metadata`` field for later
    retrospective analysis.
    """

    score: float
    state: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)


Evaluator = Callable[[str], EvaluationResult]
MutatorFn = Callable[..., MutationResult]


# ---------------------------------------------------------------------------
# Config + output
# ---------------------------------------------------------------------------


@dataclass
class EvolutionConfig:
    """All the injected dependencies + tuning knobs for one ``evolve`` run."""

    problem_context: str
    evaluator: Evaluator
    signature: Signature
    n_parents_per_generation: int = 4
    reset_enabled: bool = True
    mutator_fn: MutatorFn = _default_mutate
    rng_seed: int = 0
    history_builder: Optional[Callable[[ProgramDB], str]] = None


@dataclass
class GenerationReport:
    """Per-generation summary returned by ``run_generation``."""

    generation: int
    n_children_attempted: int
    n_children_inserted: int
    n_fallback_identity: int
    best_child_score: Optional[float]
    reset_islands: list[int] = field(default_factory=list)


@dataclass
class EvolutionResult:
    """Populated + returned by ``evolve``."""

    generations_completed: int
    budget_exhausted: bool
    global_best: Optional[Program]
    reports: list[GenerationReport] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------


def seed_population(
    db: ProgramDB,
    *,
    seeds: list[tuple[str, EvaluationResult]],
    signature: Signature,
) -> list[Program]:
    """Insert initial programs. ``seeds`` is a list of (code, eval_result).

    Distributed round-robin across islands so every island starts non-empty —
    otherwise ``sample_parent`` on an empty island fails the first generation.
    """
    inserted: list[Program] = []
    for i, (code, res) in enumerate(seeds):
        island_id = i % db.n_islands
        sig = tuple(signature.extract_features(res.state) if res.state is not None else (0.0,))
        prog = db.add(
            code=code,
            score=res.score,
            signature=sig,
            island_id=island_id,
            metadata=dict(res.metadata),
        )
        inserted.append(prog)
    return inserted


# ---------------------------------------------------------------------------
# One generation
# ---------------------------------------------------------------------------


def run_generation(
    db: ProgramDB,
    config: EvolutionConfig,
    *,
    clock: BudgetClock,
    rng: random.Random,
) -> GenerationReport:
    """Run one generation. Returns a GenerationReport."""
    history_summary = ""
    if config.history_builder is not None:
        try:
            history_summary = config.history_builder(db)
        except Exception:  # noqa: BLE001 — history is optional, never fatal
            history_summary = ""

    n_attempted = 0
    n_inserted = 0
    n_identity = 0
    best_child_score: Optional[float] = None

    per_island = max(1, config.n_parents_per_generation // db.n_islands)
    island_ids = list(range(db.n_islands))

    for island_id in island_ids:
        for _ in range(per_island):
            if clock.exhausted():
                break
            if not db._islands[island_id].program_ids:
                # Empty island — skip; reset logic will re-seed it eventually.
                continue

            parent = db.sample_parent(island_id, rng)
            n_attempted += 1

            mut = config.mutator_fn(
                parent_code=parent.code,
                problem_context=config.problem_context,
                history_summary=history_summary,
            )
            if mut.fallback_reason is not None:
                n_identity += 1
                continue

            clock.tick_evaluation()
            try:
                eval_res = config.evaluator(mut.child_code)
            except Exception as e:  # noqa: BLE001 — a bad child must not kill the loop
                # Malformed child — discard and continue.
                eval_res = EvaluationResult(
                    score=_worst_score(db.goal),
                    state=None,
                    metadata={"evaluator_error": type(e).__name__, "message": str(e)},
                )

            sig = tuple(
                config.signature.extract_features(eval_res.state)
                if eval_res.state is not None
                else (0.0,)
            )
            db.add(
                code=mut.child_code,
                score=eval_res.score,
                signature=sig,
                island_id=island_id,
                parent_id=parent.program_id,
                metadata={
                    **eval_res.metadata,
                    "mutation_blocks": mut.n_diff_blocks,
                },
            )
            n_inserted += 1
            if best_child_score is None or _better(
                eval_res.score, best_child_score, goal=db.goal
            ):
                best_child_score = eval_res.score

    # Tick generation on every island AFTER all children placed.
    db.tick_all_generations()
    clock.tick_iteration()

    # Reset islands if due.
    reset_ids: list[int] = []
    if config.reset_enabled and db.should_reset():
        reset_ids = db.reset_islands()

    gen_number = max(isl.generation for isl in db._islands.values())
    return GenerationReport(
        generation=gen_number,
        n_children_attempted=n_attempted,
        n_children_inserted=n_inserted,
        n_fallback_identity=n_identity,
        best_child_score=best_child_score,
        reset_islands=reset_ids,
    )


# ---------------------------------------------------------------------------
# Outer loop
# ---------------------------------------------------------------------------


def evolve(
    db: ProgramDB,
    config: EvolutionConfig,
    *,
    budget: Budget,
    max_generations: int = 100,
) -> EvolutionResult:
    """Run ``run_generation`` until budget exhaustion or max_generations.

    The function returns even if no parent was sampled — a DB with no seeds
    would otherwise loop forever. The caller seeds via ``seed_population``
    before invoking ``evolve``.
    """
    clock = budget.started()
    rng = random.Random(config.rng_seed)
    reports: list[GenerationReport] = []
    gens_done = 0

    for _ in range(max_generations):
        if clock.exhausted():
            break
        # Abort if no island has programs — nothing to sample from.
        if all(not isl.program_ids for isl in db._islands.values()):
            break
        report = run_generation(db, config, clock=clock, rng=rng)
        reports.append(report)
        gens_done += 1
        if clock.exhausted():
            break

    return EvolutionResult(
        generations_completed=gens_done,
        budget_exhausted=clock.exhausted(),
        global_best=db.global_best(),
        reports=reports,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _worst_score(goal: str) -> float:
    return -math.inf if goal == "maximize" else math.inf


def _better(candidate: float, incumbent: float, *, goal: str) -> bool:
    if goal == "maximize":
        return candidate > incumbent
    return candidate < incumbent
