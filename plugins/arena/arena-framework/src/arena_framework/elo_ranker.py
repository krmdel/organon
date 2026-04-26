"""Elo tournament ranking for near-threshold candidate selection (Upgrade U13).

When ≥3 candidates cluster near the same arena score (within
``min_improvement × shortcut_multiplier``), numeric scoring can't pick the
best submission reliably. This module runs pairwise Elo judgments — each
judgment returns which of two candidates has the more plausible solution
given their diagnostics — and picks whichever candidate ends the tournament
with the highest Elo rating.

Integration: the submit gate calls ``rank_candidates`` when it has multiple
near-tied candidates. In the overwhelming common case (one clear winner)
the shortcut fires and returns the numeric best without invoking the judge
at all.

Source: PLAN.md §5.3 U13 + HANDOFF.md §4 U13. The pattern is from Google
co-scientist (research memo 02 §B.15).

Design:

- Judge is injected so tests can hand a deterministic stub. Default
  ``default_llm_judge`` builds an Anthropic client and asks it to compare
  two candidates; on any failure it returns ``'tie'`` (4-path graceful
  degradation matching seed_generator + mutator).
- Standard Elo update with configurable K-factor. Default K=32 suits short
  tournaments (N ≤ 8 candidates → at most 28 pairwise games).
- Pairwise order is deterministic given input order: the ``itertools.combinations``
  schedule produces stable ratings for identical inputs.
- ``shortcut_multiplier`` of 10 × ``min_improvement`` is the default
  separator. If the top numeric gap exceeds that, numeric scoring wins
  outright and we skip the tournament.
"""

from __future__ import annotations

import itertools
import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .rate_limiter import LLMCallLimiter, get_default_limiter


# ---------------------------------------------------------------------------
# Candidate + result
# ---------------------------------------------------------------------------


@dataclass
class Candidate:
    """One near-threshold candidate under consideration.

    ``diagnostics`` is an opaque dict the judge reads — verdict notes,
    rigor verdict, source of the candidate, evaluator trace, etc. Whatever
    the caller wants the LLM to see.
    """

    candidate_id: str
    score: float
    diagnostics: dict[str, Any] = field(default_factory=dict)
    code_or_payload_path: Optional[str] = None


JudgeVerdict = str  # "a_better" | "b_better" | "tie"
JudgeFn = Callable[[Candidate, Candidate], JudgeVerdict]


@dataclass
class PairwiseGame:
    """One pairwise judgment in the tournament."""

    a_id: str
    b_id: str
    verdict: JudgeVerdict
    a_rating_before: float
    b_rating_before: float
    a_rating_after: float
    b_rating_after: float


@dataclass
class EloRanking:
    winner: Candidate
    final_ratings: dict[str, float]
    games: list[PairwiseGame] = field(default_factory=list)
    shortcut_reason: Optional[str] = None

    @property
    def n_games(self) -> int:
        return len(self.games)

    def to_dict(self) -> dict[str, Any]:
        return {
            "winner_id": self.winner.candidate_id,
            "winner_score": self.winner.score,
            "final_ratings": dict(self.final_ratings),
            "n_games": self.n_games,
            "shortcut_reason": self.shortcut_reason,
            "games": [
                {
                    "a": g.a_id,
                    "b": g.b_id,
                    "verdict": g.verdict,
                    "a_after": g.a_rating_after,
                    "b_after": g.b_rating_after,
                }
                for g in self.games
            ],
        }


# ---------------------------------------------------------------------------
# Elo math
# ---------------------------------------------------------------------------


def expected_score(r_a: float, r_b: float) -> float:
    """Standard Elo expected-score formula."""
    return 1.0 / (1.0 + 10 ** ((r_b - r_a) / 400.0))


def update_ratings(
    r_a: float, r_b: float, verdict: JudgeVerdict, *, k: float = 32.0
) -> tuple[float, float]:
    """Return new (r_a, r_b) after one game.

    Verdict 'a_better' → a_score = 1.0, b_score = 0.0.
    Verdict 'b_better' → flipped.
    Verdict 'tie'     → 0.5 / 0.5.
    """
    if verdict == "a_better":
        s_a, s_b = 1.0, 0.0
    elif verdict == "b_better":
        s_a, s_b = 0.0, 1.0
    elif verdict == "tie":
        s_a, s_b = 0.5, 0.5
    else:
        raise ValueError(f"unknown verdict: {verdict!r}")
    e_a = expected_score(r_a, r_b)
    e_b = 1.0 - e_a
    new_a = r_a + k * (s_a - e_a)
    new_b = r_b + k * (s_b - e_b)
    return new_a, new_b


# ---------------------------------------------------------------------------
# Default LLM judge
# ---------------------------------------------------------------------------


JUDGE_SYSTEM_PROMPT = """You are an arena submission judge. You are shown two
candidate solutions to the same math optimization problem, each with a score
and a diagnostics dictionary (rigor verdict, construction family, reviewer
notes, evaluator trace snippets, etc).

Pick which candidate you think is more plausible as a rigorous solution
worth submitting. The numeric score alone doesn't settle it — near-tied
scores often hide rigor failures, exploit patterns, or suspicious overfitting.

Output exactly ONE of these three tokens on its own line:

    a_better
    b_better
    tie

No prose, no JSON, no markdown. Just the token."""


def default_llm_judge(
    *,
    limiter: Optional[LLMCallLimiter] = None,
    client: Any = None,
) -> JudgeFn:
    """Return a judge function that calls Claude via the Anthropic SDK.

    Falls back to 'tie' on any of the four standard failure paths
    (no API key, rate-limited, parse error, exception). The submit gate
    should NEVER fail because the judge is unavailable — it falls through
    to numeric tie-break instead.
    """
    bound_client = client if client is not None else _build_default_claude_client()
    bound_limiter = limiter or get_default_limiter()

    def _judge(a: Candidate, b: Candidate) -> JudgeVerdict:
        if bound_client is None:
            return "tie"
        try:
            if not bound_limiter.acquire():
                return "tie"
        except RuntimeError:
            return "tie"

        prompt = _build_pairwise_prompt(a, b)
        try:
            reply = bound_client.messages.create(
                model=os.environ.get("ORGANON_CLAUDE_MODEL", "claude-sonnet-4-6"),
                max_tokens=50,
                system=JUDGE_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            text = reply.content[0].text.strip().lower()
        except Exception:  # noqa: BLE001 — universal fallback
            return "tie"

        if "a_better" in text:
            return "a_better"
        if "b_better" in text:
            return "b_better"
        return "tie"

    return _judge


def _build_pairwise_prompt(a: Candidate, b: Candidate) -> str:
    return (
        f"Candidate A (id={a.candidate_id}, score={a.score}):\n"
        f"{json.dumps(a.diagnostics, indent=2, default=str)}\n\n"
        f"Candidate B (id={b.candidate_id}, score={b.score}):\n"
        f"{json.dumps(b.diagnostics, indent=2, default=str)}\n\n"
        "Which is more plausible as a rigorous submission?"
    )


def _build_default_claude_client() -> Any:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic  # type: ignore

        return anthropic.Anthropic()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Tournament
# ---------------------------------------------------------------------------


def rank_candidates(
    candidates: list[Candidate],
    *,
    goal: str = "maximize",
    min_improvement: float = 1e-8,
    shortcut_multiplier: float = 10.0,
    judge_fn: Optional[JudgeFn] = None,
    k_factor: float = 32.0,
    initial_rating: float = 1500.0,
) -> EloRanking:
    """Return the best candidate per the Elo tournament.

    Shortcut paths (no judge calls):

    - ``len(candidates) < 2`` → only option wins by default.
    - ``len(candidates) == 2`` or the top numeric gap exceeds
      ``min_improvement × shortcut_multiplier`` → numeric winner wins;
      ``shortcut_reason`` is set accordingly.

    Otherwise the full N(N-1)/2 tournament runs.
    """
    if not candidates:
        raise ValueError("rank_candidates requires at least one candidate")
    if goal not in ("maximize", "minimize"):
        raise ValueError("goal must be 'maximize' or 'minimize'")

    if len(candidates) == 1:
        return EloRanking(
            winner=candidates[0],
            final_ratings={candidates[0].candidate_id: initial_rating},
            shortcut_reason="single_candidate",
        )

    sorted_cands = sorted(
        candidates,
        key=lambda c: c.score,
        reverse=(goal == "maximize"),
    )
    top = sorted_cands[0]
    runner_up = sorted_cands[1]
    gap = abs(top.score - runner_up.score)

    if len(candidates) < 3:
        return EloRanking(
            winner=top,
            final_ratings={c.candidate_id: initial_rating for c in candidates},
            shortcut_reason="fewer_than_3_candidates",
        )

    if gap > min_improvement * shortcut_multiplier:
        return EloRanking(
            winner=top,
            final_ratings={c.candidate_id: initial_rating for c in candidates},
            shortcut_reason="numeric_gap_exceeds_threshold",
        )

    # Full tournament.
    judge = judge_fn or default_llm_judge()
    ratings: dict[str, float] = {c.candidate_id: initial_rating for c in candidates}
    games: list[PairwiseGame] = []

    # Ensure all ids unique so ratings dict is unambiguous.
    seen: set[str] = set()
    for c in candidates:
        if c.candidate_id in seen:
            raise ValueError(f"duplicate candidate_id: {c.candidate_id}")
        seen.add(c.candidate_id)

    by_id = {c.candidate_id: c for c in candidates}
    for a_id, b_id in itertools.combinations(ratings.keys(), 2):
        a = by_id[a_id]
        b = by_id[b_id]
        verdict = judge(a, b)
        ra_before = ratings[a_id]
        rb_before = ratings[b_id]
        ra_after, rb_after = update_ratings(ra_before, rb_before, verdict, k=k_factor)
        ratings[a_id] = ra_after
        ratings[b_id] = rb_after
        games.append(
            PairwiseGame(
                a_id=a_id,
                b_id=b_id,
                verdict=verdict,
                a_rating_before=ra_before,
                b_rating_before=rb_before,
                a_rating_after=ra_after,
                b_rating_after=rb_after,
            )
        )

    # Pick winner: highest rating, tie-break on numeric score in goal direction.
    def _winner_key(cid: str) -> tuple[float, float]:
        c = by_id[cid]
        numeric = c.score if goal == "maximize" else -c.score
        return (ratings[cid], numeric)

    winner_id = max(ratings.keys(), key=_winner_key)
    return EloRanking(
        winner=by_id[winner_id],
        final_ratings=ratings,
        games=games,
    )
