import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import os from "node:os";
import path from "node:path";

/**
 * Reads the same session JSONL files that `claude /usage` aggregates and
 * computes real token + cost stats for a given project working directory.
 *
 * Source: ~/.claude/projects/<encoded-cwd>/<session-id>.jsonl
 *
 * Path encoding: every "/" in the absolute working-directory path becomes a
 * "-". So `/Users/x/Projects/scientific-os` → `-Users-x-Projects-scientific-os`.
 */

type Pricing = {
  in: number;
  out: number;
  cacheRead: number;
  cacheCreate: number;
};

const PRICING: Record<string, Pricing> = {
  opus: { in: 15, out: 75, cacheRead: 1.5, cacheCreate: 18.75 },
  sonnet: { in: 3, out: 15, cacheRead: 0.3, cacheCreate: 3.75 },
  haiku: { in: 1, out: 5, cacheRead: 0.1, cacheCreate: 1.25 },
};

type ModelKey = keyof typeof PRICING;

type AssistantUsage = {
  ts: number;
  model: string;
  inputTokens: number;
  outputTokens: number;
  cacheRead: number;
  cacheCreate: number;
  cost: number;
  sessionId: string;
};

export type UsageWindow = {
  tokensIn: number;
  tokensOut: number;
  cacheRead: number;
  cacheCreate: number;
  totalTokens: number;
  cost: number;
  messages: number;
  sessions: number;
  earliestTs: number | null;
};

export type UsageReport = {
  fiveHour: UsageWindow;
  daily: UsageWindow;
  weekly: UsageWindow;
  weeklySonnet: UsageWindow;
  weeklyOpus: UsageWindow;
  hourly24: { hour: string; tokens: number }[];
  weeklyDays: { date: string; tokens: number; cost: number }[];
  forecast: { avgPerDay: number; projectedWeek: number };
  modelBreakdown: { model: string; tokens: number; cost: number }[];
  totalSessions: number;
  computedAt: string;
  fiveHourResetAt: string | null;
};

export function encodeProjectPath(absPath: string): string {
  return absPath.replace(/\//g, "-");
}

function projectsDirFor(absPath: string): string {
  return path.join(os.homedir(), ".claude", "projects", encodeProjectPath(absPath));
}

function modelKey(model: string): ModelKey | null {
  const m = (model || "").toLowerCase();
  if (m.includes("opus")) return "opus";
  if (m.includes("sonnet")) return "sonnet";
  if (m.includes("haiku")) return "haiku";
  return null;
}

function costFor(
  usage: {
    input_tokens?: number;
    output_tokens?: number;
    cache_read_input_tokens?: number;
    cache_creation_input_tokens?: number;
  },
  model: string,
): number {
  const key = modelKey(model);
  if (!key) return 0;
  const p = PRICING[key];
  return (
    ((usage.input_tokens ?? 0) * p.in +
      (usage.output_tokens ?? 0) * p.out +
      (usage.cache_read_input_tokens ?? 0) * p.cacheRead +
      (usage.cache_creation_input_tokens ?? 0) * p.cacheCreate) /
    1_000_000
  );
}

function collectUsage(absPath: string, sinceMs: number): AssistantUsage[] {
  const dir = projectsDirFor(absPath);
  if (!existsSync(dir)) return [];

  const files = readdirSync(dir).filter((f) => f.endsWith(".jsonl"));
  const events: AssistantUsage[] = [];

  for (const f of files) {
    const full = path.join(dir, f);
    let stat;
    try {
      stat = statSync(full);
    } catch {
      continue;
    }
    if (stat.mtimeMs < sinceMs - 60_000) continue;

    let raw: string;
    try {
      raw = readFileSync(full, "utf8");
    } catch {
      continue;
    }
    for (const line of raw.split("\n")) {
      if (!line || line.length < 50) continue;
      if (!line.includes('"type":"assistant"')) continue;
      let obj;
      try {
        obj = JSON.parse(line);
      } catch {
        continue;
      }
      const ts = obj.timestamp ? Date.parse(obj.timestamp) : NaN;
      if (!Number.isFinite(ts)) continue;
      if (ts < sinceMs) continue;
      const message = obj.message;
      if (!message || message.role !== "assistant") continue;
      const usage = message.usage;
      if (!usage) continue;
      const model = String(message.model ?? "");
      events.push({
        ts,
        model,
        inputTokens: usage.input_tokens ?? 0,
        outputTokens: usage.output_tokens ?? 0,
        cacheRead: usage.cache_read_input_tokens ?? 0,
        cacheCreate: usage.cache_creation_input_tokens ?? 0,
        cost: costFor(usage, model),
        sessionId: String(obj.sessionId ?? f.replace(/\.jsonl$/, "")),
      });
    }
  }
  return events;
}

function aggregateWindow(
  events: AssistantUsage[],
  sinceMs: number,
  filter?: (e: AssistantUsage) => boolean,
): UsageWindow {
  const filtered = events.filter((e) => e.ts >= sinceMs && (!filter || filter(e)));
  const sessions = new Set<string>();
  let tokensIn = 0,
    tokensOut = 0,
    cacheRead = 0,
    cacheCreate = 0,
    cost = 0;
  for (const e of filtered) {
    tokensIn += e.inputTokens;
    tokensOut += e.outputTokens;
    cacheRead += e.cacheRead;
    cacheCreate += e.cacheCreate;
    cost += e.cost;
    sessions.add(e.sessionId);
  }
  const earliestTs = filtered.length > 0 ? Math.min(...filtered.map((e) => e.ts)) : null;
  return {
    tokensIn,
    tokensOut,
    cacheRead,
    cacheCreate,
    totalTokens: tokensIn + tokensOut + cacheRead + cacheCreate,
    cost,
    messages: filtered.length,
    sessions: sessions.size,
    earliestTs,
  };
}

export function computeUsageReport(absPath: string): UsageReport {
  const now = Date.now();
  const weekAgo = now - 7 * 24 * 3600 * 1000;
  const events = collectUsage(absPath, weekAgo);

  const fiveHourAgo = now - 5 * 3600 * 1000;
  const dayAgo = now - 24 * 3600 * 1000;

  const fiveHour = aggregateWindow(events, fiveHourAgo);
  const daily = aggregateWindow(events, dayAgo);
  const weekly = aggregateWindow(events, weekAgo);
  const weeklySonnet = aggregateWindow(events, weekAgo, (e) => modelKey(e.model) === "sonnet");
  const weeklyOpus = aggregateWindow(events, weekAgo, (e) => modelKey(e.model) === "opus");

  const fiveHourResetAt = fiveHour.earliestTs
    ? new Date(fiveHour.earliestTs + 5 * 3600 * 1000).toISOString()
    : null;

  const hourly24: { hour: string; tokens: number }[] = [];
  for (let i = 23; i >= 0; i--) {
    const start = now - (i + 1) * 3600 * 1000;
    const end = now - i * 3600 * 1000;
    const tokens = events
      .filter((e) => e.ts >= start && e.ts < end)
      .reduce((s, e) => s + e.inputTokens + e.outputTokens + e.cacheRead + e.cacheCreate, 0);
    const d = new Date(end);
    hourly24.push({
      hour: `${d.getHours().toString().padStart(2, "0")}`,
      tokens,
    });
  }

  const weeklyDays: { date: string; tokens: number; cost: number }[] = [];
  for (let i = 6; i >= 0; i--) {
    const day = new Date(now - i * 24 * 3600 * 1000);
    day.setHours(0, 0, 0, 0);
    const start = day.getTime();
    const end = start + 24 * 3600 * 1000;
    const dayEvents = events.filter((e) => e.ts >= start && e.ts < end);
    weeklyDays.push({
      date: day.toISOString().slice(0, 10),
      tokens: dayEvents.reduce(
        (s, e) => s + e.inputTokens + e.outputTokens + e.cacheRead + e.cacheCreate,
        0,
      ),
      cost: dayEvents.reduce((s, e) => s + e.cost, 0),
    });
  }

  const avgPerDay = weekly.cost / 7;

  const modelMap = new Map<string, { tokens: number; cost: number }>();
  for (const e of events) {
    if (e.ts < weekAgo) continue;
    const k = modelKey(e.model) ?? e.model.replace(/^claude-/, "").split("-").slice(0, 2).join("-");
    const cur = modelMap.get(k) ?? { tokens: 0, cost: 0 };
    cur.tokens += e.inputTokens + e.outputTokens + e.cacheRead + e.cacheCreate;
    cur.cost += e.cost;
    modelMap.set(k, cur);
  }
  const modelBreakdown = Array.from(modelMap.entries())
    .map(([model, v]) => ({ model, ...v }))
    .sort((a, b) => b.tokens - a.tokens);

  const allSessions = new Set(events.map((e) => e.sessionId));

  return {
    fiveHour,
    daily,
    weekly,
    weeklySonnet,
    weeklyOpus,
    hourly24,
    weeklyDays,
    forecast: { avgPerDay, projectedWeek: avgPerDay * 7 },
    modelBreakdown,
    totalSessions: allSessions.size,
    computedAt: new Date().toISOString(),
    fiveHourResetAt,
  };
}

/**
 * Phase 66 (v2.2) — M5: read Claude Code's plan-usage cache (path A).
 *
 * Returns the user's daily + weekly plan-usage state if Claude Code
 * persists it locally (which it currently does NOT in the codebase
 * shipped at the time of v2.2 — researcher confirmed `~/.claude/` has
 * no usage/plan/limit JSON). The shape lands first so future Claude
 * Code releases that surface plan state via a JSON file Just Work
 * without a chip refactor.
 *
 * Returns `null` (never throws) when the cache file is absent or
 * malformed. The chip falls back to the path-C local-token rate via
 * the existing computeUsageReport pipeline.
 */
export type ClaudePlanUsage = {
  daily: { used: number; limit: number; resetAt: string };
  weekly: { used: number; limit: number; resetAt: string };
};

const PLAN_CACHE_CANDIDATES = [
  ".claude/usage.json",
  ".claude/plan-usage.json",
  ".config/claude-code/usage.json",
];

function readJsonIfExists(p: string): unknown | null {
  if (!existsSync(p)) return null;
  try {
    return JSON.parse(readFileSync(p, "utf8"));
  } catch {
    return null;
  }
}

function isPlanShape(obj: unknown): obj is ClaudePlanUsage {
  if (!obj || typeof obj !== "object") return false;
  const o = obj as Record<string, unknown>;
  const ok = (w: unknown) => {
    if (!w || typeof w !== "object") return false;
    const x = w as Record<string, unknown>;
    return (
      typeof x.used === "number" &&
      typeof x.limit === "number" &&
      typeof x.resetAt === "string"
    );
  };
  return ok(o.daily) && ok(o.weekly);
}

export function getClaudePlanUsage(): ClaudePlanUsage | null {
  for (const rel of PLAN_CACHE_CANDIDATES) {
    const candidate = path.join(os.homedir(), rel);
    const obj = readJsonIfExists(candidate);
    if (isPlanShape(obj)) return obj;
  }
  return null;
}

export function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

export function formatCost(n: number): string {
  if (n < 0.01) return "$0.00";
  return `$${n.toFixed(2)}`;
}
