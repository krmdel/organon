"""Reference paper auto-extraction (Gap 5).

Parses problem.json (description + references + any embedded URLs) AND the
discussion threads for arXiv IDs, DOIs, and named references, then writes
{workspace}/literature/REFERENCES.md as priority-1 context for the
arena-literature-agent.

Zero network calls -- we extract *identifiers*, not metadata. The
literature agent hydrates identifiers via paper-search MCP / paperclip /
WebFetch.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

ARXIV_ID_RE = re.compile(
    r"""\b(?:arXiv[:\s]+)?
        (?P<id>
            \d{4}\.\d{4,5}(?:v\d+)?            # modern: 1706.00567
            |
            (?:[a-z\-]+(?:\.[A-Z]{2})?/\d{7}) # pre-2007: hep-th/9901001
        )\b
    """,
    re.VERBOSE | re.IGNORECASE,
)

DOI_RE = re.compile(
    r"""\b
        (?:doi[:\s]+|https?://(?:dx\.)?doi\.org/)?
        (?P<doi>10\.\d{4,9}/[-._;()/:A-Z0-9]+)
        \b
    """,
    re.VERBOSE | re.IGNORECASE,
)

NAMED_REF_RE = re.compile(
    r"""
    (?P<authors>
        (?:[A-Z][^\W\d_]+(?:\s+et\s+al\.|\s*(?:,|\band\b|&)\s*[A-Z][^\W\d_]+){0,3})
    )
    \s*[\(\s]*(?P<year>(?:19|20)\d{2})[\)\s]*
    """,
    re.VERBOSE | re.UNICODE,
)


# ---------------------------------------------------------------------------
# Core extractor
# ---------------------------------------------------------------------------


def _iter_text_blobs(problem: dict[str, Any], discussions: list[dict[str, Any]]) -> Iterable[str]:
    """Yield every string field from a problem spec + its discussions."""
    for key in ("title", "description", "statement", "problemStatement", "notes"):
        v = problem.get(key)
        if isinstance(v, str):
            yield v

    refs = problem.get("references")
    if isinstance(refs, list):
        for r in refs:
            if isinstance(r, str):
                yield r
            elif isinstance(r, dict):
                for v in r.values():
                    if isinstance(v, str):
                        yield v
    elif isinstance(refs, str):
        yield refs

    schema = problem.get("solutionSchema")
    if isinstance(schema, dict):
        for v in schema.values():
            if isinstance(v, str):
                yield v

    for thread in discussions or []:
        if not isinstance(thread, dict):
            continue
        for key in ("title", "body", "content"):
            v = thread.get(key)
            if isinstance(v, str):
                yield v
        for reply in thread.get("replies", []) or []:
            if isinstance(reply, dict):
                v = reply.get("body") or reply.get("content")
                if isinstance(v, str):
                    yield v


def extract_references(
    problem: dict[str, Any], discussions: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    """Extract unique paper identifiers from a problem spec + discussions.

    Returns a list of dicts shaped like:
        {"kind": "arxiv", "id": "1706.00567", "source": "problem.description"}
        {"kind": "doi",   "id": "10.1007/...", "source": "discussions"}
        {"kind": "named", "id": "Cohn-Gonçalves 2017", "source": "problem.references"}

    Deduplicates across all sources. Preserves insertion order of first sight.
    """
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def _add(kind: str, ident: str, source: str) -> None:
        key = (kind, ident.lower())
        if key in seen:
            return
        seen.add(key)
        out.append({"kind": kind, "id": ident, "source": source})

    for blob in _iter_text_blobs(problem, discussions or []):
        for m in ARXIV_ID_RE.finditer(blob):
            _add("arxiv", m.group("id"), "problem+discussions")
        for m in DOI_RE.finditer(blob):
            _add("doi", m.group("doi"), "problem+discussions")
        for m in NAMED_REF_RE.finditer(blob):
            # Filter out trivial matches like "Top 10 2026" from leaderboard noise.
            authors = m.group("authors").strip()
            year = m.group("year")
            if len(authors) < 3 or authors.lower().startswith(("the ", "a ", "an ")):
                continue
            _add("named", f"{authors} {year}", "problem+discussions")

    return out


# ---------------------------------------------------------------------------
# Render to markdown
# ---------------------------------------------------------------------------


def render_references_md(slug: str, refs: list[dict[str, Any]]) -> str:
    """Render a REFERENCES.md that the literature agent reads first.

    Priority-1 context: tells the agent "these are the exact papers the
    problem cites -- hydrate these before running WebSearch."
    """
    lines: list[str] = [
        f"# {slug} -- Extracted References",
        "",
        "<!-- Auto-extracted by arena-attack-problem/scripts/extract_refs.py.",
        "     Priority-1 context for arena-literature-agent: hydrate these",
        "     identifiers via paper-search MCP / paperclip / WebFetch BEFORE",
        "     running broader literature queries. -->",
        "",
    ]

    if not refs:
        lines.append("No references auto-extracted from problem.json or discussions.")
        lines.append("")
        lines.append("arena-literature-agent should fall back to broad WebSearch "
                     "for the seminal paper on this problem.")
        return "\n".join(lines) + "\n"

    by_kind: dict[str, list[dict[str, Any]]] = {"arxiv": [], "doi": [], "named": []}
    for r in refs:
        by_kind.setdefault(r["kind"], []).append(r)

    if by_kind["arxiv"]:
        lines.append("## arXiv IDs")
        lines.append("")
        for r in by_kind["arxiv"]:
            lines.append(f"- `{r['id']}` -- https://arxiv.org/abs/{r['id']} "
                         f"(from {r['source']})")
        lines.append("")

    if by_kind["doi"]:
        lines.append("## DOIs")
        lines.append("")
        for r in by_kind["doi"]:
            lines.append(f"- `{r['id']}` -- https://doi.org/{r['id']} "
                         f"(from {r['source']})")
        lines.append("")

    if by_kind["named"]:
        lines.append("## Named references")
        lines.append("")
        for r in by_kind["named"]:
            lines.append(f"- {r['id']} (from {r['source']})")
        lines.append("")

    lines.append("## Hydration recipe for arena-literature-agent")
    lines.append("")
    lines.append("1. For each arXiv ID: fetch abstract + key theorems via")
    lines.append("   `mcp__paper-search__get_paper_details` or `WebFetch(arxiv.org/abs/{id})`.")
    lines.append("2. For each DOI: resolve via `mcp__paper-search__search_papers` or")
    lines.append("   `WebFetch(doi.org/{id})`.")
    lines.append("3. For each named reference: route through")
    lines.append("   `sci-literature-research` parallel fanout to resolve to a concrete paper.")
    lines.append("4. Every resolved paper goes in the BibTeX block of LITERATURE.md.")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI (for one-off testing)
# ---------------------------------------------------------------------------


if __name__ == "__main__":  # pragma: no cover
    import argparse
    import json
    import sys
    from pathlib import Path

    ap = argparse.ArgumentParser()
    ap.add_argument("--problem-json", required=True)
    ap.add_argument("--discussions-json", default=None)
    ap.add_argument("--slug", default="unknown")
    args = ap.parse_args()

    problem = json.loads(Path(args.problem_json).read_text())
    discussions = []
    if args.discussions_json:
        discussions = json.loads(Path(args.discussions_json).read_text())

    refs = extract_references(problem, discussions)
    sys.stdout.write(render_references_md(args.slug, refs))
