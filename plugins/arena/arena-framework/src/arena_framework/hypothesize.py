"""arena-hypothesize — synthesises the 5-agent council into a hypothesis graph.

Inputs (all optional, graceful degradation on missing):
- `literature/LITERATURE.md` from arena-literature-agent
- `recon/COMPETITOR_FORENSICS.md` from arena-historian-agent
- `recon/APPLICABLE_PATTERNS.md` from arena-pattern-scout-agent
- `recon/CRITIQUE.md` from arena-critic-agent
- `recon/RIGOR_REPORT.md` from arena-rigor-agent (and rigor_scan.json)

Output:
- `HYPOTHESES.md`: hypothesis graph with per-node provenance recording
  which agent(s) contributed each hypothesis.

The synthesizer is deliberately rule-based (not LLM-based). Each agent
produces structured markdown; we parse specific sections and turn them
into hypothesis nodes. This keeps Slice 16 testable without live agent
invocations. The LLM invocation IS the agents themselves; this composer
just wires their outputs together.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .hypothesis_graph import HypothesisGraph, HypothesisNode


@dataclass
class CouncilOutputs:
    """Pointers to each agent's artifact. Any may be None (graceful
    degradation — the synthesizer still produces a graph)."""

    literature: Optional[Path] = None
    historian: Optional[Path] = None
    pattern_scout: Optional[Path] = None
    critic: Optional[Path] = None
    rigor: Optional[Path] = None

    @classmethod
    def from_recon_dir(cls, recon_dir: Path) -> "CouncilOutputs":
        """Discover agent outputs inside a recon_dir by convention."""
        recon_dir = Path(recon_dir)

        def _maybe(rel: str) -> Optional[Path]:
            p = recon_dir / rel
            return p if p.exists() else None

        return cls(
            literature=_maybe("literature/LITERATURE.md"),
            historian=_maybe("recon/COMPETITOR_FORENSICS.md"),
            pattern_scout=_maybe("recon/APPLICABLE_PATTERNS.md"),
            critic=_maybe("recon/CRITIQUE.md"),
            rigor=_maybe("recon/RIGOR_REPORT.md"),
        )


@dataclass
class HypothesizeResult:
    graph: HypothesisGraph
    provenance_by_node: dict[str, list[str]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Section extractors
# ---------------------------------------------------------------------------


def _extract_section(text: str, heading: str) -> str:
    """Return the content of a `## heading` section (up to the next `## `)."""
    pat = re.compile(rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^##\s+|\Z)",
                     re.DOTALL | re.MULTILINE)
    m = pat.search(text)
    return m.group(1).strip() if m else ""


def _open_questions(literature_md: str) -> list[str]:
    section = _extract_section(literature_md, "Open questions")
    # Open questions are bullet lines starting with "- "
    return [ln[2:].strip() for ln in section.splitlines() if ln.startswith("- ")]


def _exploit_signal(literature_md: str) -> bool:
    return "## EXPLOIT SIGNAL" in literature_md or "EXPLOIT SIGNAL" in literature_md


def _applicable_patterns(pattern_scout_md: str) -> list[tuple[str, str]]:
    """Return [(pattern_name, confidence), ...] from the APPLICABLE_PATTERNS.md
    'Applicable patterns (ranked)' table."""
    section = _extract_section(pattern_scout_md, "Applicable patterns (ranked)")
    out: list[tuple[str, str]] = []
    for line in section.splitlines():
        m = re.match(r"\|\s*`([\w-]+)`\s*\|\s*(\w+)\s*\|", line)
        if m:
            out.append((m.group(1), m.group(2)))
    return out


def _critic_missing_hypotheses(critic_md: str) -> list[dict]:
    """Extract `id`, `statement`, `kill_criterion`, `parents`, `priority`,
    `rationale` from the '## Missing hypotheses' section.

    Accepts two heading formats:
      ``### H-id`` — statement lives in the ``- **statement:**`` bullet
      ``### H-id — title`` — title in heading (stored as initial statement
        until/unless a ``- **statement:**`` bullet overrides it)
    """
    section = _extract_section(critic_md, "Missing hypotheses")
    # Heading regex: captures ID (first token), then optionally an em-dash
    # or hyphen-space separator followed by a title. Hyphen (``-``) inside
    # an id (e.g. ``H-alt-Singer-q-sweep``) is fine because only the FIRST
    # run of non-whitespace is the id.
    heading_re = re.compile(
        r"^###\s+(?P<id>\S+)(?:\s+[—-]\s+(?P<title>.*))?\s*$"
    )
    bullet_re = re.compile(
        r"^-\s+\*\*(?P<key>[\w_ ]+):\*\*\s+(?P<val>.*)$"
    )
    out: list[dict] = []
    current: Optional[dict] = None
    for line in section.splitlines():
        stripped = line.strip()
        heading = heading_re.match(stripped)
        if heading:
            if current is not None:
                out.append(current)
            current = {"id": heading.group("id")}
            title = heading.group("title")
            if title:
                current["statement"] = title.strip()
            continue
        if current is None:
            continue
        kv = bullet_re.match(stripped)
        if not kv:
            continue
        key = kv.group("key").strip().lower().replace(" ", "_")
        val = kv.group("val").strip()
        if key == "id":
            current["id"] = val
        elif key == "statement":
            current["statement"] = val
        elif key == "kill_criterion" or key == "kill":
            current["kill_criterion"] = val
        elif key == "success_criterion" or key == "success":
            current["success_criterion"] = val
        elif key == "parents":
            current["parents"] = [x.strip() for x in val.split(",") if x.strip()]
        elif key == "priority":
            try:
                current["priority"] = int(val)
            except ValueError:
                pass
        elif key == "rationale":
            current["rationale"] = val
    if current is not None:
        out.append(current)
    return out


def _critic_fatal_ids(critic_md: str) -> list[str]:
    """IDs of hypotheses marked FATAL in the Findings table."""
    section = _extract_section(critic_md, "Findings")
    out: list[str] = []
    for line in section.splitlines():
        m = re.match(r"\|\s*(\S+)\s*\|\s*FATAL\s*\|", line)
        if m:
            out.append(m.group(1))
    return out


def _rigor_exploit_k(rigor_md: str) -> Optional[int]:
    """Parse 'k = <n>' out of the Exploit line section. Returns None if
    rigor report has no exploit."""
    section = _extract_section(rigor_md, "Exploit line")
    m = re.search(r"k\s*[=≥]?\s*(\d+)", section)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Graph synthesis
# ---------------------------------------------------------------------------


def _record_provenance(
    provenance: dict[str, list[str]], node_id: str, agent: str
) -> None:
    provenance.setdefault(node_id, []).append(agent)


def synthesize(outputs: CouncilOutputs) -> HypothesizeResult:
    """Compose a hypothesis graph from whatever subset of agent outputs
    are available. Records per-node provenance; never raises on missing
    outputs (logs warnings instead)."""
    g = HypothesisGraph()
    provenance: dict[str, list[str]] = {}
    warnings: list[str] = []
    next_id = 1

    def nid() -> str:
        nonlocal next_id
        s = f"H{next_id}"
        next_id += 1
        return s

    # --- exploit signal: if literature flagged, seed a sturm-rigor-gate hypothesis
    if outputs.literature and outputs.literature.exists():
        lit = outputs.literature.read_text()
        if _exploit_signal(lit):
            h = nid()
            g.add_node(
                HypothesisNode(
                    id=h,
                    statement="Arena verifier exhibits a sturm-rigor-gate exploit",
                    success_criterion=(
                        "rigorous_score (via Sturm sqf_list) differs from arena "
                        "score by more than rel_tol on at least one top-K solution"
                    ),
                    kill_criterion=(
                        "rigor_gate verdicts are 'rigorous' for every top-K solution"
                    ),
                    priority=1,
                    provenance=["arena-literature-agent"],
                )
            )
            _record_provenance(provenance, h, "arena-literature-agent")

        # Open-question → hypothesis (one per literature open-question)
        for q in _open_questions(lit)[:5]:
            h = nid()
            g.add_node(
                HypothesisNode(
                    id=h,
                    statement=f"Address open question: {q}",
                    priority=7,
                    provenance=["arena-literature-agent"],
                )
            )
            _record_provenance(provenance, h, "arena-literature-agent")
    else:
        warnings.append("literature agent output missing")

    # --- applicable patterns → hypothesis per HIGH-confidence pattern
    if outputs.pattern_scout and outputs.pattern_scout.exists():
        ps = outputs.pattern_scout.read_text()
        for pattern_name, confidence in _applicable_patterns(ps):
            priority = {"HIGH": 2, "MEDIUM": 4, "LOW": 6}.get(confidence, 6)
            h = nid()
            g.add_node(
                HypothesisNode(
                    id=h,
                    statement=f"Apply pattern `{pattern_name}` to this problem",
                    priority=priority,
                    provenance=["arena-pattern-scout-agent"],
                    metadata={"pattern": pattern_name, "confidence": confidence},
                )
            )
            _record_provenance(provenance, h, "arena-pattern-scout-agent")
    else:
        warnings.append("pattern-scout agent output missing")

    # --- critic's missing hypotheses → graph nodes
    if outputs.critic and outputs.critic.exists():
        critic_md = outputs.critic.read_text()
        for entry in _critic_missing_hypotheses(critic_md):
            hid = entry.get("id") or nid()
            if hid in {n.id for n in g.nodes()}:
                # id collision with an existing node — prefix to disambiguate
                hid = f"{hid}.crit"
            try:
                g.add_node(
                    HypothesisNode(
                        id=hid,
                        statement=entry.get("statement", ""),
                        success_criterion=entry.get("success_criterion", ""),
                        kill_criterion=entry.get("kill_criterion", ""),
                        priority=entry.get("priority", 5),
                        parents=entry.get("parents", []),
                        provenance=["arena-critic-agent"],
                    )
                )
                _record_provenance(provenance, hid, "arena-critic-agent")
            except ValueError:
                warnings.append(f"critic proposed duplicate id {hid}; skipped")

        # Kill literature-FATAL'd hypotheses: not applicable here because the
        # critic FATAL targets draft hypotheses — we don't have a draft being
        # revised in this synthesis path. But if the critic listed IDs that
        # happen to exist in our graph, kill them.
        for fatal_id in _critic_fatal_ids(critic_md):
            if fatal_id in {n.id for n in g.nodes()}:
                g.kill(fatal_id, outcome="literature-FATAL per arena-critic-agent")
    else:
        warnings.append("critic agent output missing")

    # --- rigor report: if exploit line found, seed a k-climbing hypothesis
    if outputs.rigor and outputs.rigor.exists():
        rigor_md = outputs.rigor.read_text()
        exploit_k = _rigor_exploit_k(rigor_md)
        if exploit_k is not None:
            h = nid()
            g.add_node(
                HypothesisNode(
                    id=h,
                    statement=(
                        f"Exploit line at k = {exploit_k}: attacks at k < {exploit_k} "
                        "are rigorous; k >= {exploit_k} is exploit-only territory"
                    ),
                    success_criterion=(
                        f"rigorous attacks improve best rigorous score at k < {exploit_k}"
                    ),
                    kill_criterion=(
                        f"no rigorous improvement found after exhausting primitives "
                        f"at k < {exploit_k}"
                    ),
                    priority=2,
                    provenance=["arena-rigor-agent"],
                    metadata={"exploit_k": exploit_k},
                )
            )
            _record_provenance(provenance, h, "arena-rigor-agent")
    else:
        warnings.append("rigor agent output missing")

    # Historian signal: append as metadata to existing nodes if the historian
    # report mentions a technique already matched by pattern-scout. Otherwise
    # note in warnings. We don't create new nodes from historian output alone;
    # historian informs, it doesn't propose.
    if outputs.historian is None or not outputs.historian.exists():
        warnings.append("historian agent output missing")

    return HypothesizeResult(
        graph=g,
        provenance_by_node=provenance,
        warnings=warnings,
    )


def save_hypotheses(result: HypothesizeResult, out_path: Path) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(result.graph.to_markdown())
