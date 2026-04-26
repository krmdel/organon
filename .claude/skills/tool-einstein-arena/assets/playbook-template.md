# {Problem Slug} — {Approach Tag} Playbook

<!-- fill: short prose tag for this playbook instance, e.g. "Option A — Difference Bases" or "Round 3 — First Autocorrelation" -->

## Problem

- **Name:** <!-- fill: human-readable problem name -->
- **Slug:** <!-- fill: arena slug, e.g. "difference-bases" -->
- **Verifier:** <!-- fill: one sentence of how the arena verifier scores a solution -->
- **Scoring formula:** <!-- fill: exact formula, including direction of improvement -->
- **Threshold to beat:** <!-- fill: current #1 minus arena minImprovement (typically 1e-5 or 1e-8) -->
- **Problem parameters:** <!-- fill: any fixed constants, e.g. m=8011, |B|=360 -->

---

## SOTA snapshot

| Field | Value |
|---|---|
| Current #1 score | <!-- fill: exact float --> |
| Who holds it | <!-- fill: agent name(s); note ties --> |
| Our current rank | <!-- fill: e.g. "tied #1 (unsubmitted)" or "#4" --> |
| Our best score | <!-- fill: our best local result --> |
| Best novel (non-incumbent) | <!-- fill: best score from our NEW constructions, not matches of SOTA --> |
| Win threshold | <!-- fill: strictly-less-than or strictly-greater-than value --> |
| Plateau | <!-- fill: N generations/sessions without improvement; blank if actively improving --> |

---

## Approaches tried

<!-- fill: one row per distinct approach — NOT per sub-experiment.
     Aggregate sweeps/grids into a single row with the best cell in Notes.
     Keep the table flat — no nested headers. -->

| Approach | Result | Notes |
|---|---|---|
| <!-- fill: approach name --> | <!-- fill: best score --> | <!-- fill: what, when, why — cite SESSION_LOG row --> |

---

## Dead ends

<!-- fill: bullet list of falsified directions.
     Each bullet = one sentence stating the direction + one sentence explaining WHY it's mechanistically dead (not just "didn't improve"). -->

- **<!-- fill: direction name -->** — <!-- fill: mechanistic reason it cannot work -->

---

## Fertile directions

<!-- fill: bullet list of 1-5 directions worth trying next.
     Each entry MUST include: (a) what makes it NEW / not covered by Dead Ends,
     (b) P(BEAT) estimate as a %, (c) feasibility in sessions. -->

- **<!-- fill: direction name -->** (NEW after <!-- fill: session tag -->) — <!-- fill: what makes this different from every Dead End above -->. **P(BEAT): X-Y%.** Feasibility: <!-- fill: ≤ N sessions -->.

---

## Open questions

<!-- fill: research-grade open questions whose answers would change the approach.
     Not "should I run bigger grids" — actual theoretical / mathematical questions. -->

- <!-- fill: question 1 -->
- <!-- fill: question 2 -->

---

## Submissions

| Date | Score | Rank | Status |
|---|---|---|---|
| <!-- fill: YYYY-MM-DD or "(never submitted)" --> | <!-- fill: score --> | <!-- fill: rank at submit time --> | <!-- fill: APPROVED / PENDING / NOT SUBMITTED (with one-line rationale) --> |

<!--
  Template usage:
    1. Copy to projects/{category}/{approach-tag}/PLAYBOOK.md
    2. Replace every <!-- fill: ... --> placeholder with real content.
    3. Delete section rows that don't apply (e.g. if no submissions yet, keep ONE row reading "(never submitted)").
    4. Keep the playbook under 400 lines. If Approaches tried grows past 30 rows, roll early rows into Dead ends.
    5. Never rename or reorder sections — the schema test validates structure.
-->
