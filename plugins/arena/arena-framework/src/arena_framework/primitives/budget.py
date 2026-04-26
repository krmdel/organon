"""Common Budget + Manifold + Result contracts used by every primitive."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Protocol


@dataclass
class Budget:
    """Caps wall-clock seconds, iteration count, or loss evaluations.

    Any cap set to ``None`` is disabled. The primitive should respect
    whichever cap is hit first.
    """

    wall_clock_s: Optional[float] = None
    max_iterations: Optional[int] = None
    max_evaluations: Optional[int] = None

    def started(self, *, now: Optional[float] = None) -> "BudgetClock":
        return BudgetClock(self, start_time=now if now is not None else time.monotonic())


@dataclass
class BudgetClock:
    """Mutable clock tracking progress against a Budget."""

    budget: Budget
    start_time: float
    iterations: int = 0
    evaluations: int = 0

    def tick_iteration(self) -> None:
        self.iterations += 1

    def tick_evaluation(self) -> None:
        self.evaluations += 1

    def elapsed_s(self) -> float:
        return time.monotonic() - self.start_time

    def exhausted(self) -> bool:
        b = self.budget
        if b.wall_clock_s is not None and self.elapsed_s() >= b.wall_clock_s:
            return True
        if b.max_iterations is not None and self.iterations >= b.max_iterations:
            return True
        if b.max_evaluations is not None and self.evaluations >= b.max_evaluations:
            return True
        return False


class Manifold(Protocol):
    """Search-space abstraction. State is opaque to primitives."""

    def sample_initial(self, rng) -> Any: ...

    def perturb(self, state: Any, *, temperature: float, rng) -> Any: ...


@dataclass
class PrimitiveResult:
    """Common shape returned by every optimization primitive."""

    best_score: float
    best_state: Any
    n_iterations: int
    n_evaluations: int
    wall_time_s: float
    trace: list[dict[str, Any]] = field(default_factory=list)
    primitive_metadata: dict[str, Any] = field(default_factory=dict)
