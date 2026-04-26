---
name: tool-arena-attack-problem
description: 'Autonomous end-to-end attack pipeline for any Einstein Arena problem. Composes recon -- parallel 5-agent research spawn -- hypothesis graph synthesis -- OVERVIEW.md -- user gate -- attack -- polish -- tri-verify -- submit gate -- retrospective. Triggers on "attack arena problem", "investigate arena challenge", "work on challenge", "new arena problem", "autonomous arena attack", "bootstrap arena attack", "arena investigate", "attack this problem". Not for tactical polish only (use tool-arena-runner) or raw API ops (use tool-einstein-arena).'
---

# tool-arena-attack-problem -- Autonomous arena challenge attack pipeline

One command, one slug, end-to-end autonomous campaign. Pre-integrates every Organon tool the framework has for arena work: the full `arena-framework` orchestrator, all 5 specialist recon agents, `sci-literature-research` parallel fanout, `tool-paperclip` biomedical grounding, `tool-firecrawl-scraper` web fallback, `sci-council`, `sci-optimization-recipes`, `ops-ulp-polish`, `ops-parallel-tempering-sa`, `tool-einstein-arena` API. The human only enters at gates.

## When to use

User says: "attack prime-number-theorem", "work on the new heilbronn problem", "investigate the uncertainty principle challenge", "take this arena problem on autonomously". Skip when the user only wants a tactical polish of an existing solution (route to `tool-arena-runner polish`) or raw API traffic (route to `tool-einstein-arena`).

## Methodology -- 7 stages

The skill is a playbook. Each stage is one CLI call + (sometimes) parallel Agent spawns. Claude drives the agent spawns directly via the Agent tool -- the Python scripts handle all non-agent work.

### Stage 1 -- RECON (autonomous)

```bash
python3 .claude/skills/tool-arena-attack-problem/scripts/attack.py recon \
    --slug {SLUG} --workspace projects/tool-arena/{SLUG}
```

This fetches problem spec + leaderboard + top-K solutions + discussions via `tool-einstein-arena`, runs the rigor scan, extracts reference papers from `problem.json` (arXiv IDs, DOIs, named works), writes:

- `{workspace}/problem.json`, `leaderboard.json`, `best_solutions.json`, `discussions.json`
- `{workspace}/recon/SUMMARY.md`
- `{workspace}/literature/REFERENCES.md` (priority-1 context for the literature agent)
- `{workspace}/PLAYBOOK.md` (bootstrapped from `tool-einstein-arena/assets/playbook-template.md`)

### Stage 2 -- RESEARCH FAN-OUT (Claude spawns 5 agents in parallel)

Claude MUST spawn these agents simultaneously in a single message with 5 Agent tool calls. Each agent receives the workspace path and writes exactly one file. See `references/spawn-agents.md` for the exact prompts.

| Agent | Writes | Purpose |
|---|---|---|
| `arena-literature-agent` | `{workspace}/literature/LITERATURE.md` | Published bounds, SOTA, BibTeX. Uses `sci-literature-research` fanout + paperclip + WebSearch fallback. |
| `arena-historian-agent`  | `{workspace}/recon/COMPETITOR_FORENSICS.md` | Per-rank structural diffs, discussion mining |
| `arena-pattern-scout-agent` | `{workspace}/recon/APPLICABLE_PATTERNS.md` | Matches problem shape against `arena-framework/arena-patterns/` |
| `arena-rigor-agent` | `{workspace}/recon/RIGOR_REPORT.md` | Classifies top-K as rigorous vs exploit |
| `arena-router-agent` (optional) | `{workspace}/recon/ROUTING.md` | Problem class + ranked primitive stack |

All 5 share the same inputs from Stage 1 and do not see each other. Adversarial diversity is the design.

### Stage 3 -- HYPOTHESIZE (autonomous)

```bash
python3 .claude/skills/tool-arena-attack-problem/scripts/attack.py hypothesize \
    --workspace projects/tool-arena/{SLUG}
```

Composes the 4 agent artifacts into a hypothesis graph via `arena_framework.hypothesize.synthesize`. Writes `HYPOTHESES_DRAFT.md`.

### Stage 4 -- CRITIC REVIEW (Claude spawns one agent)

Spawn `arena-critic-agent` on the draft graph. It writes `{workspace}/recon/CRITIQUE.md` with FATAL/MAJOR/MINOR findings + missing hypotheses.

### Stage 5 -- OVERVIEW + USER GATE (autonomous)

```bash
python3 .claude/skills/tool-arena-attack-problem/scripts/attack.py overview \
    --workspace projects/tool-arena/{SLUG}
```

Re-synthesises with CRITIQUE.md included, writes:

- `{workspace}/HYPOTHESES.md` (final graph)
- `{workspace}/OVERVIEW.md` -- the rich human-readable briefing: problem statement, published bounds table, competitor timeline, top-5 hypotheses with P(BEAT) + kill criteria, 3 proposed attack directions, open questions.

Claude prints a concise summary of OVERVIEW.md and asks the user whether to proceed (`AskUserQuestion`). The user approves, modifies, or kills the campaign here.

### Stage 6 -- ATTACK + POLISH + TRI-VERIFY (autonomous on approval)

On approval, invoke `AttackOrchestrator` with the hypothesis graph + routing decision. Integrates `ops-parallel-tempering-sa`, `sci-optimization-recipes`, `ops-ulp-polish`, and arena-runner's `tri-verify`. Writes `solutions/best.json`, `solutions/polished.json`, `attack_candidate.json`.

### Stage 7 -- SUBMIT GATE + RETROSPECTIVE (user-gated)

Presents the final candidate + tri-verify report to the user. On approval, `tool-einstein-arena submit` fires. Regardless of submit outcome, `retrospective.py` runs and proposes new patterns / fixtures for the next campaign (see `arena-patterns/` additions).

## API

```python
from attack import run_stage, main

# Library entrypoint for tests and programmatic use
run_stage("recon", slug="prime-number-theorem", workspace=Path("/tmp/w"))

# Full-campaign driver (for scripts)
main(argv=["recon", "--slug", "x", "--workspace", "/tmp/w"])
```

## Dependencies

| Dependency | Required | Provides | Fallback |
|---|---|---|---|
| `arena-framework` library (`plugins/arena/arena-framework/`) | Yes | Recon, AttackOrchestrator, synthesize | None -- skill fails loudly |
| `.claude/agents/arena-*.md` | Yes (5 specialist agents) | Research fan-out | None -- cannot proceed without them |
| `tool-einstein-arena` | Yes | API ops (fetch, submit) | Offline mode with cached JSON |
| `sci-literature-research` | Optional | Parallel fanout (paperclip + arXiv + PubMed + S2) | Sequential search via paper-search MCP |
| `tool-paperclip` | Optional | Biomedical full-text grounding | Federated search only |
| `tool-firecrawl-scraper` | Optional | Web fallback when WebFetch blocked | Skip scrape, note in LITERATURE.md |

Run `bash .claude/skills/tool-arena-attack-problem/scripts/setup.sh` once on a fresh clone.

## References

- `references/workflow.md` -- step-by-step playbook for Claude (stage timing, what to do if an agent fails, how to interpret gate prompts)
- `references/spawn-agents.md` -- exact prompts for each of the 5 agents (Stage 2 + Stage 4)
- `references/overview-schema.md` -- what sections OVERVIEW.md must contain and why

## Tests

```bash
python3 -m pytest .claude/skills/tool-arena-attack-problem/tests/ -v
```

Covers: stage dispatch, recon -> reference extraction round-trip, hypothesize with partial agent outputs (graceful degradation), overview rendering with all 5 sections, missing-workspace error handling, idempotent re-run.

## Routing

Use when user says: "attack arena problem X", "investigate challenge X", "work on new arena problem", "autonomous arena campaign for X", "take on Einstein Arena challenge", "bootstrap arena attack on X", "full attack pipeline for X".

Do NOT use for: tactical polish only (`tool-arena-runner polish`), leaderboard inspection (`tool-einstein-arena analyze`), post-hoc submission retry (`tool-einstein-arena submit`).
