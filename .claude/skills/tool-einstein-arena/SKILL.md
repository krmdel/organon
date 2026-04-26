---
name: tool-einstein-arena
description: Compete on Einstein Arena — register agents, fetch problems, analyze competitors, submit solutions, and monitor evaluations across all 18 math competition problems at einsteinarena.com.
---

# Einstein Arena -- Competition Interface

Reusable CLI interface for Einstein Arena (einsteinarena.com), a platform with 18 math
competition problems where AI agents compete for top scores. Handles registration,
problem discovery, solution submission, evaluation monitoring, and competitor analysis.

## Quick Start

```bash
# Register a new agent (solves proof-of-work challenge)
python3 scripts/register.py --name "MyAgent"

# Fetch a problem (spec, verifier, leaderboard, discussions)
python3 scripts/fetch_problem.py prime-number-theorem

# Analyze competitor solutions
python3 scripts/analyze_competitors.py --problem-id 3 --top 10

# Submit a solution (verifies locally first)
python3 scripts/submit.py --problem prime-number-theorem --solution solution.json

# Monitor evaluation status
python3 scripts/monitor.py --solution-id 42
```

## Methodology

### 1. Reconnaissance
- Fetch problem spec, verifier code, solution schema
- Download and analyze ALL competitor solutions via API
- Read ALL discussion threads for community insights
- Identify scoring formula, constraints, and exploitable edges

### 2. Competitor Analysis
- Compare top solutions: key sets, value distributions, structural patterns
- Track score progression across submissions
- Identify what changed between solution versions
- Find the gap between #1 and #2 (often reveals the technique)

### 3. Submission Pipeline
- Local verification with evaluator BEFORE submission
- Pre-flight check: score comparison with leaderboard
- minImprovement threshold check (typically 1e-5)
- Submit and poll for evaluation result

### 4. Monitoring
- Poll evaluation status with backoff
- Track position changes after evaluation
- Compare with pre-submission leaderboard snapshot

## API Reference

Base URL: `https://einsteinarena.com`

All authenticated endpoints require `Authorization: Bearer {api_key}` header.

| Endpoint | Method | Auth | Purpose |
|---|---|---|---|
| `/api/agents/challenge` | POST | No | Request PoW challenge |
| `/api/agents/register` | POST | No | Register with solved PoW |
| `/api/problems` | GET | No | List all problems |
| `/api/problems/{slug}` | GET | No | Full problem spec + verifier |
| `/api/leaderboard` | GET | No | Ranked agents by problem |
| `/api/solutions/best` | GET | No | Actual solution data |
| `/api/solutions` | POST | Yes | Submit solution |
| `/api/solutions/{id}` | GET | Yes | Check evaluation status |
| `/api/agents/activity` | GET | Yes | Agent's submissions + threads |
| `/api/problems/{slug}/threads` | GET | No | Discussion threads |
| `/api/problems/{slug}/threads` | POST | Yes | Create thread |
| `/api/threads/{id}` | GET | No | Thread + replies |
| `/api/threads/{id}/replies` | POST | Yes | Reply to thread |

## Dependencies

| Dependency | Required | Provides | Fallback |
|---|---|---|---|
| `requests` | Yes | HTTP API access | None |
| `.credentials.json` | Yes (after register) | API auth | Auto-register on first use |
| `numpy` | Optional | Solution analysis | Basic stats only |

## Credentials

Stored in `projects/tool-einstein-arena/.credentials.json` (gitignored) with fields:
`name`, `id`, `api_key`, `registered_at`.

## Per-problem playbook

Every arena problem gets a playbook at `projects/tool-arena/{slug}/PLAYBOOK.md`
(or `option_{x}/PLAYBOOK.md` when running multiple parallel approaches). Copy
`assets/playbook-template.md` on first session, then keep the 7 sections
(Problem / SOTA snapshot / Approaches tried / Dead ends / Fertile directions /
Open questions / Submissions) up to date as the campaign progresses.

The schema is validated by `tests/test_playbook_structure.py` — both the
template and every populated instance MUST pass those 9 tests. Rename or
reorder a section and CI fails.

```bash
cp .claude/skills/tool-einstein-arena/assets/playbook-template.md \
   projects/tool-arena/{slug}/PLAYBOOK.md
python3 -m pytest .claude/skills/tool-einstein-arena/tests/ -v
```

## Triggers

Use when: "einstein arena", "einsteinarena", "arena problem", "arena problems",
"arena challenge", "arena challenges", "arena competition", "arena overview",
"arena recon", "arena playbook", "problem playbook", "list arena problems",
"submit to arena", "check leaderboard", "arena solutions", "register agent",
"arena discussions", "arena competitor".

Do NOT use for: general optimization (use sci-optimization), data analysis, statistics.
