# Paper pipeline — design + operating notes

> **Guardrails v3 updates (authoritative over this file where they conflict):**
> - **Structured JSON reports.** `sci-verifier` and `sci-reviewer` now write `{slug}-verification.json` and `{slug}-review.json` (not just markdown). Each must contain `{version, nonce, phase, verdict, counts: {fatal|critical, major, minor}, findings}`. Markdown companions are for humans; the pipeline ignores them.
> - **Nonce handshake.** `cmd_init` mints a UUID nonce stored in `state.nonce` and returned on every command payload. Subagent reports must echo it or the pipeline raises `ForgeryError` and refuses.
> - **Phase preconditions.** Every command declares allowed phases via `ALLOWED_TRANSITIONS`. Out-of-order calls raise `PipelineError`. `phase='refused'` is terminal — only `status` runs from there.
> - **`cmd_init` refuses re-init** unless `--force`. Force writes an append-only entry to `$SCI_OS_LEDGER` (default `~/.scientific-os/pipeline-ledger.jsonl`) capturing the prior phase, nonce, and retry_count. Retry budget can no longer be reset by deleting the state file.
> - **Atomic state writes.** `save_state` uses tempfile + `os.replace`.
> - **Upstream provenance trace.** `cmd_gate_draft` auto-discovers `{slug}.quotes.json` from the researcher phase and passes `--quotes` to `verify_ops.py`. Any draft sidecar quote that doesn't substring-match an upstream candidate is flagged CRITICAL.
> - **PreToolUse hook.** Independent of this pipeline, every direct Write/Edit to `projects/sci-writing/**/*.md` is intercepted by `verify_gate.py` in PreToolUse, which simulates the proposed content, runs `verify_ops`, and returns exit 2 to actually block the tool call. This is a second, independent line of defense — even a pipeline short-circuit can't sneak a fabrication onto disk.

The paper pipeline is the 4-agent review cascade that guards every
`sci-writing` draft mode request. It enforces the integrity commandments
defined in `.planning/fabrication-guardrails-v2.md` and is the most
aggressive review workflow scientific-os runs.

Agents (defined under `.claude/agents/`):

- `sci-researcher` — builds the numbered evidence table, `.bib`, quotes
  sidecar.
- `sci-writer` — drafts from the evidence table, bound to `[@Key]`
  markers matching the bib.
- `sci-verifier` — mechanical (`verify_ops.py`) + semantic (claim, quote)
  check.
- `sci-reviewer` — adversarial audit in verification mode with FATAL /
  MAJOR / MINOR findings.

`scripts/paper_pipeline.py` is the state machine that Claude calls at
each transition. Python does NOT spawn subagents — it manages the
workspace and parses the agents' output files.

## Why 4 agents, not 1

Papers take weeks of work and get read by peers who can tell when a
citation doesn't support the claim. The context isolation between writer
and verifier prevents the writer from "optimizing around" the check —
when one agent drafts and verifies in the same context, it learns to
hedge just enough to pass, not to be correct. Separate subagents force
the reviewer to see the draft cold. Token math is explicit in the v2
plan: ~80–100k extra tokens per draft, acceptable for a multi-week
manuscript.

## Full flow

```
skill (Claude)                     paper_pipeline.py           subagents
───────────────                     ─────────────────            ──────────
1. skill detects draft mode

2. skill calls pipeline ─────────▶ init <slug> --topic ... --section ...
                                   (creates projects/sci-writing/<slug>/)
   ◀─── {status: ok, workspace}

3. skill spawns sci-researcher ────────────────────────────▶ sci-researcher
                                                             writes
                                                             research.md,
                                                             <slug>.bib,
                                                             <slug>.quotes.json

4. skill calls pipeline ─────────▶ check-research <slug>
                                   (verifies artifacts exist)
   ◀─── {status: ok, artifacts}

5. skill spawns sci-writer ────────────────────────────────▶ sci-writer
                                                             writes
                                                             <slug>-draft.md,
                                                             <slug>-draft.md.citations.json

6. skill calls pipeline ─────────▶ gate-draft <slug>
                                   (runs verify_ops.py on the draft)
   ◀─── {status: passed|blocked|refused}

   if blocked: re-spawn sci-writer with findings,
               re-run gate-draft (this is an inner writer fix pass,
               NOT a cascade retry; it doesn't count against retry_count)

7. skill spawns sci-verifier ──────────────────────────────▶ sci-verifier
                                                             writes
                                                             <slug>-verification.md

8. skill calls pipeline ─────────▶ collect-verification <slug>
                                   (parses verification.md for CRITICAL/MAJOR/MINOR)
   ◀─── {status: ok, critical, major, minor}

9. skill spawns sci-reviewer ──────────────────────────────▶ sci-reviewer
                                                             writes
                                                             <slug>-review.md

10. skill calls pipeline ────────▶ collect-review <slug>
                                   (parses review.md for FATAL/MAJOR/MINOR)
    ◀─── {status: ok, fatal, major, minor}

11. skill calls pipeline ────────▶ retry-check <slug>
                                   (fatal = verification.critical + review.fatal)
    ◀─── {status: ok | revise | retry | refused}

    if retry:
      skill re-spawns sci-writer with <slug>-review.md as fix instructions
      then loops back to step 6 (gate-draft → verifier → reviewer → retry-check).
      retry_count increments once per full cascade retry.

    if refused:
      skill halts, surfaces <slug>-review.md and <slug>-verification.md,
      does NOT save.

    if revise (MAJOR but no FATAL):
      skill reports MAJOR findings to user for manual revision before finalize.

12. skill calls pipeline ────────▶ finalize <slug>
                                   (confirms save allowed)
    ◀─── {status: ok, workspace, artifacts}
```

## State file schema

`projects/sci-writing/<slug>/.pipeline_state.json`:

```json
{
  "pipeline": "paper",
  "slug": "biomarker-intro",
  "topic": "...",
  "section": "introduction",
  "phase": "init | researched | drafted | verified | reviewed | retry | refused | clean | needs-major-revision | finalized",
  "retry_count": 0,
  "max_retries": 1,
  "mechanical_exits": [0, 2, 0],
  "verification_counts": [ {...} ],
  "review_counts": [ {...} ],
  "history": [ {"event": "...", "at": "..."} ]
}
```

## Retry budget

Exactly one cascade retry. `mechanical_exits` may grow during inner
writer fix passes triggered by `gate-draft` blocked states — those are
NOT cascade retries. `retry_count` only increments when the full
cascade (verifier + reviewer) fires again after a FATAL finding.

## Exit codes

- `0` — success, proceed
- `1` — script error (missing file, bad argument)
- `2` — blocked / revise (inner fix pass or MAJOR revision required)
- `3` — refused (do not save)

## Mandatory writer discipline

The `sci-writer` subagent is told in its system prompt that it can only
cite entries from the evidence table. The mechanical gate re-checks
this via `verify_ops.py` phase A (bib key match). The verifier then
re-checks via semantic comparison with the sidecar quotes. And finally
the reviewer re-checks as part of its weakness audit. Four layers because
the stakes are high.

## Troubleshooting

- **"No paper pipeline state for <slug>"** — `init` not called first.
- **check-research returns incomplete** — `sci-researcher` failed to
  produce one of the three required artifacts. Re-spawn it.
- **gate-draft exit 3** — the writer produced a draft without a sidecar
  or with an empty bib. Fix and re-run.
- **retry-check reports retry then immediately refused on second pass**
  — expected: retry budget is exactly one. If FATAL persists, the
  pipeline refuses.
- **Finalize returns refused** — at least one FATAL finding is still
  present at the last collected verification or review. Inspect state
  history to see what changed.
