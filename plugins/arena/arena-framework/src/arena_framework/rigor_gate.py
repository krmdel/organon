"""Generic rigor-vs-exploit classifier.

Every arena problem has two notions of "score":
1. **Arena score** — what the competition server computes. This is authoritative
   for leaderboard rank but may rest on numerical shortcuts (float64 sign checks,
   low-precision root finders) that can be gamed.
2. **Rigorous score** — the mathematical truth: what the score would be if
   evaluated at unlimited precision with no arithmetic compromises.

For most problems (PNT linear programming, Erdős QCQP, kissing numbers) these
agree up to float64 rounding — there is no exploit surface. For Uncertainty
Principle, our Session 1 session found arena and rigorous scores diverge by
two orders of magnitude at k≥15: the server's ``np.sign(lambdify(gq)(r ± 1e-6))``
check misses genuine sign changes of a rational polynomial whose float64
evaluation magnitude is ~1e40.

This module provides the generic gate. Per-problem adapters live in
``arena_framework.evaluators`` and plug their ``arena_evaluator`` +
``rigorous_evaluator`` callables into ``rigor_gate()`` here.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Literal, Optional, TypeVar

Config = TypeVar("Config")
Verdict = Literal["rigorous", "exploit", "unknown"]


@dataclass(frozen=True)
class RigorVerdict:
    """Result of comparing arena score vs rigorous score.

    verdict:
      - ``"rigorous"`` — arena and rigorous agree within tolerance; the arena
        score IS a certifiable upper/lower bound (whichever the problem measures).
      - ``"exploit"`` — they differ beyond tolerance; arena is a numerical
        artifact. Submitting would claim a mathematical result that isn't true.
      - ``"unknown"`` — no rigorous evaluator available for this problem;
        cannot assess exploitation risk.

    exploit_factor is rigorous / arena when verdict == "exploit" and both
    are positive (how many times "better" the arena claims than reality).
    """

    arena_score: float
    rigorous_score: Optional[float]
    verdict: Verdict
    gap: Optional[float] = None
    rel_gap: Optional[float] = None
    exploit_factor: Optional[float] = None
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def classify_verdict(
    arena_score: float,
    rigorous_score: Optional[float],
    *,
    rel_tol: float = 1e-6,
    abs_tol: float = 1e-8,
) -> tuple[Verdict, Optional[float], Optional[float], Optional[float]]:
    """Pure-logic classifier: given two scores, return (verdict, gap, rel_gap, exploit_factor).

    Separated from ``rigor_gate`` so we can unit-test the decision rule without
    invoking heavyweight evaluators.
    """
    if rigorous_score is None:
        return ("unknown", None, None, None)

    if not math.isfinite(arena_score) or not math.isfinite(rigorous_score):
        # If either score is non-finite, we can't classify reliably.
        return ("unknown", None, None, None)

    gap = abs(arena_score - rigorous_score)
    # Scale without the 1.0 floor: flooring at 1.0 would inflate the threshold
    # for small scores (e.g. kissing d=11 near 0) and hide real exploits there.
    # abs_tol handles the exact-zero case on its own.
    scale = max(abs(arena_score), abs(rigorous_score))
    rel_gap = gap / scale if scale > 0 else 0.0

    threshold = max(rel_tol * scale, abs_tol)
    if gap <= threshold:
        return ("rigorous", gap, rel_gap, None)

    exploit_factor = None
    if arena_score > 0 and rigorous_score > 0 and rigorous_score > arena_score:
        exploit_factor = rigorous_score / arena_score
    return ("exploit", gap, rel_gap, exploit_factor)


def rigor_gate(
    config: Config,
    arena_evaluator: Callable[[Config], float],
    rigorous_evaluator: Optional[Callable[[Config], tuple[float, dict[str, Any]]]],
    *,
    rel_tol: float = 1e-6,
    abs_tol: float = 1e-8,
) -> RigorVerdict:
    """Evaluate a candidate config against both arena and rigorous evaluators.

    Arguments:
      config: opaque problem-specific representation (list of floats, array, etc.)
      arena_evaluator: callable returning the arena's exact score for this config.
      rigorous_evaluator: callable returning ``(rigorous_score, diagnostics_dict)``
        or ``None`` if no rigorous check is available for this problem (e.g.
        kissing numbers, where the server's Decimal-80 check IS the rigorous
        truth — no separate gate needed).
      rel_tol, abs_tol: tolerance for deciding rigorous vs exploit. Defaults are
        conservative (1e-6 rel, 1e-8 abs) because arena verifiers are
        deterministic at float64 precision.

    Returns:
      ``RigorVerdict`` with verdict, scores, gap, and diagnostics.

    Callers are expected to handle the ``"exploit"`` verdict explicitly:
    either surface it to the user via the submit gate (Slice 3) or fail-closed
    depending on framework configuration (default is warn-then-prompt).
    """
    arena_score = float(arena_evaluator(config))

    rigorous_score: Optional[float] = None
    diagnostics: dict[str, Any] = {}
    if rigorous_evaluator is not None:
        rigorous_score_raw, rigorous_diag = rigorous_evaluator(config)
        rigorous_score = float(rigorous_score_raw)
        diagnostics.update(rigorous_diag)

    verdict, gap, rel_gap, exploit_factor = classify_verdict(
        arena_score,
        rigorous_score,
        rel_tol=rel_tol,
        abs_tol=abs_tol,
    )

    return RigorVerdict(
        arena_score=arena_score,
        rigorous_score=rigorous_score,
        verdict=verdict,
        gap=gap,
        rel_gap=rel_gap,
        exploit_factor=exploit_factor,
        diagnostics=diagnostics,
    )
