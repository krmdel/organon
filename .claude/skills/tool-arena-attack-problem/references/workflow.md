# arena-attack-problem -- Claude's step-by-step playbook

A single campaign walks through 7 stages. The Python scripts handle all
non-agent work; Claude drives the Agent spawns.

## Preconditions

- `python3 .claude/skills/arena-attack-problem/scripts/setup.sh` passes
  (run once per clone).
- `tool-einstein-arena` `.credentials.json` exists at
  `projects/tool-einstein-arena/.credentials.json` (run
  `tool-arena-runner register` first if not).

## The 7 stages

### Stage 1 -- RECON

Claude runs one bash call:

    python3 .claude/skills/arena-attack-problem/scripts/attack.py recon \
        --slug {SLUG} --workspace projects/einstein-arena-{SLUG}

Reports to the user:
- problem title, scoring formula, minImprovement
- leaderboard depth, #1 agent + score
- references extracted (count, list of arXiv IDs / DOIs)
- exploits flagged in rigor scan

### Stage 2 -- SPAWN 4 AGENTS IN PARALLEL

Claude issues ONE message with 4 `Agent` tool calls:
- `arena-literature-agent`
- `arena-historian-agent`
- `arena-pattern-scout-agent`
- `arena-rigor-agent`

Each prompt is filled in per `references/spawn-agents.md` with the
concrete `{slug}` and `{workspace}` values.

Wait for all 4 to complete, then **verify the artifacts landed on disk**:

    python3 .claude/skills/tool-arena-attack-problem/scripts/attack.py verify \
        --workspace projects/einstein-arena-{SLUG} --stage agents

If `verify` exits non-zero, at least one subagent returned its output
inline (in the reply message) but never called `Write`. This is a
recurring Claude-Code failure mode. Recovery: `Write` the returned
content to the missing path directly, OR re-spawn the agent with an
explicit `WRITE to {path}` reminder in the prompt. Do NOT proceed to
Stage 3 with missing artifacts — the synthesizer will silently produce
a thin graph.

Individual failures after verify re-spawn are OK (graceful
degradation at synthesise time — the warnings surface in OVERVIEW.md).

### Stage 3 -- HYPOTHESIZE

    python3 .claude/skills/arena-attack-problem/scripts/attack.py hypothesize \
        --workspace projects/einstein-arena-{SLUG}

Writes `HYPOTHESES_DRAFT.md` + `SYNTHESIS_WARNINGS.json`. Claude reports
how many nodes + any warnings.

### Stage 4 -- CRITIC REVIEW

One `Agent` tool call to `arena-critic-agent`. Wait for `CRITIQUE.md`,
then **verify**:

    python3 .claude/skills/tool-arena-attack-problem/scripts/attack.py verify \
        --workspace projects/einstein-arena-{SLUG} --stage critic

If the critic returned its content inline but skipped `Write` (common),
write the returned message body to `{workspace}/recon/CRITIQUE.md`
directly before running Stage 5.

### Stage 5 -- RENDER OVERVIEW + USER GATE

    python3 .claude/skills/arena-attack-problem/scripts/attack.py overview \
        --workspace projects/einstein-arena-{SLUG}

Claude then:
1. Reads `{workspace}/OVERVIEW.md`.
2. Prints a concise summary to the user (Problem + top-3 hypotheses +
   proposed attack directions + open questions). Point the user at the
   full `OVERVIEW.md` path for detail.
3. Issues an `AskUserQuestion` with three options:
   - **Approve** -- proceed to Stage 6 autonomously.
   - **Modify** -- gather user's edits (add a hypothesis, de-prioritise
     one, change the attack direction); re-render OVERVIEW.md.
   - **Abort** -- stop the campaign; report current artifacts.

### Stage 6 -- ATTACK / POLISH / TRI-VERIFY (autonomous on approval)

Invoke `AttackOrchestrator.run()` with:
- `stop_at=Phase.SUBMIT` (so submit stays human-gated)
- the hypothesis graph from Stage 5
- `attack_loop` chosen from the router (or `attack_loop_cold_start` for
  fresh problems)

Tail the attack loop's output; when a candidate is in hand, run
`tool-arena-runner tri-verify` on it.

### Stage 7 -- SUBMIT GATE + RETROSPECTIVE

Final `AskUserQuestion` with the tri-verify report + candidate score:
- **Submit** -- `tool-arena-runner submit`, then poll for evaluation.
- **Iterate** -- loop back to Stage 6 with the critic's feedback + new
  priors (saved to `HYPOTHESES.md`).
- **Stop** -- run retrospective only.

Regardless of submit outcome, run
`retrospective.py` over the workspace to propose new patterns / fixtures
for future campaigns.

## Failure modes

| Symptom | Cause | Recovery |
|---|---|---|
| `recon` exits non-zero | No credentials / network error | Run `tool-arena-runner register`, retry |
| `.phases/{phase}.done` exists but workspace corrupted | Prior campaign's stale marker | `rm -rf {workspace}/.phases/ && python3 scripts/attack.py recon …` |
| Literature agent hit every WebFetch block | Firecrawl key absent, or site blocks all UAs | Proceed; synthesiser flags it in warnings; user sees the gap in OVERVIEW.md |
| Critic produces zero findings | Draft graph is already tight (rare) | OK; proceed |
| Critic produces 100 findings | Draft graph is weak | Rerun `hypothesize` after manually populating missing recon artifacts |

## Rule of thumb

Every bash command is idempotent -- re-running is safe. Every Agent
spawn is one-shot; if the agent fails or returns junk, re-spawn it
(not the whole pipeline).
