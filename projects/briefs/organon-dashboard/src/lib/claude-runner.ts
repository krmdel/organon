import { spawn, type ChildProcessByStdio } from "node:child_process";
import type { Readable } from "node:stream";

// Phase 12c (v1.0.1) — D-2: stdin is closed at spawn ("ignore"), so the
// child process type narrows to "no stdin, stdout + stderr pipes". This
// is the precise spawn-overload return type for `stdio: ["ignore","pipe","pipe"]`.
type RunnerChild = ChildProcessByStdio<null, Readable, Readable>;
import { appendRunEvent, ensureRunsDir, newRunPath, type RunEvent, type RunExitReason } from "./runs";
import { claudeBin } from "./env";
import { organonRoot } from "./paths";

export type RunnerEvent = RunEvent;

/**
 * Phase 12c (v1.0.1) — D-2: filter runner-internal stderr noise out of
 * the live SSE stream. Lines starting with `[runner-internal]` (or any
 * subprocess that adopts the same convention) are stripped from the
 * chunk before it's emitted to the SSE consumer. The full unfiltered
 * chunk is still persisted to the run log so audit / debug paths stay
 * complete. Exported so the regression test can pin the filter
 * contract on plain strings without touching child_process.
 */
export function filterRunnerInternal(chunk: string): string {
  if (!chunk.includes("[runner-internal]")) return chunk;
  return chunk
    .split("\n")
    .filter((line) => !line.includes("[runner-internal]"))
    .join("\n");
}

/**
 * Phase 4 (fix-sprint) — runtime caps + observability for the long-running
 * `claude -p` subprocess. Closes dogfood Finding #14: "claude -p SIGTERM
 * with no UI feedback".
 */
export const DEFAULT_TIMEOUT_MS = 8 * 60 * 1000;
export const DEFAULT_HEARTBEAT_MS = 15 * 1000;
const SIGKILL_GRACE_MS = 5 * 1000;

export type RunnerOptions = {
  projectPath: string;
  projectSlug: string;
  prompt: string;
  skill?: string;
  abortSignal?: AbortSignal;
  /** Override the binary — handy for tests. */
  command?: string;
  /** Override argv (defaults to ["-p", prompt]) — for the test harness. */
  args?: string[];
  /** Phase 4: hard cap on subprocess wall-clock (default 8 min). */
  timeoutMs?: number;
  /** Phase 4: keepalive cadence (default 15 s). 0 disables. */
  heartbeatMs?: number;
  /**
   * Phase 31 (v1.3) — D-6++ fast-classifier model override knob. When
   * set + `args` is NOT overridden, the runner appends `["--model", model]`
   * to the default `["-p", prompt]` argv. When `args` IS overridden, the
   * override stays untouched (test escape hatch). Pass an alias
   * (`"haiku"`, `"sonnet"`, `"opus"`) or full model name; if the CLI
   * doesn't recognise it, the subprocess exits non-zero and callers
   * fall back to their existing keyword path.
   */
  model?: string;
};

/**
 * Runs `claude -p <prompt>` (or override via env) and yields events as they
 * happen.  Run log is written to the project's `.organon/runs/` directory.
 *
 * The subprocess cwd is the **Organon repo root**, NOT the project path. This
 * is because `.mcp.json` lives at the root and uses relative paths
 * (`scripts/with-env.sh`, `mcp-servers/paper-search/dist/index.js`); spawning
 * in a project subdirectory makes those resolve to nonexistent paths and the
 * MCP servers silently fail to start. The active project is communicated to
 * the skill via the prompt (the dashboard's runViaSkill caller embeds
 * `active_project_slug=...`), and project-scoped output paths use
 * `projects/{slug}/...` relative to the root.
 */
export async function* runClaude(opts: RunnerOptions): AsyncGenerator<RunnerEvent> {
  ensureRunsDir(opts.projectPath);
  const { file } = newRunPath(opts.projectPath);

  const startEvt: RunnerEvent = {
    type: "start",
    ts: new Date().toISOString(),
    prompt: opts.prompt,
    skill: opts.skill,
    project: opts.projectSlug,
  };
  appendRunEvent(file, startEvt);
  yield startEvt;

  // Phase 4: pre-aborted signal — short-circuit before spawn so we don't
  // start a subprocess we're going to immediately kill.
  if (opts.abortSignal?.aborted) {
    const exitEvt: RunnerEvent = {
      type: "exit",
      ts: new Date().toISOString(),
      code: null,
      reason: "cancelled",
      success: false,
      message: "Run cancelled before subprocess spawn.",
    };
    appendRunEvent(file, exitEvt);
    yield exitEvt;
    return;
  }

  const cmd = opts.command ?? claudeBin();
  // Phase 31 (v1.3) — D-6++ default-args path appends --model when set.
  // The override path leaves opts.args untouched so existing tests +
  // ad-hoc invocations keep working.
  const defaultArgs = ["-p", opts.prompt];
  if (opts.model && opts.model.length > 0) {
    defaultArgs.push("--model", opts.model);
  }
  const args = opts.args ?? defaultArgs;
  const timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const heartbeatMs = opts.heartbeatMs ?? DEFAULT_HEARTBEAT_MS;

  let child: RunnerChild;
  try {
    // Phase 12c (v1.0.1) — D-2: explicitly close stdin so a skill that
    // accidentally calls `input()` (or any blocking-read primitive) hangs
    // the subprocess instead of dragging the whole SSE response with it.
    // stdout + stderr stay piped so the runner can stream them.
    child = spawn(cmd, args, {
      cwd: organonRoot(),
      env: process.env,
      shell: false,
      stdio: ["ignore", "pipe", "pipe"],
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    const evt: RunnerEvent = {
      type: "stderr",
      ts: new Date().toISOString(),
      chunk: `Failed to spawn '${cmd}': ${msg}\n`,
    };
    appendRunEvent(file, evt);
    yield evt;
    const exitEvt: RunnerEvent = {
      type: "exit",
      ts: new Date().toISOString(),
      code: -1,
      reason: "spawn-error",
      success: false,
      message: `Failed to spawn '${cmd}': ${msg}`,
    };
    appendRunEvent(file, exitEvt);
    yield exitEvt;
    return;
  }

  // Phase 4: state owned by this run — used by the watchdog timer + abort
  // handler to classify the eventual exit reason correctly.
  let cancelledByUser = false;
  let timedOut = false;
  let sigkillTimer: NodeJS.Timeout | null = null;

  const killWithSigterm = () => {
    try { child.kill("SIGTERM"); } catch { /* already gone */ }
    if (sigkillTimer) clearTimeout(sigkillTimer);
    sigkillTimer = setTimeout(() => {
      try { child.kill("SIGKILL"); } catch { /* already gone */ }
    }, SIGKILL_GRACE_MS);
  };

  if (opts.abortSignal) {
    opts.abortSignal.addEventListener("abort", () => {
      cancelledByUser = true;
      killWithSigterm();
    });
  }

  const queue: RunnerEvent[] = [];
  let resolveNext: ((evt: RunnerEvent | null) => void) | null = null;

  const push = (evt: RunnerEvent) => {
    appendRunEvent(file, evt);
    if (resolveNext) {
      const r = resolveNext;
      resolveNext = null;
      r(evt);
    } else {
      queue.push(evt);
    }
  };

  // Phase 4: heartbeat keeps proxies + browser EventSource alive on long
  // claude -p runs. UI shows them as "still working" pings.
  let heartbeatTimer: NodeJS.Timeout | null = null;
  if (heartbeatMs > 0) {
    heartbeatTimer = setInterval(() => {
      push({ type: "heartbeat", ts: new Date().toISOString() });
    }, heartbeatMs);
  }

  // Phase 4: timeout watchdog. Fires `timeout` event then SIGTERM-with-grace.
  let timeoutTimer: NodeJS.Timeout | null = null;
  if (timeoutMs > 0) {
    timeoutTimer = setTimeout(() => {
      timedOut = true;
      push({ type: "timeout", ts: new Date().toISOString(), ms: timeoutMs });
      killWithSigterm();
    }, timeoutMs);
  }

  child.stdout.setEncoding("utf8");
  child.stderr.setEncoding("utf8");

  child.stdout.on("data", (chunk: string) => {
    push({ type: "stdout", ts: new Date().toISOString(), chunk });
  });
  child.stderr.on("data", (chunk: string) => {
    // Phase 12c (v1.0.1) — D-2: filter runner-internal noise out of the
    // SSE stream. The subprocess (and the dashboard's spawned skills)
    // tag their own diagnostics with `[runner-internal]`; surfacing
    // those in the prose window makes the researcher think the skill
    // failed when it's actually housekeeping. The full chunk still
    // lands in the .organon/runs/<id>.jsonl file via appendRunEvent
    // before filtering — we only suppress the live SSE event.
    const filtered = filterRunnerInternal(chunk);
    if (chunk !== filtered) {
      // Persist the unfiltered chunk so audit logs stay complete.
      appendRunEvent(file, {
        type: "stderr",
        ts: new Date().toISOString(),
        chunk,
      });
      if (filtered.length > 0) {
        // Use push() (not appendRunEvent again) so the SSE consumer
        // still sees the user-visible portion. push() also writes to
        // disk, which would double-log the chunk — so we strip the
        // appendRunEvent inside push() by branching here.
        const evt: RunnerEvent = {
          type: "stderr",
          ts: new Date().toISOString(),
          chunk: filtered,
        };
        if (resolveNext) {
          const r = resolveNext;
          resolveNext = null;
          r(evt);
        } else {
          queue.push(evt);
        }
      }
    } else {
      push({ type: "stderr", ts: new Date().toISOString(), chunk });
    }
  });

  let done = false;
  child.on("close", (code) => {
    if (heartbeatTimer) clearInterval(heartbeatTimer);
    if (timeoutTimer) clearTimeout(timeoutTimer);
    if (sigkillTimer) clearTimeout(sigkillTimer);

    // Phase 4: classify the exit. Order matters — timeout takes precedence
    // over cancelled because the watchdog SIGTERM also flips abortSignal
    // when callers wire them together.
    let reason: RunExitReason;
    let message: string | undefined;
    if (timedOut) {
      reason = "timeout";
      message = `Run exceeded ${Math.round(timeoutMs / 1000)}s wall-clock limit.`;
    } else if (cancelledByUser) {
      reason = "cancelled";
      message = "Run cancelled by user.";
    } else if (code === 0) {
      reason = "ok";
    } else {
      reason = "failed";
      message = code === null
        ? "Subprocess terminated by signal with no exit code."
        : `Subprocess exited with code ${code}.`;
    }

    push({
      type: "exit",
      ts: new Date().toISOString(),
      code: code ?? null,
      reason,
      success: reason === "ok",
      message,
    });
    done = true;
    if (resolveNext) {
      const r = resolveNext;
      resolveNext = null;
      r(null);
    }
  });

  while (!done || queue.length > 0) {
    if (queue.length > 0) {
      yield queue.shift()!;
      continue;
    }
    const next = await new Promise<RunnerEvent | null>((resolve) => {
      resolveNext = resolve;
    });
    if (next) yield next;
    if (next?.type === "exit") break;
  }
}
