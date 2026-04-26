# Composition notes — how `tool-arena-runner` fits the Organon stack

`tool-arena-runner` is deliberately a thin composition layer. It contains no
HTTP client, no ULP arithmetic, no verifier logic of its own. Everything it
does is a call into an existing skill, with opinionated defaults tuned for
Einstein Arena campaigns.

## Routing table

| User intent | Skill invoked | Script |
|---|---|---|
| "register an arena agent" | `tool-einstein-arena` | `scripts/register.py` |
| "fetch problem X" | `tool-einstein-arena` | `scripts/fetch_problem.py` |
| "who's on the leaderboard" | `tool-einstein-arena` | `scripts/analyze_competitors.py` |
| "submit this solution" | `tool-einstein-arena` | `scripts/submit.py` |
| "monitor my submission" | `tool-einstein-arena` | `scripts/monitor.py` |
| "bootstrap a new arena project dir" | **`tool-arena-runner`** | `scripts/arena_runner.py recon` |
| "polish to the ULP floor" | **`tool-arena-runner`** -> `ops-ulp-polish` | `scripts/arena_runner.py polish` |
| "tri-verify this solution" | **`tool-arena-runner`** | `scripts/arena_runner.py tri-verify` |
| "generic ULP descent on any problem" | `ops-ulp-polish` | `scripts/polish.py` |

So: all **API traffic** stays in `tool-einstein-arena`. All **numerical
optimization primitives** stay in `ops-ulp-polish`. `tool-arena-runner` is a
boxed pipeline entry-point that scientists reach for when they want the arena
defaults without remembering eight CLI flags.

## Why a separate skill?

Two reasons:

1. **Operational vs API separation.** `tool-einstein-arena` is API-shaped
   (register / fetch / submit / monitor). Polish and tri-verify are
   *operational* — they don't touch the arena server, they operate on local
   files. Mixing them in the same skill bloats the trigger space and makes
   the SKILL.md harder to scan.
2. **Defaults belong in one place.** The "3600 second budget + warm-start
   from `solutions/best.json` + output to `solutions/polished.json`"
   convention is specific to arena campaigns. `ops-ulp-polish` should remain
   problem-agnostic so it can be reused outside the arena (lattice packings,
   spherical codes, kissing configs). `tool-arena-runner` is where the arena
   policy lives.

## Interaction with `sci-council`

Campaign strategy (which approach to try next) goes through `sci-council`
when you want a three-persona fan-out. Tactical execution of a specific
approach — polishing a candidate, verifying a score — goes through
`tool-arena-runner`. There is no direct dependency; the human (or the
orchestrator) chains them.

## Future direction: absorbing `tool-einstein-arena`

If/when we want a single arena skill, the migration path is:

1. Move `tool-einstein-arena/scripts/` under `tool-arena-runner/scripts/arena/`.
2. Add `arena` sub-subcommands (`arena register`, `arena fetch`, `arena submit`,
   `arena monitor`, `arena compete`) to `arena_runner.py`.
3. Keep `polish` / `tri-verify` / `recon` as top-level subcommands so
   muscle-memory invocations still work.
4. Update the Skill Registry to point the arena triggers at `tool-arena-runner`
   and retire the old skill folder (via `scripts/remove-skill.sh`).

Until then, **do not cross the streams**. `tool-arena-runner/scripts/` should
not import `tool-einstein-arena/scripts/` and vice versa. The only allowed
coupling is the `assets/playbook-template.md` read (one-way, for `recon`).

## Testing philosophy

`tool-arena-runner` ships with 14 focused tests. None of them hit the network,
none of them import `numpy`/`mpmath`, and the slowest one spawns a 10-second
subprocess to smoke-test the CLI `--help` surface. The design goal is: a new
contributor should be able to run the full suite in under a second and have
full confidence the composition wiring is correct, without needing arena
credentials or a warm-start file in hand.
