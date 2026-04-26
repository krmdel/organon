# literature-first-recon

## Trigger

Any new arena problem that has a recognised theoretical landscape
(kissing numbers, Uncertainty Principle, autocorrelation, PNT, ...).
Pure evolutionary / solver-first attacks waste hours rediscovering
published bounds.

## Recipe

15–30 minutes of parallel-agent literature research BEFORE writing any
solver:

1. Spawn `sci-literature-research` against the problem's defining keyword
   set. Ask for: published bounds (lower and upper), best-known methods,
   attribution history.
2. Parallel: `tool-paperclip` grep-and-scan over the primary theorists'
   recent preprints (e.g. Cohn, Gonçalves, Viazovska for UP).
3. Parallel: web search for the current SOTA and its arXiv id.
4. Output: `literature/LITERATURE.md` summarising (a) published upper
   bound, (b) published lower bound, (c) SOTA method, (d) reproducibility
   notes (what's released vs what's private).

If the arena leaderboard score is already below a published lower bound,
you have an exploit — pivot immediately to `sturm-rigor-gate`.

## Observed in

- **uncertainty-principle**: literature recon flagged GOSS 2016 C ≥ 0.2025.
  Arena's 0.26543 was above; after H1 snap dropped to 0.13365, that's
  BELOW GOSS's lower bound → mathematically impossible → exploit confirmed
  within seconds of the snap rather than hours of speculation.
- **kissing-d11 (Session 3)**: Path C research agent discovered AlphaEvolve
  2025 had already pushed 592→593 via LLM-driven evolutionary search.
  Changed the whole strategic picture from "extend Ganzhinov" to "understand
  where 594 came from", saving hours of wasted reproduction work.

## Test

No pytest — manual workflow enforced by `arena-attack-problem` step 4.
