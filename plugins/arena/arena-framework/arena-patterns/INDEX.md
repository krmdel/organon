# Arena Patterns — index

Cross-problem techniques indexed by **structural trigger**, not problem slug.
When the hypothesize phase runs on a new arena problem, it walks this index
and pattern-matches the triggers against the problem's shape.

Each pattern file has four sections:
- **Trigger** — the problem-structural condition that activates the pattern
- **Recipe** — concrete steps and primitive to invoke
- **Observed in** — arena problems where this pattern delivered real progress
- **Test** — path to an executable pytest that exercises the pattern on a fixture

## Patterns

| Pattern | Trigger | Observed in | Test |
|---------|---------|-------------|------|
| [`sturm-rigor-gate`](sturm-rigor-gate.md) | evaluator uses `np.sign(lambdify(rational_poly))` | uncertainty-principle | `tests/test_rigor_gate.py` |
| [`dyadic-rational-snap`](dyadic-rational-snap.md) | evaluator routes floats through `sympy.Rational` | uncertainty-principle (H1) | `tests/test_dyadic_snap.py` |
| [`smooth-max-beta-anneal`](smooth-max-beta-anneal.md) | objective is max over a discrete set | first-autocorrelation-inequality | `tests/test_smooth_max_beta.py` |
| [`literature-first-recon`](literature-first-recon.md) | any new problem with a known theoretical landscape | uncertainty-principle, kissing-d11 | (manual, no pytest) |
| [`two-tier-evaluator`](two-tier-evaluator.md) | exact verifier is >5× slower than a fast approximation | uncertainty-principle, first-autocorrelation | `tests/test_rigor_gate.py::test_up_path_b_real_evaluator_end_to_end` (slow) |
| [`k-climbing`](k-climbing.md) | construction has a tunable size parameter k | uncertainty-principle, kissing-d11, kissing-d12 | (manual, deferred) |
| [`gap-space-reparam`](gap-space-reparam.md) | sorted-list inputs where ordering is a constraint | uncertainty-principle (deferred), kissing-d11 | (manual) |
| [`competitor-solution-forensics`](competitor-solution-forensics.md) | any problem with existing submissions | every arena problem | `tests/test_recon.py::test_recon_up_flags_exploit_at_k15` |
| [`exploit-then-rigor`](exploit-then-rigor.md) | arena verifier has numerical leniency (see sturm-rigor-gate trigger) | uncertainty-principle | `tests/test_submit_gate.py` |
| [`ulp-precision-bridge`](ulp-precision-bridge.md) | continuous gradient stalls at ~1e-12 but evaluator says residual ~1e-13 | first-autocorrelation-inequality (C1), kissing-d11 | `tests/test_ulp_polish.py` |

## Self-improvement hook

When `arena-retrospective` (Slice 17) runs after an attack, it:
1. Scans the session for novel techniques not in this index.
2. Promotes them as new pattern files.
3. Appends the row above with the new structural trigger.
4. Records a fixture in `tests/arena_fixtures/` so the pattern regression-tests.
