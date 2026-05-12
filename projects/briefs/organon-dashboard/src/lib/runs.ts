import { appendFileSync, existsSync, mkdirSync, readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { organonRoot } from "./paths";

/**
 * Phase 4 (fix-sprint) — terminal-state classification surfaced to UI.
 * "ok" exits cleanly with code 0. "timeout" was killed by our internal
 * watchdog. "cancelled" was killed by an explicit user/abortSignal.
 * "failed" is any other non-zero exit. "spawn-error" is when the
 * subprocess never started (binary missing, permissions, etc.).
 */
export type RunExitReason =
  | "ok"
  | "timeout"
  | "cancelled"
  | "failed"
  | "spawn-error";

export type RunEvent =
  | { type: "start"; ts: string; prompt: string; skill?: string; project: string }
  | { type: "stdout"; ts: string; chunk: string }
  | { type: "stderr"; ts: string; chunk: string }
  | { type: "heartbeat"; ts: string }
  | { type: "timeout"; ts: string; ms: number }
  | {
      type: "exit";
      ts: string;
      code: number | null;
      /** Phase 4: classification — undefined on legacy run logs. */
      reason?: RunExitReason;
      /** Phase 4: human-readable reason — only set when reason !== "ok". */
      message?: string;
      success?: boolean;
    };

export type RunSummary = {
  id: string;
  ts: string;
  project: string;
  skill?: string;
  prompt: string;
  status: "running" | "ok" | "error" | "timeout" | "cancelled";
  exitCode: number | null;
  /** Phase 4: terminal classification when known. */
  reason?: RunExitReason;
  durationMs: number | null;
  excerpt: string;
};

/**
 * Per PHASE_1_TASKS.md D2:
 * - Per-project: `<projectPath>/.organon/runs/<id>.jsonl`
 * - Synthetic root: `<organon-root>/.organon-dashboard/runs/<id>.jsonl`
 */
export function runsDir(projectPath: string): string {
  const isRoot = path.resolve(projectPath) === path.resolve(organonRoot());
  if (isRoot) return path.join(projectPath, ".organon-dashboard", "runs");
  return path.join(projectPath, ".organon", "runs");
}

export function ensureRunsDir(projectPath: string): string {
  const dir = runsDir(projectPath);
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  return dir;
}

export function newRunPath(projectPath: string): { id: string; file: string } {
  const dir = ensureRunsDir(projectPath);
  const id = new Date().toISOString().replace(/[:.]/g, "-");
  return { id, file: path.join(dir, `${id}.jsonl`) };
}

export function appendRunEvent(file: string, event: RunEvent) {
  appendFileSync(file, JSON.stringify(event) + "\n", "utf8");
}

export function listRuns(projectPath: string, limit = 20): RunSummary[] {
  const dir = runsDir(projectPath);
  if (!existsSync(dir)) return [];
  const files = readdirSync(dir)
    .filter((f) => f.endsWith(".jsonl"))
    .sort()
    .reverse()
    .slice(0, limit);

  return files.map((f) => readRunSummary(path.join(dir, f), f));
}

function readRunSummary(file: string, basename: string): RunSummary {
  const id = basename.replace(/\.jsonl$/, "");
  let raw = "";
  try {
    raw = readFileSync(file, "utf8");
  } catch {
    /* ignore */
  }

  const events: RunEvent[] = raw
    .split("\n")
    .filter(Boolean)
    .map((line) => {
      try {
        return JSON.parse(line) as RunEvent;
      } catch {
        return null;
      }
    })
    .filter((e): e is RunEvent => e !== null);

  const start = events.find((e) => e.type === "start") as
    | Extract<RunEvent, { type: "start" }>
    | undefined;
  const exit = events.find((e) => e.type === "exit") as
    | Extract<RunEvent, { type: "exit" }>
    | undefined;
  const stdoutChunks = events
    .filter((e): e is Extract<RunEvent, { type: "stdout" }> => e.type === "stdout")
    .map((e) => e.chunk)
    .join("");

  const ts = start?.ts ?? new Date(0).toISOString();
  let durationMs: number | null = null;
  if (start && exit) {
    durationMs = new Date(exit.ts).getTime() - new Date(start.ts).getTime();
  }

  // Phase 4: prefer the runner's own classification when available, fall
  // back to (code === 0 ? ok : error) for legacy run logs.
  const timeout = events.find((e) => e.type === "timeout");
  let status: RunSummary["status"] = "running";
  let reason: RunExitReason | undefined;
  if (exit) {
    reason = exit.reason ?? (exit.code === 0 ? "ok" : timeout ? "timeout" : "failed");
    switch (reason) {
      case "ok": status = "ok"; break;
      case "timeout": status = "timeout"; break;
      case "cancelled": status = "cancelled"; break;
      default: status = "error"; break;
    }
  }

  const excerpt = stdoutChunks.slice(0, 240).replace(/\s+/g, " ").trim();

  return {
    id,
    ts,
    project: start?.project ?? "",
    skill: start?.skill,
    prompt: start?.prompt ?? "",
    status,
    reason,
    exitCode: exit?.code ?? null,
    durationMs,
    excerpt,
  };
}

export type RunDetail = {
  id: string;
  ts: string;
  project: string;
  skill?: string;
  prompt: string;
  status: RunSummary["status"];
  /** Phase 4: terminal classification when known. */
  reason?: RunExitReason;
  exitCode: number | null;
  durationMs: number | null;
  stdout: string;
  stderr: string;
  events: RunEvent[];
  linkedArtifacts: { type: string; id?: string; raw: string }[];
};

export function readRunDetail(
  projectPath: string,
  runId: string,
): RunDetail | null {
  const file = path.join(runsDir(projectPath), `${runId}.jsonl`);
  if (!existsSync(file)) return null;
  let raw = "";
  try { raw = readFileSync(file, "utf8"); } catch { return null; }
  const events: RunEvent[] = raw
    .split("\n")
    .filter(Boolean)
    .map((l) => { try { return JSON.parse(l) as RunEvent; } catch { return null; } })
    .filter((e): e is RunEvent => e !== null);

  const start = events.find((e) => e.type === "start") as
    | Extract<RunEvent, { type: "start" }>
    | undefined;
  const exit = events.find((e) => e.type === "exit") as
    | Extract<RunEvent, { type: "exit" }>
    | undefined;
  const stdout = events
    .filter((e): e is Extract<RunEvent, { type: "stdout" }> => e.type === "stdout")
    .map((e) => e.chunk).join("");
  const stderr = events
    .filter((e): e is Extract<RunEvent, { type: "stderr" }> => e.type === "stderr")
    .map((e) => e.chunk).join("");

  let durationMs: number | null = null;
  if (start && exit) {
    durationMs = new Date(exit.ts).getTime() - new Date(start.ts).getTime();
  }
  // Phase 4: same classification logic as readRunSummary.
  const detailTimeout = events.find((e) => e.type === "timeout");
  let status: RunSummary["status"] = "running";
  let detailReason: RunExitReason | undefined;
  if (exit) {
    detailReason = exit.reason ?? (exit.code === 0 ? "ok" : detailTimeout ? "timeout" : "failed");
    switch (detailReason) {
      case "ok": status = "ok"; break;
      case "timeout": status = "timeout"; break;
      case "cancelled": status = "cancelled"; break;
      default: status = "error"; break;
    }
  }

  // Parse linked _artifact lines from stdout for the drill-down panel.
  const linkedArtifacts: RunDetail["linkedArtifacts"] = [];
  for (const line of stdout.split("\n")) {
    const t = line.trim();
    if (!t.startsWith('{"_artifact"')) continue;
    try {
      const obj = JSON.parse(t) as { _artifact?: string; id?: string };
      if (obj && typeof obj._artifact === "string") {
        linkedArtifacts.push({ type: obj._artifact, id: obj.id, raw: t.slice(0, 240) });
      }
    } catch { /* skip */ }
  }

  return {
    id: runId,
    ts: start?.ts ?? new Date(0).toISOString(),
    project: start?.project ?? "",
    skill: start?.skill,
    prompt: start?.prompt ?? "",
    status,
    reason: detailReason,
    exitCode: exit?.code ?? null,
    durationMs,
    stdout,
    stderr,
    events,
    linkedArtifacts,
  };
}

export function runActivityByDay(
  projectPath: string,
  days = 7,
): { date: string; count: number }[] {
  const summaries = listRuns(projectPath, 500);
  const counts = new Map<string, number>();
  const today = new Date();
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(today.getDate() - i);
    counts.set(d.toISOString().slice(0, 10), 0);
  }
  for (const r of summaries) {
    const day = r.ts.slice(0, 10);
    if (counts.has(day)) counts.set(day, (counts.get(day) ?? 0) + 1);
  }
  return Array.from(counts.entries()).map(([date, count]) => ({ date, count }));
}
