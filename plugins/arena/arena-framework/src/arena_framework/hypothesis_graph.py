"""Hypothesis graph — nodes with parent/child relationships, kill
propagation, outcome tracking, and round-trip markdown persistence.

A flat HYPOTHESES.md list (one hypothesis per bullet) loses the dependency
structure that makes attack planning coherent. This module adds graph
structure so that:

1. Hypotheses have ``parents`` (prerequisites) and ``children`` (derived
   hypotheses that depend on this one being true).
2. A ``kill`` on node H propagates to all descendants along the DAG,
   marking them ``unreachable`` (they depended on H being true).
3. Each node carries ``success_criterion``, ``kill_criterion``, and
   ``outcome`` so retrospective analysis can tell which branches were
   productive.
4. The graph round-trips through markdown: every saved HYPOTHESES.md is
   reloadable, no graph state lives only in memory.

Used by ``arena-hypothesize`` (Slice 16) to compose council agent outputs
into a dependency graph, and by ``arena-retrospective`` (Slice 17) to scan
kill-criteria results after an attack.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional

NodeStatus = Literal[
    "pending",      # not yet tested
    "in_progress",  # being attacked
    "confirmed",    # success criterion met
    "falsified",    # kill criterion triggered
    "unreachable",  # prerequisite was falsified (propagation)
]

VALID_STATUSES: set[str] = {
    "pending",
    "in_progress",
    "confirmed",
    "falsified",
    "unreachable",
}


@dataclass
class HypothesisNode:
    """One hypothesis in the graph.

    id                : short identifier (e.g. "H3", "H5.2")
    statement         : one-sentence claim we're testing
    success_criterion : measurable condition under which this is "confirmed"
    kill_criterion    : measurable condition under which this is "falsified"
    priority          : int 0 (highest) upward; ordering for attack scheduling
    parents           : ids this hypothesis depends on (logical AND)
    children          : ids that depend on this one
    status            : NodeStatus
    outcome           : free-form text describing empirical result
    provenance        : which council agent(s) contributed this hypothesis
    metadata          : open dict for attack artifacts, links, etc.
    """

    id: str
    statement: str
    success_criterion: str = ""
    kill_criterion: str = ""
    priority: int = 10
    parents: list[str] = field(default_factory=list)
    children: list[str] = field(default_factory=list)
    status: NodeStatus = "pending"
    outcome: str = ""
    provenance: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class HypothesisGraph:
    """Ordered DAG of HypothesisNodes.

    Cycle-free by construction: ``add_edge`` rejects an edge that would
    create a cycle. Operations that mutate status (``confirm``, ``kill``)
    propagate along outgoing edges according to DAG semantics.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, HypothesisNode] = {}

    # ---- construction / mutation ----

    def add_node(self, node: HypothesisNode) -> None:
        if node.id in self._nodes:
            raise ValueError(f"duplicate node id: {node.id}")
        self._nodes[node.id] = node

    def add_edge(self, parent_id: str, child_id: str) -> None:
        if parent_id not in self._nodes:
            raise KeyError(f"unknown parent {parent_id}")
        if child_id not in self._nodes:
            raise KeyError(f"unknown child {child_id}")
        if self._would_create_cycle(parent_id, child_id):
            raise ValueError(
                f"adding {parent_id} -> {child_id} would create a cycle"
            )
        parent = self._nodes[parent_id]
        child = self._nodes[child_id]
        if child_id not in parent.children:
            parent.children.append(child_id)
        if parent_id not in child.parents:
            child.parents.append(parent_id)

    def _would_create_cycle(self, parent_id: str, child_id: str) -> bool:
        # walking forward from child_id, do we ever reach parent_id?
        stack = [child_id]
        visited: set[str] = set()
        while stack:
            cur = stack.pop()
            if cur == parent_id:
                return True
            if cur in visited:
                continue
            visited.add(cur)
            stack.extend(self._nodes[cur].children)
        return False

    # ---- status transitions ----

    def mark_in_progress(self, node_id: str) -> None:
        self._require(node_id).status = "in_progress"

    def confirm(self, node_id: str, outcome: str = "") -> None:
        node = self._require(node_id)
        node.status = "confirmed"
        if outcome:
            node.outcome = outcome

    def kill(self, node_id: str, outcome: str = "") -> list[str]:
        """Mark node falsified + propagate unreachable to descendants.
        Returns the list of descendant ids that became unreachable."""
        node = self._require(node_id)
        node.status = "falsified"
        if outcome:
            node.outcome = outcome
        affected: list[str] = []
        self._propagate_unreachable(node_id, affected)
        return affected

    def _propagate_unreachable(self, start: str, affected: list[str]) -> None:
        stack = list(self._nodes[start].children)
        seen: set[str] = set()
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            n = self._nodes[cur]
            if n.status in ("confirmed",):
                # A confirmed child doesn't depend on a falsified parent in
                # the strict logical sense — preserve its status but record
                # the falsified ancestry in metadata.
                n.metadata.setdefault("ancestor_falsifications", []).append(start)
                continue
            n.status = "unreachable"
            affected.append(cur)
            stack.extend(n.children)

    # ---- queries ----

    def get(self, node_id: str) -> HypothesisNode:
        return self._require(node_id)

    def nodes(self) -> list[HypothesisNode]:
        return list(self._nodes.values())

    def roots(self) -> list[HypothesisNode]:
        return [n for n in self._nodes.values() if not n.parents]

    def leaves(self) -> list[HypothesisNode]:
        return [n for n in self._nodes.values() if not n.children]

    def by_status(self, status: NodeStatus) -> list[HypothesisNode]:
        return [n for n in self._nodes.values() if n.status == status]

    def attack_queue(self) -> list[HypothesisNode]:
        """Pending-or-in-progress nodes whose parents are all confirmed,
        sorted by priority (lower number = higher priority)."""
        queue = [
            n for n in self._nodes.values()
            if n.status in ("pending", "in_progress")
            and all(self._nodes[p].status == "confirmed" for p in n.parents)
        ]
        queue.sort(key=lambda n: (n.priority, n.id))
        return queue

    def _require(self, node_id: str) -> HypothesisNode:
        if node_id not in self._nodes:
            raise KeyError(f"unknown node {node_id}")
        return self._nodes[node_id]

    # ---- persistence ----

    def to_markdown(self) -> str:
        """Render the full graph as HYPOTHESES.md. Round-trippable via
        ``HypothesisGraph.from_markdown``."""
        lines: list[str] = []
        lines.append("# Hypothesis Graph")
        lines.append("")
        lines.append(
            f"- **Nodes:** {len(self._nodes)} | "
            f"**Roots:** {len(self.roots())} | "
            f"**Leaves:** {len(self.leaves())}"
        )
        counts = {s: len(self.by_status(s)) for s in VALID_STATUSES}
        lines.append(
            "- **Status:** "
            + ", ".join(f"{k}={v}" for k, v in counts.items() if v)
        )
        lines.append("")
        # Deterministic order: by insertion
        for n in self._nodes.values():
            lines.extend(self._render_node(n))
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def _render_node(self, n: HypothesisNode) -> list[str]:
        out = [f"## {n.id} — {n.statement}"]
        out.append("")
        out.append(f"- **Status:** {n.status}")
        out.append(f"- **Priority:** {n.priority}")
        if n.parents:
            out.append(f"- **Parents:** {', '.join(n.parents)}")
        if n.children:
            out.append(f"- **Children:** {', '.join(n.children)}")
        if n.success_criterion:
            out.append(f"- **Success:** {n.success_criterion}")
        if n.kill_criterion:
            out.append(f"- **Kill:** {n.kill_criterion}")
        if n.provenance:
            out.append(f"- **Provenance:** {', '.join(n.provenance)}")
        if n.outcome:
            out.append(f"- **Outcome:** {n.outcome}")
        if n.metadata:
            out.append(f"- **Metadata:** `{json.dumps(n.metadata, sort_keys=True)}`")
        return out

    @classmethod
    def from_markdown(cls, text: str) -> "HypothesisGraph":
        """Parse HYPOTHESES.md back into a graph. Idempotent with
        ``to_markdown``. Tolerant to extra prose around the nodes —
        any line not matching a ``## <id> — <statement>`` heading is
        treated as node-body content for the preceding node."""
        g = cls()
        current: Optional[dict[str, Any]] = None
        blocks: list[dict[str, Any]] = []
        heading_re = re.compile(r"^## ([\w.]+)\s+—\s+(.*)$")
        for raw in text.splitlines():
            m = heading_re.match(raw.strip())
            if m:
                if current is not None:
                    blocks.append(current)
                current = {"id": m.group(1), "statement": m.group(2)}
                continue
            if current is None:
                continue
            line = raw.strip()
            if not line.startswith("- "):
                continue
            key_match = re.match(r"- \*\*([\w ]+):\*\*\s*(.*)$", line)
            if not key_match:
                continue
            key = key_match.group(1).strip().lower()
            value = key_match.group(2).strip()
            if key == "status":
                current["status"] = value
            elif key == "priority":
                try:
                    current["priority"] = int(value)
                except ValueError:
                    pass
            elif key == "parents":
                current["parents"] = [x.strip() for x in value.split(",") if x.strip()]
            elif key == "children":
                current["children"] = [x.strip() for x in value.split(",") if x.strip()]
            elif key == "success":
                current["success_criterion"] = value
            elif key == "kill":
                current["kill_criterion"] = value
            elif key == "provenance":
                current["provenance"] = [x.strip() for x in value.split(",") if x.strip()]
            elif key == "outcome":
                current["outcome"] = value
            elif key == "metadata":
                try:
                    current["metadata"] = json.loads(value.strip("`"))
                except json.JSONDecodeError:
                    pass
        if current is not None:
            blocks.append(current)

        # First pass: add nodes
        for b in blocks:
            g.add_node(
                HypothesisNode(
                    id=b["id"],
                    statement=b.get("statement", ""),
                    success_criterion=b.get("success_criterion", ""),
                    kill_criterion=b.get("kill_criterion", ""),
                    priority=b.get("priority", 10),
                    status=b.get("status", "pending"),  # type: ignore
                    outcome=b.get("outcome", ""),
                    provenance=b.get("provenance", []),
                    metadata=b.get("metadata", {}),
                )
            )
        # Second pass: add edges from parent lists (idempotent)
        for b in blocks:
            for parent_id in b.get("parents", []):
                try:
                    g.add_edge(parent_id, b["id"])
                except (KeyError, ValueError):
                    continue  # tolerate orphan refs + cycles; caller can validate
        return g

    def save(self, path: Path) -> None:
        Path(path).write_text(self.to_markdown())

    @classmethod
    def load(cls, path: Path) -> "HypothesisGraph":
        return cls.from_markdown(Path(path).read_text())
