"""Parallel Tempering Simulated Annealing — CPU-first primitive.

N replicas run at geometrically-spaced inverse temperatures β₁ < … < βₙ.
Each replica performs a local Metropolis step; every ``swap_every`` iterations
adjacent replicas exchange states with Metropolis-Hastings acceptance. Low-β
replicas explore broadly; high-β replicas exploit the best basin found.

Designed after jmsung/einstein's ``gpu_tempering/core.py`` but without GPU
bindings. A GPU port can be dropped in as a subclass that overrides
``_propose_step``.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .budget import Budget, Manifold, PrimitiveResult


@dataclass
class PTSAConfig:
    """Hyperparameters for ParallelTemperingSA."""

    n_replicas: int = 8
    min_beta: float = 0.1  # highest temperature (most exploratory)
    max_beta: float = 100.0  # lowest temperature (most greedy)
    swap_every: int = 10
    seed: Optional[int] = None


@dataclass
class PTSAResult(PrimitiveResult):
    """Extends PrimitiveResult with PT-specific stats."""

    final_states: list[Any] = field(default_factory=list)
    final_scores: list[float] = field(default_factory=list)
    n_accepted_swaps: int = 0
    n_total_swaps: int = 0


class ParallelTemperingSA:
    """Problem-agnostic parallel tempering SA.

    Example usage::

        def rastrigin(x): return 10*len(x) + sum(xi*xi - 10*math.cos(2*math.pi*xi) for xi in x)

        class Rast2D:
            def sample_initial(self, rng): return [rng.uniform(-5, 5) for _ in range(2)]
            def perturb(self, s, *, temperature, rng):
                return [si + rng.gauss(0, max(0.01, 1.0/temperature)) for si in s]

        pt = ParallelTemperingSA(PTSAConfig(n_replicas=6))
        result = pt.run(rastrigin, Rast2D(), Budget(max_iterations=5000))
    """

    def __init__(self, config: PTSAConfig) -> None:
        if config.n_replicas < 2:
            raise ValueError("n_replicas must be >= 2")
        if config.min_beta <= 0 or config.max_beta <= 0:
            raise ValueError("temperatures must be positive")
        if config.min_beta >= config.max_beta:
            raise ValueError("min_beta must be < max_beta")
        self.config = config

    def _betas(self) -> list[float]:
        """Geometrically-spaced inverse temperatures."""
        n = self.config.n_replicas
        if n == 1:
            return [self.config.max_beta]
        ratio = (self.config.max_beta / self.config.min_beta) ** (1.0 / (n - 1))
        return [self.config.min_beta * (ratio ** i) for i in range(n)]

    def run(
        self,
        loss_fn: Callable[[Any], float],
        manifold: Manifold,
        budget: Budget,
        *,
        warm_start: Optional[list[Any]] = None,
    ) -> PTSAResult:
        rng = random.Random(self.config.seed)
        betas = self._betas()
        n = len(betas)

        # Initialise states and scores
        if warm_start is not None:
            if len(warm_start) != n:
                raise ValueError(f"warm_start length {len(warm_start)} != n_replicas {n}")
            states = list(warm_start)
        else:
            states = [manifold.sample_initial(rng) for _ in range(n)]
        scores = [float(loss_fn(s)) for s in states]
        n_evals = n

        # Track best ever seen
        best_score = min(scores)
        best_state = states[scores.index(best_score)]

        clock = budget.started()
        clock.iterations = 0
        clock.evaluations = n_evals

        n_accepted_swaps = 0
        n_total_swaps = 0
        trace: list[dict[str, Any]] = []

        while not clock.exhausted():
            # Local Metropolis step for each replica at its own β
            for i in range(n):
                candidate = manifold.perturb(states[i], temperature=1.0 / betas[i], rng=rng)
                cs = float(loss_fn(candidate))
                clock.tick_evaluation()
                d = cs - scores[i]
                accept = d <= 0 or rng.random() < math.exp(-betas[i] * d)
                if accept:
                    states[i] = candidate
                    scores[i] = cs
                    if cs < best_score:
                        best_score = cs
                        best_state = candidate
            clock.tick_iteration()

            # Swap proposals between adjacent replicas
            if clock.iterations % self.config.swap_every == 0:
                # Alternate even/odd swap rounds to decorrelate
                start = 0 if (clock.iterations // self.config.swap_every) % 2 == 0 else 1
                for i in range(start, n - 1, 2):
                    n_total_swaps += 1
                    delta = (betas[i] - betas[i + 1]) * (scores[i + 1] - scores[i])
                    if delta >= 0 or rng.random() < math.exp(delta):
                        states[i], states[i + 1] = states[i + 1], states[i]
                        scores[i], scores[i + 1] = scores[i + 1], scores[i]
                        n_accepted_swaps += 1

            # Periodic trace entry (every 10 iterations to keep the log small)
            if clock.iterations % 10 == 0:
                trace.append(
                    {
                        "iteration": clock.iterations,
                        "elapsed_s": clock.elapsed_s(),
                        "best_score": best_score,
                        "replica_scores": list(scores),
                    }
                )

            if clock.exhausted():
                break

        return PTSAResult(
            best_score=best_score,
            best_state=best_state,
            n_iterations=clock.iterations,
            n_evaluations=clock.evaluations,
            wall_time_s=clock.elapsed_s(),
            trace=trace,
            primitive_metadata={
                "primitive": "ParallelTemperingSA",
                "betas": betas,
                "n_replicas": n,
            },
            final_states=list(states),
            final_scores=list(scores),
            n_accepted_swaps=n_accepted_swaps,
            n_total_swaps=n_total_swaps,
        )
