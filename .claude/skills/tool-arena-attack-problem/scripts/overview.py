"""OVERVIEW.md renderer (Gap 3).

Composes all the recon artifacts + hypothesis graph + agent outputs into a
single rich, human-readable briefing. This is what the user sees at the
Stage 5 gate before approving the attack campaign.

Sections (required, fixed order):
    ## Problem
    ## SOTA snapshot
    ## Published bounds
    ## Competitor forensics
    ## Hypothesis graph (top-5)
    ## Proposed attack directions
    ## Open questions
    ## Agent coverage
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional


def _section_from(md_path: Optional[Path], heading: str, fallback: str = "") -> str:
    """Extract `## heading ... (up to next ##)` from an agent artifact.

    Returns ``fallback`` if the file is missing or the heading absent.
    """
    if md_path is None or not md_path.exists():
        return fallback
    text = md_path.read_text()
    pat = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^##\s+|\Z)",
        re.DOTALL | re.MULTILINE,
    )
    m = pat.search(text)
    return m.group(1).strip() if m else fallback


def _top_k_hypotheses(graph: Any, k: int = 5) -> list[Any]:
    """Return up to k non-falsified, non-unreachable nodes ordered by priority."""
    active = [
        n for n in graph.nodes()
        if getattr(n, "status", "pending") in ("pending", "in_progress", "confirmed")
    ]
    active.sort(key=lambda n: (getattr(n, "priority", 10), getattr(n, "id", "")))
    return active[:k]


def _render_problem_section(recon: Any, slug: str) -> str:
    if recon is None or not getattr(recon, "problem", None):
        return f"- **Slug:** `{slug}`\n- (no problem.json in workspace yet)"
    p = recon.problem
    lines = [
        f"- **Title:** {p.get('title', 'N/A')}",
        f"- **Slug:** `{p.get('slug', slug)}`",
    ]
    if p.get("scoring"):
        lines.append(f"- **Scoring:** {p['scoring']}")
    if p.get("minImprovement") is not None:
        lines.append(f"- **Minimum improvement:** {p['minImprovement']}")
    desc = p.get("description") or p.get("statement") or ""
    if isinstance(desc, str) and desc:
        lines.append("")
        lines.append("> " + desc.strip().replace("\n", "\n> ")[:1200])
    return "\n".join(lines)


def _render_sota_snapshot(recon: Any) -> str:
    if recon is None or not getattr(recon, "leaderboard", None):
        return "- (no leaderboard snapshot -- recon ran offline or before first submission)"
    lb = recon.leaderboard
    lines = ["| Rank | Agent | Score | Submissions |", "|---|---|---|---|"]
    for i, row in enumerate(lb[:10], 1):
        agent = row.get("agent_name") or row.get("agent") or row.get("author") or "?"
        score = row.get("score") or row.get("bestScore") or "?"
        subs = row.get("submissions") or row.get("submission_count") or "?"
        lines.append(f"| {i} | {agent} | {score} | {subs} |")
    return "\n".join(lines)


def _render_bounds_from_literature(literature_md: Optional[Path]) -> str:
    bounds = _section_from(literature_md, "Published bounds", "")
    if not bounds:
        return "- (literature agent did not produce a `Published bounds` section)"
    return bounds


def _render_competitor_forensics(historian_md: Optional[Path]) -> str:
    diffs = _section_from(historian_md, "Per-rank structural diffs", "")
    sig = _section_from(historian_md, "Methodology signals from discussions", "")
    parts = []
    if diffs:
        parts.append("### Per-rank structural diffs\n\n" + diffs)
    if sig:
        parts.append("### Methodology signals\n\n" + sig)
    if not parts:
        return "- (historian agent output missing or empty)"
    return "\n\n".join(parts)


def _render_hypothesis_top_k(graph: Any, provenance: dict[str, list[str]]) -> str:
    top = _top_k_hypotheses(graph, k=5)
    if not top:
        return "- (no hypotheses in graph yet)"
    lines = []
    for n in top:
        hid = getattr(n, "id", "?")
        statement = getattr(n, "statement", "")
        priority = getattr(n, "priority", 10)
        kill = getattr(n, "kill_criterion", "") or "(no kill criterion)"
        prov = provenance.get(hid) or getattr(n, "provenance", []) or ["(unprovenance)"]
        lines.append(f"### {hid} -- {statement}")
        lines.append(f"- **Priority:** {priority}")
        lines.append(f"- **Kill criterion:** {kill}")
        lines.append(f"- **Provenance:** {', '.join(prov)}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _render_attack_directions(
    graph: Any, pattern_scout_md: Optional[Path]
) -> str:
    """Top-3 attack directions: highest-priority hypotheses + any HIGH-confidence
    pattern the pattern-scout surfaced."""
    top3 = _top_k_hypotheses(graph, k=3)
    if not top3 and (pattern_scout_md is None or not pattern_scout_md.exists()):
        return "- (no attack directions available -- run the 5 agents first)"
    lines = []
    for i, n in enumerate(top3, 1):
        statement = getattr(n, "statement", "")
        pri = getattr(n, "priority", 10)
        lines.append(f"**D{i}.** {statement} (priority={pri})")
    patterns_section = _section_from(
        pattern_scout_md, "Applicable patterns (ranked)", ""
    )
    if patterns_section:
        lines.append("")
        lines.append("**Cross-problem patterns matched:**")
        lines.append("")
        lines.append(patterns_section)
    return "\n".join(lines)


def _render_open_questions(literature_md: Optional[Path], critic_md: Optional[Path]) -> str:
    lit_q = _section_from(literature_md, "Open questions", "")
    crit_missing = _section_from(critic_md, "Missing hypotheses", "")
    parts = []
    if lit_q:
        parts.append("### From literature\n\n" + lit_q)
    if crit_missing:
        parts.append("### From critic's review\n\n" + crit_missing[:1200])
    if not parts:
        return "- (no open questions surfaced by literature or critic agents)"
    return "\n\n".join(parts)


def _render_agent_coverage(council_outputs: Any, warnings: list[str]) -> str:
    agents = [
        ("arena-literature-agent", council_outputs.literature),
        ("arena-historian-agent", council_outputs.historian),
        ("arena-pattern-scout-agent", council_outputs.pattern_scout),
        ("arena-rigor-agent", council_outputs.rigor),
        ("arena-critic-agent", council_outputs.critic),
    ]
    lines = ["| Agent | Status | Output |", "|---|---|---|"]
    for name, path in agents:
        if path is None:
            lines.append(f"| `{name}` | MISSING | (not spawned) |")
        elif not path.exists():
            lines.append(f"| `{name}` | MISSING | {path.name} not found |")
        else:
            size = path.stat().st_size
            lines.append(f"| `{name}` | present | `{path.name}` ({size} bytes) |")
    if warnings:
        lines.append("")
        lines.append("**Synthesiser warnings:**")
        for w in warnings:
            lines.append(f"- {w}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def render_overview(
    *,
    workspace: Path,
    recon: Any,
    graph: Any,
    provenance: dict[str, list[str]],
    council_outputs: Any,
    warnings: list[str],
) -> str:
    """Assemble the full OVERVIEW.md from all available recon artefacts."""
    slug = getattr(recon, "slug", workspace.name.removeprefix("einstein-arena-"))

    body = [
        f"# {slug} -- Campaign Overview",
        "",
        "<!-- Rendered by arena-attack-problem/scripts/overview.py after the",
        "     5-agent research fan-out + hypothesis graph synthesis.",
        "     This is the briefing the user sees at the Stage 5 gate. -->",
        "",
        "## Problem",
        "",
        _render_problem_section(recon, slug),
        "",
        "## SOTA snapshot",
        "",
        _render_sota_snapshot(recon),
        "",
        "## Published bounds",
        "",
        _render_bounds_from_literature(council_outputs.literature),
        "",
        "## Competitor forensics",
        "",
        _render_competitor_forensics(council_outputs.historian),
        "",
        "## Hypothesis graph (top-5)",
        "",
        _render_hypothesis_top_k(graph, provenance),
        "",
        "## Proposed attack directions",
        "",
        _render_attack_directions(graph, council_outputs.pattern_scout),
        "",
        "## Open questions",
        "",
        _render_open_questions(council_outputs.literature, council_outputs.critic),
        "",
        "## Agent coverage",
        "",
        _render_agent_coverage(council_outputs, warnings),
        "",
    ]
    return "\n".join(body)
