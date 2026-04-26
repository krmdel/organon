"""Warm-start polish recipe for ``warmstart_polish_only`` problems.

Generalises the Session-5 ``attack_c2_warmstart.py`` driver. Takes an
existing warm-start candidate (typically a top-K competitor solution
or the project's current best) and probes the basin for slack via:

1. Multiplicative / additive noise trials at a schedule of scales.
2. ULP (±``np.spacing``) tweaks on the top-K highest-magnitude cells.
3. Random broader noise trials until the budget drains.

Fix relative to Session 5: every inner loop now checks ``BudgetClock``
so ULP phase can't run past the wall-clock cap (the Session 5 driver
ran ~1,000 s past the 600 s budget because ``ulp_tweaks`` didn't check).

Registered against ``warmstart_polish_only`` — the fallback class for
problems that didn't match another shape but have top-K competitor
solutions to polish. Tailored to the specific geometry via a handful
of config knobs (multiplicative vs additive, nonneg_clip, mask
threshold, scoring direction).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

import numpy as np

from arena_framework.primitives.budget import Budget, BudgetClock

from ..recipe import AttackResult
from ..registry import register_recipe


DEFAULT_NOISE_SCHEDULE: tuple[float, ...] = (1e-5, 1e-4, 1e-3, 3e-3, 1e-2)


@dataclass
class WarmstartPolishConfig:
    """Configuration for :class:`WarmstartPolishRecipe`.

    All fields have defaults; callers only need to supply config when
    overriding the Session-5 defaults or tuning for a non-C₂ geometry.
    """

    noise_schedule: tuple[float, ...] = DEFAULT_NOISE_SCHEDULE
    n_trials_per_noise: int = 20
    ulp_top_k: int = 500
    ulp_enabled: bool = True
    phase1_fraction: float = 0.5
    phase2_fraction: float = 0.75
    noise_style: str = "multiplicative"  # "multiplicative" | "additive"
    nonneg_clip: bool = True
    nonzero_mask_threshold: float = 1e-9
    random_noise_range: tuple[float, float] = (-5.0, -2.0)  # log10 range for phase 3
    n_trials_random_noise: int = 30
    seed: int = 42


def _is_improvement(new: float, best: float, scoring: str) -> bool:
    if scoring == "maximize":
        return new > best
    return new < best


def _initial_best(scoring: str) -> float:
    # Sentinel worst for the chosen direction
    return -float("inf") if scoring == "maximize" else float("inf")


def _apply_noise(
    base: np.ndarray,
    noise_scale: float,
    rng: np.random.Generator,
    cfg: WarmstartPolishConfig,
) -> np.ndarray:
    pert = base.copy()
    if cfg.noise_style == "multiplicative":
        mask = np.abs(base) > cfg.nonzero_mask_threshold
        if np.any(mask):
            noise = rng.standard_normal(int(mask.sum()))
            pert[mask] = pert[mask] * (1.0 + noise_scale * noise)
    else:  # additive
        pert = pert + rng.standard_normal(pert.shape) * noise_scale
    if cfg.nonneg_clip:
        pert = np.maximum(pert, 0.0)
    return pert


def _infer_flatten(
    start_candidate: Any,
) -> tuple[np.ndarray, Callable[[np.ndarray], list]]:
    arr = np.asarray(start_candidate, dtype=np.float64)
    shape = arr.shape
    flat = arr.reshape(-1)

    def restore(flat_x: np.ndarray) -> list:
        return flat_x.reshape(shape).tolist()

    return flat, restore


class WarmstartPolishRecipe:
    """Continuous-attack recipe for polishing a known-good warm start.

    Does NOT run L-BFGS — the expected use case is a warm start that is
    already at or near the optimum of its basin. Probes for slack via
    noise trials + ULP tweaks. For polishing from scratch, use the
    shape-specific recipes (sphere_lbfgs, softmin_cascade, nonneg_smooth_max).
    """

    name: str = "warmstart_polish"
    problem_classes: tuple[str, ...] = ("warmstart_polish_only",)

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
        if start_candidate is None:
            raise ValueError(
                "WarmstartPolishRecipe requires a start_candidate; it has no "
                "cold-start pathway. Route unknown problems with top-K "
                "solutions here with start_candidate=top_solution."
            )
        cfg = self._build_config(config)
        return self._run(evaluator, start_candidate, scoring, cfg, budget)

    def _build_config(
        self, config: Optional[dict[str, Any]]
    ) -> WarmstartPolishConfig:
        raw = dict(config or {})
        if "noise_schedule" in raw and not isinstance(raw["noise_schedule"], tuple):
            raw["noise_schedule"] = tuple(raw["noise_schedule"])
        if "random_noise_range" in raw and not isinstance(
            raw["random_noise_range"], tuple
        ):
            raw["random_noise_range"] = tuple(raw["random_noise_range"])
        allowed = set(WarmstartPolishConfig.__dataclass_fields__)
        filtered = {k: v for k, v in raw.items() if k in allowed}
        return WarmstartPolishConfig(**filtered)

    def _run(
        self,
        evaluator: Callable[[Any], float],
        start_candidate: Any,
        scoring: str,
        cfg: WarmstartPolishConfig,
        budget: Budget,
    ) -> AttackResult:
        rng = np.random.default_rng(cfg.seed)
        clock = budget.started()
        flat, restore = _infer_flatten(start_candidate)

        def _score(flat_x: np.ndarray) -> float:
            clock.tick_evaluation()
            return float(evaluator(restore(flat_x)))

        best_score = _score(flat)
        best_x = flat.copy()
        phase_history: list[dict[str, Any]] = [
            {
                "phase": "warmstart",
                "score": best_score,
                "t": clock.elapsed_s(),
            }
        ]

        wall = budget.wall_clock_s

        # Phase 1 — scheduled noise trials
        phase1_deadline = wall * cfg.phase1_fraction if wall is not None else None
        for noise_scale in cfg.noise_schedule:
            if clock.exhausted() or (
                phase1_deadline is not None
                and clock.elapsed_s() >= phase1_deadline
            ):
                break
            trial_best_score = best_score
            trial_best_x = best_x
            improved = False
            for _ in range(cfg.n_trials_per_noise):
                if clock.exhausted() or (
                    phase1_deadline is not None
                    and clock.elapsed_s() >= phase1_deadline
                ):
                    break
                pert = _apply_noise(trial_best_x, noise_scale, rng, cfg)
                s = _score(pert)
                clock.tick_iteration()
                if _is_improvement(s, trial_best_score, scoring):
                    trial_best_score = s
                    trial_best_x = pert
                    improved = True
            if improved and _is_improvement(trial_best_score, best_score, scoring):
                best_score = trial_best_score
                best_x = trial_best_x
                phase_history.append(
                    {
                        "phase": f"noise-{noise_scale:g}",
                        "score": best_score,
                        "t": clock.elapsed_s(),
                        "accept": True,
                    }
                )
            else:
                phase_history.append(
                    {
                        "phase": f"noise-{noise_scale:g}",
                        "t": clock.elapsed_s(),
                        "accept": False,
                    }
                )

        # Phase 2 — ULP tweaks on top-K cells (this is where Session 5 leaked budget)
        if cfg.ulp_enabled and not clock.exhausted():
            phase2_deadline = (
                wall * cfg.phase2_fraction if wall is not None else None
            )
            improved = self._ulp_phase(
                evaluator,
                restore,
                best_x,
                best_score,
                scoring,
                cfg,
                clock,
                phase2_deadline,
            )
            if improved is not None:
                best_score, best_x = improved
                phase_history.append(
                    {
                        "phase": "ulp",
                        "score": best_score,
                        "t": clock.elapsed_s(),
                        "accept": True,
                    }
                )
            else:
                phase_history.append(
                    {
                        "phase": "ulp",
                        "t": clock.elapsed_s(),
                        "accept": False,
                    }
                )

        # Phase 3 — random broader noise until wall drains
        n_random_rounds = 0
        while not clock.exhausted():
            n_random_rounds += 1
            ns = 10 ** rng.uniform(*cfg.random_noise_range)
            trial_best_score = best_score
            trial_best_x = best_x
            for _ in range(cfg.n_trials_random_noise):
                if clock.exhausted():
                    break
                pert = _apply_noise(trial_best_x, ns, rng, cfg)
                s = _score(pert)
                clock.tick_iteration()
                if _is_improvement(s, trial_best_score, scoring):
                    trial_best_score = s
                    trial_best_x = pert
            if _is_improvement(trial_best_score, best_score, scoring):
                best_score = trial_best_score
                best_x = trial_best_x
                phase_history.append(
                    {
                        "phase": f"random-noise-{ns:.2e}",
                        "score": best_score,
                        "t": clock.elapsed_s(),
                        "accept": True,
                    }
                )

        return AttackResult(
            best_score=best_score,
            best_state=restore(best_x),
            n_iterations=clock.iterations,
            n_evaluations=clock.evaluations,
            wall_time_s=clock.elapsed_s(),
            primitive_metadata={
                "n_flat": int(flat.size),
                "seed": cfg.seed,
                "noise_style": cfg.noise_style,
                "n_random_phase3_rounds": n_random_rounds,
            },
            recipe_name=self.name,
            problem_class="warmstart_polish_only",
            n_restarts=0,
            n_basin_hops=0,
            phase_history=phase_history,
        )

    def _ulp_phase(
        self,
        evaluator: Callable[[Any], float],
        restore: Callable[[np.ndarray], Any],
        best_x: np.ndarray,
        best_score: float,
        scoring: str,
        cfg: WarmstartPolishConfig,
        clock: BudgetClock,
        deadline_s: Optional[float],
    ) -> Optional[tuple[float, np.ndarray]]:
        """±1 ULP tweaks on the top-K highest-magnitude cells.

        Session-5 bug fix: this inner loop now respects the clock. Any
        iteration checks ``clock.exhausted()`` and the phase-2 deadline
        before spending another evaluation.
        """
        idx_order = np.argsort(np.abs(best_x))[::-1][: cfg.ulp_top_k]
        improved = False
        cur_score = best_score
        cur_x = best_x.copy()
        for idx in idx_order:
            if clock.exhausted() or (
                deadline_s is not None and clock.elapsed_s() >= deadline_s
            ):
                break
            for sign in (+1.0, -1.0):
                if clock.exhausted() or (
                    deadline_s is not None and clock.elapsed_s() >= deadline_s
                ):
                    break
                trial = cur_x.copy()
                v = float(trial[idx])
                if v == 0.0:
                    continue
                ulp = float(np.spacing(abs(v)))
                trial[idx] = v + sign * ulp
                if cfg.nonneg_clip:
                    trial[idx] = max(0.0, trial[idx])
                s = float(evaluator(restore(trial)))
                clock.tick_evaluation()
                clock.tick_iteration()
                if _is_improvement(s, cur_score, scoring):
                    cur_score = s
                    cur_x = trial
                    improved = True
        return (cur_score, cur_x) if improved else None


# Register on import
register_recipe("warmstart_polish_only", WarmstartPolishRecipe)
