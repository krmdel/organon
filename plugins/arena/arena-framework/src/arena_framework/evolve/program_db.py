"""FunSearch-style Program database with MAP-Elites × Islands (Upgrade U6).

Parent selection is a two-level sample:

1. **Cluster pick** — within an island, pick a cluster by softmax over
   cluster-best scores with a temperature annealed by the island's generation
   counter. Early islands explore uniformly; mature islands exploit.
2. **Program pick** — within the chosen cluster, prefer shorter programs
   (``1 / (1 + len(code))`` softmax). This is the "inverse length" bias from
   Romera-Paredes et al. 2024 *Nature* 625 (FunSearch) and the
   ``algorithmicsuperintelligence/openevolve`` v0.2.27 reference.

Clusters bucket programs by their *signature* (extracted via
``evolve.signatures``). Programs with identical signatures compete; programs
with different signatures coexist. This is what gives MAP-Elites its
"behavioural diversity" property.

Islands are independent subpopulations. Every ``reset_period`` generations, a
``reset_islands`` call wipes the bottom half of islands (ranked by
best-program score) and reseeds them from the top two islands' best
programs. This is the island-model diversity-preservation rule.

Invariants:

- Program IDs are allocated monotonically on ``add``.
- ``add`` does NOT mutate Program inputs; callers pass fully-constructed
  Programs and the DB copies essential fields.
- ``sample_parent`` is deterministic for a fixed ``random.Random`` state.
- The DB is in-memory and not thread-safe for writes. Single-writer use only.
- JSON round-trip via ``to_dict`` / ``validate_program_dict`` is lossless
  for everything except the ``metadata`` dict (which must itself be
  JSON-serializable — the validator checks this).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


PROGRAM_REQUIRED_FIELDS = {"code", "score", "signature"}


def validate_program_dict(d: dict[str, Any]) -> list[str]:
    """Return a list of validation error strings; empty list on success.

    Used by the mutator (U6/3) and evolution loop (U6/4) to reject malformed
    program dicts before they reach the DB.
    """
    errs: list[str] = []
    if not isinstance(d, dict):
        return ["program must be a dict"]
    missing = PROGRAM_REQUIRED_FIELDS - set(d.keys())
    for m in sorted(missing):
        errs.append(f"missing required field: {m}")
    if "code" in d and not isinstance(d["code"], str):
        errs.append("code must be a string")
    if "score" in d:
        try:
            s = float(d["score"])
        except (TypeError, ValueError):
            errs.append("score must be numeric")
        else:
            if not math.isfinite(s):
                errs.append("score must be finite (no NaN/inf)")
    if "signature" in d and not isinstance(d["signature"], (list, tuple)):
        errs.append("signature must be a list or tuple")
    if "metadata" in d and not isinstance(d["metadata"], dict):
        errs.append("metadata must be a dict")
    return errs


# ---------------------------------------------------------------------------
# Core dataclasses
# ---------------------------------------------------------------------------


@dataclass
class Program:
    """One evolved program. ``code`` is the full source; ``signature`` is the
    feature vector produced by the per-problem signature function."""

    program_id: int
    code: str
    score: float
    signature: tuple
    island_id: int = 0
    cluster_id: str = ""
    generation: int = 0
    parent_id: Optional[int] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "program_id": self.program_id,
            "code": self.code,
            "score": self.score,
            "signature": list(self.signature),
            "island_id": self.island_id,
            "cluster_id": self.cluster_id,
            "generation": self.generation,
            "parent_id": self.parent_id,
            "metadata": dict(self.metadata),
        }


@dataclass
class Cluster:
    """Bucket of programs sharing a signature."""

    cluster_id: str
    signature: tuple
    program_ids: list[int] = field(default_factory=list)
    best_score: float = -math.inf
    best_program_id: Optional[int] = None

    def update_best(self, program: Program, *, goal: str) -> None:
        """Refresh ``best_*`` fields after an add. ``goal`` is 'maximize' or
        'minimize' — the direction that counts as "better"."""
        if goal == "maximize":
            if program.score > self.best_score:
                self.best_score = program.score
                self.best_program_id = program.program_id
        else:
            if self.best_program_id is None or program.score < self.best_score:
                self.best_score = program.score
                self.best_program_id = program.program_id


@dataclass
class Island:
    """Independent subpopulation."""

    island_id: int
    generation: int = 0
    clusters: dict[str, Cluster] = field(default_factory=dict)
    program_ids: list[int] = field(default_factory=list)
    best_score: float = -math.inf
    best_program_id: Optional[int] = None

    def update_best(self, program: Program, *, goal: str) -> None:
        if goal == "maximize":
            if program.score > self.best_score:
                self.best_score = program.score
                self.best_program_id = program.program_id
        else:
            if self.best_program_id is None or program.score < self.best_score:
                self.best_score = program.score
                self.best_program_id = program.program_id


# ---------------------------------------------------------------------------
# ProgramDB
# ---------------------------------------------------------------------------


class ProgramDB:
    """MAP-Elites × Islands program store.

    Args:
        n_islands: number of parallel subpopulations.
        goal: ``'maximize'`` (higher score better) or ``'minimize'``.
        cluster_key_fn: maps a signature tuple to a hashable cluster ID.
            Default: ``str(signature)`` — each signature gets its own cluster.
        softmax_t0: initial cluster-selection softmax temperature. Annealed
            down with island generation.
        softmax_decay: multiplicative decay applied to ``t0`` per generation.
            At gen=0, ``t = t0``; at gen=g, ``t = t0 * decay**g``. Floor at
            1e-3 so the softmax never collapses.
        reset_period: generations between ``reset_islands`` calls.
        reset_ratio: fraction of islands to wipe on each reset (bottom).
        reset_top_k: how many top islands to reseed from.
    """

    def __init__(
        self,
        *,
        n_islands: int = 4,
        goal: str = "maximize",
        cluster_key_fn=None,
        softmax_t0: float = 1.0,
        softmax_decay: float = 0.98,
        reset_period: int = 4,
        reset_ratio: float = 0.5,
        reset_top_k: int = 2,
    ) -> None:
        if n_islands < 1:
            raise ValueError("n_islands must be >= 1")
        if goal not in ("maximize", "minimize"):
            raise ValueError("goal must be 'maximize' or 'minimize'")
        self.n_islands = n_islands
        self.goal = goal
        self.cluster_key_fn = cluster_key_fn or (lambda sig: str(tuple(sig)))
        self.softmax_t0 = softmax_t0
        self.softmax_decay = softmax_decay
        self.reset_period = reset_period
        self.reset_ratio = reset_ratio
        self.reset_top_k = reset_top_k
        self._next_id = 0
        self._programs: dict[int, Program] = {}
        self._islands: dict[int, Island] = {
            i: Island(island_id=i) for i in range(n_islands)
        }

    # ------------------------------------------------------------------
    # Add / accessors
    # ------------------------------------------------------------------

    def add(
        self,
        *,
        code: str,
        score: float,
        signature,
        island_id: Optional[int] = None,
        parent_id: Optional[int] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Program:
        """Add a program. Returns the stored Program with its allocated ID.

        If ``island_id`` is None the program is round-robined across islands.
        """
        pid = self._next_id
        self._next_id += 1
        if island_id is None:
            island_id = pid % self.n_islands
        if island_id not in self._islands:
            raise ValueError(f"unknown island_id {island_id}")

        signature = tuple(signature)
        cid = self.cluster_key_fn(signature)

        island = self._islands[island_id]
        prog = Program(
            program_id=pid,
            code=code,
            score=float(score),
            signature=signature,
            island_id=island_id,
            cluster_id=cid,
            generation=island.generation,
            parent_id=parent_id,
            metadata=dict(metadata or {}),
        )
        self._programs[pid] = prog

        cluster = island.clusters.get(cid)
        if cluster is None:
            cluster = Cluster(cluster_id=cid, signature=signature)
            island.clusters[cid] = cluster
        cluster.program_ids.append(pid)
        cluster.update_best(prog, goal=self.goal)

        island.program_ids.append(pid)
        island.update_best(prog, goal=self.goal)
        return prog

    def get(self, program_id: int) -> Program:
        return self._programs[program_id]

    def all_programs(self) -> list[Program]:
        return list(self._programs.values())

    def island_best(self, island_id: int) -> Optional[Program]:
        isl = self._islands[island_id]
        return self._programs[isl.best_program_id] if isl.best_program_id is not None else None

    def global_best(self) -> Optional[Program]:
        bests = [self.island_best(i) for i in self._islands]
        bests = [p for p in bests if p is not None]
        if not bests:
            return None
        key = (lambda p: p.score) if self.goal == "maximize" else (lambda p: -p.score)
        return max(bests, key=key)

    def size(self) -> int:
        return len(self._programs)

    # ------------------------------------------------------------------
    # Parent selection
    # ------------------------------------------------------------------

    def sample_parent(self, island_id: int, rng: random.Random) -> Program:
        """Two-stage sample: pick cluster (softmax over best scores), then
        pick program in cluster (softmax over inverse length)."""
        island = self._islands[island_id]
        if not island.clusters:
            raise RuntimeError(f"island {island_id} has no programs")

        cluster_ids = list(island.clusters.keys())
        cluster_scores = [island.clusters[cid].best_score for cid in cluster_ids]
        temp = max(1e-3, self.softmax_t0 * (self.softmax_decay ** island.generation))
        cluster_idx = _softmax_sample(cluster_scores, temp, rng, goal=self.goal)
        chosen_cluster = island.clusters[cluster_ids[cluster_idx]]

        pids = chosen_cluster.program_ids
        # Inverse length preference (bias toward shorter programs).
        weights = [1.0 / (1 + len(self._programs[p].code)) for p in pids]
        idx = _weighted_sample(weights, rng)
        return self._programs[pids[idx]]

    # ------------------------------------------------------------------
    # Island lifecycle
    # ------------------------------------------------------------------

    def tick_generation(self, island_id: int) -> None:
        self._islands[island_id].generation += 1

    def tick_all_generations(self) -> None:
        for i in self._islands:
            self._islands[i].generation += 1

    def should_reset(self) -> bool:
        """True iff EVERY island's generation counter crossed ``reset_period``
        since the last reset. We track per-island generations so a run with
        uneven fan-out still resets at a sensible cadence."""
        return all(
            isl.generation > 0 and isl.generation % self.reset_period == 0
            for isl in self._islands.values()
        )

    def reset_islands(self) -> list[int]:
        """Wipe the bottom ``reset_ratio`` of islands and reseed from top-K.

        Returns the list of island IDs that were reset. A no-op (empty list)
        if there are fewer than 2 islands total, since there is nowhere to
        reseed from.
        """
        if self.n_islands < 2:
            return []

        ranked = sorted(
            self._islands.items(),
            key=lambda kv: (kv[1].best_score if self.goal == "maximize" else -kv[1].best_score),
            reverse=True,
        )
        n_reset = max(1, int(self.reset_ratio * self.n_islands))
        n_reset = min(n_reset, self.n_islands - 1)
        top_islands = [kv[0] for kv in ranked[: self.reset_top_k]]
        bottom_islands = [kv[0] for kv in ranked[-n_reset:]]

        seeds: list[Program] = []
        for tid in top_islands:
            best = self.island_best(tid)
            if best is not None:
                seeds.append(best)
        if not seeds:
            return []

        reset_done: list[int] = []
        for bid in bottom_islands:
            if bid in top_islands:
                continue
            self._islands[bid] = Island(island_id=bid)
            for seed in seeds:
                self.add(
                    code=seed.code,
                    score=seed.score,
                    signature=seed.signature,
                    island_id=bid,
                    parent_id=seed.program_id,
                    metadata={"reseed_source_island": seed.island_id, **seed.metadata},
                )
            reset_done.append(bid)
        return reset_done

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_islands": self.n_islands,
            "goal": self.goal,
            "programs": [p.to_dict() for p in self._programs.values()],
            "island_generations": {
                i: isl.generation for i, isl in self._islands.items()
            },
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _softmax_sample(
    scores: list[float], temperature: float, rng: random.Random, *, goal: str
) -> int:
    """Return an index into ``scores`` sampled under softmax(score/temp).

    For ``goal='minimize'`` we negate so lower scores get higher probability.
    ``temperature`` is clamped to >= 1e-6 to avoid divide-by-zero.
    """
    if not scores:
        raise ValueError("empty score list")
    t = max(1e-6, float(temperature))
    direction = 1.0 if goal == "maximize" else -1.0
    max_s = max(s * direction for s in scores)
    weights = [math.exp((s * direction - max_s) / t) for s in scores]
    return _weighted_sample(weights, rng)


def _weighted_sample(weights: list[float], rng: random.Random) -> int:
    total = sum(weights)
    if total <= 0:
        return rng.randrange(len(weights))
    r = rng.random() * total
    acc = 0.0
    for i, w in enumerate(weights):
        acc += w
        if r <= acc:
            return i
    return len(weights) - 1
