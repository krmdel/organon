"""2D plane-packing recipe for ``plane_minimize_distance_ratio`` and
``plane_maximize_radius`` problems (U14/6).

2D analog of :class:`SphereLBFGSRecipe`. Differences:

* Euclidean 2D points — no manifold projection. Free ambient optimisation.
* Handles both ``minimize`` and ``maximize`` scoring (min-distance-ratio-2d
  is minimise; circle-packing / hexagon-packing / circles-rectangle are
  maximise). The recipe flips sign when feeding scipy's minimiser.
* Starts sample from a configurable region (``unit_square`` /
  ``unit_disc`` / ``rectangle``) rather than the unit sphere.
* Basin-hop keeps steps that stay in the starting region via rejection;
  callers needing hard barriers should supply ``objective_and_grad``
  encoding the penalty themselves.
* Optional Phase 3 simulated-annealing with geometric cooling when
  ``sa_enabled=True``.

As with :class:`SphereLBFGSRecipe`, an analytic
``objective_and_grad(flat_x) -> (f, grad)`` may be supplied via ``config``;
when absent scipy falls back to numerical gradients against the arena
evaluator. Caller-supplied gradients MUST already be expressed in
minimise form — this recipe does not flip them. (Consistent with the
other recipes: sphere_lbfgs + nonneg_smooth_max both require minimise-
form analytic gradients.)
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Callable, Optional

import numpy as np
from scipy.optimize import minimize

from arena_framework.primitives.budget import Budget

from ..recipe import AttackResult
from ..registry import register_recipe


_VALID_REGIONS = ("unit_square", "unit_disc", "rectangle")


@dataclass
class Plane2DPackingConfig:
    """Configuration for :class:`Plane2DPackingRecipe`.

    ``n`` is usually inferred from ``solutionSchema``. Container fields
    (``start_region``, ``rect_width``, ``rect_height``) only affect the
    random starts and basin-hop rejection gate — the arena verifier is
    ultimately what scores a submission.
    """

    n: int = 0
    n_restarts: int = 40
    maxiter_lbfgs: int = 400
    basin_hop_maxiter: int = 600
    basin_hop_noise: float = 0.05
    phase1_fraction: float = 0.6
    seed: int = 42
    start_region: str = "unit_square"
    rect_width: float = 1.0
    rect_height: float = 1.0
    # Optional analytic (flat_x) -> (f, grad) in MINIMISE form.
    objective_and_grad: Optional[
        Callable[[np.ndarray], tuple[float, np.ndarray]]
    ] = None
    # Phase 3 simulated annealing (off by default; cheap to enable).
    sa_enabled: bool = False
    sa_temperature: float = 0.01
    sa_cooling: float = 0.97
    sa_step: float = 0.02


def _infer_n_from_schema(schema: dict[str, Any]) -> int:
    for v in schema.values():
        s = str(v).lower()
        m = re.search(r"array of (\d+)", s)
        if m:
            return int(m.group(1))
        m2 = re.search(r"(\d+)\s*(?:points|coordinate pairs|\[x, y\])", s)
        if m2:
            return int(m2.group(1))
    return 0


def _sample_region(
    n: int, cfg: Plane2DPackingConfig, rng: np.random.Generator
) -> np.ndarray:
    """Return ``(n, 2)`` points inside the configured start region.

    ``unit_square``: ``[0, 1]^2``.
    ``unit_disc``: centred on origin, radius 1 (rejection sampling).
    ``rectangle``: ``[0, rect_width] x [0, rect_height]``.
    """
    if cfg.start_region == "unit_square":
        return rng.uniform(0.0, 1.0, size=(n, 2))
    if cfg.start_region == "rectangle":
        return np.column_stack(
            [
                rng.uniform(0.0, cfg.rect_width, size=n),
                rng.uniform(0.0, cfg.rect_height, size=n),
            ]
        )
    if cfg.start_region == "unit_disc":
        out = np.empty((n, 2), dtype=np.float64)
        filled = 0
        while filled < n:
            cand = rng.uniform(-1.0, 1.0, size=(2 * (n - filled), 2))
            keep = cand[np.einsum("ij,ij->i", cand, cand) <= 1.0]
            take = min(len(keep), n - filled)
            if take > 0:
                out[filled : filled + take] = keep[:take]
                filled += take
        return out
    raise ValueError(
        f"unknown start_region {cfg.start_region!r}; "
        f"must be one of {_VALID_REGIONS}"
    )


def _in_region(points: np.ndarray, cfg: Plane2DPackingConfig) -> bool:
    """Inclusive containment check for the configured start region.

    Used as a soft barrier in the basin-hop + SA phases: a perturbed
    candidate that escapes the region is rejected before L-BFGS polishes
    it. Callers needing hard-constraint gradients should bake the
    barrier into ``objective_and_grad`` and set a permissive region.
    """
    if cfg.start_region == "unit_square":
        return bool(
            np.all(points >= -1e-9) and np.all(points <= 1.0 + 1e-9)
        )
    if cfg.start_region == "rectangle":
        return bool(
            np.all(points[:, 0] >= -1e-9)
            and np.all(points[:, 0] <= cfg.rect_width + 1e-9)
            and np.all(points[:, 1] >= -1e-9)
            and np.all(points[:, 1] <= cfg.rect_height + 1e-9)
        )
    if cfg.start_region == "unit_disc":
        return bool(np.all(np.sum(points * points, axis=1) <= 1.0 + 1e-9))
    return True


class Plane2DPackingRecipe:
    """Continuous-attack recipe for 2D plane packing / distance-ratio
    problems.

    Shape requirement: solution is ``n`` points in :math:`\\mathbb{R}^2`,
    the arena verifier reads them as an ``(n, 2)`` list and computes
    either a distance ratio (minimise) or a packing radius (maximise).
    For minimise problems the recipe does NOT project or rescale —
    distance-ratio objectives are scale-invariant, so L-BFGS converges to
    the same minimum from any starting norm.
    """

    name: str = "plane_2d_packing"
    problem_classes: tuple[str, ...] = (
        "plane_minimize_distance_ratio",
        "plane_maximize_radius",
    )

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
                f"Plane2DPackingRecipe: could not infer n from schema "
                f"{solution_schema!r}; pass n=... in config"
            )
        if cfg.start_region not in _VALID_REGIONS:
            raise ValueError(
                f"Plane2DPackingRecipe: start_region must be one of "
                f"{_VALID_REGIONS}; got {cfg.start_region!r}"
            )
        scoring = (scoring or "minimize").lower()
        if scoring not in ("minimize", "maximize"):
            raise ValueError(
                f"Plane2DPackingRecipe: scoring must be 'minimize' or "
                f"'maximize'; got {scoring!r}"
            )
        problem_class = (
            "plane_minimize_distance_ratio"
            if scoring == "minimize"
            else "plane_maximize_radius"
        )
        return self._run(evaluator, start_candidate, cfg, scoring, problem_class, budget)

    def _build_config(
        self,
        config: Optional[dict[str, Any]],
        solution_schema: dict[str, Any],
    ) -> Plane2DPackingConfig:
        raw = dict(config or {})
        if "n" not in raw:
            raw["n"] = _infer_n_from_schema(solution_schema or {})
        allowed = set(Plane2DPackingConfig.__dataclass_fields__)
        filtered = {k: v for k, v in raw.items() if k in allowed}
        return Plane2DPackingConfig(**filtered)

    def _run(
        self,
        evaluator: Callable[[Any], float],
        start_candidate: Any | None,
        cfg: Plane2DPackingConfig,
        scoring: str,
        problem_class: str,
        budget: Budget,
    ) -> AttackResult:
        rng = np.random.default_rng(cfg.seed)
        clock = budget.started()
        # scipy.optimize.minimize minimises; flip arena score for maximise.
        sign = 1.0 if scoring == "minimize" else -1.0

        def _arena_score(flat_x: np.ndarray) -> float:
            """Raw arena score (not sign-flipped). Direction-aware callers
            should wrap this with ``_arena_score_signed`` before handing to
            scipy."""
            clock.tick_evaluation()
            return float(evaluator(flat_x.reshape(cfg.n, 2).tolist()))

        def _arena_score_signed(flat_x: np.ndarray) -> float:
            return sign * _arena_score(flat_x)

        def _lbfgs(x0_flat: np.ndarray, maxiter: int) -> tuple[float, np.ndarray]:
            if cfg.objective_and_grad is not None:
                res = minimize(
                    cfg.objective_and_grad,
                    x0_flat,
                    jac=True,
                    method="L-BFGS-B",
                    options={"maxiter": maxiter, "gtol": 1e-10, "ftol": 1e-12},
                )
                return float(res.fun), np.asarray(res.x)
            res = minimize(
                _arena_score_signed,
                x0_flat,
                method="L-BFGS-B",
                options={"maxiter": maxiter, "gtol": 1e-8, "ftol": 1e-10},
            )
            return float(res.fun), np.asarray(res.x)

        def _is_improvement(new: float, best: float) -> bool:
            if scoring == "maximize":
                return new > best
            return new < best

        worst = -math.inf if scoring == "maximize" else math.inf
        best_score = worst
        best_x: Optional[np.ndarray] = None
        phase_history: list[dict[str, Any]] = []

        # Warm start
        if start_candidate is not None:
            arr = np.asarray(start_candidate, dtype=np.float64)
            if arr.ndim == 1 and arr.size == 2 * cfg.n:
                x0_flat = arr.reshape(-1)
            else:
                x0_flat = arr.reshape(cfg.n, 2).reshape(-1)
            _, x_warm = _lbfgs(x0_flat, cfg.maxiter_lbfgs)
            arena_s = _arena_score(x_warm)
            if _is_improvement(arena_s, best_score):
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

        # Phase 1: random restarts from start_region
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
            x0 = _sample_region(cfg.n, cfg, rng).reshape(-1)
            _, x = _lbfgs(x0, cfg.maxiter_lbfgs)
            arena_s = _arena_score(x)
            n_restarts += 1
            clock.tick_iteration()
            if _is_improvement(arena_s, best_score):
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

        # Phase 2: basin hop around best (reject out-of-region perturbations)
        n_basin_hops = 0
        while not clock.exhausted() and best_x is not None:
            x_struct = best_x.reshape(cfg.n, 2)
            perturbation = rng.standard_normal(x_struct.shape) * cfg.basin_hop_noise
            x0_struct = x_struct + perturbation
            # Soft barrier: only attempt the polish if the perturbed seed
            # stays in region. Skips instead of raising — basin-hop is
            # best-effort and we still own the budget clock.
            if not _in_region(x0_struct, cfg):
                clock.tick_iteration()
                continue
            _, x = _lbfgs(x0_struct.reshape(-1), cfg.basin_hop_maxiter)
            arena_s = _arena_score(x)
            n_basin_hops += 1
            clock.tick_iteration()
            if _is_improvement(arena_s, best_score):
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

        # Phase 3: optional simulated annealing — Metropolis chain over the
        # raw arena score. Tracks a separate ``current`` pointer so worse
        # SA moves don't corrupt ``best_score`` / ``best_x``.
        sa_accepts = 0
        sa_improvements = 0
        if cfg.sa_enabled and best_x is not None:
            current_score = best_score
            current_x = best_x.copy()
            temperature = cfg.sa_temperature
            while not clock.exhausted():
                x_struct = current_x.reshape(cfg.n, 2)
                step = rng.standard_normal(x_struct.shape) * cfg.sa_step
                x_cand_struct = x_struct + step
                if not _in_region(x_cand_struct, cfg):
                    clock.tick_iteration()
                    temperature *= cfg.sa_cooling
                    continue
                cand_flat = x_cand_struct.reshape(-1)
                cand_score = _arena_score(cand_flat)
                clock.tick_iteration()
                delta = (
                    (current_score - cand_score)
                    if scoring == "maximize"
                    else (cand_score - current_score)
                )
                accepted = delta < 0 or rng.random() < math.exp(
                    -delta / max(temperature, 1e-12)
                )
                if accepted:
                    current_score = cand_score
                    current_x = cand_flat
                    sa_accepts += 1
                    if _is_improvement(cand_score, best_score):
                        best_score = cand_score
                        best_x = cand_flat.copy()
                        sa_improvements += 1
                        phase_history.append(
                            {
                                "phase": "sa",
                                "i": sa_improvements,
                                "score": cand_score,
                                "t": clock.elapsed_s(),
                                "T": temperature,
                                "accept": True,
                            }
                        )
                temperature *= cfg.sa_cooling

        best_state: Optional[list[list[float]]] = None
        if best_x is not None:
            best_state = best_x.reshape(cfg.n, 2).tolist()

        return AttackResult(
            best_score=best_score if best_x is not None else worst,
            best_state=best_state,
            n_iterations=clock.iterations,
            n_evaluations=clock.evaluations,
            wall_time_s=clock.elapsed_s(),
            primitive_metadata={
                "n": cfg.n,
                "d": 2,
                "seed": cfg.seed,
                "scoring": scoring,
                "start_region": cfg.start_region,
                "used_analytic_grad": cfg.objective_and_grad is not None,
                "sa_enabled": cfg.sa_enabled,
                "sa_accepts": sa_accepts,
            },
            recipe_name=self.name,
            problem_class=problem_class,
            n_restarts=n_restarts,
            n_basin_hops=n_basin_hops,
            phase_history=phase_history,
        )


# Register on import — a single class handles both plane classes.
register_recipe("plane_minimize_distance_ratio", Plane2DPackingRecipe)
register_recipe("plane_maximize_radius", Plane2DPackingRecipe)
