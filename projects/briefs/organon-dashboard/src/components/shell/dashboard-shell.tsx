"use client";

import { useCallback, useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useHotkeys } from "react-hotkeys-hook";
import { Sidebar } from "./sidebar";
import { Topbar, type TopbarProject } from "./topbar";
import { CommandPalette } from "./command-palette";
import type { ClaudePlanUsage, UsageReport } from "@/lib/usage-types";

type Skill = { name: string; category: string; description: string; slug: string };
type SkillGroup = { category: string; label: string; skills: Skill[] };

export type DashboardShellProps = {
  initialProjects: TopbarProject[];
  initialProject: string;
  initialSkillGroups: SkillGroup[];
  children: React.ReactNode;
};

/**
 * Shared client shell: sidebar + topbar + Cmd+K palette.
 * Wraps every workspace page so navigation, project switching, and the palette
 * stay consistent.
 */
export function DashboardShell({
  initialProjects,
  initialProject,
  initialSkillGroups,
  children,
}: DashboardShellProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const urlProject = searchParams.get("project");
  const [project, setProject] = useState(urlProject ?? initialProject);
  const [skillGroups, setSkillGroups] = useState<SkillGroup[]>(initialSkillGroups);
  const [usage, setUsage] = useState<UsageReport | null>(null);
  const [plan, setPlan] = useState<ClaudePlanUsage | null>(null);
  const [paletteOpen, setPaletteOpen] = useState(false);

  // Cmd+K opens palette
  useHotkeys(
    "mod+k",
    (e) => {
      e.preventDefault();
      setPaletteOpen((o) => !o);
    },
    { enableOnFormTags: true },
  );

  // Sync URL → state
  useEffect(() => {
    if (urlProject && urlProject !== project) setProject(urlProject);
  }, [urlProject, project]);

  // Refresh skill groups when project changes
  const refreshSkills = useCallback(async (slug: string) => {
    try {
      const res = await fetch(`/api/skills?project=${encodeURIComponent(slug)}`);
      const data = await res.json();
      if (data.groups) setSkillGroups(data.groups);
    } catch {
      // keep last good
    }
  }, []);

  const refreshUsage = useCallback(async (slug: string) => {
    try {
      const res = await fetch(`/api/usage?project=${encodeURIComponent(slug)}`);
      const data = await res.json();
      if (data.report) setUsage(data.report);
      // Phase 66 (v2.2) — M5: capture the plan field (may be null when
      // no local plan-usage cache exists). The chip handles both states.
      setPlan(data.plan ?? null);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    refreshUsage(project);
    if (project !== initialProject) refreshSkills(project);
  }, [project, initialProject, refreshSkills, refreshUsage]);

  // Auto-refresh usage every 60s
  useEffect(() => {
    const id = setInterval(() => refreshUsage(project), 60_000);
    return () => clearInterval(id);
  }, [project, refreshUsage]);

  const handleProjectChange = (slug: string) => {
    setProject(slug);
    // Preserve the current pathname; just update ?project=
    const params = new URLSearchParams(Array.from(searchParams.entries()));
    params.set("project", slug);
    router.replace(`${pathname}?${params.toString()}`);
  };

  return (
    <div className="min-h-screen flex">
      <Sidebar activePath={pathname} currentProject={project} />
      <div className="flex-1 flex flex-col min-w-0">
        <Topbar
          projects={initialProjects}
          current={project}
          onChange={handleProjectChange}
          onOpenPalette={() => setPaletteOpen(true)}
          usage={usage}
          plan={plan}
        />
        <main className="flex-1 min-h-0">{children}</main>
      </div>
      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        projects={initialProjects}
        skillGroups={skillGroups}
        currentProject={project}
        onProjectChange={handleProjectChange}
      />
    </div>
  );
}
