import { listProjects } from "./projects";
import { listSkillGroups } from "./skills";

export type ShellInit = {
  projects: { slug: string; name: string; is_root: boolean; is_brief: boolean }[];
  initialProject: string;
  skillGroups: ReturnType<typeof listSkillGroups>;
};

/**
 * Server-side hydration data shared by every page.
 * Resolves the default project per PHASE_1_TASKS.md D7:
 *   URL ?project=… (handled in client) > localStorage (client) > first non-root alpha > __root__
 */
export function initShell(urlProject?: string | null): ShellInit {
  const projects = listProjects();
  const projectsForWire = projects.map((p) => ({
    slug: p.slug,
    name: p.name,
    is_root: p.isRoot,
    is_brief: p.isBrief,
  }));

  let initialSlug = "__root__";
  if (urlProject && projects.some((p) => p.slug === urlProject)) {
    initialSlug = urlProject;
  } else {
    const firstNonRoot = projects.find((p) => !p.isRoot);
    if (firstNonRoot) initialSlug = firstNonRoot.slug;
  }

  const initial = projects.find((p) => p.slug === initialSlug)!;
  const skillGroups = listSkillGroups(initial.path);

  return {
    projects: projectsForWire,
    initialProject: initialSlug,
    skillGroups,
  };
}
