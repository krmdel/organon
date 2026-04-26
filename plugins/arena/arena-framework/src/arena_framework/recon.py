"""Arena recon — load/fetch problem + leaderboard + top-K + discussions,
run rigor scan over top-K, emit ``SUMMARY.md`` with an exploit alert when
any top-K solution's arena score diverges from its rigorous score.

Designed for two modes:
- **Online**: calls ``tool-einstein-arena``'s ``EinsteinArena.fetch_all`` (needs
  creds + network). Writes artifacts to a per-problem ``recon/`` directory.
- **Offline / cached**: loads pre-fetched JSON files from a cache directory.
  Used by tests and replay scenarios.

The rigor scan looks up a per-problem evaluator registry. If no evaluator is
registered for a problem, every top-K verdict is ``"unknown"`` (not a false
exploit alarm). When a rigor cache is supplied (a JSON file with pre-computed
verdicts), it's used directly — eliminating compute cost on replay.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from .rigor_gate import RigorVerdict, classify_verdict, rigor_gate


@dataclass(frozen=True)
class RigorScanEntry:
    """One row of a rigor scan: per-solution verdict on whether the arena score
    agrees with a rigorous evaluation."""

    solution_id: int
    agent_name: str
    arena_score: float
    rigorous_score: Optional[float]
    verdict: str
    exploit_factor: Optional[float] = None
    k: Optional[int] = None  # problem-specific size parameter (e.g. UP Laguerre k)
    created_at: Optional[str] = None


@dataclass
class ReconArtifacts:
    """Bundle of recon outputs for a single arena problem."""

    slug: str
    problem: dict[str, Any]
    leaderboard: list[dict[str, Any]]
    top_solutions: list[dict[str, Any]]
    discussions: list[dict[str, Any]]
    rigor_scan: list[RigorScanEntry] = field(default_factory=list)
    summary_markdown: str = ""

    def has_exploit(self) -> bool:
        return any(e.verdict == "exploit" for e in self.rigor_scan)

    def exploit_entries(self) -> list[RigorScanEntry]:
        return [e for e in self.rigor_scan if e.verdict == "exploit"]


# ---------------------------------------------------------------------------
# Evaluator registry (per-problem)
# ---------------------------------------------------------------------------

# A registry entry wires together the three pieces a rigor scan needs:
#   arena_evaluator(config) -> float
#   rigorous_evaluator(config) -> (float, dict) | None
#   config_extractor(solution) -> config
# plus an optional k_extractor that surfaces the problem's size parameter so
# SUMMARY.md can flag "the exploit line" (e.g. k=15 for UP).

EvaluatorRegistry = dict[str, dict[str, Any]]


def _register_from_module(
    registry: EvaluatorRegistry, slug: str, module_name: str
) -> None:
    """Wire a per-problem adapter module into the registry.

    Each adapter exports four callables: ``arena_evaluator``,
    ``rigorous_evaluator``, ``config_extractor``, ``k_extractor``. Imports are
    deferred to call time via tiny wrappers so importing the registry stays
    cheap (the adapters themselves defer sympy/mpmath imports one level
    deeper).
    """
    mod_path = f".evaluators.{module_name}"

    def _arena(config):
        import importlib

        m = importlib.import_module(mod_path, package="arena_framework")
        return m.arena_evaluator(config)

    def _rigorous(config):
        import importlib

        m = importlib.import_module(mod_path, package="arena_framework")
        return m.rigorous_evaluator(config)

    def _config(solution):
        import importlib

        m = importlib.import_module(mod_path, package="arena_framework")
        return m.config_extractor(solution)

    def _k(solution):
        import importlib

        m = importlib.import_module(mod_path, package="arena_framework")
        return m.k_extractor(solution)

    registry[slug] = {
        "arena_evaluator": _arena,
        "rigorous_evaluator": _rigorous,
        "config_extractor": _config,
        "k_extractor": _k,
    }


# Canonical slug → module-name map. Slugs are the einstein-arena.com identifiers
# used in URLs and the ``problem.json`` ``slug`` field. Adding a new problem to
# this map AND dropping its adapter module into ``evaluators/<module>.py`` is
# all that's needed to light up rigor_scan for it.
EVALUATOR_MODULES: dict[str, str] = {
    "uncertainty-principle": "uncertainty_principle",
    "first-autocorrelation-inequality": "first_autocorrelation",
    "second-autocorrelation-inequality": "second_autocorrelation",
    "third-autocorrelation-inequality": "third_autocorrelation",
    "erdos-min-overlap": "erdos_min_overlap",
    "prime-number-theorem": "prime_number_theorem",
    "heilbronn-triangles": "heilbronn_triangles",
    "heilbronn-convex": "heilbronn_convex",
    "kissing-d11": "kissing_d11",
    "kissing-d12": "kissing_d12",
    "difference-bases": "difference_bases",
    "thomson-problem": "thomson_problem",
    "tammes-problem": "tammes_problem",
}


def default_evaluator_registry() -> EvaluatorRegistry:
    """Build the lazy-import evaluator registry for every problem we have an
    adapter module for. Registration covers 13 live problems as of
    2026-04-21 (Session 5 added second-autocorrelation, thomson, tammes)."""
    registry: EvaluatorRegistry = {}
    for slug, module_name in EVALUATOR_MODULES.items():
        _register_from_module(registry, slug, module_name)
    return registry


# ---------------------------------------------------------------------------
# Rigor scan driver
# ---------------------------------------------------------------------------


def run_rigor_scan(
    top_solutions: list[dict[str, Any]],
    *,
    slug: str,
    evaluator_registry: Optional[EvaluatorRegistry] = None,
    rigor_cache: Optional[list[dict[str, Any]]] = None,
    max_solutions: int = 10,
) -> list[RigorScanEntry]:
    """Run (or lookup) rigor classification for the top-K arena solutions.

    If ``rigor_cache`` is supplied, entries in it are matched by
    ``(agent_name, arena_score)`` and their cached rigorous_score is used
    without invoking the evaluator. This keeps tests fast and makes replay
    deterministic.

    If no ``rigor_cache`` and no matching registry entry exist, every row
    gets verdict ``"unknown"``. No false exploit alarms.
    """
    registry = evaluator_registry or {}
    reg_entry = registry.get(slug)

    cache_by_sig: dict[tuple[str, float], dict[str, Any]] = {}
    if rigor_cache:
        for c in rigor_cache:
            sig = (str(c.get("agent", "")), float(c.get("arena", 0.0)))
            cache_by_sig[sig] = c

    rows: list[RigorScanEntry] = []
    for sol in top_solutions[:max_solutions]:
        agent = str(sol.get("agentName", sol.get("agent", "?")))
        arena = float(sol.get("score", 0.0))
        k: Optional[int] = None
        if reg_entry and reg_entry.get("k_extractor"):
            try:
                k = reg_entry["k_extractor"](sol)
            except Exception:
                k = None

        cached = cache_by_sig.get((agent, arena))
        if cached:
            rigorous = float(cached.get("rigor", cached.get("rigorous_score", 0.0)))
            verdict, _gap, _rel, exploit_factor = classify_verdict(arena, rigorous)
            rows.append(
                RigorScanEntry(
                    solution_id=int(sol.get("id", 0)),
                    agent_name=agent,
                    arena_score=arena,
                    rigorous_score=rigorous,
                    verdict=verdict,
                    exploit_factor=exploit_factor,
                    k=k or cached.get("k"),
                    created_at=sol.get("createdAt"),
                )
            )
            continue

        if reg_entry:
            try:
                cfg = reg_entry["config_extractor"](sol)
                verdict_obj = rigor_gate(
                    cfg,
                    reg_entry["arena_evaluator"],
                    reg_entry["rigorous_evaluator"],
                )
                rows.append(
                    RigorScanEntry(
                        solution_id=int(sol.get("id", 0)),
                        agent_name=agent,
                        arena_score=verdict_obj.arena_score,
                        rigorous_score=verdict_obj.rigorous_score,
                        verdict=verdict_obj.verdict,
                        exploit_factor=verdict_obj.exploit_factor,
                        k=k,
                        created_at=sol.get("createdAt"),
                    )
                )
                continue
            except Exception:  # pragma: no cover - evaluator failures handled gracefully
                pass

        # No registry entry and no cache -> unknown verdict
        rows.append(
            RigorScanEntry(
                solution_id=int(sol.get("id", 0)),
                agent_name=agent,
                arena_score=arena,
                rigorous_score=None,
                verdict="unknown",
                k=k,
                created_at=sol.get("createdAt"),
            )
        )

    return rows


# ---------------------------------------------------------------------------
# SUMMARY.md renderer
# ---------------------------------------------------------------------------


def render_summary_markdown(art: ReconArtifacts) -> str:
    """Render a 1-page recon summary as markdown. Downstream skills
    (arena-hypothesize, submit-gate) read this verbatim."""
    lines: list[str] = []
    prob = art.problem or {}
    title = prob.get("title", art.slug)
    prob_id = prob.get("id", "?")
    scoring = prob.get("scoring", "?")
    min_impr = prob.get("minImprovement", "?")

    lines.append(f"# Recon — {title}")
    lines.append("")
    lines.append(f"- **Slug:** `{art.slug}`")
    lines.append(f"- **Problem ID:** {prob_id}")
    lines.append(f"- **Scoring:** {scoring}")
    lines.append(f"- **Min improvement:** {min_impr}")
    lines.append(f"- **Leaderboard entries:** {len(art.leaderboard)}")
    lines.append(f"- **Top solutions fetched:** {len(art.top_solutions)}")
    lines.append(f"- **Discussion threads:** {len(art.discussions)}")
    lines.append("")

    # Exploit alert (first, so a reader can't miss it)
    exploits = art.exploit_entries()
    if exploits:
        lines.append("## ⚠ EXPLOIT DETECTED")
        lines.append("")
        lines.append(
            "One or more top-K solutions score significantly below their "
            "rigorous mathematical value. The arena's verifier is accepting "
            "numerical artifacts as claimed upper/lower bounds. Any submission "
            "relying on this pattern would claim a mathematical result that "
            "isn't true — the framework's submit gate will refuse without "
            "`--allow-exploit`."
        )
        lines.append("")

        k_values_exploited = sorted({e.k for e in exploits if e.k is not None})
        if k_values_exploited:
            lowest = min(k_values_exploited)
            lines.append(
                f"**Exploit line**: verdict flips to exploit starting at "
                f"**k = {lowest}** (observed k values: {k_values_exploited}). "
                f"Below this, leaderboard entries are rigorous bounds; above, "
                f"they are float-precision artifacts."
            )
            lines.append("")

        lines.append("| Agent | k | Arena | Rigorous | Factor |")
        lines.append("|-------|---|-------|----------|--------|")
        for e in exploits:
            k_str = str(e.k) if e.k is not None else "?"
            fac = f"{e.exploit_factor:.1f}×" if e.exploit_factor else "?"
            rig = f"{e.rigorous_score:.4f}" if e.rigorous_score is not None else "?"
            lines.append(
                f"| {e.agent_name} | {k_str} | {e.arena_score:.6f} | {rig} | {fac} |"
            )
        lines.append("")

    # Leaderboard
    if art.leaderboard:
        lines.append("## Leaderboard (top 10)")
        lines.append("")
        lines.append("| # | Agent | Score | Submissions |")
        lines.append("|---|-------|-------|-------------|")
        for i, lb in enumerate(art.leaderboard[:10], 1):
            name = lb.get("agentName", lb.get("name", "?"))
            score = lb.get("score", lb.get("bestScore", "?"))
            subs = lb.get("submissionCount", lb.get("submissions", "?"))
            lines.append(f"| {i} | {name} | {score} | {subs} |")
        lines.append("")

    # Rigor scan table (full)
    if art.rigor_scan:
        lines.append("## Rigor scan")
        lines.append("")
        lines.append(
            "Per-solution classification: does the arena score match a "
            "rigorous mathematical evaluation? `rigorous` = yes (certifiable). "
            "`exploit` = no (numerical artifact). `unknown` = no rigorous "
            "evaluator registered for this problem."
        )
        lines.append("")
        lines.append("| Agent | k | Arena | Rigorous | Verdict |")
        lines.append("|-------|---|-------|----------|---------|")
        for e in art.rigor_scan:
            k_str = str(e.k) if e.k is not None else "?"
            rig = f"{e.rigorous_score:.4f}" if e.rigorous_score is not None else "—"
            lines.append(
                f"| {e.agent_name} | {k_str} | {e.arena_score:.6f} | {rig} | {e.verdict} |"
            )
        lines.append("")

    # Discussion snippets
    if art.discussions:
        lines.append("## Discussions")
        lines.append("")
        lines.append(f"Fetched {len(art.discussions)} threads. See `discussions.json`.")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main recon driver
# ---------------------------------------------------------------------------


class Recon:
    """Load (cached) or fetch (live) arena recon for a problem, run rigor scan,
    emit SUMMARY.md.

    Example — offline replay from an existing project folder::

        recon = Recon("uncertainty-principle", cache_dir=Path("projects/einstein-arena-uncertainty-principle"))
        art = recon.run()
        (output_dir / "SUMMARY.md").write_text(art.summary_markdown)

    Example — online (requires tool-einstein-arena creds)::

        recon = Recon("thomson-problem")
        art = recon.run_live(output_dir=Path("projects/einstein-arena-thomson-problem/recon"))
    """

    def __init__(
        self,
        slug: str,
        *,
        cache_dir: Optional[Path] = None,
        evaluator_registry: Optional[EvaluatorRegistry] = None,
        rigor_cache_path: Optional[Path] = None,
        max_top_solutions: int = 10,
    ) -> None:
        self.slug = slug
        self.cache_dir = Path(cache_dir) if cache_dir else None
        # Use `is None` not `or`: an explicit empty dict means "disable the
        # default registry", which tests rely on to keep the rigor scan offline.
        self.evaluator_registry = (
            default_evaluator_registry() if evaluator_registry is None else evaluator_registry
        )
        self.rigor_cache_path = Path(rigor_cache_path) if rigor_cache_path else None
        self.max_top_solutions = max_top_solutions

    def _load_cached(self) -> ReconArtifacts:
        assert self.cache_dir is not None
        c = self.cache_dir

        def _load(name: str, default):
            p = c / name
            if p.exists():
                return json.loads(p.read_text())
            return default

        return ReconArtifacts(
            slug=self.slug,
            problem=_load("problem.json", {}),
            leaderboard=_load("leaderboard.json", []),
            top_solutions=_load("best_solutions.json", []),
            discussions=_load("discussions.json", []),
        )

    def _load_rigor_cache(self) -> Optional[list[dict[str, Any]]]:
        if not self.rigor_cache_path or not self.rigor_cache_path.exists():
            return None
        return json.loads(self.rigor_cache_path.read_text())

    def run(self) -> ReconArtifacts:
        """Offline path: load from cache_dir, run rigor scan, render summary."""
        if self.cache_dir is None:
            raise ValueError("run() requires cache_dir; use run_live() to fetch online")
        art = self._load_cached()
        rigor_cache = self._load_rigor_cache()
        art.rigor_scan = run_rigor_scan(
            art.top_solutions,
            slug=self.slug,
            evaluator_registry=self.evaluator_registry,
            rigor_cache=rigor_cache,
            max_solutions=self.max_top_solutions,
        )
        art.summary_markdown = render_summary_markdown(art)
        return art

    def run_live(
        self,
        *,
        output_dir: Path,
        arena_client: Optional[Any] = None,
    ) -> ReconArtifacts:
        """Online path: call tool-einstein-arena fetch_all, then run rigor scan.

        ``arena_client`` lets tests inject a stub; production path builds a
        real EinsteinArena client from tool-einstein-arena at call time.
        """
        if arena_client is None:
            arena_client = _build_arena_client()

        raw = arena_client.fetch_all(self.slug, output_dir=str(output_dir))
        art = ReconArtifacts(
            slug=self.slug,
            problem=raw.get("problem", {}),
            leaderboard=raw.get("leaderboard", []),
            top_solutions=raw.get("solutions", []),
            discussions=raw.get("discussions", []),
        )
        rigor_cache = self._load_rigor_cache()
        art.rigor_scan = run_rigor_scan(
            art.top_solutions,
            slug=self.slug,
            evaluator_registry=self.evaluator_registry,
            rigor_cache=rigor_cache,
            max_solutions=self.max_top_solutions,
        )
        art.summary_markdown = render_summary_markdown(art)
        return art

    def save(self, art: ReconArtifacts, output_dir: Path) -> None:
        """Write all recon artifacts to ``output_dir``. Idempotent."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "problem.json").write_text(json.dumps(art.problem, indent=2))
        (output_dir / "leaderboard.json").write_text(json.dumps(art.leaderboard, indent=2))
        (output_dir / "best_solutions.json").write_text(
            json.dumps(art.top_solutions, indent=2)
        )
        (output_dir / "discussions.json").write_text(json.dumps(art.discussions, indent=2))
        rigor_rows = [
            {
                "solution_id": e.solution_id,
                "agent": e.agent_name,
                "arena": e.arena_score,
                "rigorous": e.rigorous_score,
                "verdict": e.verdict,
                "exploit_factor": e.exploit_factor,
                "k": e.k,
                "created_at": e.created_at,
            }
            for e in art.rigor_scan
        ]
        (output_dir / "rigor_scan.json").write_text(json.dumps(rigor_rows, indent=2))
        (output_dir / "SUMMARY.md").write_text(art.summary_markdown)


def _build_arena_client() -> Any:
    """Lazy-import the real EinsteinArena client from tool-einstein-arena.

    Kept isolated so tests can stub ``arena_client`` without pulling ``requests``.
    """
    import sys
    from pathlib import Path

    skill_scripts = (
        Path(__file__).resolve().parents[4]
        / ".claude"
        / "skills"
        / "tool-einstein-arena"
        / "scripts"
    )
    if str(skill_scripts) not in sys.path:
        sys.path.insert(0, str(skill_scripts))
    from arena_ops import EinsteinArena  # type: ignore

    return EinsteinArena()
