"""Seed generator for verified best-of-N attacks (Upgrade U4 + U7).

Three modes, selected by the caller based on the history available:

- ``diverse_rng``: stateless — emit N RNG seeds spaced across a large range.
  Default for first-round attacks.
- ``perturbation``: given a best-known state, emit N perturbations scaled by
  a schedule (useful for C₃-style basin escape: [0.5%, 1%, 1%, 2%]).
- ``opro``: given ``(params, score)`` history of length ≥ 8, ask Claude to
  propose the next K parameter sets (OPRO pattern, arXiv 2309.03409).

The OPRO mode depends on ``claude_client.propose_next_seeds`` which wraps the
Anthropic SDK. It respects ``LLMCallLimiter`` (60 calls/min default) and falls
back to ``perturbation`` if the SDK is unavailable — never a hard failure.
"""

from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from .parallel_runner import SeedSpec
from .rate_limiter import LLMCallLimiter, get_default_limiter


# ---------------------------------------------------------------------------
# History record
# ---------------------------------------------------------------------------


@dataclass
class HistoryEntry:
    """One (params, score) record from a prior attack round."""

    params: dict[str, Any]
    score: float
    seed: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "params": self.params,
            "score": self.score,
            "seed": self.seed,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "HistoryEntry":
        return cls(
            params=dict(d.get("params", {})),
            score=float(d["score"]),
            seed=int(d.get("seed", 0)),
            metadata=dict(d.get("metadata", {})),
        )


# ---------------------------------------------------------------------------
# Mode 1: diverse RNG
# ---------------------------------------------------------------------------


def generate_diverse_rng(
    *, n: int, base_seed: int = 0, stride: int = 100,
    base_config: Optional[dict[str, Any]] = None,
) -> list[SeedSpec]:
    """Emit ``n`` diverse RNG seeds. Stride chosen to separate the per-seed
    stochastic trajectories widely enough that replicas don't overlap in the
    first few iterations (observed on UP Track 1: base 200, stride 100 gave
    non-overlapping basins)."""
    base_config = dict(base_config or {})
    return [
        SeedSpec(
            seed=base_seed + i * stride,
            config=dict(base_config),
            tag=f"rng-{base_seed + i * stride}",
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Mode 2: perturbation of a best-known state
# ---------------------------------------------------------------------------


def generate_perturbations(
    *,
    n: int,
    base_state: Any,
    noise_schedule: Optional[list[float]] = None,
    base_seed: int = 1000,
    extra_config: Optional[dict[str, Any]] = None,
) -> list[SeedSpec]:
    """Emit ``n`` perturbation specs against a known-good state.

    ``noise_schedule`` is a list of relative-noise levels cycled across the
    N seeds. Defaults to the C₃ cascade recipe [0.01]*n. The state is passed
    verbatim to the attack function via ``config["base_state"]``.
    """
    if noise_schedule is None:
        noise_schedule = [0.01] * n
    extra = dict(extra_config or {})
    out: list[SeedSpec] = []
    for i in range(n):
        noise = float(noise_schedule[i % len(noise_schedule)])
        cfg = {
            **extra,
            "base_state": base_state,
            "rel_noise": noise,
            "perturbation_index": i,
        }
        out.append(
            SeedSpec(
                seed=base_seed + i * 100,
                config=cfg,
                tag=f"perturb-i{i}-noise{noise:.0e}",
            )
        )
    return out


# ---------------------------------------------------------------------------
# Mode 3: OPRO — LLM as optimizer over history
# ---------------------------------------------------------------------------


OPRO_SYSTEM_PROMPT = """You are an optimization proposer. Given a history of
(parameters, score) pairs from past rounds of an iterative attack on a math
optimization problem, you propose the next K parameter configurations likely
to produce better scores.

Rules:
1. Output ONLY a JSON array of K parameter objects. No prose, no markdown.
2. Each object must have the same keys as the input history entries.
3. You MUST produce diverse configurations — no two proposals within a round
   should differ only in a single parameter by less than 10% relative.
4. You MAY extrapolate beyond the observed range, but flag extreme jumps in a
   "rationale" key per proposal.
5. Prefer minimizing when the problem_goal is "minimize"; maximizing otherwise.
"""


def generate_opro_proposals(
    *,
    history: list[HistoryEntry],
    n: int,
    problem_goal: str = "minimize",
    base_seed: int = 5000,
    limiter: Optional[LLMCallLimiter] = None,
    client: Any = None,
) -> list[SeedSpec]:
    """Ask Claude for ``n`` next parameter sets given the history.

    Falls back to ``generate_perturbations`` around the best entry if:
      - ``history`` has fewer than 8 entries (insufficient signal)
      - the Anthropic SDK isn't installed
      - any LLM/network error occurs

    ``client`` defaults to an Anthropic client built from ``ANTHROPIC_API_KEY``
    (for tests, inject a stub with ``.messages.create`` returning a fake Reply
    whose ``.content[0].text`` is a JSON array).
    """
    if len(history) < 8:
        if history:
            best = min(history, key=lambda e: e.score) if problem_goal == "minimize" else max(history, key=lambda e: e.score)
            return generate_perturbations(
                n=n, base_state=best.params, base_seed=base_seed,
            )
        return generate_diverse_rng(n=n, base_seed=base_seed)

    limiter = limiter or get_default_limiter()
    client = client or _build_default_claude_client()
    if client is None:
        best = (
            min(history, key=lambda e: e.score)
            if problem_goal == "minimize"
            else max(history, key=lambda e: e.score)
        )
        return generate_perturbations(n=n, base_state=best.params, base_seed=base_seed)

    try:
        limiter.acquire()
    except RuntimeError:
        best = (
            min(history, key=lambda e: e.score)
            if problem_goal == "minimize"
            else max(history, key=lambda e: e.score)
        )
        return generate_perturbations(n=n, base_state=best.params, base_seed=base_seed)

    # Truncate to top-20 by score (per OPRO paper recommendation).
    sorted_hist = sorted(
        history,
        key=lambda e: e.score,
        reverse=(problem_goal == "maximize"),
    )
    shown = sorted_hist[:20]

    user_prompt = (
        f"problem_goal: {problem_goal}\n"
        f"n_requested: {n}\n"
        f"history (top 20 by score, best first):\n"
        + json.dumps([e.to_dict() for e in shown], indent=2)
        + "\n\nReturn a JSON array of exactly "
        + str(n)
        + " parameter objects."
    )

    try:
        reply = client.messages.create(
            model=os.environ.get("ORGANON_CLAUDE_MODEL", "claude-sonnet-4-6"),
            max_tokens=4000,
            system=OPRO_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = reply.content[0].text
        proposals = _parse_json_array(text)
    except Exception:
        best = (
            min(history, key=lambda e: e.score)
            if problem_goal == "minimize"
            else max(history, key=lambda e: e.score)
        )
        return generate_perturbations(n=n, base_state=best.params, base_seed=base_seed)

    out: list[SeedSpec] = []
    for i, p in enumerate(proposals[:n]):
        out.append(
            SeedSpec(
                seed=base_seed + i * 13,
                config={"params": p, "source": "opro"},
                tag=f"opro-{i}",
            )
        )
    if len(out) < n:
        # Top-up with perturbations so caller always gets N seeds back.
        best = (
            min(history, key=lambda e: e.score)
            if problem_goal == "minimize"
            else max(history, key=lambda e: e.score)
        )
        out.extend(
            generate_perturbations(
                n=n - len(out),
                base_state=best.params,
                base_seed=base_seed + 10000,
            )
        )
    return out


def _parse_json_array(text: str) -> list[dict[str, Any]]:
    """Extract the first JSON array from a model reply.

    Claude sometimes wraps arrays in prose despite instructions; this finds
    the first ``[ ... ]`` block and parses it.
    """
    text = text.strip()
    if text.startswith("["):
        return json.loads(text)
    i = text.find("[")
    j = text.rfind("]")
    if i == -1 or j == -1 or j <= i:
        raise ValueError("no JSON array in reply")
    return json.loads(text[i : j + 1])


def _build_default_claude_client() -> Any:
    """Build an Anthropic client or return None if SDK/key missing.

    Kept isolated so tests can stub ``client`` without importing anthropic.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic  # type: ignore

        return anthropic.Anthropic()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Persistent history log
# ---------------------------------------------------------------------------


def load_history(path: Path) -> list[HistoryEntry]:
    """Load the per-problem ``{problem}/history.jsonl`` log. Empty on missing."""
    if not Path(path).exists():
        return []
    entries: list[HistoryEntry] = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(HistoryEntry.from_dict(json.loads(line)))
        except (json.JSONDecodeError, KeyError):
            continue
    return entries


def append_history(path: Path, entry: HistoryEntry) -> None:
    """Append one entry. JSONL for crash-safe append-only semantics."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a") as f:
        f.write(json.dumps(entry.to_dict()) + "\n")
