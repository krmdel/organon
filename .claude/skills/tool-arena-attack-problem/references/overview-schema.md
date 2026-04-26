# OVERVIEW.md -- required schema

OVERVIEW.md is the Stage-5 gate artifact. It must contain every section
below, in order. `overview.py::render_overview` produces the file; tests
assert the contract.

## Required sections

1. `## Problem` -- title, slug, scoring formula, minImprovement, one-quote
   problem statement.
2. `## SOTA snapshot` -- top-10 leaderboard table (rank / agent / score /
   submissions).
3. `## Published bounds` -- copied from `LITERATURE.md#Published bounds`.
4. `## Competitor forensics` -- `### Per-rank structural diffs` and
   `### Methodology signals` from `COMPETITOR_FORENSICS.md`.
5. `## Hypothesis graph (top-5)` -- 5 highest-priority non-falsified
   hypotheses, each with id / statement / priority / kill criterion /
   provenance.
6. `## Proposed attack directions` -- top-3 hypotheses rendered as
   `D1. … (priority=N)` plus cross-problem patterns matched (from
   pattern-scout).
7. `## Open questions` -- from literature + critic.
8. `## Agent coverage` -- table showing which of the 5 agents produced
   output + any synthesiser warnings.

## Non-goals

- NOT a plan of attack for Claude. Claude decides the attack in Stage 6
  from the hypothesis graph + router. OVERVIEW.md is for the user.
- NOT a full report. Each section is ≤ 20 lines. For depth, the
  summary points at the underlying `LITERATURE.md`,
  `COMPETITOR_FORENSICS.md`, `HYPOTHESES.md`, etc.

## Fixtures

`tests/test_overview.py` runs `render_overview` against a synthetic
workspace with all-5-present, 3-of-5-present, and 0-of-5-present agent
outputs. Every variant must contain every required section header; body
content graciously degrades to `(missing…)` stubs.
