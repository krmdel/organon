"""arena-retrospective — post-attack self-improvement loop.

Inputs:
- A completed attack's hypothesis graph (HYPOTHESES.md).
- A session summary describing what worked, what failed, what was
  hand-rolled. Either a free-form file path, or a structured
  ``SessionSummary`` object.
- Access to the framework's existing `arena-patterns/` and test fixture
  bank so we can identify what's already covered.

Outputs:
- ``RETROSPECTIVE.md`` — structured report with sections:
  * Confirmed hypotheses (what succeeded)
  * Falsified hypotheses (what the graph killed)
  * New pattern candidates (techniques from the session not yet in
    `arena-patterns/`)
  * Fixture additions (new problem solutions we should regression-test)
  * Missing primitive flags (hand-rolled code to promote)
  * Learnings to append to `context/learnings.md`

The retrospective is deliberately conservative: it proposes actions, it
doesn't take them. The user reviews RETROSPECTIVE.md and decides which
promotions to merge. This keeps the self-improvement loop auditable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .hypothesis_graph import HypothesisGraph


@dataclass
class SessionSummary:
    """What the attack produced, beyond what's recorded in the graph.

    Populated by the orchestrator (``arena-attack-problem``) at the end
    of a run, or hand-edited by the operator.
    """

    slug: str
    final_arena_score: Optional[float] = None
    final_rigorous_score: Optional[float] = None
    final_verdict: Optional[str] = None  # "rigorous" | "exploit" | "unknown"
    techniques_used: list[str] = field(default_factory=list)
    hand_rolled_snippets: list[str] = field(default_factory=list)
    wall_time_hours: Optional[float] = None
    surprises: list[str] = field(default_factory=list)


@dataclass
class NovelResult:
    """A candidate that beats an existing fixture's arena score by >= min_improvement.

    Emitted by the retrospective's novelty fallback (Section 4.1) when the
    hypothesis graph itself carries no confirmed nodes but the final
    candidate materially improves over the fixture baseline.
    """

    fixture_name: str
    fixture_arena_score: float
    candidate_arena_score: float
    improvement_abs: float
    improvement_pct: float
    min_improvement: float


@dataclass
class RetrospectiveResult:
    markdown: str
    new_pattern_candidates: list[str] = field(default_factory=list)
    fixture_addition_slug: Optional[str] = None
    missing_primitive_flags: list[str] = field(default_factory=list)
    learnings_entries: list[str] = field(default_factory=list)
    novel_result: Optional[NovelResult] = None


def _load_known_patterns(patterns_dir: Path) -> set[str]:
    if not patterns_dir.exists():
        return set()
    return {p.stem for p in patterns_dir.glob("*.md") if p.stem != "INDEX"}


def _fixture_exists(fixtures_dir: Path, slug: str) -> bool:
    if not fixtures_dir.exists():
        return False
    return (fixtures_dir / slug).exists() or any(
        p.name.startswith(slug) for p in fixtures_dir.iterdir() if p.is_dir()
    )


def _load_fixture_reference(
    fixtures_dir: Path, slug: str, verdict: Optional[str]
) -> Optional[tuple[str, float]]:
    """Find the best-matching fixture to compare a candidate against.

    Returns ``(fixture_dir_name, expected_arena_score)`` or ``None`` when no
    usable fixture exists. Match rules:

    - Direct match on ``<slug>/fixture.json`` wins.
    - Otherwise scan siblings whose name starts with ``<slug>-`` (e.g.
      ``uncertainty-principle`` matches ``uncertainty-principle-path-a``).
    - When multiple siblings match, prefer one whose ``rigor_verdict`` equals
      the candidate's verdict (exploit vs rigorous), then fall back to the
      lowest ``expected_arena_score`` — the toughest existing baseline.
    """

    if not fixtures_dir.exists():
        return None

    candidates: list[tuple[str, float, Optional[str]]] = []
    for sub in fixtures_dir.iterdir():
        if not sub.is_dir():
            continue
        matches = sub.name == slug or sub.name.startswith(slug + "-")
        if not matches:
            continue
        fx = sub / "fixture.json"
        if not fx.exists():
            continue
        try:
            data = json.loads(fx.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        score = data.get("expected_arena_score")
        if not isinstance(score, (int, float)):
            continue
        candidates.append((sub.name, float(score), data.get("rigor_verdict")))

    if not candidates:
        return None

    if verdict:
        for name, score, fixture_verdict in candidates:
            if fixture_verdict == verdict:
                return (name, score)

    best = min(candidates, key=lambda c: c[1])
    return (best[0], best[1])


def _check_novelty(
    summary: SessionSummary,
    fixtures_dir: Path,
    *,
    min_improvement: float,
) -> Optional[NovelResult]:
    """Candidate-level novelty detector.

    When the hypothesis graph has no confirmed nodes the retrospective would
    otherwise emit an empty learnings section. This fallback compares the
    session's ``final_arena_score`` against the closest matching fixture;
    when the candidate beats the reference by more than ``min_improvement``
    it surfaces the improvement as a novel-result learning.
    """

    if summary.final_arena_score is None:
        return None

    match = _load_fixture_reference(fixtures_dir, summary.slug, summary.final_verdict)
    if match is None:
        return None

    name, fixture_score = match
    improvement_abs = fixture_score - summary.final_arena_score
    if improvement_abs <= min_improvement:
        return None

    improvement_pct = (
        (improvement_abs / fixture_score) * 100.0 if fixture_score > 0 else 0.0
    )
    return NovelResult(
        fixture_name=name,
        fixture_arena_score=fixture_score,
        candidate_arena_score=float(summary.final_arena_score),
        improvement_abs=improvement_abs,
        improvement_pct=improvement_pct,
        min_improvement=min_improvement,
    )


def run_retrospective(
    graph: HypothesisGraph,
    summary: SessionSummary,
    *,
    patterns_dir: Path,
    fixtures_dir: Path,
    min_improvement: float = 1e-5,
) -> RetrospectiveResult:
    known_patterns = _load_known_patterns(patterns_dir)
    confirmed = graph.by_status("confirmed")
    falsified = graph.by_status("falsified")
    pending = [n for n in graph.nodes() if n.status in ("pending", "in_progress")]

    # Pattern candidates = techniques used but not in the known pattern set
    new_patterns = []
    for tech in summary.techniques_used:
        # Normalise into kebab-case for pattern name comparison
        pattern_candidate = tech.lower().replace(" ", "-").replace("_", "-")
        if pattern_candidate not in known_patterns:
            new_patterns.append(pattern_candidate)

    # Missing primitives = hand-rolled snippets that don't already exist
    # as arena_framework.primitives modules
    missing_primitives = []
    for snip in summary.hand_rolled_snippets:
        # Simple heuristic: snippets mentioning "polish", "anneal", "snap",
        # "basin", "tempering", etc. that don't map to an existing primitive
        # are candidates for promotion.
        if not _looks_like_existing_primitive(snip):
            missing_primitives.append(snip)

    # Fixture addition if this problem isn't in our fixture bank
    fixture_add: Optional[str] = None
    if not _fixture_exists(fixtures_dir, summary.slug):
        fixture_add = summary.slug

    # Candidate-level novelty fallback (Section 4.1): surfaces a learning
    # even when the hypothesis graph has no confirmed nodes, as long as the
    # final candidate beats the fixture by more than min_improvement.
    novel_result = _check_novelty(
        summary, fixtures_dir, min_improvement=min_improvement
    )

    # Learnings: one line per confirmed hypothesis + one per surprise +
    # one for any novel result.
    learnings: list[str] = []
    for node in confirmed[:5]:
        if node.outcome:
            learnings.append(f"{node.id} confirmed: {node.outcome}")
    for surprise in summary.surprises[:3]:
        learnings.append(f"Surprise: {surprise}")
    if novel_result is not None:
        learnings.append(
            f"Novel result: arena_score {novel_result.candidate_arena_score:.10g} "
            f"beats fixture {novel_result.fixture_name} "
            f"({novel_result.fixture_arena_score:.10g}) by "
            f"{novel_result.improvement_pct:.2f}% "
            f"(abs {novel_result.improvement_abs:.2e}, above min_improvement "
            f"{novel_result.min_improvement:.0e})"
        )

    md = _render_markdown(
        summary=summary,
        graph=graph,
        confirmed=confirmed,
        falsified=falsified,
        pending=pending,
        new_patterns=new_patterns,
        missing_primitives=missing_primitives,
        fixture_add=fixture_add,
        learnings=learnings,
        novel_result=novel_result,
    )
    return RetrospectiveResult(
        markdown=md,
        new_pattern_candidates=new_patterns,
        fixture_addition_slug=fixture_add,
        missing_primitive_flags=missing_primitives,
        learnings_entries=learnings,
        novel_result=novel_result,
    )


def _looks_like_existing_primitive(snippet: str) -> bool:
    """Rough map: mention of primitive-style keyword suggests we already have
    it. Conservative — missing this test is fine, it just surfaces more
    candidates for review."""
    tokens = [
        "ParallelTemperingSA",
        "ulp_polish",
        "smooth_max_beta",
        "dyadic_snap",
        "dinkelbach",
        "basin_hopping",
        "column_generation",
        "rigor_gate",
    ]
    return any(t in snippet for t in tokens)


def _render_markdown(
    *,
    summary: SessionSummary,
    graph: HypothesisGraph,
    confirmed: list,
    falsified: list,
    pending: list,
    new_patterns: list[str],
    missing_primitives: list[str],
    fixture_add: Optional[str],
    learnings: list[str],
    novel_result: Optional[NovelResult] = None,
) -> str:
    lines: list[str] = [f"# Retrospective — {summary.slug}", ""]
    lines.append("## Session summary")
    lines.append("")
    if summary.final_arena_score is not None:
        lines.append(f"- **Final arena score:** {summary.final_arena_score:.10g}")
    if summary.final_rigorous_score is not None:
        lines.append(f"- **Final rigorous score:** {summary.final_rigorous_score:.10g}")
    if summary.final_verdict:
        lines.append(f"- **Final verdict:** {summary.final_verdict}")
    if summary.wall_time_hours is not None:
        lines.append(f"- **Wall-clock:** {summary.wall_time_hours:.2f} h")
    lines.append("")

    lines.append("## Hypothesis graph summary")
    lines.append("")
    lines.append(f"- Confirmed: {len(confirmed)} — {[n.id for n in confirmed]}")
    lines.append(f"- Falsified: {len(falsified)} — {[n.id for n in falsified]}")
    lines.append(f"- Pending / in-progress: {len(pending)} — {[n.id for n in pending]}")
    lines.append("")

    if confirmed:
        lines.append("## Confirmed hypotheses")
        lines.append("")
        for n in confirmed:
            lines.append(f"- **{n.id}**: {n.statement}")
            if n.outcome:
                lines.append(f"  - Outcome: {n.outcome}")
        lines.append("")

    if falsified:
        lines.append("## Falsified hypotheses")
        lines.append("")
        for n in falsified:
            lines.append(f"- **{n.id}**: {n.statement}")
            if n.outcome:
                lines.append(f"  - Kill reason: {n.outcome}")
        lines.append("")

    lines.append("## Proposed framework additions")
    lines.append("")
    if novel_result is not None:
        lines.append("### Novel result")
        lines.append("")
        lines.append(
            f"- candidate arena_score = {novel_result.candidate_arena_score:.10g}"
        )
        lines.append(
            f"- fixture reference    = {novel_result.fixture_arena_score:.10g} "
            f"(`{novel_result.fixture_name}`)"
        )
        lines.append(
            f"- improvement          = {novel_result.improvement_pct:.2f}% "
            f"(abs {novel_result.improvement_abs:.2e}, above min_improvement "
            f"{novel_result.min_improvement:.0e})"
        )
        lines.append("")
    if new_patterns:
        lines.append("### New pattern candidates")
        lines.append("")
        for name in new_patterns:
            lines.append(f"- `{name}` — seen in this session but not in `arena-patterns/`")
        lines.append("")
    elif novel_result is None:
        lines.append("No new pattern candidates. Every technique used is already documented.")
        lines.append("")

    if missing_primitives:
        lines.append("### Missing primitive flags")
        lines.append("")
        for snip in missing_primitives:
            lines.append(f"- {snip}")
        lines.append("")

    if fixture_add:
        lines.append("### Fixture addition")
        lines.append("")
        lines.append(
            f"- Add regression fixture for `{fixture_add}` to "
            f"`tests/arena_fixtures/{fixture_add}/fixture.json`."
        )
        lines.append(
            "  Run `python3 scripts/generate_fixtures.py` after adding the "
            "builder for this slug."
        )
        lines.append("")

    if learnings:
        lines.append("## Learnings (append to `context/learnings.md`)")
        lines.append("")
        for entry in learnings:
            lines.append(f"- {entry}")
        lines.append("")

    lines.append("## Action items")
    lines.append("")
    if not (new_patterns or missing_primitives or fixture_add or learnings or novel_result):
        lines.append("No framework changes proposed from this session.")
    else:
        lines.append(
            "Operator: review the sections above and merge approved additions."
        )
    lines.append("")
    return "\n".join(lines)


def save_retrospective(result: RetrospectiveResult, out_path: Path) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(result.markdown)
