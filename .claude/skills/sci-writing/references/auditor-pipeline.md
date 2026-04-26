# Auditor pipeline — design + operating notes

> **Guardrails v3 updates (authoritative over this file where they conflict):**
> - **Structured JSON audit report.** `sci-auditor` now writes `{slug}-audit.json` with `{version, nonce, phase: "audit", verdict, counts, findings}`. The nonce must match `state.nonce` issued at `cmd_init`. Any mismatch raises `ForgeryError`; the pipeline refuses.
> - **Review-mode seed gate.** `cmd_gate` refuses the `sci-writing` category unless `{slug}.quotes.json` exists in the workspace. Review mode will no longer reverse-engineer the sidecar from the draft — you must run `sci-literature-research` cite mode first.
> - **Upstream provenance trace** (shared with paper pipeline): `cmd_gate` auto-discovers `{slug}.quotes.json` and passes `--quotes` to `verify_ops.py`. Draft sidecar claims must substring-match an upstream candidate.
> - **Post-humanize re-verification (T4.1).** New `cmd_post_humanize` command. Runs only from `phase=finalized`. After `tool-humanizer` rewrites the draft, call `auditor_pipeline.py post-humanize <category> <slug>`; a non-zero exit flips the pipeline to terminal `refused`, preventing the humanized draft from shipping. Every skill that invokes the humanizer on a gate-passed artifact MUST wire through this command.
> - **Phase preconditions + refused terminal** + **nonce handshake** + **atomic state writes** + **forced-reinit ledger** — see `paper-pipeline.md` for the shared contract.
> - **`sci-auditor` is read-only.** `.claude/agents/sci-auditor.md` no longer grants `Write`. The auditor produces a deliverable (the audit report); it does not mutate the draft.
> - **PreToolUse hook** intercepts every direct Write/Edit to `projects/sci-communication/**/*.md` the same way it does for `sci-writing`. The auditor pipeline is the happy path; the PreToolUse gate is the backstop.

The auditor pipeline is the single-subagent review cascade used by
`sci-communication` (all modes: blog, tutorial, explainer, lay summary,
newsletter, social thread, press release) and by `sci-writing` review mode
when the user hands us an existing draft to audit rather than asking us
to draft fresh.

Designed in `.planning/fabrication-guardrails-v2.md` §5k. Uses the
`sci-auditor` subagent defined in `.claude/agents/sci-auditor.md`.

## Why one auditor instead of four agents

Paper manuscripts get the full 4-agent cascade (researcher → writer →
verifier → reviewer) because the stakes are weeks of work and the draft
is long. Blog posts and short explainers are single-session work — a
100k-token cascade is theater for that use case. The single auditor
combines the verifier's semantic (claim, quote) check with the reviewer's
adversarial commentary, saving roughly 60k tokens per run without
sacrificing the fabrication guardrails that actually matter.

## The script's role

`scripts/auditor_pipeline.py` is a CLI state machine. It does NOT spawn
subagents — Python cannot call the `Agent` tool. Instead the skill
(running inside Claude's loop) calls the script at each transition point
and spawns the subagent itself. The script is responsible for:

1. Creating the workspace directory under `projects/{category}/{slug}/`.
2. Persisting `.pipeline_state.json` so a partial run is recoverable.
3. Running `verify_ops.py` as the mechanical floor.
4. Parsing `{slug}-audit.md` to decide whether a retry is needed.
5. Enforcing the retry budget (`MAX_RETRIES = 1`) and refusing to
   finalize if FATAL findings persist after it.

## Full flow

```
skill (Claude)                      auditor_pipeline.py        sci-auditor
───────────────                      ────────────────────        ────────────
1. skill decides to use auditor pipe
   based on mode detection

2. skill calls pipeline ───────────▶ init {category} {slug}
                                     (creates workspace, writes state)
   ◀─── {status: ok, workspace}

3. skill writes {slug}.md,
   {slug}.bib, {slug}.md.citations.json
   into the workspace (drafting step,
   may or may not involve another
   subagent depending on mode)

4. skill calls pipeline ───────────▶ gate {category} {slug}
                                     (runs verify_ops.py on the draft)
   ◀─── {status: passed|blocked|refused, report}

   if refused: skill halts, tells user
   what to fix; do NOT proceed to audit.

5. skill spawns sci-auditor ─────────────────────────────▶ sci-auditor
                                                            reads draft,
                                                            runs verify_ops
                                                            again, does
                                                            semantic pass,
                                                            writes
                                                            {slug}-audit.md
   ◀─── {status: ship|revise|refuse}

6. skill calls pipeline ───────────▶ retry-check {category} {slug}
                                     (parses audit.md, counts FATAL,
                                      increments retry_count if needed)
   ◀─── {status: retry|refused|ok, verdict}

   if retry:
     skill applies the audit's revision plan
     (rewrite the parts flagged FATAL)
     then loops back to step 4 (gate + sci-auditor)

   if refused:
     skill halts, surfaces audit.md to user, stops

7. skill calls pipeline ───────────▶ finalize {category} {slug}
                                     (confirms save is allowed)
   ◀─── {status: ok, artifacts}

8. skill completes the usual post-save
   steps (gdrive gate, obsidian gate, etc.)
```

## State file schema

`projects/{category}/{slug}/.pipeline_state.json`:

```json
{
  "pipeline": "auditor",
  "category": "sci-communication",
  "slug": "crispr-explainer",
  "phase": "init | gated | audited | retry | finalized | refused",
  "retry_count": 0,
  "max_retries": 1,
  "mechanical_exits": [0, 2],
  "audit_verdicts": ["refuse", "ship"],
  "history": [ {"event": "...", "at": "..."} ]
}
```

## Retry budget

Exactly one retry is permitted. The budget exists so a determined
hallucination doesn't trigger an infinite loop of "fix → fails → fix →
fails". After the second audit still flags FATAL findings, the pipeline
refuses to finalize — the skill must halt and surface the audit.

## Exit codes

Each subcommand returns JSON on stdout and an exit code:

- `0` — success, proceed to next step
- `1` — error (missing file, bad argument, etc.)
- `2` — blocked (CRITICAL findings, or MAJOR+ audit verdict — retry may
  still be possible)
- `3` — refused (contract failure, or retry budget exhausted with
  FATAL persisting — do NOT save)

## When to use this pipeline vs the paper pipeline

- **Paper pipeline** (`paper_pipeline.py`): every `sci-writing` draft mode
  request. Anything scientific that gets treated as a formal manuscript
  section.
- **Auditor pipeline** (`auditor_pipeline.py`): every `sci-communication`
  request regardless of style, AND `sci-writing` review mode when the
  user provides an existing draft rather than asking us to draft fresh.

The split is locked in `.planning/fabrication-guardrails-v2.md` §2b and
should not be softened without explicit user approval.

## Troubleshooting

- **"No pipeline state for {category}/{slug}. Run `init` first."** — the
  skill called `gate`/`retry-check`/`finalize` before calling `init`. Fix
  by running `init` first.
- **Exit 3 on gate** — either no bib exists or the bib parses to zero
  entries. Run `sci-literature-research` cite mode before calling the
  pipeline.
- **Exit 3 on finalize** — last gate was exit 3 and never healed, or
  FATAL findings are still present. Read `.pipeline_state.json` history
  to see the sequence.
- **Retry loop immediately refuses** — `retry_count` already at
  `max_retries` from a prior abandoned run. If this is intentional the
  skill should delete `.pipeline_state.json` and re-init; if not, inspect
  the history to understand what happened before deciding.
