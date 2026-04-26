"""Evolutionary search primitives (Upgrade U6 — MAP-Elites × Islands).

This subpackage hosts the FunSearch-style program database, Claude-backed
SEARCH/REPLACE mutator, evolution loop, and per-problem signature functions
that together implement the MAP-Elites × islands architecture described in
``projects/arena-agentic-upgrade/PLAN.md`` §5.2 U6.

Imports here stay LAZY — the subpackage must never pull sympy/mpmath/scipy
at module load. Heavy deps import at call time inside signature functions.
"""

from __future__ import annotations

from .evolution_loop import (
    EvaluationResult,
    EvolutionConfig,
    EvolutionResult,
    GenerationReport,
    evolve,
    run_generation,
    seed_population,
)
from .mutator import (
    DiffBlock,
    MutationResult,
    apply_diff_blocks,
    find_evolve_blocks,
    mutate,
    parse_diff_blocks,
)
from .program_db import (
    Cluster,
    Island,
    Program,
    ProgramDB,
    validate_program_dict,
)

__all__ = [
    "Cluster",
    "DiffBlock",
    "EvaluationResult",
    "EvolutionConfig",
    "EvolutionResult",
    "GenerationReport",
    "Island",
    "MutationResult",
    "Program",
    "ProgramDB",
    "apply_diff_blocks",
    "evolve",
    "find_evolve_blocks",
    "mutate",
    "parse_diff_blocks",
    "run_generation",
    "seed_population",
    "validate_program_dict",
]
