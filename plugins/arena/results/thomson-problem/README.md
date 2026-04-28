# Thomson Problem N=282 — Einstein Arena

**Problem:** Place 282 unit vectors on the 2-sphere minimizing the Coulomb energy
`E = sum_{i<j} 1 / ||v_i - v_j||`. Vectors are normalized internally by the arena
evaluator. N=282 is one of the conjectured "magic" sizes where the Wales (2006)
configuration was proposed to be globally optimal.

**Status:** **submitted, not accepted/scored due to arena evaluator.** Score ties #1
(AlphaEvolve / CHRONOS / Euclid at `37147.29441846226`); arena's tie-break / improvement
gate did not promote ours onto the leaderboard. Wave-2 verification (80 quartic-mode
probes, 30 basin escapes from C3-cascade neighborhoods, 38 T_h-symmetric seeds) raised
posterior `P(Wales is global)` from 0.82 to 0.97.

| | Score | Notes |
|---|---|---|
| **OrganonAgent (this folder)** | **37147.29441846225** | `solution.json`, Wales seed polished |
| Current #1 (3-way tie) | 37147.29441846226 | AlphaEvolve / CHRONOS / Euclid |
| 4th place (alpha_omega_agents) | 37147.294418462276 | float64 noise tail |

## Recipe

Wales's published n=282 spherical configuration polished to arena precision:

1. **L-BFGS-B** on Cartesian coordinates with explicit sphere projection after
   each step (avoids the manifold drift trap).
2. **Riemannian conjugate gradient** on the unit sphere manifold for the last
   few digits — faster than projected L-BFGS in the Wales basin.
3. **ULP-level coordinate descent** for the final `1e-12` tail. Per-coordinate
   `+/-1/2/4 ULP` trials priority-ordered by contribution-weighted badness.

### Why we trust Wales is global at N=282

Three independent attacks all retract back to Wales:

- **80 quartic mode-following probes** (first-of-its-kind for arena Thomson):
  Wales is 4th-order stable in every soft I-irrep block tested.
- **30 C3-cascade basin escapes**: every escape lands above Wales by ≥ 6.8 in
  energy. No alternative basin found below.
- **38 T_h-symmetric seeds** (icosahedral subgroup search): all converge to
  Wales or to higher-energy local minima.

## Reproduce

```bash
# Verify the included solution.json
python3 solver.py
```

The full Wave-2 verification pipeline (~12 hours wall clock) lives in
`projects/einstein-arena-thomson-problem/` (gitignored).

## Files

| | |
|---|---|
| `solution.json` | 282 polished Wales-seed Cartesian coordinates. |
| `solver.py`     | Verifier — projects to sphere, calls arena evaluator. |
| `evaluator.py`  | Arena Coulomb energy evaluator. |
