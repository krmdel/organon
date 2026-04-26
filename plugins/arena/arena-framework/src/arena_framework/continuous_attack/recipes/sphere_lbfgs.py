"""Sphere-manifold L-BFGS + basin-hop recipe for ``sphere_minimize`` problems.

Generalises the Session-5 ``attack_thomson.py`` driver. Parameters (n, d)
are inferred from the problem's ``solutionSchema`` text when not overridden
via ``config``. An analytic objective-plus-gradient in ambient
:math:`\\mathbb{R}^{n \\cdot d}` may be passed through ``config["objective_and_grad"]``;
when absent, scipy's numerical gradient is used against the arena evaluator.

Method (matches the reference driver):
  1. Optional warm start — if ``start_candidate`` is provided, L-BFGS-polish it.
  2. Phase 1 (``phase1_fraction`` of wall budget) — random-sphere restarts with
     L-BFGS at ``maxiter_lbfgs`` iterations each.
  3. Phase 2 (remainder) — basin-hop around the current best with Gaussian
     perturbation (``basin_hop_noise``), re-project onto unit sphere, polish.

The arena verifier projects submitted vectors to the unit sphere, so the
recipe also projects before scoring each candidate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import numpy as np
from scipy.optimize import minimize

from arena_framework.primitives.budget import Budget

from ..recipe import AttackResult
from ..registry import register_recipe


@dataclass
class SphereLBFGSConfig:
    """Configuration for :class:`SphereLBFGSRecipe`.

    Fields with sensible defaults can be omitted from a caller's config
    dict; ``n`` / ``d`` are usually inferred from ``solutionSchema``.
    """

    n: int = 0
    d: int = 3
    n_restarts: int = 30
    maxiter_lbfgs: int = 800
    basin_hop_maxiter: int = 1200
    basin_hop_noise: float = 0.08
    phase1_fraction: float = 0.5
    seed: int = 42
    # Optional: (flat_x) -> (f, grad) in ambient coordinates. When present,
    # L-BFGS uses the analytic gradient; when absent, scipy falls back to
    # numerical gradient on the arena evaluator.
    objective_and_grad: Optional[Callable[[np.ndarray], tuple[float, np.ndarray]]] = (
        None
    )


def _infer_n_from_schema(schema: dict[str, Any]) -> int:
    for v in schema.values():
        m = re.search(r"array of (\d+) points", str(v).lower())
        if m:
            return int(m.group(1))
        m2 = re.search(r"(\d+)\s*points", str(v).lower())
        if m2:
            return int(m2.group(1))
    return 0


def _infer_d_from_schema(schema: dict[str, Any]) -> int:
    for v in schema.values():
        s = str(v).lower()
        if "[x, y, z]" in s:
            return 3
        if "[x, y]" in s:
            return 2
    return 3


def _project_to_sphere(x_flat: np.ndarray, n: int, d: int) -> np.ndarray:
    x = x_flat.reshape(n, d)
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    norms = np.where(norms < 1e-12, 1e-12, norms)
    return (x / norms).reshape(-1)


class SphereLBFGSRecipe:
    """Continuous-attack recipe for ``sphere_minimize`` problems.

    Shape requirement: solution is ``n`` points in :math:`\\mathbb{R}^d`
    with the arena verifier normalising to unit sphere before scoring.
    ``n`` and ``d`` are inferred from the problem's solution schema when
    possible.
    """

    name: str = "sphere_lbfgs"
    problem_classes: tuple[str, ...] = ("sphere_minimize",)

    def attack(
        self,
        *,
        evaluator: Callable[[Any], float],
        rigorous_evaluator: Optional[
            Callable[[Any], tuple[float, dict[str, Any]]]
        ] = None,
        start_candidate: Any | None = None,
        solution_schema: dict[str, Any],
        scoring: str,
        budget: Budget,
        config: dict[str, Any] | None = None,
    ) -> AttackResult:
        cfg = self._build_config(config, solution_schema)
        if cfg.n <= 0:
            raise ValueError(
                f"SphereLBFGSRecipe: could not infer n from schema {solution_schema!r}; "
                f"pass n=... in config"
            )
        return self._run(evaluator, start_candidate, cfg, budget)

    def _build_config(
        self,
        config: Optional[dict[str, Any]],
        solution_schema: dict[str, Any],
    ) -> SphereLBFGSConfig:
        raw = dict(config or {})
        if "n" not in raw:
            raw["n"] = _infer_n_from_schema(solution_schema or {})
        if "d" not in raw:
            raw["d"] = _infer_d_from_schema(solution_schema or {})
        allowed = set(SphereLBFGSConfig.__dataclass_fields__)
        filtered = {k: v for k, v in raw.items() if k in allowed}
        return SphereLBFGSConfig(**filtered)

    def _run(
        self,
        evaluator: Callable[[Any], float],
        start_candidate: Any | None,
        cfg: SphereLBFGSConfig,
        budget: Budget,
    ) -> AttackResult:
        rng = np.random.default_rng(cfg.seed)
        clock = budget.started()

        def _arena_score(flat_x: np.ndarray) -> float:
            clock.tick_evaluation()
            x = flat_x.reshape(cfg.n, cfg.d)
            return float(evaluator(x.tolist()))

        def _lbfgs(x0_flat: np.ndarray, maxiter: int) -> tuple[float, np.ndarray]:
            if cfg.objective_and_grad is not None:
                res = minimize(
                    cfg.objective_and_grad,
                    x0_flat,
                    jac=True,
                    method="L-BFGS-B",
                    options={"maxiter": maxiter, "gtol": 1e-10, "ftol": 1e-12},
                )
            else:
                res = minimize(
                    _arena_score,
                    x0_flat,
                    method="L-BFGS-B",
                    options={"maxiter": maxiter, "gtol": 1e-8, "ftol": 1e-10},
                )
            return float(res.fun), np.asarray(res.x)

        def _random_start() -> np.ndarray:
            x = rng.standard_normal((cfg.n, cfg.d))
            x /= np.linalg.norm(x, axis=1, keepdims=True)
            return x.reshape(-1)

        best_score = float("inf")
        best_x: Optional[np.ndarray] = None
        phase_history: list[dict[str, Any]] = []

        # Warm start
        if start_candidate is not None:
            x0 = np.asarray(start_candidate, dtype=np.float64).reshape(-1)
            x0 = _project_to_sphere(x0, cfg.n, cfg.d)
            _, x_warm = _lbfgs(x0, cfg.maxiter_lbfgs)
            arena_s = _arena_score(x_warm)
            if arena_s < best_score:
                best_score = arena_s
                best_x = x_warm
            phase_history.append(
                {
                    "phase": "warmstart",
                    "score": arena_s,
                    "t": clock.elapsed_s(),
                }
            )
            clock.tick_iteration()

        # Phase 1: random restarts
        n_restarts = 0
        phase1_wall_s = (
            (budget.wall_clock_s * cfg.phase1_fraction)
            if budget.wall_clock_s is not None
            else None
        )
        while (
            not clock.exhausted()
            and n_restarts < cfg.n_restarts
            and (phase1_wall_s is None or clock.elapsed_s() < phase1_wall_s)
        ):
            _, x = _lbfgs(_random_start(), cfg.maxiter_lbfgs)
            arena_s = _arena_score(x)
            n_restarts += 1
            clock.tick_iteration()
            if arena_s < best_score:
                best_score = arena_s
                best_x = x
                phase_history.append(
                    {
                        "phase": "random",
                        "i": n_restarts,
                        "score": arena_s,
                        "t": clock.elapsed_s(),
                        "accept": True,
                    }
                )

        # Phase 2: basin hop around best
        n_basin_hops = 0
        while not clock.exhausted() and best_x is not None:
            x_struct = best_x.reshape(cfg.n, cfg.d)
            perturbation = rng.standard_normal(x_struct.shape) * cfg.basin_hop_noise
            x0_struct = x_struct + perturbation
            x0_struct /= np.linalg.norm(x0_struct, axis=1, keepdims=True)
            _, x = _lbfgs(x0_struct.reshape(-1), cfg.basin_hop_maxiter)
            arena_s = _arena_score(x)
            n_basin_hops += 1
            clock.tick_iteration()
            if arena_s < best_score:
                best_score = arena_s
                best_x = x
                phase_history.append(
                    {
                        "phase": "basin_hop",
                        "i": n_basin_hops,
                        "score": arena_s,
                        "t": clock.elapsed_s(),
                        "accept": True,
                    }
                )

        best_state: Optional[list[list[float]]] = None
        if best_x is not None:
            best_state = best_x.reshape(cfg.n, cfg.d).tolist()

        return AttackResult(
            best_score=best_score if best_x is not None else float("inf"),
            best_state=best_state,
            n_iterations=clock.iterations,
            n_evaluations=clock.evaluations,
            wall_time_s=clock.elapsed_s(),
            primitive_metadata={
                "n": cfg.n,
                "d": cfg.d,
                "seed": cfg.seed,
                "used_analytic_grad": cfg.objective_and_grad is not None,
            },
            recipe_name=self.name,
            problem_class="sphere_minimize",
            n_restarts=n_restarts,
            n_basin_hops=n_basin_hops,
            phase_history=phase_history,
        )


# Register on import
register_recipe("sphere_minimize", SphereLBFGSRecipe)
