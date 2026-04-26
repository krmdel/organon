"""β-annealed smooth-max recipe for ``nonneg_function_maximize`` problems.

Generalises the Session-5 ``attack_second_autocorr.py`` driver and
covers C1 / C2 / C3 autocorrelation inequalities (plus any future
"maximise a scale-invariant functional of a non-negative 1-D function"
problem).

Method
------
1. Parametrise ``f = x**2`` to enforce non-negativity while keeping x free
   on ℝ.
2. Cascade L-BFGS at increasing β against caller-supplied
   ``loss_and_grad_at_beta(x, beta) → (-C, -grad C)``. ``beta=0`` means
   hard-max (the final polish stage).
3. After each start, run a final hard-max polish (``beta=0``).
4. Phase 1 uses ``phase1_fraction`` of wall; phase 2 basin-hops around
   the current best with Gaussian perturbation in x-space.

The recipe does NOT own the gradient: each problem family has a
different functional (C1, C2, C3 differ in how L2 / L1 / Linf are
combined) so callers pass a closure over their own objective.
Basin-hop perturbation is clamped positive to keep f = x**2 sensible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import numpy as np
from scipy.optimize import minimize

from arena_framework.primitives.budget import Budget

from ..recipe import AttackResult
from ..registry import register_recipe


#: Default β cascade — matches Session-5 attack_second_autocorr.py.
DEFAULT_BETA_SCHEDULE: tuple[float, ...] = (20.0, 80.0, 400.0, 2000.0, 10000.0, 1.0e5)


@dataclass
class NonnegSmoothMaxConfig:
    """Configuration for :class:`NonnegSmoothMaxRecipe`.

    ``n_grid`` is required — the discretisation size of the function
    array. ``loss_and_grad_at_beta`` is also required: the recipe refuses
    to guess the β-smoothed objective's gradient for arbitrary
    autocorrelation functionals.
    """

    n_grid: int = 0
    n_restarts: int = 30
    maxiter_lbfgs: int = 600
    maxiter_final: int = 1200
    basin_hop_maxiter: int = 600
    basin_hop_noise: float = 0.05
    phase1_fraction: float = 0.5
    beta_schedule: tuple[float, ...] = DEFAULT_BETA_SCHEDULE
    seed: int = 42
    loss_and_grad_at_beta: Optional[
        Callable[[np.ndarray, float], tuple[float, np.ndarray]]
    ] = None
    start_candidate_fn: Optional[
        Callable[[int, np.random.Generator], np.ndarray]
    ] = None


def _uniform_positive_start(n_grid: int, rng: np.random.Generator) -> np.ndarray:
    return rng.uniform(0.1, 1.0, size=n_grid)


class NonnegSmoothMaxRecipe:
    """Continuous-attack recipe for ``nonneg_function_maximize`` problems.

    Covers the first / second / third autocorrelation inequalities and
    any future "maximise a functional of a non-negative 1-D function"
    shape. Supply the β-parametric loss + gradient via config.
    """

    name: str = "nonneg_smooth_max"
    problem_classes: tuple[str, ...] = ("nonneg_function_maximize",)

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
        cfg = self._build_config(config)
        if cfg.n_grid <= 0:
            raise ValueError(
                "NonnegSmoothMaxRecipe: config['n_grid'] must be set to a positive "
                "integer (the function discretisation size); schema does not "
                "fix it for autocorrelation problems."
            )
        if cfg.loss_and_grad_at_beta is None:
            raise ValueError(
                "NonnegSmoothMaxRecipe requires config['loss_and_grad_at_beta'] "
                "(callable (x, beta) -> (loss, grad)) — recipe has no generic "
                "functional to optimise."
            )
        return self._run(evaluator, start_candidate, cfg, budget)

    def _build_config(
        self,
        config: Optional[dict[str, Any]],
    ) -> NonnegSmoothMaxConfig:
        raw = dict(config or {})
        if "beta_schedule" in raw and not isinstance(raw["beta_schedule"], tuple):
            raw["beta_schedule"] = tuple(raw["beta_schedule"])
        allowed = set(NonnegSmoothMaxConfig.__dataclass_fields__)
        filtered = {k: v for k, v in raw.items() if k in allowed}
        return NonnegSmoothMaxConfig(**filtered)

    def _run_cascade(
        self,
        x0: np.ndarray,
        cfg: NonnegSmoothMaxConfig,
        *,
        maxiter: int,
        maxiter_final: int,
    ) -> np.ndarray:
        x = x0.copy()
        assert cfg.loss_and_grad_at_beta is not None
        for beta in cfg.beta_schedule:
            res = minimize(
                lambda v, b=beta: cfg.loss_and_grad_at_beta(v, b),
                x,
                jac=True,
                method="L-BFGS-B",
                options={"maxiter": maxiter, "gtol": 1e-10, "ftol": 1e-13},
            )
            x = np.asarray(res.x)
        # Final hard-max polish (beta = 0)
        res = minimize(
            lambda v: cfg.loss_and_grad_at_beta(v, 0.0),
            x,
            jac=True,
            method="L-BFGS-B",
            options={"maxiter": maxiter_final, "gtol": 1e-11, "ftol": 1e-14},
        )
        return np.asarray(res.x)

    def _run(
        self,
        evaluator: Callable[[Any], float],
        start_candidate: Any | None,
        cfg: NonnegSmoothMaxConfig,
        budget: Budget,
    ) -> AttackResult:
        rng = np.random.default_rng(cfg.seed)
        clock = budget.started()

        start_fn = cfg.start_candidate_fn or _uniform_positive_start

        def _arena_score_from_x(x: np.ndarray) -> float:
            clock.tick_evaluation()
            values = (x ** 2).tolist()
            return float(evaluator(values))

        best_score = -float("inf")
        best_x: Optional[np.ndarray] = None
        phase_history: list[dict[str, Any]] = []

        # Warm start — caller hands over ``values`` (= f); we invert to x = sqrt(f)
        if start_candidate is not None:
            f0 = np.asarray(start_candidate, dtype=np.float64).reshape(-1)
            f0 = np.maximum(f0, 0.0)
            x0 = np.sqrt(f0)
            try:
                x = self._run_cascade(
                    x0, cfg,
                    maxiter=cfg.maxiter_lbfgs,
                    maxiter_final=cfg.maxiter_final,
                )
                arena_s = _arena_score_from_x(x)
                if arena_s > best_score:
                    best_score = arena_s
                    best_x = x
                phase_history.append(
                    {
                        "phase": "warmstart",
                        "score": arena_s,
                        "t": clock.elapsed_s(),
                    }
                )
            except Exception as exc:  # pragma: no cover - recorded + continue
                phase_history.append(
                    {
                        "phase": "warmstart",
                        "error": str(exc)[:200],
                        "t": clock.elapsed_s(),
                    }
                )
            clock.tick_iteration()

        # Phase 1: diverse seeds + β-cascade
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
            x0 = start_fn(cfg.n_grid, rng)
            try:
                x = self._run_cascade(
                    x0, cfg,
                    maxiter=cfg.maxiter_lbfgs,
                    maxiter_final=cfg.maxiter_final,
                )
                arena_s = _arena_score_from_x(x)
            except Exception as exc:  # pragma: no cover
                phase_history.append(
                    {
                        "phase": "seed",
                        "i": n_restarts + 1,
                        "error": str(exc)[:200],
                        "t": clock.elapsed_s(),
                    }
                )
                n_restarts += 1
                clock.tick_iteration()
                continue
            n_restarts += 1
            clock.tick_iteration()
            if arena_s > best_score:
                best_score = arena_s
                best_x = x
                phase_history.append(
                    {
                        "phase": "seed",
                        "i": n_restarts,
                        "score": arena_s,
                        "t": clock.elapsed_s(),
                        "accept": True,
                    }
                )

        # Phase 2: basin hop around best with Gaussian perturbation in x-space
        n_basin_hops = 0
        while not clock.exhausted() and best_x is not None:
            perturb_scale = cfg.basin_hop_noise * max(
                float(np.abs(best_x).mean()), 1e-6
            )
            x0 = best_x + rng.standard_normal(best_x.shape) * perturb_scale
            x0 = np.maximum(x0, 1e-6)
            try:
                x = self._run_cascade(
                    x0, cfg,
                    maxiter=cfg.basin_hop_maxiter,
                    maxiter_final=cfg.maxiter_final,
                )
                arena_s = _arena_score_from_x(x)
            except Exception as exc:  # pragma: no cover
                phase_history.append(
                    {
                        "phase": "basin_hop",
                        "i": n_basin_hops + 1,
                        "error": str(exc)[:200],
                        "t": clock.elapsed_s(),
                    }
                )
                n_basin_hops += 1
                clock.tick_iteration()
                continue
            n_basin_hops += 1
            clock.tick_iteration()
            if arena_s > best_score:
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

        best_state: Optional[list[float]] = None
        if best_x is not None:
            best_state = (best_x ** 2).tolist()

        return AttackResult(
            best_score=best_score if best_x is not None else -float("inf"),
            best_state=best_state,
            n_iterations=clock.iterations,
            n_evaluations=clock.evaluations,
            wall_time_s=clock.elapsed_s(),
            primitive_metadata={
                "n_grid": cfg.n_grid,
                "seed": cfg.seed,
                "beta_schedule": list(cfg.beta_schedule),
            },
            recipe_name=self.name,
            problem_class="nonneg_function_maximize",
            n_restarts=n_restarts,
            n_basin_hops=n_basin_hops,
            phase_history=phase_history,
        )


# Register on import
register_recipe("nonneg_function_maximize", NonnegSmoothMaxRecipe)
