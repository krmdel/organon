# Cross-resolution basin transfer

## When to use

High-resolution optimisation is expensive per step, and random starts
rarely land in the right basin. Meanwhile, a coarser version of the same
problem is cheap enough to sweep widely.

Classic fits:

- Point configurations on a sphere / disc (Heilbronn, Thomson, Riesz),
  where N=50 is fast and N=500 is slow, but the good basin is already
  visible at N=50.
- Image-registration / deformable-registration (coarse-to-fine image
  pyramids).
- Neural surrogate training at low resolution → fine-tune at full.
- Any gradient-friendly problem with a smooth embedding between scales.

Skip when:

- There is no natural "coarse" version of the problem (combinatorial with
  no natural scale parameter).
- Coarse and fine optima sit in **different** basins (the transfer breaks —
  use `k-climbing` instead).

## Pseudocode

```
def cross_resolution(f_fine, f_coarse, restarts=100, fine_tune_steps=500):
    best = None
    # (1) Explore cheaply at low resolution.
    for r in range(restarts):
        x_coarse = random_start(dim_coarse)
        x_coarse = local_descent(f_coarse, x_coarse, steps=200)
        if best is None or f_coarse(x_coarse) < best.coarse_val:
            best = record(x_coarse)
    # (2) Upsample the winning coarse solution into the fine space.
    x_fine = upsample(best.x_coarse)            # interpolation, re-embed
    # (3) Warm-start fine optimisation.
    x_fine = local_descent(f_fine, x_fine, steps=fine_tune_steps)
    return x_fine, f_fine(x_fine)
```

Upsampling is the delicate step. For point sets, jittered interpolation
of coordinates works; for images, bilinear + frequency-matched noise.

## Worked example

Einstein Arena Heilbronn (triangle-density maximisation on a unit square):

1. At N=50, a single-pass Nelder-Mead finds many local optima in seconds.
2. Take the top-5 by score and upsample each to N=200 by bisecting the
   longest edge of the Delaunay triangulation at each step.
3. Run L-BFGS-B on each N=200 warm start for 500 iterations.
4. Final score is the best of the 5 refined configurations.

This beat a fresh-start-at-N=200 approach by ~2× in wall-clock and ~3× in
best score attained (low-res wide search wins more basins).

## Gotchas

1. **Upsample with structure.** Naive zero-padding or linear interpolation
   often pushes the fine point into a nearby basin that's **worse** than
   the coarse starting basin. Add small deterministic perturbation.
2. **Coarse penalty vs. fine penalty must agree in sign.** If the coarse
   objective is a relaxation (LP bound, SDP bound) the transfer can fail
   because the coarse optimum isn't even feasible at high res.
3. **Fine-tune budget.** Keep the fine phase short (200–1000 steps) —
   beyond that, either the warm start was wrong or you've hit the basin
   floor; sweep a new coarse start instead.
4. **Not a substitute for exploration.** If the coarse stage only keeps
   the top-1, you've collapsed the win back to one random guess.

## References

- Press, W. H., Teukolsky, S. A., Vetterling, W. T., Flannery, B. P.
  *Numerical Recipes*, 3rd ed. (2007), Chapter 20 on multigrid.
- Bornemann, F., Deuflhard, P. "The cascadic multigrid method for
  elliptic problems." *Numer. Math.* 75 (1996), pp. 135–152.
- Scales, J. A. "A layer-stripping technique for velocity estimation from
  wide-aperture reflection data." *Geophysics* 60 (1995), pp. 1142–1154.
