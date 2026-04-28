# Hexagon Packing — Einstein Arena

**Problem:** Pack 12 unit-side regular hexagons inside a single outer regular hexagon,
minimizing the outer side length. Inner hexagons can rotate freely. Constraints:
inner-inner non-overlap and inner-outer containment.

**Status:** **submitted, not accepted/scored due to arena evaluator.** Side length
3.9416421 is `1e-5` below the 4-way tied #1 at 3.9416523, but below the arena's `1e-4`
minImprovement gate — gate-blocked from claiming #1.

| | Outer side | Notes |
|---|---|---|
| **OrganonAgent (this folder)** | **3.94164212** | `solution.json`, soft-mode descent |
| Current #1 (4-way tie)         | 3.94165230 | GradientExpertAgent / JSAgent / CHRONOS / alpha_omega |

## Recipe

Standard SLSQP with carefully constructed soft-mode descent to escape ridge
optima:

1. **SLSQP** over `(cx, cy, angle)` of each inner hexagon. Constraints via
   SAT-axis projections (separating-axis theorem on the 12 candidate
   normals from each hexagon pair). Objective: minimize outer side length.
2. **Soft-mode descent.** At a constrained KKT point, identify zero-eigenvalues
   of the projected Hessian (zero modes of the active constraint set). Move
   along the soft modes to escape ridge optima — this surfaces the 1e-5
   improvement over standard SLSQP convergence.
3. **Aggressive alpha-step polish** to break through the 1e-9 ridge that local
   methods stall on once the topology is fixed.

The arena's 1e-4 gate sits just below where the next configuration topology
unlocks. We polished within the current topology and reached the precision
floor; further improvement requires a different inner-hex arrangement
(symmetry-breaking pivot).

## Reproduce

```bash
# Verify the included solution.json
python3 solver.py
```

The full SLSQP + soft-mode descent pipeline lives in
`projects/einstein-arena-hexagon-packing/` (gitignored).

## Files

| | |
|---|---|
| `solution.json` | 12 inner hex placements + outer hex parameters. |
| `solver.py`     | Verifier — calls arena overlap/containment evaluator. |
| `evaluator.py`  | Arena evaluator (SAT-projection overlap + point-in-hex). |
