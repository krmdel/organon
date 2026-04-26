"""Problem-to-primitive router (Upgrade U2).

Deterministic rule engine that reads a problem spec and returns a structured
routing decision: problem class (A or B), ranked primitive stack, default
budget, rationale. Fires in Phase 1 of the orchestrator, immediately after
recon and before hypothesize.

Companion to ``.claude/agents/arena-router-agent.md``. The agent spec is the
prompt-based fallback when a Claude subagent is available; this module is
the fast, always-available rule engine the orchestrator calls by default.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Routing decision shape
# ---------------------------------------------------------------------------


@dataclass
class PrimitiveRecommendation:
    """One primitive entry in the routing decision."""

    name: str
    confidence: str  # "HIGH" | "MEDIUM" | "LOW"
    default_params: dict[str, Any] = field(default_factory=dict)
    rationale: str = ""
    pattern_match: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "confidence": self.confidence,
            "default_params": self.default_params,
            "rationale": self.rationale,
            "pattern_match": self.pattern_match,
        }


@dataclass
class RoutingDecision:
    """Full routing decision shape."""

    problem_class: str  # "A" | "B" | "mixed"
    fallback_class: str
    primitives: list[PrimitiveRecommendation] = field(default_factory=list)
    default_budget: dict[str, Any] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "problem_class": self.problem_class,
            "fallback_class": self.fallback_class,
            "primitives": [p.to_dict() for p in self.primitives],
            "default_budget": self.default_budget,
            "diagnostics": self.diagnostics,
            "rationale": self.rationale,
        }


# ---------------------------------------------------------------------------
# Problem-class classifier
# ---------------------------------------------------------------------------


CLASS_A_KEYWORDS = {
    "construction", "constructions", "packing", "code", "design",
    "set", "sidon", "golomb", "ruler", "difference", "vectors", "integer",
    "kissing", "sphere", "lattice", "graph", "combinatorial", "block",
}
CLASS_B_KEYWORDS = {
    "function", "sequence", "convolution", "autoconvolution", "correlate",
    "integral", "derivative", "smooth", "polynomial", "laguerre", "fourier",
    "wavelet", "measure", "density", "inequality",
}


# Slug → (primary, fallback) pins. Overrides the classifier for known problems.
KNOWN_SLUG_CLASSIFICATION: dict[str, tuple[str, str]] = {
    "uncertainty-principle": ("B", "A"),
    "first-autocorrelation-inequality": ("B", "A"),
    "third-autocorrelation-inequality": ("B", "A"),
    "erdos-min-overlap": ("B", "A"),
    "prime-number-theorem": ("B", "A"),
    "heilbronn-triangles": ("B", "A"),
    "heilbronn-convex": ("B", "A"),
    "kissing-d11": ("A", "B"),
    "kissing-d12": ("A", "B"),
    "difference-bases": ("A", "B"),
}


def _count_keyword_hits(text: str, vocab: set[str]) -> int:
    if not text:
        return 0
    t = text.lower()
    hits = 0
    for word in vocab:
        hits += len(re.findall(r"\b" + re.escape(word) + r"\b", t))
    return hits


def _scan_verifier_signals(verifier_src: str) -> list[str]:
    """Inspect the server's verifier source for structural signals."""
    signals: list[str] = []
    if not verifier_src:
        return signals
    src = verifier_src.lower()
    if "decimal" in src or "getcontext" in src:
        signals.append("Decimal exact check")
    if "int_vecs" in src or "int(" in src and "np.round" in src:
        signals.append("integer fast path")
    if "np.convolve" in src or "numpy.convolve" in src:
        signals.append("numpy.convolve")
    if "np.correlate" in src or "numpy.correlate" in src:
        signals.append("numpy.correlate")
    if "sympy" in src or "sturm" in src or "sqf_list" in src:
        signals.append("symbolic polynomial (sympy/Sturm)")
    if "convexhull" in src:
        signals.append("convex hull (scipy)")
    if "montecarlo" in src or "rng.uniform" in src or "np.random" in src:
        signals.append("Monte Carlo sampling")
    if "lp" in src or "linprog" in src:
        signals.append("LP solver")
    return signals


def classify_problem_class(
    problem: dict[str, Any],
    top_solutions: Optional[list[dict[str, Any]]] = None,
) -> tuple[str, str, dict[str, Any]]:
    """Return (primary_class, fallback_class, diagnostics).

    Rule order:
    1. Known slug → use the pinned classification.
    2. Solution schema value types (integer-heavy → A, float-heavy → B).
    3. Verifier signals (Decimal/integer → A, convolve/correlate → B).
    4. Description keyword counts.
    5. Default mixed.
    """
    slug = problem.get("slug", "")
    diagnostics: dict[str, Any] = {"reasons": []}

    if slug in KNOWN_SLUG_CLASSIFICATION:
        pri, fb = KNOWN_SLUG_CLASSIFICATION[slug]
        diagnostics["reasons"].append(f"pinned by slug: {slug}")
        return pri, fb, diagnostics

    # Rule 2: inspect a sample solution
    schema_shape = _infer_schema_shape(problem, top_solutions)
    diagnostics["solution_schema_shape"] = schema_shape
    if schema_shape in {"list[int]", "set[int]", "list[list[int]]"}:
        diagnostics["reasons"].append(f"schema_shape={schema_shape} → Class A")
        return "A", "B", diagnostics
    if schema_shape in {"list[float]", "list[list[float]]", "dict[int,float]"}:
        diagnostics["reasons"].append(f"schema_shape={schema_shape} → Class B")
        return "B", "A", diagnostics

    # Rule 3: verifier signals
    verifier_src = problem.get("verifier", "")
    signals = _scan_verifier_signals(verifier_src)
    diagnostics["evaluator_signals"] = signals
    integer_signals = {"Decimal exact check", "integer fast path"}
    continuous_signals = {"numpy.convolve", "numpy.correlate", "symbolic polynomial (sympy/Sturm)", "convex hull (scipy)"}
    if any(s in integer_signals for s in signals):
        diagnostics["reasons"].append(f"verifier signals {signals} → Class A")
        return "A", "B", diagnostics
    if any(s in continuous_signals for s in signals):
        diagnostics["reasons"].append(f"verifier signals {signals} → Class B")
        return "B", "A", diagnostics

    # Rule 4: description keywords
    desc = problem.get("description", "")
    a_hits = _count_keyword_hits(desc, CLASS_A_KEYWORDS)
    b_hits = _count_keyword_hits(desc, CLASS_B_KEYWORDS)
    diagnostics["keyword_hits"] = {"A": a_hits, "B": b_hits}
    if a_hits >= 2 * max(b_hits, 1):
        diagnostics["reasons"].append("keyword bias → Class A")
        return "A", "B", diagnostics
    if b_hits >= 2 * max(a_hits, 1):
        diagnostics["reasons"].append("keyword bias → Class B")
        return "B", "A", diagnostics

    diagnostics["reasons"].append("ambiguous; defaulting to mixed (B primary)")
    return "mixed", "A", diagnostics


def _infer_schema_shape(
    problem: dict[str, Any], top_solutions: Optional[list[dict[str, Any]]]
) -> str:
    """Best-effort shape inference from the solution schema + a sample."""
    schema = problem.get("solutionSchema", {}) or {}

    # Prefer direct inspection of a real solution
    if top_solutions:
        for sol in top_solutions[:3]:
            data = sol.get("data") or sol
            for key, val in data.items():
                if isinstance(val, list):
                    if all(isinstance(x, (list, tuple)) for x in val):
                        inner = val[0] if val else []
                        if inner and all(isinstance(x, int) for x in inner):
                            return "list[list[int]]"
                        if inner and all(isinstance(x, float) or isinstance(x, int) for x in inner):
                            all_int_ish = all(
                                abs(float(x) - round(float(x))) < 1e-9 for x in inner
                            )
                            return "list[list[int]]" if all_int_ish else "list[list[float]]"
                    if all(isinstance(x, int) for x in val):
                        return "list[int]"
                    if all(isinstance(x, (int, float)) for x in val):
                        return "list[float]"
                if isinstance(val, dict):
                    # PNT-style partial_function dict[int, float]
                    try:
                        sample_key = next(iter(val))
                        sample_val = val[sample_key]
                        if isinstance(sample_val, (int, float)) and str(sample_key).isdigit():
                            return "dict[int,float]"
                    except StopIteration:
                        pass

    # Fallback to schema text matching
    for key, desc in schema.items():
        if not isinstance(desc, str):
            continue
        d = desc.lower()
        if "integer" in d and "array" in d:
            return "list[int]" if "1d" in d or "set" in d else "list[list[int]]"
        if "float" in d and "array" in d:
            return "list[float]" if "1d" in d or "sequence" in d else "list[list[float]]"
    return "unknown"


# ---------------------------------------------------------------------------
# Primitive-stack selection
# ---------------------------------------------------------------------------


def _primitives_for_class_a(signals: list[str]) -> list[PrimitiveRecommendation]:
    recs = [
        PrimitiveRecommendation(
            name="column_generation",
            confidence="HIGH" if "LP solver" in signals else "MEDIUM",
            default_params={"max_iterations": 100},
            rationale="LP-guided variable selection for overcomplete key/vector sets",
            pattern_match="literature-first-recon",
        ),
        PrimitiveRecommendation(
            name="active_triple_fingerprint",
            confidence="MEDIUM",
            default_params={},
            rationale="Diagnose active-constraint structure in packings",
        ),
        PrimitiveRecommendation(
            name="map_elites_evolve",
            confidence="MEDIUM",
            default_params={
                "n_islands": 4,
                "population_per_island": 20,
                "n_generations": 50,
            },
            rationale=(
                "MAP-Elites × islands program DB (U6) for construction-"
                "discovery problems. Needs a problem-specific signature "
                "function; see arena_framework.evolve.signatures."
            ),
            pattern_match="map-elites-program-db",
        ),
        PrimitiveRecommendation(
            name="dyadic_snap",
            confidence="LOW",
            default_params={},
            rationale="Try dyadic snapping on active coords if continuous polish dominates",
        ),
    ]
    return recs


def _primitives_for_class_b(
    signals: list[str], scoring: str
) -> list[PrimitiveRecommendation]:
    recs = []
    if "numpy.convolve" in signals or "numpy.correlate" in signals:
        recs.append(
            PrimitiveRecommendation(
                name="smooth_max_beta",
                confidence="HIGH",
                default_params={"beta_schedule": [1e3, 1e5, 1e7, 1e9, 1e11]},
                rationale="Max-over-set objective; β-annealing is the canonical polish",
                pattern_match="smooth-max-beta-anneal",
            )
        )
        recs.append(
            PrimitiveRecommendation(
                name="basin_hopping",
                confidence="HIGH",
                default_params={"n_steps": 50, "T": 0.01},
                rationale="Equioscillation plateaus: recursive basin-escape applies",
                pattern_match="recursive-basin-escape",
            )
        )
    if "symbolic polynomial (sympy/Sturm)" in signals:
        recs.append(
            PrimitiveRecommendation(
                name="dyadic_snap",
                confidence="HIGH",
                default_params={"max_denom_2pow": 32},
                rationale="Sturm-rigor-gate: dyadic snap bridges float → symbolic",
                pattern_match="dyadic-rational-snap",
            )
        )
    if "LP solver" in signals or "Monte Carlo sampling" in signals:
        recs.append(
            PrimitiveRecommendation(
                name="column_generation",
                confidence="HIGH",
                default_params={"max_iterations": 200},
                rationale="LP + post-LP scaling the PNT way",
                pattern_match="k-climbing",
            )
        )
        recs.append(
            PrimitiveRecommendation(
                name="dinkelbach",
                confidence="MEDIUM",
                default_params={},
                rationale="Fractional program structure; Dinkelbach iteration",
                pattern_match="exploit-then-rigor",
            )
        )
    # ULP polish is always a good final stage for continuous problems
    recs.append(
        PrimitiveRecommendation(
            name="ulp_polish",
            confidence="MEDIUM",
            default_params={"passes": 3},
            rationale="Coordinate descent at ULP grain for float64 residuals",
            pattern_match="ulp-precision-bridge",
        )
    )
    recs.append(
        PrimitiveRecommendation(
            name="parallel_tempering",
            confidence="LOW" if "symbolic polynomial (sympy/Sturm)" in signals else "MEDIUM",
            default_params={"n_replicas": 8, "T_min": 1e-12, "T_max": 1e-4},
            rationale="PT-SA for rough landscapes with multiple local minima",
        )
    )
    return recs


def _default_budget(problem: dict[str, Any]) -> dict[str, Any]:
    """Scale budget by solution size."""
    desc = problem.get("description", "").lower()
    schema = problem.get("solutionSchema", {}) or {}
    schema_str = " ".join(str(v) for v in schema.values()).lower()

    # Heuristic: bigger solutions deserve longer budgets.
    size_tokens = [
        ("90000", 3600),
        ("594", 3600),
        ("841", 3600),
        ("2000", 1800),
        ("600", 1200),
        ("90k", 3600),
    ]
    wall = 1800  # default 30 min
    for token, t in size_tokens:
        if token in desc or token in schema_str:
            wall = max(wall, t)
            break
    return {
        "wall_clock_s": wall,
        "max_iterations": None,
        "max_evaluations": None,
    }


# ---------------------------------------------------------------------------
# Top-level route()
# ---------------------------------------------------------------------------


def route(
    problem: dict[str, Any],
    top_solutions: Optional[list[dict[str, Any]]] = None,
    leaderboard: Optional[list[dict[str, Any]]] = None,
) -> RoutingDecision:
    """Produce a RoutingDecision from the problem spec + optional recon.

    Callers may pass ``top_solutions`` (for shape inference) and
    ``leaderboard`` (for competitor-count diagnostics). Both are optional.
    """
    pri_class, fb_class, diagnostics = classify_problem_class(problem, top_solutions)
    signals = diagnostics.get("evaluator_signals", [])
    if not signals:
        signals = _scan_verifier_signals(problem.get("verifier", ""))
        diagnostics["evaluator_signals"] = signals

    scoring = problem.get("scoring", "minimize")
    if pri_class == "A":
        primitives = _primitives_for_class_a(signals)
    elif pri_class == "B":
        primitives = _primitives_for_class_b(signals, scoring)
    else:  # mixed
        primitives = (
            _primitives_for_class_b(signals, scoring)
            + _primitives_for_class_a(signals)
        )

    budget = _default_budget(problem)
    diagnostics.update(
        {
            "scoring_direction": scoring,
            "min_improvement": problem.get("minImprovement"),
            "competitor_count": len(leaderboard or []),
            "leaderboard_top_score": (
                leaderboard[0].get("score") if leaderboard else None
            ),
        }
    )

    top_rec = primitives[0] if primitives else None
    rationale_parts = [
        f"Class {pri_class} (fallback {fb_class}).",
    ]
    if top_rec:
        rationale_parts.append(
            f"Top primitive: {top_rec.name} ({top_rec.confidence})."
        )
    if diagnostics.get("reasons"):
        rationale_parts.append("Rules: " + "; ".join(diagnostics["reasons"][:3]))

    return RoutingDecision(
        problem_class=pri_class,
        fallback_class=fb_class,
        primitives=primitives,
        default_budget=budget,
        diagnostics=diagnostics,
        rationale=" ".join(rationale_parts),
    )


def save_routing_decision(decision: RoutingDecision, recon_dir: Path) -> None:
    """Write ROUTING.json + ROUTING.md into ``recon_dir``."""
    recon_dir = Path(recon_dir)
    recon_dir.mkdir(parents=True, exist_ok=True)
    (recon_dir / "ROUTING.json").write_text(
        json.dumps(decision.to_dict(), indent=2)
    )
    (recon_dir / "ROUTING.md").write_text(_render_routing_markdown(decision))


def _render_routing_markdown(d: RoutingDecision) -> str:
    lines = [
        f"# Routing decision",
        "",
        f"- **Problem class**: {d.problem_class}",
        f"- **Fallback class**: {d.fallback_class}",
        f"- **Wall-clock budget**: {d.default_budget.get('wall_clock_s', 'n/a')} s",
        "",
        "## Primitives (ordered)",
        "",
        "| # | Name | Confidence | Pattern | Rationale |",
        "|---|------|------------|---------|-----------|",
    ]
    for i, p in enumerate(d.primitives, 1):
        lines.append(
            f"| {i} | `{p.name}` | {p.confidence} | {p.pattern_match or '—'} | {p.rationale} |"
        )
    lines.extend(
        [
            "",
            "## Diagnostics",
            "",
            "```json",
            json.dumps(d.diagnostics, indent=2, default=str),
            "```",
            "",
            "## Rationale",
            "",
            d.rationale,
            "",
        ]
    )
    return "\n".join(lines)
