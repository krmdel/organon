/**
 * Client-safe types + formatters mirroring usage.ts.
 * Client components can't import the server-only `usage.ts` (it pulls in
 * node:fs).
 */
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

/**
 * Phase 66 (v2.2) — M5: client-safe mirror of usage.ts ClaudePlanUsage.
 * Server-side helper lives in usage.ts (uses node:fs); the chip imports
 * the type from this module so no fs / os pulls into the bundle.
 */
export type ClaudePlanUsage = {
  daily: { used: number; limit: number; resetAt: string };
  weekly: { used: number; limit: number; resetAt: string };
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

export function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

export function formatCost(n: number): string {
  if (n < 0.01) return "$0.00";
  return `$${n.toFixed(2)}`;
}

export function formatResetTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const now = new Date();
  const diffMs = d.getTime() - now.getTime();
  if (diffMs < 0) return "any moment";
  const mins = Math.floor(diffMs / 60_000);
  if (mins < 60) return `in ${mins}m`;
  const hours = Math.floor(mins / 60);
  const remMins = mins % 60;
  const local = d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  return `${local} (in ${hours}h${remMins ? ` ${remMins}m` : ""})`;
}
