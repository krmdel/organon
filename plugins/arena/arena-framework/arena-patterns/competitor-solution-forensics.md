# competitor-solution-forensics

## Trigger

Any arena problem with existing submissions. The
`/api/solutions/best?problemId=<id>` endpoint returns the FULL solution
payload (not just score) for the top 20 submitters — the single
highest-leverage recon call on the platform.

## Recipe

1. Call `tool-einstein-arena.arena_ops.get_best_solutions(problem_id)`.
2. Write to `projects/einstein-arena-<slug>/best_solutions.json`.
3. For each entry: extract the config via the problem's config_extractor,
   diff adjacent ranks (what's structurally different between #1 and #2),
   compute summary stats (n_entries, score range, creation timeline).
4. Run rigor gate across all entries; flag exploit outliers.
5. Mine discussion threads for methodology posts from the top submitters
   (their own self-documentation is usually the fastest intel).

## Observed in

- **first-autocorrelation-inequality (Session 1)**: downloading all 25
  solutions revealed that #1 was literally #2 × 1.0001 — a post-LP scaling
  trick. Saved hours of re-deriving the LP from scratch.
- **uncertainty-principle (Session 1)**: alpha_omega's k=19 config +
  JSAgent's k=14 + thread #183 (gap-space) + thread #191 (dyadic snap)
  together laid out the entire H1 breakthrough path inside 15 minutes of
  recon.

## Test

`tests/test_recon.py::test_recon_up_flags_exploit_at_k15` exercises the
full forensics pipeline on UP's cached data and verifies the k=15 exploit
line surfaces in SUMMARY.md.

## Primitive

`arena_framework.recon.Recon(slug).run()` wraps forensics + rigor scan +
SUMMARY.md rendering.
