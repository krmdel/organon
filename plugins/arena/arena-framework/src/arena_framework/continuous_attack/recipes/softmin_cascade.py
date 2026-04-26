"""Soft-min β-cascade recipe for ``sphere_maximize_mindist`` problems.

Generalises the Session-5 ``attack_tammes.py`` driver. The objective
(minimum pairwise Euclidean distance on the unit sphere) is non-smooth,
so L-BFGS alone stalls at kinks. Trick: replace ``min_i d_i`` with the
soft-min ``s_β = -(1/β) log Σ exp(-β d_i)`` which converges to ``min_i d_i``
as β → ∞. Minimise ``-s_β`` with L-BFGS, anneal β up a cascade, basin-hop.

Callers supply ``objective_and_grad_at_beta(flat_x, beta) -> (loss, grad)``
in ``config`` — a closure that bakes the specific geometry. The recipe
handles the cascade loop, seed diversity (Fibonacci-sphere seeds for
sphere problems), and basin-hop schedule.

This shape covers Tammes directly and generalises to any
"distribute points to maximise minimum pairwise spacing" problem.
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


DEFAULT_BETA_SCHEDULE: tuple[float, ...] = (50.0, 200.0, 1000.0, 5000.0, 20000.0, 100000.0)
DEFAULT_NOISE_SCHEDULE: tuple[float, ...] = (0.02, 0.05, 0.02, 0.01, 0.03)


@dataclass
class SoftminCascadeConfig:
    """Configuration for :class:`SoftminCascadeRecipe`.

    ``objective_and_grad_at_beta`` is required — the recipe has no generic
    gradient shortcut because the objective is non-smooth. Callers are
    expected to supply the β-parametric soft-min they want minimised.
    """

    n: int = 0
    d: int = 3
    n_restarts: int = 30
    maxiter_lbfgs: int = 300
    basin_hop_maxiter: int = 500
    phase1_fraction: float = 0.5
    beta_schedule: tuple[float, ...] = DEFAULT_BETA_SCHEDULE
    noise_schedule: tuple[float, ...] = DEFAULT_NOISE_SCHEDULE
    use_fibonacci_seeds: bool = True
    seed: int = 42
    objective_and_grad_at_beta: Optional[
        Callable[[np.ndarray, float], tuple[float, np.ndarray]]
    ] = None


def _infer_n_from_schema(schema: dict[str, Any]) -> int:
    for v in schema.values():
        m = re.search(r"array of (\d+) points", str(v).lower())
        if m:
            return int(m.group(1))
    return 0


def _infer_d_from_schema(schema: dict[str, Any]) -> int:
    for v in schema.values():
        s = str(v).lower()
        if "[x, y, z]" in s:
            return 3
        if "[x, y]" in s:
            return 2
    return 3


def _fibonacci_sphere(n: int, rng: np.random.Generator) -> np.ndarray:
    """Fibonacci-sphere point distribution with a small random rotation.

    Near-optimal warm start for packing / Tammes-style problems on ``S^2``.
    The random rotation breaks symmetry so repeated calls give different
    starts — useful for seed diversity.
    """
    idx = np.arange(n, dtype=np.float64) + 0.5
    phi = np.arccos(1.0 - 2.0 * idx / n)
    theta = np.pi * (1 + 5 ** 0.5) * idx
    pts = np.stack(
        [np.sin(phi) * np.cos(theta), np.sin(phi) * np.sin(theta), np.cos(phi)],
        axis=1,
    )
    rot = rng.standard_normal((3, 3))
    q, _ = np.linalg.qr(rot)
    return pts @ q.T


def _random_sphere(n: int, d: int, rng: np.random.Generator) -> np.ndarray:
    x = rng.standard_normal((n, d))
    x /= np.linalg.norm(x, axis=1, keepdims=True)
    return x


class SoftminCascadeRecipe:
    """Continuous-attack recipe for ``sphere_maximize_mindist`` problems.

    Shape: ``n`` points in :math:`\\mathbb{R}^d` projected to unit sphere
    before scoring. Callers provide ``objective_and_grad_at_beta`` in
    config — a closure over the specific soft-min objective they want.
    """

    name: str = "softmin_cascade"
    problem_classes: tuple[str, ...] = ("sphere_maximize_mindist",)

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
                f"SoftminCascadeRecipe: could not infer n from schema "
                f"{solution_schema!r}; pass n=... in config"
            )
        if cfg.objective_and_grad_at_beta is None:
            raise ValueError(
                "SoftminCascadeRecipe requires config['objective_and_grad_at_beta'] "
                "(callable (flat_x, beta) -> (loss, grad)) — recipe has no generic "
                "non-smooth fallback."
            )
        return self._run(evaluator, start_candidate, cfg, budget)

    def _build_config(
        self,
        config: Optional[dict[str, Any]],
        solution_schema: dict[str, Any],
    ) -> SoftminCascadeConfig:
        raw = dict(config or {})
        if "n" not in raw:
            raw["n"] = _infer_n_from_schema(solution_schema or {})
        if "d" not in raw:
            raw["d"] = _infer_d_from_schema(solution_schema or {})
        # Tuple-ify schedules if caller passed lists
        if "beta_schedule" in raw and not isinstance(raw["beta_schedule"], tuple):
            raw["beta_schedule"] = tuple(raw["beta_schedule"])
        if "noise_schedule" in raw and not isinstance(raw["noise_schedule"], tuple):
            raw["noise_schedule"] = tuple(raw["noise_schedule"])
        allowed = set(SoftminCascadeConfig.__dataclass_fields__)
        filtered = {k: v for k, v in raw.items() if k in allowed}
        return SoftminCascadeConfig(**filtered)

    def _cascade(
        self,
        x0_flat: np.ndarray,
        objective_and_grad_at_beta: Callable[
            [np.ndarray, float], tuple[float, np.ndarray]
        ],
        beta_schedule: tuple[float, ...],
        maxiter: int,
    ) -> np.ndarray:
        x = x0_flat
        for beta in beta_schedule:
            res = minimize(
                lambda v, b=beta: objective_and_grad_at_beta(v, b),
                x,
                jac=True,
                method="L-BFGS-B",
                options={"maxiter": maxiter, "gtol": 1e-10, "ftol": 1e-13},
            )
            x = np.asarray(res.x)
        return x

    def _run(
        self,
        evaluator: Callable[[Any], float],
        start_candidate: Any | None,
        cfg: SoftminCascadeConfig,
        budget: Budget,
    ) -> AttackResult:
        assert cfg.objective_and_grad_at_beta is not None  # guarded in attack()
        rng = np.random.default_rng(cfg.seed)
        clock = budget.started()

        def _arena_score(x_struct: np.ndarray) -> float:
            clock.tick_evaluation()
            return float(evaluator(x_struct.tolist()))

        best_score = -float("inf")
        best_x: Optional[np.ndarray] = None
        phase_history: list[dict[str, Any]] = []

        # Warm start
        if start_candidate is not None:
            x0 = np.asarray(start_candidate, dtype=np.float64).reshape(cfg.n, cfg.d)
            norms = np.linalg.norm(x0, axis=1, keepdims=True)
            norms = np.where(norms < 1e-12, 1e-12, norms)
            x0 = x0 / norms
            x_flat = self._cascade(
                x0.reshape(-1),
                cfg.objective_and_grad_at_beta,
                cfg.beta_schedule,
                cfg.maxiter_lbfgs,
            )
            arena_s = _arena_score(x_flat.reshape(cfg.n, cfg.d))
            if arena_s > best_score:
                best_score = arena_s
                best_x = x_flat
            phase_history.append(
                {
                    "phase": "warmstart",
                    "score": arena_s,
                    "t": clock.elapsed_s(),
                }
            )
            clock.tick_iteration()

        # Phase 1: Fibonacci + random seeds with β-cascade
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
            if cfg.use_fibonacci_seeds and cfg.d == 3 and (
                n_restarts == 0 or n_restarts % 3 == 0
            ):
                x0 = _fibonacci_sphere(cfg.n, rng)
            else:
                x0 = _random_sphere(cfg.n, cfg.d, rng)
            x_flat = self._cascade(
                x0.reshape(-1),
                cfg.objective_and_grad_at_beta,
                cfg.beta_schedule,
                cfg.maxiter_lbfgs,
            )
            arena_s = _arena_score(x_flat.reshape(cfg.n, cfg.d))
            n_restarts += 1
            clock.tick_iteration()
            if arena_s > best_score:
                best_score = arena_s
                best_x = x_flat
                phase_history.append(
                    {
                        "phase": "seed",
                        "i": n_restarts,
                        "score": arena_s,
                        "t": clock.elapsed_s(),
                        "accept": True,
                    }
                )

        # Phase 2: basin hop around best with cyclic noise schedule
        n_basin_hops = 0
        while not clock.exhausted() and best_x is not None:
            noise = cfg.noise_schedule[n_basin_hops % len(cfg.noise_schedule)]
            x_struct = best_x.reshape(cfg.n, cfg.d)
            perturbation = rng.standard_normal(x_struct.shape) * noise
            x0 = x_struct + perturbation
            x0 /= np.linalg.norm(x0, axis=1, keepdims=True)
            x_flat = self._cascade(
                x0.reshape(-1),
                cfg.objective_and_grad_at_beta,
                cfg.beta_schedule,
                cfg.basin_hop_maxiter,
            )
            arena_s = _arena_score(x_flat.reshape(cfg.n, cfg.d))
            n_basin_hops += 1
            clock.tick_iteration()
            if arena_s > best_score:
                best_score = arena_s
                best_x = x_flat
                phase_history.append(
                    {
                        "phase": "basin_hop",
                        "i": n_basin_hops,
                        "score": arena_s,
                        "t": clock.elapsed_s(),
                        "noise": noise,
                        "accept": True,
                    }
                )

        best_state: Optional[list[list[float]]] = None
        if best_x is not None:
            best_state = best_x.reshape(cfg.n, cfg.d).tolist()

        return AttackResult(
            best_score=best_score if best_x is not None else -float("inf"),
            best_state=best_state,
            n_iterations=clock.iterations,
            n_evaluations=clock.evaluations,
            wall_time_s=clock.elapsed_s(),
            primitive_metadata={
                "n": cfg.n,
                "d": cfg.d,
                "seed": cfg.seed,
                "beta_schedule": list(cfg.beta_schedule),
            },
            recipe_name=self.name,
            problem_class="sphere_maximize_mindist",
            n_restarts=n_restarts,
            n_basin_hops=n_basin_hops,
            phase_history=phase_history,
        )


# Register on import
register_recipe("sphere_maximize_mindist", SoftminCascadeRecipe)
