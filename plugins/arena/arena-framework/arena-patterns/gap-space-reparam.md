# gap-space-reparam

## Trigger

Inputs are a sorted list where ordering is a problem-imposed constraint
(Laguerre z_i, kissing angle list, lattice gram matrix diagonal). Standard
coordinate optimizers operate on the raw `z_i` values, which tightly
couple the sort-order constraint into the search space.

## Recipe

1. Reparameterise as `g_i = z_i - z_{i-1}` (consecutive gaps). All gaps
   must be positive → constraint becomes box-bounds on `g`.
2. Rebuild `z` from `g` via cumulative sum when evaluating.
3. Run L-BFGS-B or trust-region on the gap representation with bounds.
4. Conditioning usually improves 10–100× because the variables are now
   decoupled in magnitude.

## Observed in

- **uncertainty-principle**: JSAgent's thread #183 explicitly called gap
  parameterisation out as their search method. We didn't fully exploit
  it in Session 1 — deferred as a high-priority next-session attack in
  the Path B Option-2 playbook.
- **kissing-d11**: raw-vector optimization drifts in norm even with
  normalization projection; the Gram-matrix gap representation
  (eigenvalue spacing) is more stable.

## Test

No pytest yet — primitive deferred until UP regression (Slice 19) validates
the pattern end-to-end on a real problem.

## Primitive

Planned (not yet implemented; Phase 5 / on-demand): a gap-reparam wrapper
that takes a coordinate-space optimizer + domain bounds and auto-applies
the reparameterisation. Until it lands, pair L-BFGS-B manually with a
Jacobian that threads through the cumulative-sum transform.
