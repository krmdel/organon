"""Parallel runner — verified best-of-N fan-out for attack loops (Upgrade U4).

Generalises the ``scripts/run_tracks.py`` pattern. Given a callable ``attack(seed, budget, **config)`` and a list of seed configurations, fans them out as
subprocesses (process-based parallelism, not threads — avoids Python GIL on the
sympy/mpmath evaluators that dominate our compute), waits, collects results,
and aggregates the best by the supplied scoring rule.

Budget discipline: every child has its own ``Budget`` carved from the
aggregate. The aggregate is enforced by a wall-clock watchdog that kills laggy
children when the parent's ``wall_clock_s`` is hit. Total LLM calls are capped
by ``LLMCallLimiter`` (see ``rate_limiter.py``) when children make LLM calls.

Result shape preserves the ``PrimitiveResult`` contract so parallel_run fits
into the existing orchestrator without new glue.

Example::

    from arena_framework.parallel_runner import parallel_run, SeedSpec

    seeds = [
        SeedSpec(seed=200, config={"noise": 0.01}),
        SeedSpec(seed=300, config={"noise": 0.01}),
        SeedSpec(seed=400, config={"noise": 0.02}),
    ]
    result = parallel_run(
        attack=my_attack_function,  # or a path to a subprocess script
        seeds=seeds,
        budget=Budget(wall_clock_s=1800),
        scorer=lambda r: r.best_score,
        minimize=True,
    )
    print(result.best_score, result.best_state)
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from .primitives.budget import Budget, PrimitiveResult


# ---------------------------------------------------------------------------
# Seed specification
# ---------------------------------------------------------------------------


@dataclass
class SeedSpec:
    """One child's configuration.

    ``seed`` is the RNG seed; ``config`` is an opaque dict passed through to
    the attack function. ``tag`` is a short name for logs.
    """

    seed: int
    config: dict[str, Any] = field(default_factory=dict)
    tag: str = ""

    def display_tag(self) -> str:
        return self.tag or f"seed-{self.seed}"


# ---------------------------------------------------------------------------
# Per-child result
# ---------------------------------------------------------------------------


@dataclass
class ChildResult:
    """Outcome of a single parallel child."""

    tag: str
    seed: int
    status: str  # "ok" | "killed_by_budget" | "error" | "missing"
    result: Optional[PrimitiveResult] = None
    error: Optional[str] = None
    wall_time_s: float = 0.0


@dataclass
class ParallelRunResult:
    """Aggregated outcome of a parallel fan-out."""

    best_child: Optional[ChildResult]
    all_children: list[ChildResult]
    wall_elapsed_s: float
    budget_exhausted: bool = False

    @property
    def best_score(self) -> Optional[float]:
        if self.best_child and self.best_child.result:
            return self.best_child.result.best_score
        return None

    @property
    def best_state(self) -> Any:
        if self.best_child and self.best_child.result:
            return self.best_child.result.best_state
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "best_tag": self.best_child.tag if self.best_child else None,
            "best_seed": self.best_child.seed if self.best_child else None,
            "best_score": self.best_score,
            "wall_elapsed_s": self.wall_elapsed_s,
            "budget_exhausted": self.budget_exhausted,
            "n_children": len(self.all_children),
            "n_ok": sum(1 for c in self.all_children if c.status == "ok"),
            "children": [
                {
                    "tag": c.tag,
                    "seed": c.seed,
                    "status": c.status,
                    "score": (c.result.best_score if c.result else None),
                    "wall_time_s": c.wall_time_s,
                    "error": c.error,
                }
                for c in self.all_children
            ],
        }


# ---------------------------------------------------------------------------
# In-process parallel runner (ProcessPoolExecutor)
# ---------------------------------------------------------------------------


def parallel_run(
    attack: Callable[..., PrimitiveResult],
    seeds: list[SeedSpec],
    *,
    budget: Budget,
    scorer: Callable[[PrimitiveResult], float] = lambda r: r.best_score,
    minimize: bool = True,
    max_workers: Optional[int] = None,
    per_child_budget_fraction: float = 1.0,
    kill_on_aggregate_timeout: bool = True,
) -> ParallelRunResult:
    """Fan out ``attack`` across ``seeds`` as separate processes.

    Each child gets its own ``Budget`` carved from the aggregate, scaled by
    ``per_child_budget_fraction``. The default 1.0 means each child has the
    full wall-clock budget (reasonable when children run concurrently and we
    want each to be able to use all the time). Set < 1.0 to divide work.

    ``scorer`` + ``minimize`` define the aggregation rule. The best child is
    whichever has the minimum (if minimize=True) or maximum (if False) score.

    Process-based parallelism via ``ProcessPoolExecutor``. For subprocess-based
    parallelism (when ``attack`` is a CLI script, not a Python callable),
    use ``parallel_run_subprocess`` instead.
    """
    if not seeds:
        return ParallelRunResult(best_child=None, all_children=[], wall_elapsed_s=0.0)

    n_workers = max_workers or min(len(seeds), os.cpu_count() or 4)
    child_budget = Budget(
        wall_clock_s=(
            budget.wall_clock_s * per_child_budget_fraction
            if budget.wall_clock_s is not None
            else None
        ),
        max_iterations=budget.max_iterations,
        max_evaluations=budget.max_evaluations,
    )

    t_start = time.monotonic()
    children: list[ChildResult] = []

    with concurrent.futures.ProcessPoolExecutor(max_workers=n_workers) as pool:
        futures: dict[concurrent.futures.Future, SeedSpec] = {}
        for spec in seeds:
            fut = pool.submit(
                _child_entrypoint, attack, spec.seed, spec.config, child_budget
            )
            futures[fut] = spec

        timeout = budget.wall_clock_s
        try:
            for fut in concurrent.futures.as_completed(futures, timeout=timeout):
                spec = futures[fut]
                t_child_end = time.monotonic()
                try:
                    res = fut.result()
                    children.append(
                        ChildResult(
                            tag=spec.display_tag(),
                            seed=spec.seed,
                            status="ok",
                            result=res,
                            wall_time_s=t_child_end - t_start,
                        )
                    )
                except Exception as exc:
                    children.append(
                        ChildResult(
                            tag=spec.display_tag(),
                            seed=spec.seed,
                            status="error",
                            error=str(exc),
                            wall_time_s=t_child_end - t_start,
                        )
                    )
        except (concurrent.futures.TimeoutError, TimeoutError):
            # Aggregate wall-clock hit. Mark any still-pending children as
            # killed_by_budget and cancel them (if requested).
            pass

        for fut, spec in futures.items():
            if fut.done():
                continue
            children.append(
                ChildResult(
                    tag=spec.display_tag(),
                    seed=spec.seed,
                    status="killed_by_budget",
                    wall_time_s=time.monotonic() - t_start,
                )
            )
            if kill_on_aggregate_timeout:
                fut.cancel()

    t_elapsed = time.monotonic() - t_start
    budget_exhausted = (
        budget.wall_clock_s is not None and t_elapsed >= budget.wall_clock_s
    )

    # Aggregate best
    best: Optional[ChildResult] = None
    for c in children:
        if c.status != "ok" or c.result is None:
            continue
        s = scorer(c.result)
        if best is None:
            best = c
            continue
        bs = scorer(best.result) if best.result else None
        if bs is None:
            best = c
        elif (minimize and s < bs) or (not minimize and s > bs):
            best = c

    return ParallelRunResult(
        best_child=best,
        all_children=children,
        wall_elapsed_s=t_elapsed,
        budget_exhausted=budget_exhausted,
    )


def _child_entrypoint(
    attack: Callable[..., PrimitiveResult],
    seed: int,
    config: dict[str, Any],
    budget: Budget,
) -> PrimitiveResult:
    """Runs in the child process. Must be module-level for pickling."""
    return attack(seed=seed, budget=budget, **config)


# ---------------------------------------------------------------------------
# Subprocess-based parallel runner (for CLI scripts)
# ---------------------------------------------------------------------------


@dataclass
class SubprocessSpec:
    """Specification for a subprocess-based child."""

    tag: str
    cmd: list[str]
    cwd: Optional[Path] = None
    summary_path: Optional[Path] = None  # JSON file to parse for the result


def parallel_run_subprocess(
    specs: list[SubprocessSpec],
    *,
    wall_clock_s: Optional[float] = None,
    log_dir: Optional[Path] = None,
    score_key: str = "best_score",
    minimize: bool = True,
    kill_on_timeout: bool = True,
) -> ParallelRunResult:
    """Fan out CLI subprocesses. Each spec's ``summary_path`` is expected to
    contain a JSON document after the child exits; the value at ``score_key``
    is the score used for aggregation.

    Handles the ``--flag=VALUE`` argparse gotcha already documented in
    ``scripts/run_tracks.py`` — callers should already use the ``=`` form for
    dash-leading values.
    """
    if not specs:
        return ParallelRunResult(best_child=None, all_children=[], wall_elapsed_s=0.0)

    if log_dir is not None:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

    t_start = time.monotonic()
    procs: list[tuple[SubprocessSpec, subprocess.Popen, Any]] = []
    for spec in specs:
        log_fh = None
        if log_dir is not None:
            log_fh = open(log_dir / f"{spec.tag}.log", "w")
        p = subprocess.Popen(
            spec.cmd,
            cwd=str(spec.cwd) if spec.cwd else None,
            stdout=log_fh,
            stderr=subprocess.STDOUT if log_fh else None,
        )
        procs.append((spec, p, log_fh))

    budget_exhausted = False
    deadline = t_start + wall_clock_s if wall_clock_s else None

    children: list[ChildResult] = []
    for spec, p, log_fh in procs:
        try:
            remaining = None
            if deadline is not None:
                remaining = max(0.1, deadline - time.monotonic())
            rc = p.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            budget_exhausted = True
            if kill_on_timeout:
                p.terminate()
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    p.kill()
                    p.wait()
            children.append(
                ChildResult(
                    tag=spec.tag,
                    seed=0,
                    status="killed_by_budget",
                    wall_time_s=time.monotonic() - t_start,
                )
            )
            continue
        finally:
            if log_fh is not None:
                log_fh.close()

        if rc != 0:
            children.append(
                ChildResult(
                    tag=spec.tag,
                    seed=0,
                    status="error",
                    error=f"exit_code={rc}",
                    wall_time_s=time.monotonic() - t_start,
                )
            )
            continue

        score = None
        metadata: dict[str, Any] = {}
        if spec.summary_path and spec.summary_path.exists():
            try:
                metadata = json.loads(spec.summary_path.read_text())
                score = metadata.get(score_key)
            except (OSError, json.JSONDecodeError) as exc:
                children.append(
                    ChildResult(
                        tag=spec.tag,
                        seed=0,
                        status="error",
                        error=f"summary_read_failed: {exc}",
                        wall_time_s=time.monotonic() - t_start,
                    )
                )
                continue

        result = (
            PrimitiveResult(
                best_score=float(score) if score is not None else float("inf"),
                best_state=metadata,
                n_iterations=0,
                n_evaluations=0,
                wall_time_s=time.monotonic() - t_start,
                primitive_metadata={"summary_path": str(spec.summary_path)},
            )
            if score is not None
            else None
        )
        children.append(
            ChildResult(
                tag=spec.tag,
                seed=0,
                status="ok" if result else "missing",
                result=result,
                wall_time_s=time.monotonic() - t_start,
            )
        )

    t_elapsed = time.monotonic() - t_start
    if wall_clock_s is not None and t_elapsed >= wall_clock_s:
        budget_exhausted = True

    best: Optional[ChildResult] = None
    for c in children:
        if c.status != "ok" or c.result is None:
            continue
        s = c.result.best_score
        if best is None or (minimize and s < best.result.best_score) or (
            not minimize and s > best.result.best_score
        ):
            best = c

    return ParallelRunResult(
        best_child=best,
        all_children=children,
        wall_elapsed_s=t_elapsed,
        budget_exhausted=budget_exhausted,
    )
