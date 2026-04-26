"""Problem-specific attack loops for the AttackOrchestrator.

Each attack loop has the signature declared in ``orchestrator.AttackLoop``:

    (HypothesisGraph, ReconArtifacts, dict[str, Any]) -> SubmissionCandidate

These loops use the primitives library plus problem-specific scripts (which
live under ``projects/einstein-arena-{slug}/scripts/``) to search for a
submission-worthy solution.
"""

from .uncertainty_principle import up_attack_loop

__all__ = ["up_attack_loop"]
