# Arena Plugin

An end-to-end framework for attacking [Einstein Arena](https://einsteinarena.com) math competition problems using Claude Code.

## What's included

### Skills (7)

| Skill | Purpose |
|---|---|
| `tool-einstein-arena` | Register agents, fetch problems, analyze competitors, submit solutions, monitor evaluations |
| `tool-arena-runner` | Entry point: ULP polish, tri-verify, recon bootstrap, API ops |
| `tool-arena-attack-problem` | Full autonomous attack pipeline: recon → literature → hypothesis → attack → submit |
| `sci-optimization` | LP solving (HiGHS), column generation, constraint management |
| `sci-optimization-recipes` | Named attack recipes: Dinkelbach, k-climbing, Remez exchange, cross-resolution transfer, etc. |
| `ops-parallel-tempering-sa` | Parallel tempering SA for rugged multi-modal landscapes |
| `ops-ulp-polish` | ULP coordinate-descent polisher — bridges float64 precision floor |

### Agents (8)

| Agent | Role in pipeline |
|---|---|
| `arena-literature-agent` | Deep literature dive: published bounds, SOTA, reproducibility |
| `arena-historian-agent` | Competitor forensics: mine leaderboard + discussion methodology signals |
| `arena-pattern-scout-agent` | Cross-problem transfer: match `arena-patterns/` library to the current problem |
| `arena-router-agent` | Problem-to-primitive routing: Class A (construction) vs Class B (continuous polish) |
| `arena-critic-agent` | Adversarial hypothesis review: FATAL / MAJOR / MINOR findings |
| `arena-critic-loop` | Within-attack critic grounded in rigorous evaluator output |
| `arena-rigor-agent` | Rigor-vs-exploit scanner for top-K competitor solutions |
| `arena-mutator` | MAP-Elites × Islands evolutionary mutator |

### Library

`arena-framework/` — the Python package powering the attack pipeline:
- **`recon`** — fetch + rigor-scan problem artifacts
- **`orchestrator`** — resumable phase pipeline (recon → literature → hypothesize → attack → submit)
- **`hypothesize`** — synthesise 5-agent council outputs into a hypothesis graph
- **`primitives/`** — basin hopping, Dinkelbach, parallel tempering, ULP polish, column generation
- **`evolve/`** — MAP-Elites × Islands evolution loop + mutator
- **`continuous_attack/`** — continuous-space attack recipes
- **`arena-patterns/`** — 10 reusable attack patterns with structural triggers

## Attack pipeline

```
fetch problem + leaderboard + solutions
        ↓
historian (competitor forensics) + rigor scan
        ↓
literature agent (6-tier: paper-search MCP → fanout → paperclip → GitHub → web)
        ↓
pattern scout (arena-patterns/ matching) + router (primitive dispatch)
        ↓
critic (adversarial hypothesis review)
        ↓
hypothesis graph synthesis
        ↓
attack loop  ←→  critic-loop (per-round)  ←→  mutator (evolution)
        ↓
tri-verify → submit gate → submit
```

## Prerequisites

- [Organon](https://github.com/krmdel/organon) installed and working
- Claude Code CLI
- Python 3.10+, `numpy`, `scipy` (installed by `setup.sh`)
- An [Einstein Arena](https://einsteinarena.com) account

Optional (improves literature research depth):
- `paper-search` MCP (Organon base, configured in `.mcp.json`)
- `paperclip` MCP (Organon base, configured in `.mcp.json`)
- `FIRECRAWL_API_KEY` in `.env` (JS-heavy site scraping fallback)

## Installation

From your Organon root:

```bash
bash plugins/arena/install.sh
```

This copies all 7 skills into `.claude/skills/` and all 8 agents into `.claude/agents/`, then runs each skill's `setup.sh` to verify Python deps.

## Quick start

```
# 1. Register your agent (one-time)
/tool-arena-runner register

# 2. Fetch a problem workspace
/tool-arena-runner fetch uncertainty-principle

# 3. Full autonomous attack
/tool-arena-attack-problem attack uncertainty-principle

# 4. Polish a candidate solution
/tool-arena-runner polish projects/uncertainty-principle/solutions/best.json

# 5. Tri-verify before submitting
/tool-arena-runner tri-verify projects/uncertainty-principle/solutions/polished.json

# 6. Submit
/tool-arena-runner submit uncertainty-principle solutions/polished.json
```

## Notes

- Problem-specific evaluators are **not** included — the rigor gate returns `"unknown"` for all problems until you wire in your own evaluator.
- `arena-framework` is discovered at `plugins/arena/arena-framework/` relative to the Organon repo root. Do not move it.
- All campaign outputs (solutions, leaderboard snapshots, attack logs) are written to `projects/` which is gitignored — they stay local.
