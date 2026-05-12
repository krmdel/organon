"use client";

// Phase 11 (v1.0.1) — Workspace state persistence.
//
// Project-slug-keyed localStorage helpers. Two surfaces:
//   1. Recent searches ring  — `/lit` recent-search dropdown (max 10 entries).
//   2. WIP claim text        — `/hypothesis` draft persistence across nav.
//
// SSR-safe: every accessor checks `typeof window` first because Next 16 RSC
// can run these in node during prerender. Quota / private-mode failures
// degrade to no-op rather than throwing (a localStorage outage must never
// take the whole workspace down).

const STORAGE_PREFIX = "organon:";
export const RECENT_SEARCHES_MAX = 10;

export type RecentSearch = {
  query: string;
  sources: string[];
  ts: number;
};

function recentSearchesKey(project: string): string {
  return `${STORAGE_PREFIX}lit:recent:${project}`;
}

function wipClaimKey(project: string): string {
  return `${STORAGE_PREFIX}hypothesis:wip:${project}`;
}

function isRecentSearch(x: unknown): x is RecentSearch {
  if (!x || typeof x !== "object") return false;
  const r = x as { query?: unknown; sources?: unknown; ts?: unknown };
  return (
    typeof r.query === "string"
    && Array.isArray(r.sources)
    && r.sources.every((s) => typeof s === "string")
    && typeof r.ts === "number"
  );
}

export function readRecentSearches(project: string): RecentSearch[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(recentSearchesKey(project));
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isRecentSearch);
  } catch {
    return [];
  }
}

export function pushRecentSearch(
  project: string,
  entry: { query: string; sources: string[] },
): RecentSearch[] {
  if (typeof window === "undefined") return [];
  const trimmed = entry.query.trim();
  if (!trimmed) return readRecentSearches(project);
  const cur = readRecentSearches(project);
  const dedupKey = trimmed.toLowerCase();
  const next: RecentSearch[] = [
    { query: trimmed, sources: [...entry.sources], ts: Date.now() },
    ...cur.filter((e) => e.query.trim().toLowerCase() !== dedupKey),
  ].slice(0, RECENT_SEARCHES_MAX);
  try {
    window.localStorage.setItem(recentSearchesKey(project), JSON.stringify(next));
  } catch {
    /* quota / private-mode — degrade silently */
  }
  return next;
}

export function clearRecentSearches(project: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(recentSearchesKey(project));
  } catch {
    /* ignore */
  }
}

export function readWipClaim(project: string): string {
  if (typeof window === "undefined") return "";
  try {
    return window.localStorage.getItem(wipClaimKey(project)) ?? "";
  } catch {
    return "";
  }
}

export function writeWipClaim(project: string, claim: string): void {
  if (typeof window === "undefined") return;
  try {
    if (claim.trim().length === 0) {
      window.localStorage.removeItem(wipClaimKey(project));
    } else {
      window.localStorage.setItem(wipClaimKey(project), claim);
    }
  } catch {
    /* ignore */
  }
}
