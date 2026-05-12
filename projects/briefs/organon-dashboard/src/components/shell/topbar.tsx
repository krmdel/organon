"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { ClaudePlanUsage, UsageReport } from "@/lib/usage-types";
import { UsageChip } from "@/components/layout/usage-chip";
import {
  getCollapsedGroups,
  getPinned,
  toggleGroupCollapsed,
  togglePinned,
} from "@/lib/state/pinned-projects";
import { TasksPanel } from "@/components/header/tasks-panel";
import { DensityToggle } from "@/components/settings/density-toggle";

export type TopbarProject = {
  slug: string;
  name: string;
  is_root: boolean;
  is_brief: boolean;
};

export type TopbarProps = {
  projects: TopbarProject[];
  current: string;
  onChange: (slug: string) => void;
  onOpenPalette: () => void;
  usage?: UsageReport | null;
  plan?: ClaudePlanUsage | null;
};

// Phase 14d (v1.0.1) — F-1 project switcher search + grouping. Group
// keys are stable so collapse state persists across renames.
const GROUP_PINNED = "pinned";
const GROUP_BRIEFS = "briefs";
const GROUP_PROJECTS = "projects";
const GROUP_SYNTHETIC = "synthetic";

export function Topbar({ projects, current, onChange, onOpenPalette, usage, plan }: TopbarProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [pinned, setPinned] = useState<string[]>([]);
  const [collapsed, setCollapsed] = useState<string[]>([]);
  const currentProject = projects.find((p) => p.slug === current);

  // Hydrate localStorage state on mount so the dropdown reflects the
  // user's prior pin / collapse choices on first paint.
  useEffect(() => {
    setPinned(getPinned());
    setCollapsed(getCollapsedGroups());
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem("organon.dashboard.lastProject", current);
    } catch {
      // ignore quota / private-mode
    }
  }, [current]);

  const handleChange = (slug: string) => {
    onChange(slug);
    setOpen(false);
    setQuery("");
    if (typeof window !== "undefined") {
      const url = new URL(window.location.href);
      url.searchParams.set("project", slug);
      router.replace(url.pathname + "?" + url.searchParams.toString());
    }
  };

  const handlePin = (slug: string) => {
    setPinned(togglePinned(slug));
  };

  const handleCollapse = (groupId: string) => {
    setCollapsed(toggleGroupCollapsed(groupId));
  };

  // Phase 14d — search filters across BRIEFS + PROJECTS + SYNTHETIC +
  // pinned. Case-insensitive substring match on `name`. Pinned section
  // also filters but stays at the top so the user's favourites surface
  // first even when scoped.
  const matches = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return projects;
    return projects.filter((p) => p.name.toLowerCase().includes(needle));
  }, [projects, query]);

  const pinnedSet = useMemo(() => new Set(pinned), [pinned]);
  const pinnedItems = matches.filter((p) => pinnedSet.has(p.slug));
  const briefs = matches.filter((p) => p.is_brief);
  const roots = matches.filter((p) => !p.is_brief && !p.is_root);
  const synthetic = matches.filter((p) => p.is_root);

  return (
    <header className="h-14 border-b border-border-dim flex items-center px-6 gap-4 bg-bg sticky top-0 z-20">
      <div className="relative">
        <button
          onClick={() => setOpen((o) => !o)}
          className="flex items-center gap-2 px-3 py-1.5 border border-border rounded text-sm hover:bg-bg-soft transition"
        >
          <span className="mono text-[11px] uppercase tracking-[0.16em] text-text-muted">
            Project
          </span>
          <span className="text-text">{currentProject?.name ?? current}</span>
          <span className="text-text-muted">▾</span>
        </button>
        {open && (
          <div
            data-project-switcher
            className="absolute top-full left-0 mt-2 min-w-[320px] bg-bg-elev border border-border rounded shadow-xl z-30 max-h-[60vh] overflow-auto"
          >
            <div className="p-2 border-b border-border-dim sticky top-0 bg-bg-elev z-10">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search projects…"
                data-project-search
                autoFocus
                className="w-full bg-bg border border-border-dim rounded px-3 py-1.5 text-sm text-text focus:border-accent outline-none"
              />
            </div>
            {pinnedItems.length > 0 && (
              <ProjectGroup
                groupId={GROUP_PINNED}
                label="Pinned"
                items={pinnedItems}
                current={current}
                pinned={pinnedSet}
                collapsed={collapsed.includes(GROUP_PINNED)}
                onPick={handleChange}
                onPin={handlePin}
                onCollapse={handleCollapse}
              />
            )}
            {synthetic.length > 0 && (
              <ProjectGroup
                groupId={GROUP_SYNTHETIC}
                label="Repo root"
                items={synthetic}
                current={current}
                pinned={pinnedSet}
                collapsed={collapsed.includes(GROUP_SYNTHETIC)}
                onPick={handleChange}
                onPin={handlePin}
                onCollapse={handleCollapse}
              />
            )}
            {briefs.length > 0 && (
              <ProjectGroup
                groupId={GROUP_BRIEFS}
                label="Briefs"
                items={briefs}
                current={current}
                pinned={pinnedSet}
                collapsed={collapsed.includes(GROUP_BRIEFS)}
                onPick={handleChange}
                onPin={handlePin}
                onCollapse={handleCollapse}
              />
            )}
            {roots.length > 0 && (
              <ProjectGroup
                groupId={GROUP_PROJECTS}
                label="Projects"
                items={roots}
                current={current}
                pinned={pinnedSet}
                collapsed={collapsed.includes(GROUP_PROJECTS)}
                onPick={handleChange}
                onPin={handlePin}
                onCollapse={handleCollapse}
              />
            )}
            {pinnedItems.length === 0 &&
              briefs.length === 0 &&
              roots.length === 0 &&
              synthetic.length === 0 && (
                <div className="px-4 py-6 text-sm text-text-muted text-center">
                  No projects match {query ? `"${query}"` : "the filter"}.
                </div>
              )}
          </div>
        )}
      </div>

      <div className="flex-1" />

      <button
        onClick={onOpenPalette}
        className="flex items-center gap-2 px-3 py-1.5 border border-border rounded text-sm text-text-dim hover:text-text hover:bg-bg-soft transition mono"
        title="Open command palette"
      >
        <span>⌘K</span>
        <span className="hidden sm:inline">Search</span>
      </button>

      {/* Phase 44 (v1.5) — F7: tasks-running header panel. Bell icon
          + popover with running + last 20 completed tasks; click-
          through to the originating page. Polls /api/tasks every 5s. */}
      <TasksPanel project={current} />

      {/* Phase 65 (v2.2) — M4: dashboard density toggle. Four discrete
          levels scale --font-scale on :root; Tailwind 4 rem-based
          classes propagate automatically. */}
      <DensityToggle />

      {/* Phase 66 (v2.2) — M5: usage chip with plan-vs-local cascade.
          Drops the misleading $X.XX figure; shows daily + weekly token
          totals (path C) until/unless Claude Code starts persisting
          plan usage to a local cache (path A). */}
      <UsageChip plan={plan ?? null} report={usage ?? null} />
    </header>
  );
}

function ProjectGroup({
  groupId,
  label,
  items,
  current,
  pinned,
  collapsed,
  onPick,
  onPin,
  onCollapse,
}: {
  groupId: string;
  label: string;
  items: TopbarProject[];
  current: string;
  pinned: Set<string>;
  collapsed: boolean;
  onPick: (slug: string) => void;
  onPin: (slug: string) => void;
  onCollapse: (groupId: string) => void;
}) {
  return (
    <div className="py-2" data-project-group={groupId} data-collapsed={collapsed ? "true" : "false"}>
      <button
        onClick={() => onCollapse(groupId)}
        data-action="toggle-group"
        className="w-full text-left px-4 py-1 mono text-[10px] uppercase tracking-[0.16em] text-text-muted hover:text-text flex items-center justify-between"
      >
        <span>{label} ({items.length})</span>
        <span aria-hidden>{collapsed ? "▶" : "▼"}</span>
      </button>
      {!collapsed &&
        items.map((p) => {
          const isPinned = pinned.has(p.slug);
          return (
            <div
              key={p.slug}
              data-project-row={p.slug}
              className={`group w-full flex items-center px-4 py-2 text-sm hover:bg-bg-soft transition ${
                p.slug === current ? "text-accent" : "text-text"
              }`}
            >
              <button
                onClick={() => onPick(p.slug)}
                className="flex-1 text-left truncate"
              >
                {p.name}
                {p.slug === current && (
                  <span className="ml-2 text-text-muted text-[10px] mono uppercase">·current</span>
                )}
              </button>
              <button
                onClick={() => onPin(p.slug)}
                data-action="toggle-pin"
                data-pinned={isPinned ? "true" : "false"}
                title={isPinned ? "Unpin" : "Pin to top"}
                className={`ml-2 w-6 h-6 flex items-center justify-center rounded text-[12px] transition ${
                  isPinned ? "text-accent" : "text-text-muted opacity-0 group-hover:opacity-100"
                }`}
              >
                {isPinned ? "★" : "☆"}
              </button>
            </div>
          );
        })}
    </div>
  );
}
