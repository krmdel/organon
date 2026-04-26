# Spawn prompts for the 5 recon agents + the critic

This is the exact ritual Claude follows at Stage 2 and Stage 4 of the
`arena-attack-problem` playbook. All 4 Stage-2 agents MUST be spawned in
parallel -- same message, 4 `Agent` tool calls. The critic fires separately
after the hypothesize stage writes `HYPOTHESES_DRAFT.md`.

`{workspace}` is an absolute path like
`/Users/…/Projects/scientific-os/projects/einstein-arena-{slug}/`.

---

## Stage 2 -- parallel research fan-out (4 agents in ONE message)

### arena-literature-agent

```
subagent_type: arena-literature-agent
description: Literature dive for {slug}
prompt: |
  You are spawned during the recon phase of an arena-attack-problem run
  for problem `{slug}`. Workspace: `{workspace}`.

  Read in this order:
    1. {workspace}/problem.json
    2. {workspace}/discussions.json
    3. {workspace}/literature/REFERENCES.md  (priority-1 -- hydrate these identifiers FIRST)

  Use the Organon literature stack in this order:
    - mcp__paper-search__search_papers + mcp__paper-search__get_paper_details
      for arXiv IDs / DOIs in REFERENCES.md.
    - tool-paperclip (paperclip CLI or mcp__paperclip__paperclip) for biomedical
      full-text grounding if the problem is bioscience-adjacent.
    - sci-literature-research parallel fanout
      (python3 .claude/skills/sci-literature-research/scripts/fanout.py)
      for broad semantic queries across PubMed + arXiv + OpenAlex + Semantic Scholar.
    - WebSearch / WebFetch as a fallback.
    - tool-firecrawl-scraper if a site blocks WebFetch and FIRECRAWL_API_KEY is set.

  Follow the output contract from .claude/agents/arena-literature-agent.md
  exactly: write {workspace}/literature/LITERATURE.md with the required
  sections. No fabrication. Every claim cites a BibTeX key.
```

### arena-historian-agent

```
subagent_type: arena-historian-agent
description: Competitor forensics for {slug}
prompt: |
  Arena historian for problem `{slug}`. Workspace: `{workspace}`.

  Read {workspace}/problem.json, {workspace}/leaderboard.json,
  {workspace}/best_solutions.json, {workspace}/discussions.json.

  Output: {workspace}/recon/COMPETITOR_FORENSICS.md per the agent's
  contract. Quote, don't paraphrase. Attribute every claim to a thread id
  or rank. Flag gaps and contradictions explicitly.
```

### arena-pattern-scout-agent

```
subagent_type: arena-pattern-scout-agent
description: Cross-problem pattern scan for {slug}
prompt: |
  Pattern scout for problem `{slug}`. Workspace: `{workspace}`.

  Read {workspace}/problem.json + the arena-patterns library at
  projects/arena-framework/arena-patterns/. For each pattern, evaluate
  whether its structural triggers match this problem's shape. Output to
  {workspace}/recon/APPLICABLE_PATTERNS.md with the ranked table per
  the agent contract.
```

### arena-rigor-agent

```
subagent_type: arena-rigor-agent
description: Rigor vs exploit scan for {slug}
prompt: |
  Rigor scanner for problem `{slug}`. Workspace: `{workspace}`.

  Read {workspace}/best_solutions.json + {workspace}/problem.json. For
  each top-K solution, apply the rigor_gate at
  projects/arena-framework/src/arena_framework/rigor_gate.py and classify
  as rigorous / exploit / unknown. Output to
  {workspace}/recon/RIGOR_REPORT.md with the exploit-line analysis and
  per-solution verdicts.
```

---

## Stage 4 -- critic review (fires AFTER hypothesize)

Only spawn the critic after `python3 scripts/attack.py hypothesize` writes
`{workspace}/HYPOTHESES_DRAFT.md`. The critic needs all Stage-2 outputs +
the draft graph to do adversarial review.

### arena-critic-agent

```
subagent_type: arena-critic-agent
description: Adversarial review of hypothesis graph for {slug}
prompt: |
  Critic for problem `{slug}`. Workspace: `{workspace}`.

  Read {workspace}/HYPOTHESES_DRAFT.md + every file in
  {workspace}/recon/ + {workspace}/literature/LITERATURE.md.

  Attack each hypothesis: falsifiable success criterion? measurable kill
  criterion? does it contradict a published bound in LITERATURE.md? are
  parent hypotheses real?

  Output to {workspace}/recon/CRITIQUE.md with FATAL / MAJOR / MINOR
  findings, a Missing hypotheses section (each in full node shape), a
  Redundancies section, and a one-sentence overall verdict.
```

---

## Failure handling

- **Any single agent fails** -- the hypothesize stage tolerates 0-5 missing
  outputs and annotates the OVERVIEW.md `Agent coverage` section. Do not
  block the campaign on a single agent failure; note the gap and proceed.
- **All 5 agents fail** -- stop. Something structural is wrong
  (missing credentials, broken recon artifacts, or `{workspace}` is not
  the directory recon wrote to).
- **Agent hallucinates** -- each agent's contract forbids non-cited
  claims. The critic is the in-loop guard; the synthesiser's
  `SYNTHESIS_WARNINGS.json` is the post-hoc guard.
