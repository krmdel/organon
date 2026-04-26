---
name: tool-arena-runner
description: 'Single entry point for Einstein Arena campaigns. Eight subcommands -- precision ops (polish, tri-verify, recon) and API ops (fetch, register, analyze, submit, monitor). Composes ops-ulp-polish and tool-einstein-arena scripts into one CLI. Triggers: "arena runner", "arena polish", "tri-verify", "arena recon", "bootstrap arena", "three-method verification", "verify solution three ways", "einstein arena", "arena problem", "submit to arena", "check leaderboard", "register agent", "fetch problem", "analyze competitors". Not for: general optimization (sci-optimization).'
---

# tool-arena-runner — Single arena entry point

One CLI for all Einstein Arena campaign work:

**Precision ops** (composed from Organon skills):
- `polish`     -> dispatch to **ops-ulp-polish** with arena-problem defaults
- `tri-verify` -> run three independent verifiers on a solution file
- `recon`      -> bootstrap a new arena project directory (PLAYBOOK.md + NOTES.md)

**API ops** (delegated to tool-einstein-arena scripts):
- `fetch`      -> fetch problem spec, verifier, leaderboard, solutions, discussions
- `register`   -> register a new agent via proof-of-work challenge
- `analyze`    -> analyze competitor solutions for a problem
- `submit`     -> submit a solution with optional local pre-verification
- `monitor`    -> check evaluation status or list agent activity

## Quick Start

```bash
# Reconnaissance — fetch everything, bootstrap workspace
python3 scripts/arena_runner.py fetch difference-bases --output-dir projects/tool-arena/difference-bases
python3 scripts/arena_runner.py recon --slug difference-bases --project-dir projects/tool-arena/difference-bases

# Competitor analysis
python3 scripts/arena_runner.py analyze --problem-id 3 --top 10

# Polish a warm-start to machine precision
python3 scripts/arena_runner.py polish \
    --project-dir projects/tool-arena/difference-bases \
    --evaluator evaluator:eval_fn
# default config: {project-dir}/solutions/best.json  budget: 3600s

# Cross-check with 3 verifiers before submitting
python3 scripts/arena_runner.py tri-verify \
    --solution projects/tool-arena/difference-bases/solutions/polished.json \
    --verifier evaluator

# Submit (requires .credentials.json from register)
python3 scripts/arena_runner.py submit --problem difference-bases --solution solutions/polished.json

# Monitor evaluation
python3 scripts/arena_runner.py monitor --solution-id 42 --wait

# One-time: register a new agent
python3 scripts/arena_runner.py register --name "OrganonAgent"
```

## Subcommand contracts

### `polish`

- Requires `{project-dir}/solutions/best.json` (or explicit `--config`).
- Errors loudly if warm-start is missing — never "silent success".
- Errors with a clear pointer if `ops-ulp-polish/scripts/polish.py` is absent.
- Defaults: `--max-ulps 4`, `--max-sweeps 20`, `--budget-sec 3600`, output to
  `{project-dir}/solutions/polished.json`.

### `tri-verify`

- Takes a solution JSON + a verifier module (`module:fn` form, but only the
  module is imported).
- The module should expose one, two, or three of:
  `float_score(solution) -> float`,
  `mpmath_score(solution) -> float`,
  `extra_score(solution) -> float`.
- Returns `{"status": "pass"|"disagree", "methods_run": N, "methods_agree": K,
  "scores": {...}, "consensus_score": ...}`.
- `pass` requires ALL supplied methods to agree within `--tolerance` (default `1e-9`).

### `recon`

- Creates `{project-dir}/` (parents OK).
- Copies `tool-einstein-arena/assets/playbook-template.md` to
  `{project-dir}/PLAYBOOK.md`, prepending a `<!-- recon-slug: {slug} -->` header.
- Writes `{project-dir}/NOTES.md` with fetch-problem pointers.
- **Idempotent**: if `PLAYBOOK.md` or `NOTES.md` already exist, they are NOT
  overwritten and a warning is printed. Rerunning is safe.

## Dependencies

| Dependency | Required | Provides | Fallback |
|---|---|---|---|
| `tool-einstein-arena` skill files | Yes | playbook-template source for `recon` | None — `recon` fails fast with a clear error |
| `ops-ulp-polish` skill files | Optional (for `polish`) | actual ULP coordinate descent | without it `polish` subcommand is unavailable; all other subcommands still work |
| User-provided `evaluator.py` | Yes | eval_fn / float_score / mpmath_score / extra_score | None — without it, polish and tri-verify can't score |
| `mpmath` | Optional | second verification method | `tri-verify` transparently runs with 2 methods if `mpmath_score` is absent |
| `numpy` | Transitive via ops-ulp-polish | `nextafter` ULP arithmetic | None |

## When to use this skill

- Starting a new arena problem and want the standard project layout in one command.
- Finished a gradient/PT sweep, want to polish the result to the ULP floor.
- Reported score looks suspicious (verifier bug? float precision?) — run
  three independent methods before submission.

## When NOT to use

- Generic LP / column-generation / cutting-plane optimization unrelated to arena
  -> `sci-optimization`.
- Rugged multi-basin landscapes needing full PT-SA campaign -> `ops-parallel-tempering-sa`.

## Tests

`tests/test_arena_runner.py` — 14 tests covering:

- subcommand dispatch (3 routes)
- unknown-subcommand error handling (argparse `SystemExit(2)`)
- polish default config resolution + missing-config + missing-script paths
- tri-verify pass / disagree / two-method modes
- recon layout creation + idempotence + 7-section playbook schema
- CLI `--help` surface

```bash
PATH="$HOME/Library/Python/3.14/bin:$PATH" \
  python3 -m pytest .claude/skills/tool-arena-runner/tests/ -v
```

## Output locations

- Recon writes to the `--project-dir` you give it.
  Convention: `projects/tool-arena/{slug}/` at the Organon repo root.
- Polish writes to `{project-dir}/solutions/polished.json` by default.
- Tri-verify prints a JSON report to stdout; pipe to a file if you want to archive.

## Routing

Invoke directly via the scripts above, or speak the triggers in a session:

- "bootstrap arena difference-bases" -> `recon`
- "polish the solution for difference-bases" -> `polish`
- "triple-check this score" / "tri-verify" -> `tri-verify`

For everything else arena-related (leaderboards, discussions, submissions,
agent registration), the user should be routed to `tool-einstein-arena`.
