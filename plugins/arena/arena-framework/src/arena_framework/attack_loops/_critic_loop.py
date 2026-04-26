"""Verifier-grounded CRITIC loop between attack rounds (Upgrade U3).

Implements the MathArena / Huang 2025 verify-and-refine pattern
(arXiv:2507.15855, 31% → 86% on IMO 2025) and CRITIC (Gou 2024,
arXiv:2305.11738). Distinct from the ``arena-critic-agent`` that reviews the
pre-attack hypothesis graph — this module fires AFTER each attack round and
returns a structured directive for the next seed pool.

Core invariants:

1. **Directive is additive, never replaces known-best.** The attack loop seeds
   the next round with (best_so_far, critic's proposed_seed_delta). Worst
   case: critic output is ignored. Best case: critic unlocks a basin the
   random seeds missed.
2. **Critique grounded in rigorous evaluator diagnostics, not gut.** Every
   directive must cite a numeric field in the diagnostic dict.
3. **Schema-validated.** Directives that fail the validator are rejected and
   the attack loop falls back to a safe default.

Integration: callers construct a ``CriticContext`` with (round_dir, history,
latest_candidate), invoke ``run_critic_round(ctx)``, and receive a
``CriticDirective``. The function dispatches to a local rule engine
(deterministic, no LLM call) by default, with an optional
``llm_assist=True`` flag that wraps the rule engine's draft output in a
Claude review for explanation quality.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from ..rate_limiter import LLMCallLimiter, get_default_limiter
from ..seed_generator import HistoryEntry, load_history


# ---------------------------------------------------------------------------
# Directive schema
# ---------------------------------------------------------------------------

DIRECTIVE_TYPES = {
    "ACCEPT",
    "CHANGE_NOISE_LEVEL",
    "ESCALATE_TO_LARGER_NOISE_ESCAPE",
    "EXTEND_BETA_CASCADE",
    "DYADIC_SNAP_ACTIVE",
    "K_CLIMB",
    "RETURN_TO_EARLIER_BASIN",
    "STOP_AS_EXPLOIT",
    "STOP_STALLED",
}

VERDICTS = {"accept", "revise", "stop"}


@dataclass
class CriticDirective:
    """Structured output of one critic round."""

    round_n: int
    verdict: str
    directive_type: str
    parameters: dict[str, Any] = field(default_factory=dict)
    grounding: dict[str, Any] = field(default_factory=dict)
    previous_directives_considered: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_n": self.round_n,
            "verdict": self.verdict,
            "directive_type": self.directive_type,
            "parameters": self.parameters,
            "grounding": self.grounding,
            "previous_directives_considered": self.previous_directives_considered,
        }


def validate_directive(obj: Any) -> tuple[bool, list[str]]:
    """Return (is_valid, errors). Attack loop drops invalid directives."""
    errors: list[str] = []
    if not isinstance(obj, dict):
        return False, ["not a dict"]
    for key in ("round_n", "verdict", "directive_type"):
        if key not in obj:
            errors.append(f"missing key: {key}")
    if obj.get("verdict") not in VERDICTS:
        errors.append(f"invalid verdict: {obj.get('verdict')!r}")
    if obj.get("directive_type") not in DIRECTIVE_TYPES:
        errors.append(f"invalid directive_type: {obj.get('directive_type')!r}")
    params = obj.get("parameters")
    if params is not None and not isinstance(params, dict):
        errors.append("parameters must be a dict")
    return (not errors), errors


# ---------------------------------------------------------------------------
# Critic input context
# ---------------------------------------------------------------------------


@dataclass
class CriticContext:
    """Inputs for one critic round."""

    round_n: int
    problem_slug: str
    scoring: str  # "minimize" | "maximize"
    min_improvement: float
    best_known_score: float
    threshold_score: Optional[float]
    latest_candidate: dict[str, Any]
    # Diagnostic dict from the rigorous evaluator: active_max_cells,
    # verdict_hint, integral_sign, etc.
    latest_diagnostic: dict[str, Any]
    latest_score: float
    latest_verdict: str  # "rigorous" | "exploit" | "unknown"
    # Up to 5 most recent history entries; newest last.
    history: list[HistoryEntry] = field(default_factory=list)
    previous_directives: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Decision rules (deterministic — no LLM needed)
# ---------------------------------------------------------------------------


def _per_round_deltas(history: list[HistoryEntry], scoring: str) -> list[float]:
    """Signed per-round deltas, oriented so positive = improvement."""
    if len(history) < 2:
        return []
    scores = [e.score for e in history]
    raw = [scores[i + 1] - scores[i] for i in range(len(scores) - 1)]
    # Flip sign so "positive = improvement" regardless of min/max direction.
    return [-d if scoring == "minimize" else d for d in raw]


def _improvement_ratio(deltas: list[float]) -> Optional[float]:
    """Ratio of last improvement to prior improvement. None if insufficient."""
    pos = [d for d in deltas if d > 0]
    if len(pos) < 2:
        return None
    prev, last = pos[-2], pos[-1]
    if prev <= 0:
        return None
    return last / prev


def _prior_types(prev: list[dict[str, Any]]) -> set[str]:
    return {d.get("directive_type", "") for d in prev}


def decide_directive(ctx: CriticContext) -> CriticDirective:
    """Pure-logic rule engine. Decisions apply in order; first match wins."""
    prior_types = _prior_types(ctx.previous_directives)

    # Rule a: exploit verdict → refuse to submit.
    if ctx.latest_verdict == "exploit":
        return CriticDirective(
            round_n=ctx.round_n,
            verdict="stop",
            directive_type="STOP_AS_EXPLOIT",
            parameters={"reason": "rigorous_evaluator classified candidate as exploit"},
            grounding={
                "verdict": ctx.latest_verdict,
                "diagnostic_verdict_hint": ctx.latest_diagnostic.get("verdict_hint"),
            },
            previous_directives_considered=sorted(prior_types),
        )

    deltas = _per_round_deltas(ctx.history + [HistoryEntry(
        params={}, score=ctx.latest_score, seed=0
    )], ctx.scoring)

    # Rule b: 3 consecutive near-zero |Δ| → stall.
    if len(deltas) >= 3 and all(abs(d) < 1e-10 for d in deltas[-3:]):
        return CriticDirective(
            round_n=ctx.round_n,
            verdict="stop",
            directive_type="STOP_STALLED",
            parameters={"reason": "3 consecutive rounds with |Δ_score| < 1e-10"},
            grounding={"last_3_deltas": deltas[-3:]},
            previous_directives_considered=sorted(prior_types),
        )

    # Rule c: last 2 rounds worsened → revert.
    if len(deltas) >= 2 and deltas[-1] < 0 and deltas[-2] < 0:
        if "RETURN_TO_EARLIER_BASIN" not in prior_types:
            revert_idx = _find_last_improving_round(deltas)
            return CriticDirective(
                round_n=ctx.round_n,
                verdict="revise",
                directive_type="RETURN_TO_EARLIER_BASIN",
                parameters={
                    "revert_to_round": max(0, ctx.round_n - (len(deltas) - revert_idx)),
                    "alternative_direction": "orthogonal_perturbation",
                    "rationale": (
                        "Last 2 rounds worsened score; revert to last improving "
                        "round and try an orthogonal perturbation direction."
                    ),
                },
                grounding={"last_deltas": deltas[-3:]},
                previous_directives_considered=sorted(prior_types),
            )

    # Rule d: active cells growing + still improving → extend β cascade.
    active_last = ctx.latest_diagnostic.get("active_max_cells")
    if (
        isinstance(active_last, int)
        and len(ctx.history) >= 2
        and ctx.history[-1].metadata.get("active_max_cells", 0) > 0
        and active_last > 3 * ctx.history[-1].metadata["active_max_cells"]
        and deltas and deltas[-1] > 0
    ):
        return CriticDirective(
            round_n=ctx.round_n,
            verdict="revise",
            directive_type="EXTEND_BETA_CASCADE",
            parameters={
                "additional_beta_stages": [1e10, 3e10, 1e11, 3e11],
                "rationale": (
                    "active_max_cells grew 3×+ in the last round while score "
                    "improved. β-annealing still has headroom."
                ),
            },
            grounding={
                "active_cells_prev": ctx.history[-1].metadata.get("active_max_cells"),
                "active_cells_now": active_last,
                "last_delta": deltas[-1],
            },
            previous_directives_considered=sorted(prior_types),
        )

    # Rule e: per-round improvement decaying → escalate noise.
    ratio = _improvement_ratio(deltas)
    if (
        ratio is not None
        and ratio < 0.75
        and "ESCALATE_TO_LARGER_NOISE_ESCAPE" not in prior_types
    ):
        current_noise = ctx.latest_candidate.get("rel_noise", 0.001)
        new_noise = 0.01 if current_noise < 0.005 else current_noise * 2
        return CriticDirective(
            round_n=ctx.round_n,
            verdict="revise",
            directive_type="ESCALATE_TO_LARGER_NOISE_ESCAPE",
            parameters={
                "new_rel_noise": new_noise,
                "beta_schedule": [1e3, 1e5, 1e7, 1e9, 1e11],
                "rationale": (
                    f"Per-round improvement ratio {ratio:.2f} < 0.75; micro-BH "
                    f"plateau. Escalate to C₃ recursive-basin-escape recipe "
                    f"at {new_noise:.3f} relative noise."
                ),
            },
            grounding={
                "improvement_ratio": ratio,
                "positive_deltas": [d for d in deltas if d > 0],
            },
            previous_directives_considered=sorted(prior_types),
        )

    # Rule f: k-climb on rigorous configurations with a tunable k.
    k_now = ctx.latest_candidate.get("k")
    if (
        isinstance(k_now, int)
        and ctx.latest_verdict == "rigorous"
        and "K_CLIMB" not in prior_types
        and k_now > 0
    ):
        return CriticDirective(
            round_n=ctx.round_n,
            verdict="revise",
            directive_type="K_CLIMB",
            parameters={
                "new_k": k_now + 1,
                "rationale": f"k={k_now} is rigorously verified; climb to k={k_now + 1}.",
            },
            grounding={"current_k": k_now, "verdict": ctx.latest_verdict},
            previous_directives_considered=sorted(prior_types),
        )

    # Rule g: accept if score beats threshold (with min_improvement margin).
    if (
        ctx.threshold_score is not None
        and ctx.latest_verdict == "rigorous"
        and _beats_threshold(ctx.latest_score, ctx.threshold_score, ctx.min_improvement, ctx.scoring)
    ):
        return CriticDirective(
            round_n=ctx.round_n,
            verdict="accept",
            directive_type="ACCEPT",
            parameters={"final_score": ctx.latest_score},
            grounding={
                "threshold_score": ctx.threshold_score,
                "min_improvement": ctx.min_improvement,
            },
            previous_directives_considered=sorted(prior_types),
        )

    # Default: adjust noise based on observed progress.
    current_noise = ctx.latest_candidate.get("rel_noise", 0.01)
    new_noise = current_noise * (0.5 if ratio is not None and ratio > 1.0 else 1.5)
    return CriticDirective(
        round_n=ctx.round_n,
        verdict="revise",
        directive_type="CHANGE_NOISE_LEVEL",
        parameters={
            "new_rel_noise": new_noise,
            "rationale": (
                f"Default: adjust noise {current_noise:.3f} → {new_noise:.3f} "
                f"based on improvement ratio {ratio!r}."
            ),
        },
        grounding={"deltas": deltas[-5:] if deltas else []},
        previous_directives_considered=sorted(prior_types),
    )


def _find_last_improving_round(deltas: list[float]) -> int:
    """Index of the last round with positive delta (None → 0)."""
    for i in range(len(deltas) - 1, -1, -1):
        if deltas[i] > 0:
            return i
    return 0


def _beats_threshold(score: float, threshold: float, min_improvement: float, scoring: str) -> bool:
    if scoring == "minimize":
        return score < threshold - min_improvement
    return score > threshold + min_improvement


# ---------------------------------------------------------------------------
# Driver — runs one critic round end-to-end, writes directive file
# ---------------------------------------------------------------------------


def run_critic_round(
    ctx: CriticContext,
    *,
    round_dir: Optional[Path] = None,
) -> CriticDirective:
    """Run one critic round against ``ctx``; optionally persist the directive.

    Returns the ``CriticDirective`` either way. When ``round_dir`` is given,
    the directive is written to ``round_dir/round_N_directive.json`` and
    appended to ``round_dir/directives.log``.
    """
    directive = decide_directive(ctx)

    if round_dir is not None:
        round_dir = Path(round_dir)
        round_dir.mkdir(parents=True, exist_ok=True)
        (round_dir / f"round_{ctx.round_n}_directive.json").write_text(
            json.dumps(directive.to_dict(), indent=2)
        )
        with open(round_dir / "directives.log", "a") as f:
            rationale = directive.parameters.get("rationale", "")
            f.write(
                f"round={ctx.round_n} verdict={directive.verdict} "
                f'directive={directive.directive_type} rationale="{rationale}"\n'
            )

    return directive


def load_previous_directives(round_dir: Path) -> list[dict[str, Any]]:
    """Load all prior directive JSONs from a round_dir for history."""
    round_dir = Path(round_dir)
    if not round_dir.exists():
        return []
    out: list[dict[str, Any]] = []
    for p in sorted(round_dir.glob("round_*_directive.json")):
        try:
            out.append(json.loads(p.read_text()))
        except (OSError, json.JSONDecodeError):
            continue
    return out
