"use client";

// Phase 14d (v1.0.1) — F-1 project switcher pinned-favourites.
//
// Workspace-scoped (NOT per-tab) localStorage helper that mirrors the
// shape of recent-searches.ts. SSR-safe: every accessor guards on
// `typeof window` because Next 16 RSC can call these during prerender.
// Quota / private-mode failures degrade to no-op so a localStorage
// outage never takes the topbar down.

const STORAGE_KEY = "organon:topbar:pinned-projects";

function safeRead(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((s): s is string => typeof s === "string");
  } catch {
    return [];
  }
}

function safeWrite(slugs: string[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(slugs));
  } catch {
    /* quota / private-mode — degrade silently */
  }
}

export function getPinned(): string[] {
  return safeRead();
}

export function isPinned(slug: string): boolean {
  return safeRead().includes(slug);
}

export function togglePinned(slug: string): string[] {
  const cur = safeRead();
  const next = cur.includes(slug) ? cur.filter((s) => s !== slug) : [...cur, slug];
  safeWrite(next);
  return next;
}

// Phase 14d — group-collapse state. Same SSR-safe pattern; persists
// across tabs so a researcher who hides BRIEFS keeps it hidden on the
// next dashboard load.
const COLLAPSED_KEY = "organon:topbar:collapsed-groups";

export function getCollapsedGroups(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(COLLAPSED_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((s): s is string => typeof s === "string");
  } catch {
    return [];
  }
}

export function toggleGroupCollapsed(groupId: string): string[] {
  const cur = getCollapsedGroups();
  const next = cur.includes(groupId) ? cur.filter((g) => g !== groupId) : [...cur, groupId];
  if (typeof window !== "undefined") {
    try {
      window.localStorage.setItem(COLLAPSED_KEY, JSON.stringify(next));
    } catch {
      /* ignore */
    }
  }
  return next;
}
