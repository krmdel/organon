"""Arena submission gate — the single chokepoint through which every
submission must pass before hitting the leaderboard.

Four responsibilities:
1. **Verify**: run the arena evaluator on the candidate config and compare
   to the config's claimed score. Refuse submission on mismatch.
2. **Rigor classify**: run rigor_gate. If verdict == "exploit" and the caller
   has not opted in via ``allow_exploit=True``, refuse.
3. **Rate-limit**: track submissions in a local JSON state file with a 30-min
   rolling window (arena's soft limit is 5/30min per problem per agent).
4. **User gate + log**: produce a dual-score prompt with rank estimate; on
   approval, submit through an injected client and append to
   ``SUBMISSIONS.md``.

Designed for dry-run testability: every external dependency (arena client,
rate-limit state path, clock) is injectable. The real `tool-einstein-arena`
submit call is only invoked when ``submit()`` is explicitly approved with a
live client — tests always pass a stub.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from .recon import ReconArtifacts
from .rigor_gate import RigorVerdict, rigor_gate


# ---------------------------------------------------------------------------
# Rate-limit budget
# ---------------------------------------------------------------------------


@dataclass
class RateLimitWindow:
    """Arena soft limit: 5 submissions per 30-min rolling window, per problem.

    Stored as a JSON file with a list of epoch seconds per problem slug.
    Entries older than ``window_seconds`` are pruned on every read.
    """

    window_seconds: int = 30 * 60
    max_submissions: int = 5


@dataclass
class RateLimitState:
    submissions_in_window: int
    remaining: int
    next_slot_available_at: Optional[float]  # epoch seconds; None if slots available now


class RateLimitBudget:
    """Rolling-window submission counter persisted to disk."""

    def __init__(
        self,
        state_path: Path,
        *,
        window: RateLimitWindow = RateLimitWindow(),
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.state_path = Path(state_path)
        self.window = window
        self.clock = clock

    def _load(self) -> dict[str, list[float]]:
        if not self.state_path.exists():
            return {}
        try:
            return json.loads(self.state_path.read_text())
        except json.JSONDecodeError:
            return {}

    def _save(self, data: dict[str, list[float]]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(data, indent=2))

    def _prune(self, timestamps: list[float], now: float) -> list[float]:
        cutoff = now - self.window.window_seconds
        return [t for t in timestamps if t > cutoff]

    def check(self, slug: str) -> RateLimitState:
        now = self.clock()
        data = self._load()
        ts = self._prune(data.get(slug, []), now)
        remaining = max(0, self.window.max_submissions - len(ts))
        next_slot: Optional[float] = None
        if remaining == 0 and ts:
            next_slot = min(ts) + self.window.window_seconds
        return RateLimitState(
            submissions_in_window=len(ts),
            remaining=remaining,
            next_slot_available_at=next_slot,
        )

    def record(self, slug: str) -> None:
        now = self.clock()
        data = self._load()
        ts = self._prune(data.get(slug, []), now)
        ts.append(now)
        data[slug] = ts
        self._save(data)


# ---------------------------------------------------------------------------
# Submission plan + user prompt
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SubmissionPlan:
    """Everything the gate knows about a proposed submission before the user decides."""

    slug: str
    config: Any
    arena_score: float
    rigorous_score: Optional[float]
    rigor_verdict: str
    rigor_verdict_obj: RigorVerdict
    rate_limit: RateLimitState
    rank_estimate: Optional[int]
    current_leader_score: Optional[float]
    would_improve_leader: bool
    min_improvement: Optional[float]
    prompt_text: str
    refusal_reason: Optional[str] = None

    def is_submittable(self) -> bool:
        return self.refusal_reason is None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # RigorVerdict is already a dataclass and serializable via asdict.
        return d


def _estimate_rank(
    proposed_score: float,
    leaderboard: list[dict[str, Any]],
    *,
    lower_better: bool = True,
) -> tuple[Optional[int], Optional[float]]:
    """Given a candidate score and a leaderboard, return (estimated_rank, current_leader_score).

    Ranks are 1-based. If lower_better, a score of 0.1 against [0.2, 0.3] ranks #1.
    """
    if not leaderboard:
        return (1, None)
    scores = [float(e.get("score", e.get("bestScore", float("inf")))) for e in leaderboard]
    leader = min(scores) if lower_better else max(scores)
    if lower_better:
        rank = sum(1 for s in scores if s < proposed_score) + 1
    else:
        rank = sum(1 for s in scores if s > proposed_score) + 1
    return (rank, leader)


def format_user_prompt(plan: SubmissionPlan) -> str:
    """Human-readable prompt shown before submission is authorized.

    Kept deliberately concise (<= 25 lines) — the user will see many of these
    and should be able to skim one in <10 seconds.
    """
    v = plan.rigor_verdict_obj
    lines: list[str] = []
    lines.append(f"=== Submission gate — {plan.slug} ===")
    lines.append("")
    lines.append(f"  Arena score:     {plan.arena_score:.10g}")
    if plan.rigorous_score is not None:
        lines.append(f"  Rigorous score:  {plan.rigorous_score:.10g}")
    else:
        lines.append("  Rigorous score:  — (no rigorous evaluator registered)")
    lines.append(f"  Rigor verdict:   {plan.rigor_verdict}")

    if plan.rigor_verdict == "exploit" and v.exploit_factor:
        lines.append(
            f"  ⚠  EXPLOIT detected — arena score claims ~{v.exploit_factor:.1f}× "
            f"better than mathematical reality."
        )
        lines.append(
            "     Submitting would publish a numerical artifact, not a certified bound."
        )
        lines.append("     Pass `allow_exploit=True` to submit anyway.")

    lines.append("")

    if plan.current_leader_score is not None:
        lines.append(f"  Current leader:  {plan.current_leader_score:.10g}")
        if plan.rank_estimate is not None:
            lines.append(f"  Estimated rank:  #{plan.rank_estimate}")
        if plan.min_improvement is not None:
            delta = abs(plan.arena_score - plan.current_leader_score)
            improves = "yes" if plan.would_improve_leader else "no"
            lines.append(
                f"  Beats min-improvement ({plan.min_improvement:.0e}): {improves} "
                f"(Δ={delta:.3e})"
            )
    else:
        lines.append("  Current leader:  none (leaderboard empty or not fetched)")

    lines.append("")
    rl = plan.rate_limit
    if rl.remaining > 0:
        lines.append(
            f"  Rate-limit:      {rl.submissions_in_window}/5 used in last 30min, "
            f"{rl.remaining} remaining"
        )
    else:
        if rl.next_slot_available_at:
            mins = (rl.next_slot_available_at - time.time()) / 60.0
            lines.append(
                f"  Rate-limit:      EXHAUSTED (next slot in ~{mins:.1f} min)"
            )
        else:
            lines.append("  Rate-limit:      EXHAUSTED")

    if plan.refusal_reason:
        lines.append("")
        lines.append(f"  REFUSED: {plan.refusal_reason}")

    lines.append("")
    lines.append("  Submit? (y/n)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Submit gate driver
# ---------------------------------------------------------------------------


class SubmitGate:
    """Coordinates verification, rigor, rate-limit, and user approval.

    Usage (dry-run)::

        gate = SubmitGate(slug="uncertainty-principle", recon=art,
                         arena_evaluator=up.arena_evaluator,
                         rigorous_evaluator=up.rigorous_evaluator,
                         rate_limit_budget=budget)
        plan = gate.prepare(config=[...])
        print(plan.prompt_text)

    Usage (live, after user approval)::

        result = gate.submit(plan, approved=True, arena_client=client)
    """

    def __init__(
        self,
        slug: str,
        recon: Optional[ReconArtifacts],
        *,
        arena_evaluator: Callable[[Any], float],
        rigorous_evaluator: Optional[Callable[[Any], tuple[float, dict[str, Any]]]] = None,
        rate_limit_budget: Optional[RateLimitBudget] = None,
        submissions_log_path: Optional[Path] = None,
        lower_better: bool = True,
    ) -> None:
        self.slug = slug
        self.recon = recon
        self.arena_evaluator = arena_evaluator
        self.rigorous_evaluator = rigorous_evaluator
        self.rate_limit_budget = rate_limit_budget
        self.submissions_log_path = (
            Path(submissions_log_path) if submissions_log_path else None
        )
        self.lower_better = lower_better

    def prepare(self, config: Any, *, claimed_score: Optional[float] = None) -> SubmissionPlan:
        """Compute scores + rigor + rate-limit state. No submission side-effects."""
        verdict = rigor_gate(config, self.arena_evaluator, self.rigorous_evaluator)

        refusal_reason: Optional[str] = None
        if claimed_score is not None:
            if abs(claimed_score - verdict.arena_score) > 1e-6:
                refusal_reason = (
                    f"arena evaluator returned {verdict.arena_score:.10g}, which differs "
                    f"from claimed {claimed_score:.10g} by more than 1e-6 — config/score mismatch"
                )

        leaderboard = self.recon.leaderboard if self.recon else []
        rank, leader_score = _estimate_rank(
            verdict.arena_score, leaderboard, lower_better=self.lower_better
        )

        min_impr: Optional[float] = None
        would_improve = False
        if self.recon and self.recon.problem:
            mi_raw = self.recon.problem.get("minImprovement")
            try:
                min_impr = float(mi_raw) if mi_raw is not None else None
            except (ValueError, TypeError):
                min_impr = None
        if leader_score is not None and min_impr is not None:
            delta = leader_score - verdict.arena_score if self.lower_better else verdict.arena_score - leader_score
            would_improve = delta > min_impr
        elif leader_score is None:
            would_improve = True

        rate_state: RateLimitState
        if self.rate_limit_budget:
            rate_state = self.rate_limit_budget.check(self.slug)
        else:
            rate_state = RateLimitState(
                submissions_in_window=0, remaining=99, next_slot_available_at=None
            )

        if rate_state.remaining == 0 and refusal_reason is None:
            refusal_reason = (
                f"rate limit exhausted ({rate_state.submissions_in_window}/5 in last 30min); "
                "wait for the next window"
            )

        plan = SubmissionPlan(
            slug=self.slug,
            config=config,
            arena_score=verdict.arena_score,
            rigorous_score=verdict.rigorous_score,
            rigor_verdict=verdict.verdict,
            rigor_verdict_obj=verdict,
            rate_limit=rate_state,
            rank_estimate=rank,
            current_leader_score=leader_score,
            would_improve_leader=would_improve,
            min_improvement=min_impr,
            prompt_text="",  # populated below
            refusal_reason=refusal_reason,
        )
        # Re-create with prompt_text filled in (frozen dataclass).
        prompt = format_user_prompt(plan)
        return SubmissionPlan(**{**plan.to_dict(), "rigor_verdict_obj": verdict, "prompt_text": prompt})

    def submit(
        self,
        plan: SubmissionPlan,
        *,
        approved: bool,
        allow_exploit: bool = False,
        arena_client: Optional[Any] = None,
    ) -> dict[str, Any]:
        """Actually submit. Returns the arena client's submission response.

        Refuses when:
        - ``approved`` is False
        - ``plan.refusal_reason`` is set (verify mismatch, rate-limit)
        - ``plan.rigor_verdict == "exploit"`` and not ``allow_exploit``

        Side effects on success: records to rate-limit budget + appends to
        SUBMISSIONS.md.
        """
        if not approved:
            return {"status": "refused", "reason": "not approved by caller"}
        if plan.refusal_reason:
            return {"status": "refused", "reason": plan.refusal_reason}
        if plan.rigor_verdict == "exploit" and not allow_exploit:
            return {
                "status": "refused",
                "reason": (
                    "rigor verdict = exploit; pass allow_exploit=True to submit "
                    "a numerical-artifact score"
                ),
            }
        if arena_client is None:
            raise ValueError("live submission requires arena_client")

        response = arena_client.submit(self.slug, plan.config)

        if self.rate_limit_budget:
            self.rate_limit_budget.record(self.slug)
        self._append_log(plan, response, allow_exploit=allow_exploit)
        return {"status": "submitted", "response": response}

    def _append_log(
        self,
        plan: SubmissionPlan,
        response: dict[str, Any],
        *,
        allow_exploit: bool,
    ) -> None:
        if self.submissions_log_path is None:
            return
        path = self.submissions_log_path
        path.parent.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        lines: list[str] = []
        if not path.exists():
            lines.append("# Arena Submissions Log")
            lines.append("")
            lines.append(
                "Append-only record of every approved submission. Rigor verdict "
                "and allow_exploit flag are always captured."
            )
            lines.append("")
        lines.append(f"## {ts} — {self.slug}")
        lines.append("")
        lines.append(f"- **Arena score:** {plan.arena_score:.12g}")
        if plan.rigorous_score is not None:
            lines.append(f"- **Rigorous score:** {plan.rigorous_score:.12g}")
        lines.append(f"- **Verdict:** {plan.rigor_verdict}")
        if plan.rigor_verdict == "exploit":
            lines.append(f"- **allow_exploit flag:** {allow_exploit}")
            if plan.rigor_verdict_obj.exploit_factor:
                lines.append(
                    f"- **Exploit factor:** {plan.rigor_verdict_obj.exploit_factor:.3g}×"
                )
        if plan.rank_estimate is not None:
            lines.append(f"- **Rank estimate:** #{plan.rank_estimate}")
        lines.append(f"- **Response:** `{json.dumps(response, default=str)}`")
        lines.append("")

        existing = path.read_text() if path.exists() else ""
        path.write_text(existing + "\n".join(lines) + "\n")
