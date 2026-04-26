"""Arena watchdog — snapshot leaderboards, diff against yesterday, alert when
competitors move on problems we've attacked.

Not an optimization primitive. It's an operator-shaped tool:

1. ``take_snapshot(arena_client, problems)`` — fetch current leaderboards,
   persist to a timestamped JSON snapshot.
2. ``load_latest_snapshot()`` / ``load_previous_snapshot()`` — load from disk.
3. ``diff_snapshots(before, after)`` — produce a structured diff per problem:
   new leader, score-improved entries, new entries, dropped entries.
4. ``render_alert_markdown(diffs, watched_problems)`` — a 1-screen report
   filtered to the problems we've attacked (those produce actionable
   signals; other movements are informational at best).
5. ``Watchdog.run(...)`` — compose them; write ``WATCHDOG.md`` alert.

Intended deployment: registered as a daily ``ops-cron`` job that invokes
``python -m arena_framework.watchdog --run``. Operator / user reviews the
``WATCHDOG.md`` output and decides whether to reopen any problem.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional


# ---------------------------------------------------------------------------
# Snapshot + diff data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LeaderboardRow:
    rank: int
    agent_name: str
    score: float
    submission_count: Optional[int] = None


@dataclass(frozen=True)
class ProblemSnapshot:
    """Leaderboard for one problem at one point in time."""

    slug: str
    problem_id: Optional[int]
    rows: tuple[LeaderboardRow, ...]
    fetched_at: str


@dataclass(frozen=True)
class Snapshot:
    """Set of per-problem leaderboards captured at a single moment."""

    captured_at: str
    problems: dict[str, ProblemSnapshot]


@dataclass
class RowChange:
    agent_name: str
    before: Optional[LeaderboardRow]
    after: LeaderboardRow
    kind: str  # "new_entry" | "score_improved" | "rank_improved" | "unchanged"
    score_delta: Optional[float] = None


@dataclass
class ProblemDiff:
    """What happened on one problem between two snapshots."""

    slug: str
    leader_changed: bool
    previous_leader: Optional[str]
    current_leader: Optional[str]
    previous_leader_score: Optional[float]
    current_leader_score: Optional[float]
    leader_score_delta: Optional[float]
    changes: list[RowChange] = field(default_factory=list)
    dropped_agents: list[str] = field(default_factory=list)

    def has_news(self) -> bool:
        return bool(
            self.leader_changed
            or any(c.kind != "unchanged" for c in self.changes)
            or self.dropped_agents
        )


# ---------------------------------------------------------------------------
# Snapshot I/O
# ---------------------------------------------------------------------------


def _row_from_raw(rank: int, raw: dict[str, Any]) -> LeaderboardRow:
    return LeaderboardRow(
        rank=rank,
        agent_name=str(raw.get("agentName", raw.get("name", "?"))),
        score=float(raw.get("score", raw.get("bestScore", 0.0))),
        submission_count=raw.get("submissionCount", raw.get("submissions")),
    )


def build_problem_snapshot(
    slug: str,
    leaderboard: list[dict[str, Any]],
    *,
    problem_id: Optional[int] = None,
    fetched_at: Optional[str] = None,
) -> ProblemSnapshot:
    rows = tuple(
        _row_from_raw(i + 1, r) for i, r in enumerate(leaderboard)
    )
    return ProblemSnapshot(
        slug=slug,
        problem_id=problem_id,
        rows=rows,
        fetched_at=fetched_at or _utcnow_iso(),
    )


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def save_snapshot(snapshot: Snapshot, directory: Path) -> Path:
    """Persist a snapshot as JSON. Filename encodes capture time."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = snapshot.captured_at.replace(":", "").replace("-", "")
    out = directory / f"snapshot_{stamp}.json"
    out.write_text(json.dumps(_snapshot_to_dict(snapshot), indent=2))
    return out


def load_snapshot(path: Path) -> Snapshot:
    raw = json.loads(Path(path).read_text())
    problems = {
        slug: ProblemSnapshot(
            slug=slug,
            problem_id=ps.get("problem_id"),
            rows=tuple(
                LeaderboardRow(**r)
                for r in ps.get("rows", [])
            ),
            fetched_at=ps.get("fetched_at", raw.get("captured_at", "")),
        )
        for slug, ps in raw.get("problems", {}).items()
    }
    return Snapshot(captured_at=raw["captured_at"], problems=problems)


def load_latest_two(directory: Path) -> tuple[Optional[Snapshot], Optional[Snapshot]]:
    """Return (previous, latest) snapshots by filename sort order. Either may
    be None if the directory has <2 snapshots yet."""
    directory = Path(directory)
    if not directory.exists():
        return (None, None)
    snaps = sorted(directory.glob("snapshot_*.json"))
    latest = load_snapshot(snaps[-1]) if snaps else None
    previous = load_snapshot(snaps[-2]) if len(snaps) >= 2 else None
    return (previous, latest)


def _snapshot_to_dict(s: Snapshot) -> dict[str, Any]:
    return {
        "captured_at": s.captured_at,
        "problems": {
            slug: {
                "slug": ps.slug,
                "problem_id": ps.problem_id,
                "fetched_at": ps.fetched_at,
                "rows": [asdict(r) for r in ps.rows],
            }
            for slug, ps in s.problems.items()
        },
    }


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------


def diff_problem(
    before: Optional[ProblemSnapshot],
    after: ProblemSnapshot,
    *,
    score_rel_tol: float = 1e-9,
    score_abs_tol: float = 1e-12,
    lower_better: bool = True,
) -> ProblemDiff:
    """Produce a diff between two leaderboards for one problem.

    Agents are matched by name. A score change smaller than the tolerances
    is reported as "unchanged" to avoid noise from float roundtrips.
    """
    before_by_name: dict[str, LeaderboardRow] = (
        {r.agent_name: r for r in before.rows} if before else {}
    )
    after_by_name: dict[str, LeaderboardRow] = {r.agent_name: r for r in after.rows}

    changes: list[RowChange] = []
    for name, after_row in after_by_name.items():
        before_row = before_by_name.get(name)
        if before_row is None:
            changes.append(
                RowChange(agent_name=name, before=None, after=after_row, kind="new_entry")
            )
            continue
        score_delta = after_row.score - before_row.score
        scale = max(abs(before_row.score), abs(after_row.score))
        threshold = max(score_rel_tol * scale, score_abs_tol)
        if abs(score_delta) <= threshold and before_row.rank == after_row.rank:
            kind = "unchanged"
        elif (lower_better and score_delta < -threshold) or (
            not lower_better and score_delta > threshold
        ):
            kind = "score_improved"
        elif after_row.rank < before_row.rank:
            kind = "rank_improved"
        else:
            kind = "unchanged"
        changes.append(
            RowChange(
                agent_name=name,
                before=before_row,
                after=after_row,
                kind=kind,
                score_delta=score_delta,
            )
        )

    dropped = [name for name in before_by_name if name not in after_by_name]

    prev_leader = before.rows[0] if before and before.rows else None
    cur_leader = after.rows[0] if after.rows else None
    leader_changed = bool(
        (prev_leader is None) != (cur_leader is None)
        or (prev_leader and cur_leader and prev_leader.agent_name != cur_leader.agent_name)
    )
    leader_delta: Optional[float] = None
    if prev_leader and cur_leader:
        leader_delta = cur_leader.score - prev_leader.score

    return ProblemDiff(
        slug=after.slug,
        leader_changed=leader_changed,
        previous_leader=prev_leader.agent_name if prev_leader else None,
        current_leader=cur_leader.agent_name if cur_leader else None,
        previous_leader_score=prev_leader.score if prev_leader else None,
        current_leader_score=cur_leader.score if cur_leader else None,
        leader_score_delta=leader_delta,
        changes=changes,
        dropped_agents=dropped,
    )


def diff_snapshots(
    before: Optional[Snapshot],
    after: Snapshot,
    *,
    lower_better: bool = True,
) -> dict[str, ProblemDiff]:
    """Diff every problem that appears in ``after``. Problems in ``before``
    but not ``after`` are ignored — the watchdog only reports on what's
    currently live."""
    out: dict[str, ProblemDiff] = {}
    before_problems = before.problems if before else {}
    for slug, after_snap in after.problems.items():
        prev = before_problems.get(slug)
        out[slug] = diff_problem(prev, after_snap, lower_better=lower_better)
    return out


# ---------------------------------------------------------------------------
# Alert renderer
# ---------------------------------------------------------------------------


def render_alert_markdown(
    diffs: dict[str, ProblemDiff],
    *,
    watched_problems: Optional[set[str]] = None,
    now_iso: Optional[str] = None,
) -> str:
    """Produce a 1-screen report. Watched problems go first with full detail;
    unwatched problems get a tail summary line."""
    now_iso = now_iso or _utcnow_iso()
    watched = watched_problems or set()

    watched_diffs = [d for slug, d in diffs.items() if slug in watched and d.has_news()]
    other_news = [d for slug, d in diffs.items() if slug not in watched and d.has_news()]

    lines: list[str] = []
    lines.append("# Arena Watchdog Alert")
    lines.append("")
    lines.append(f"- **Captured:** {now_iso}")
    lines.append(f"- **Watched problems:** {len(watched)}")
    lines.append(f"- **Watched with news:** {len(watched_diffs)}")
    lines.append(f"- **Other problems with news:** {len(other_news)}")
    lines.append("")

    if not watched_diffs and not other_news:
        lines.append("No leaderboard movement detected.")
        lines.append("")
        return "\n".join(lines)

    if watched_diffs:
        lines.append("## Watched problems")
        lines.append("")
        for d in watched_diffs:
            lines.extend(_render_one_diff(d, detailed=True))
            lines.append("")

    if other_news:
        lines.append("## Other movement (informational)")
        lines.append("")
        for d in other_news:
            lines.extend(_render_one_diff(d, detailed=False))

    return "\n".join(lines)


def _render_one_diff(d: ProblemDiff, *, detailed: bool) -> list[str]:
    lines: list[str] = []
    if d.leader_changed:
        lines.append(
            f"### ⚠ {d.slug} — new leader **{d.current_leader}** "
            f"(was {d.previous_leader or '—'})"
        )
    else:
        lines.append(f"### {d.slug}")
    delta = d.leader_score_delta
    if d.previous_leader_score is not None and d.current_leader_score is not None:
        lines.append(
            f"- Leader score: {d.previous_leader_score:.6g} → {d.current_leader_score:.6g}"
            + (f" (Δ={delta:+.3e})" if delta is not None else "")
        )
    elif d.current_leader_score is not None:
        lines.append(f"- Leader score: {d.current_leader_score:.6g} (no prior snapshot)")

    changed = [c for c in d.changes if c.kind != "unchanged"]
    if detailed and changed:
        lines.append("")
        lines.append("| Agent | Change | Before → After |")
        lines.append("|-------|--------|-----------------|")
        for c in changed:
            if c.before is None:
                lines.append(
                    f"| {c.agent_name} | {c.kind} | — → {c.after.score:.6g} (rank #{c.after.rank}) |"
                )
            else:
                delta_str = f" ({c.score_delta:+.3e})" if c.score_delta is not None else ""
                lines.append(
                    f"| {c.agent_name} | {c.kind} | {c.before.score:.6g} → "
                    f"{c.after.score:.6g}{delta_str} |"
                )
    elif changed:
        # Non-detailed: just summarise count
        lines.append(f"- {len(changed)} agent(s) changed score/rank")

    if d.dropped_agents:
        lines.append(f"- Dropped agents: {', '.join(d.dropped_agents)}")
    return lines


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class Watchdog:
    """Coordinates snapshot capture, diff, and alert rendering for a list of
    problems. Daily cron entry point invokes ``Watchdog.run``."""

    def __init__(
        self,
        snapshot_dir: Path,
        *,
        watched_problems: Optional[set[str]] = None,
        lower_better_by_slug: Optional[dict[str, bool]] = None,
        clock: Callable[[], str] = _utcnow_iso,
    ) -> None:
        self.snapshot_dir = Path(snapshot_dir)
        self.watched_problems = set(watched_problems or [])
        self.lower_better_by_slug = lower_better_by_slug or {}
        self.clock = clock

    def take_snapshot(
        self,
        problems: list[str],
        *,
        arena_client: Any,
    ) -> Snapshot:
        """Fetch leaderboards for ``problems`` via the arena client and return
        an in-memory Snapshot."""
        snapshots: dict[str, ProblemSnapshot] = {}
        for slug in problems:
            try:
                prob = arena_client.get_problem(slug)
                pid = prob.get("id") if prob else None
                lb = arena_client.get_leaderboard(pid) if pid else []
                snapshots[slug] = build_problem_snapshot(slug, lb, problem_id=pid)
            except Exception as e:  # pragma: no cover
                # Record a failed fetch so the diff sees it as "no news" but we
                # don't silently miss a problem.
                snapshots[slug] = ProblemSnapshot(
                    slug=slug, problem_id=None, rows=(), fetched_at=_utcnow_iso()
                )
        return Snapshot(captured_at=self.clock(), problems=snapshots)

    def run(
        self,
        problems: list[str],
        *,
        arena_client: Any,
        alert_path: Optional[Path] = None,
    ) -> tuple[Snapshot, dict[str, ProblemDiff], str]:
        """End-to-end: snapshot -> save -> diff against previous -> render alert.

        Returns ``(snapshot, diffs, alert_markdown)``.
        """
        current = self.take_snapshot(problems, arena_client=arena_client)
        save_snapshot(current, self.snapshot_dir)
        previous, _latest = load_latest_two(self.snapshot_dir)
        # load_latest_two may return current as "latest"; use the one strictly
        # before the freshly-saved snapshot.
        prev_candidates = sorted(self.snapshot_dir.glob("snapshot_*.json"))
        prev_snapshot: Optional[Snapshot] = None
        if len(prev_candidates) >= 2:
            prev_snapshot = load_snapshot(prev_candidates[-2])

        # Compute diffs, applying per-problem lower_better policy
        diffs: dict[str, ProblemDiff] = {}
        before_problems = prev_snapshot.problems if prev_snapshot else {}
        for slug, after_snap in current.problems.items():
            lb = self.lower_better_by_slug.get(slug, True)
            diffs[slug] = diff_problem(before_problems.get(slug), after_snap, lower_better=lb)

        alert = render_alert_markdown(
            diffs, watched_problems=self.watched_problems, now_iso=current.captured_at
        )
        if alert_path is not None:
            Path(alert_path).parent.mkdir(parents=True, exist_ok=True)
            Path(alert_path).write_text(alert)
        return current, diffs, alert
