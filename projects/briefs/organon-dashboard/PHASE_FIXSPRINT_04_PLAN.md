---
phase: fixsprint-04
title: Async run-state surfacing — heartbeat, timeout, structured exit, RunStateCard, council fanout failure UX
date: 2026-05-06
fixplan_phase: 3 (T3.1–T3.7 — partial; /runs page + 504 distinct from 500 deferred to fixsprint-04b)
estimated_effort: 0.5 day (actual)
---

# Phase fixsprint-04 — PLAN

## Phase 0.5 audit

The dogfood report Finding #14 was the worst single bug found:

> claude -p died at 3:35 mid-council-fanout, with no UI feedback. The
> spinner kept spinning. There was no Cancel button. There was no Retry.
> The user discovered the failure only by checking `.organon/runs/`
> directly.

Root causes:
- The runner had no heartbeat → proxies + the browser EventSource silently
  drop the stream after 60–120 s of no traffic.
- The runner had no timeout watchdog → a stuck LLM ran forever.
- The runner emitted only `{type: "exit", code}` → the route had no way to
  distinguish "completed cleanly with code 0", "killed by SIGTERM (which we
  *also* fire on user cancel)", and "subprocess crashed". So the route's
  `done` SSE event lied: it always said "done" regardless.
- The client had a single `error` bucket → no way to render different copy
  for "timed out" vs "subprocess died" vs "you cancelled".

## Goal (one sentence)

Every long-running subprocess surfaces five terminal states (`succeeded`,
`failed`, `timeout`, `cancelled`, `spawn-error`) plus heartbeat keepalive
and configurable timeout caps; the council fanout — the dogfood blocker —
renders a structured failure card with Retry / Cancel.

## Non-goals (explicit)

- **Do NOT migrate every workspace yet.** The hypothesis council is the
  dogfood blocker; figures + draft + data already have working spinners.
  RunStateCard is mounted only in hypothesis-workspace.tsx for this commit;
  the rollout to other workspaces is fixsprint-04b.
- **Do NOT add a `/runs` failure-row affordance.** That's a UX polish
  task for fixsprint-04b.
- **Do NOT introduce a new SSE consumer helper module.** Each route's SSE
  loop got the minimal `lastExit` + enriched `done` change; introducing a
  shared `streamRunner` wrapper would force 7 routes through one mold and
  the variance kills it.
- **Do NOT decouple from `request.signal`.** Closing the tab still cancels
  the run. The fix here is to surface that as `cancelled` (with retry),
  not to keep zombie subprocesses alive.

## Tasks

### T4.A — Runner heartbeat + timeout + structured exit

`src/lib/runs.ts`:
- New `RunExitReason` union: `"ok" | "timeout" | "cancelled" | "failed" | "spawn-error"`.
- `RunEvent` gains `heartbeat` and `timeout` variants; `exit` gains
  optional `reason`, `success`, `message` (kept optional so legacy run
  logs read).
- `RunSummary.status` widened to include `"timeout"` and `"cancelled"`.
- `readRunSummary` + `readRunDetail` derive status from the runner's
  classification when present, falling back to `code === 0 ? ok : failed`.

`src/lib/claude-runner.ts`:
- `RunnerOptions` gains `timeoutMs` (default `8 * 60 * 1000`),
  `heartbeatMs` (default `15_000`), and `args` (for the test harness).
- Pre-aborted abortSignal short-circuits before spawn.
- After spawn, `setInterval(heartbeatMs)` pushes `heartbeat` events;
  `setTimeout(timeoutMs)` fires `timeout` then `child.kill("SIGTERM")`
  with a 5-second `SIGKILL` grace.
- On close, classify exit:
  - `timedOut` → `"timeout"`
  - `cancelledByUser` → `"cancelled"`
  - `code === 0` → `"ok"`
  - else → `"failed"`
  - spawn failure short-circuits to `"spawn-error"`.
- All timers cleared on close to avoid leaks.

### T4.B — SSE routes forward heartbeat + timeout + structured `done`

7 routes touched: `data/analyze`, `draft/[slug]/action`,
`hypothesis/reconcile`, `images/generate`, `images/lock`, `tools/run`,
`execute`.

Pattern is identical: capture `lastExit` in the loop; append
`{success, reason, exit_code, message}` to the terminal `done` SSE
payload. The new `heartbeat` + `timeout` runner events are auto-forwarded
because each route already does `send(evt.type, evt)`.

`images/lock` keeps its `captionLanded` gate: `done.success` is `true`
only if both runner exit was `"ok"` AND a usable caption + alt_text
landed.

### T4.C — Shared `RunStateCard` component

`src/components/primitives/run-state-card.tsx`:
- Props: `state: "idle"|"running"|"succeeded"|"failed"|"timeout"|"cancelled"`,
  `elapsedMs?`, `message?`, `label?`, `onCancel`, `onRetry`, `onDismiss`,
  `runId?`, `className?`.
- Renders nothing for `idle`. Other states render an alert/status box with
  state-specific palette (red for failed, orange for timeout, neutral for
  cancelled, green for succeeded, neutral for running with spinner +
  `mm:ss` elapsed counter).
- ARIA: `role="alert"` + `aria-live="assertive"` for failure states;
  `role="status"` for running/succeeded.
- Cancel button shows iff state="running" + onCancel.
- Retry button shows for failed/timeout/cancelled iff onRetry.
- Dismiss button shows for failed/timeout iff onDismiss.

### T4.D — Wire RunStateCard into the council fanout (the dogfood blocker)

`src/components/hypothesis/hypothesis-workspace.tsx`:
- `RunState` type widened to mirror `RunExitReason` 1:1.
- `consumeSse` now returns the parsed `done` summary; the workspace's
  `applyDone` helper maps reason → state + failure message.
- `lastGenParamsRef` holds the last council-generate params so Retry can
  replay them.
- An `elapsedMs` state ticks every 250 ms while a run is active.
- `<RunStateCard>` mounts in the main column, replacing the silent
  text-only error list. Cancel calls the existing `abortRef.current?.abort()`.

Other workspaces (data, figures, draft) keep their existing
spinners/error-text for now; rollout in fixsprint-04b.

### T4.E — Test harness binary

`tests/fixtures/fake-claude.mjs`:
- Modes: `success`, `success-after=Nms`, `fail-with=N`, `sleep=Nms`,
  `stdout-loop=Nms`. Pure Node stdlib; `chmod +x`-ready.

### T4.F — Regression test `tests/runner-failure.test.mjs`

10 tests:
1. RunEvent type carries heartbeat + timeout + structured exit.
2. Runner spawns watchdog + heartbeat interval + classifies exits.
3. Every SSE route captures lastExit + enriches `done`.
4. RunStateCard handles every state with appropriate copy.
5. Hypothesis workspace consumes done events + exposes Retry/Cancel.
6. fake-claude success mode exits 0 with stdout.
7. fake-claude fail-with mode exits non-zero with stderr.
8. fake-claude stdout-loop survives until SIGTERM.
9. Dogfood library hasn't regressed since Phase 3 (cite_key + filename
   shape preserved).

The runner's behavior is asserted via source-text scan + child_process
smoke against fake-claude. Direct TS-import of the runner is gated behind
a Node-strict-ESM resolver gap (relative imports without `.ts` extensions
don't resolve through `--experimental-strip-types` cleanly); a TS build
shim is fixsprint-04b.

## Verification checklist

- [x] `npm test` clean: 43/43 (34 prior + 9 P4).
- [x] `npm run typecheck` clean.
- [x] `npm run build` clean.
- [x] RunStateCard renders failed/timeout with red/orange + Retry button
      (visible source-text + JSX inspection).
- [x] hypothesis-workspace mounts RunStateCard and tracks last params for
      retry.

## Commit message

```
dashboard: Phase 4 (fix-sprint) — heartbeat + timeout + structured exit + RunStateCard for council fanout

Closes the dogfood Finding #14 root cause: the council fanout died at
3:35 with no UI feedback. The runner gets a watchdog + heartbeat + a
five-state exit classification; the SSE routes carry it through; the
hypothesis workspace renders a structured failure card with Retry and
Cancel.

Runner (src/lib/runs.ts + src/lib/claude-runner.ts):
- New RunExitReason union: ok | timeout | cancelled | failed | spawn-error.
- RunEvent gains heartbeat + timeout variants; exit gains
  reason/success/message.
- RunnerOptions gains timeoutMs (default 8 min) + heartbeatMs (default
  15 s).
- Pre-aborted abortSignal short-circuits before spawn.
- Heartbeat interval + timeout watchdog; SIGTERM with 5-s SIGKILL grace.
- On close, classify exit reason and emit on the exit event itself.
- readRunSummary / readRunDetail surface timeout + cancelled distinctly.

SSE routes (7 routes touched: data/analyze, draft/[slug]/action,
hypothesis/reconcile, images/generate, images/lock, tools/run, execute):
- Capture lastExit in the loop.
- Forward {success, reason, exit_code, message} on the terminal `done`
  SSE payload.
- heartbeat + timeout events auto-forward via the existing
  send(evt.type, evt) loop.

UI:
- New components/primitives/run-state-card.tsx — renders idle / running
  (with spinner + elapsed mm:ss + Cancel) / succeeded / failed (red +
  reason + Retry/Dismiss) / timeout (orange + reason + Retry) /
  cancelled (neutral + Retry). ARIA role=alert for failure states.
- hypothesis-workspace.tsx wires RunStateCard. consumeSse returns the
  done summary; applyDone maps runner reason → workspace state. Last
  council-generate params kept in a ref so Retry can replay them.
- Other workspaces (data, figures, draft) keep their existing inline
  spinners; rollout to RunStateCard is fixsprint-04b.

Tests (tests/runner-failure.test.mjs + tests/fixtures/fake-claude.mjs):
- Source-text validates runner heartbeat/timeout wiring + classification.
- Source-text validates every SSE route forwards lastExit fields.
- Source-text validates RunStateCard handles every state + ARIA.
- Source-text validates hypothesis-workspace consumes done events.
- Tiny Node-stdlib fake-claude harness for future end-to-end runner
  tests; smoke verifies the harness contract.

Verification:
- npm test: 43/43 PASS (34 prior + 9 P4)
- npm run typecheck: clean
- npm run build: clean

Out of scope (Phase 5 ≈ FIXPLAN Phase 4): citation pipeline correctness
— `\cite{<token>}` end-to-end through preview AND export, "Missing from
library" disappears for any saved paper.

Out of scope (fixsprint-04b): mount RunStateCard in figures + draft +
data workspaces; /runs page failed-row Rerun button; 504 distinct from
500 in route response status.
```
