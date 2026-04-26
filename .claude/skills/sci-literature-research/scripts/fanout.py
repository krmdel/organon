"""Parallel fan-out search for sci-literature-research (Organon F.4.C).

Public API:
    FanoutAllFailedError
    parallel_fanout(query, backends, *, timeout_per_source=30.0,
                    max_results_per_source=50) -> dict
    sequential_search(query, backends, *, max_results_per_source=50) -> dict

Each `backend` is a callable name -> list[dict]. Every paper dict should
carry at least a `doi` OR `arxiv_id`, plus `title`, `year`, `authors`.
No MCP / network imports happen at module load — safe for unit tests.
"""

from __future__ import annotations

import concurrent.futures as cf
from typing import Any, Callable, Dict, List

__all__ = [
    "FanoutAllFailedError",
    "parallel_fanout",
    "sequential_search",
]

PaperDict = Dict[str, Any]
Backend = Callable[[str], List[PaperDict]]


class FanoutAllFailedError(RuntimeError):
    """Raised when every backend in a fan-out run failed."""

    def __init__(self, failures: Dict[str, str]):
        self.failures = dict(failures)
        lines = [f"{name}: {msg}" for name, msg in failures.items()]
        super().__init__("All fan-out sources failed:\n  " + "\n  ".join(lines))


# ---------- normalisation + dedup helpers ---------------------------------

def _normalize_doi(doi: Any) -> str:
    if not doi or not isinstance(doi, str):
        return ""
    s = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if s.startswith(prefix):
            s = s[len(prefix):]
    return s.strip("/ ")


def _normalize_arxiv(aid: Any) -> str:
    if not aid or not isinstance(aid, str):
        return ""
    s = aid.strip().lower()
    for prefix in ("arxiv:", "https://arxiv.org/abs/", "http://arxiv.org/abs/"):
        if s.startswith(prefix):
            s = s[len(prefix):]
    return s.strip("/ ")


def _paper_key(paper: PaperDict) -> tuple[str, str] | None:
    """Return ("doi", value) or ("arxiv", value) — never cross-match."""
    doi = _normalize_doi(paper.get("doi"))
    if doi:
        return ("doi", doi)
    arxiv = _normalize_arxiv(paper.get("arxiv_id"))
    if arxiv:
        return ("arxiv", arxiv)
    return None


def _merge_sources(a: PaperDict, b: PaperDict) -> PaperDict:
    """Keep `a` (first seen); merge any source badges from `b`."""
    sources = list(dict.fromkeys(
        (a.get("sources") or []) + (b.get("sources") or [])
    ))
    if sources:
        a["sources"] = sources
    return a


def _merge_results(
    ordered_names: list[str],
    per_source: Dict[str, List[PaperDict]],
) -> List[PaperDict]:
    seen: Dict[tuple[str, str], PaperDict] = {}
    merged: List[PaperDict] = []
    no_key_bucket: List[PaperDict] = []
    for name in ordered_names:
        for paper in per_source.get(name, []) or []:
            key = _paper_key(paper)
            if key is None:
                no_key_bucket.append(paper)
                continue
            if key in seen:
                _merge_sources(seen[key], paper)
                continue
            seen[key] = paper
            merged.append(paper)
    merged.extend(no_key_bucket)
    return merged


# ---------- public API ----------------------------------------------------

def sequential_search(
    query: str,
    backends: Dict[str, Backend],
    *,
    max_results_per_source: int = 50,
) -> dict:
    """Drive each backend in order — the legacy path, kept for parity tests."""
    if not query or not query.strip():
        raise ValueError("query must be a non-empty string")
    ordered = list(backends.keys())
    per_source: Dict[str, List[PaperDict]] = {}
    failures: Dict[str, str] = {}
    counts: Dict[str, int] = {}
    for name in ordered:
        try:
            out = backends[name](query) or []
            out = out[:max_results_per_source]
        except Exception as exc:  # pragma: no cover - defensive
            failures[name] = f"{type(exc).__name__}: {exc}"
            out = []
        per_source[name] = out
        counts[name] = len(out)
    return {
        "results": _merge_results(ordered, per_source),
        "degraded": bool(failures),
        "failed_sources": list(failures),
        "source_counts": counts,
    }


def parallel_fanout(
    query: str,
    backends: Dict[str, Backend],
    *,
    timeout_per_source: float = 30.0,
    max_results_per_source: int = 50,
) -> dict:
    """Fire every backend in parallel; merge, deduplicate, rank.

    Returns `{results, degraded, failed_sources, source_counts}`.
    Raises `FanoutAllFailedError` only when every backend raised or timed out.
    """
    if not query or not query.strip():
        raise ValueError("query must be a non-empty string")
    if not backends:
        raise ValueError("backends must not be empty")

    ordered = list(backends.keys())
    per_source: Dict[str, List[PaperDict]] = {n: [] for n in ordered}
    failures: Dict[str, str] = {}
    counts: Dict[str, int] = {n: 0 for n in ordered}

    # Use daemon threads + non-blocking shutdown so a stuck backend doesn't
    # hold the whole fanout past its timeout budget.
    pool = cf.ThreadPoolExecutor(
        max_workers=max(1, len(ordered)),
        thread_name_prefix="fanout",
    )
    try:
        futures = {pool.submit(backends[n], query): n for n in ordered}
        for fut in list(futures):
            name = futures[fut]
            try:
                out = fut.result(timeout=timeout_per_source) or []
                out = out[:max_results_per_source]
                per_source[name] = out
                counts[name] = len(out)
            except cf.TimeoutError:
                failures[name] = (
                    f"TimeoutError: timed out after {timeout_per_source}s"
                )
                fut.cancel()
            except TimeoutError as exc:
                failures[name] = f"TimeoutError: {exc}"
            except Exception as exc:
                failures[name] = f"{type(exc).__name__}: {exc}"
    finally:
        # Don't block on straggler threads — they're effectively abandoned.
        pool.shutdown(wait=False, cancel_futures=True)

    if failures and len(failures) == len(ordered):
        raise FanoutAllFailedError(failures)

    merged = _merge_results(ordered, per_source)
    return {
        "results": merged,
        "degraded": bool(failures),
        "failed_sources": list(failures),
        "source_counts": counts,
    }
