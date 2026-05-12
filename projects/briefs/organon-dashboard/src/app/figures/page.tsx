import { DashboardShell } from "@/components/shell/dashboard-shell";
import { FiguresWorkspace } from "@/components/figures/figures-workspace";
import { initShell } from "@/lib/shell-init";
import { resolveProject } from "@/lib/projects";
import { listFigures } from "@/lib/figures/store";

export const dynamic = "force-dynamic";

type SearchParams = { [key: string]: string | string[] | undefined };

export default async function FiguresPage(props: { searchParams: Promise<SearchParams> }) {
  const sp = await props.searchParams;
  const param = typeof sp.project === "string" ? sp.project : undefined;
  const init = initShell(param);
  const project = resolveProject(init.initialProject);
  const figures = project ? listFigures(project.path) : [];
  const initialFigId = typeof sp.fig === "string" ? sp.fig : undefined;

  return (
    <DashboardShell
      initialProjects={init.projects}
      initialProject={init.initialProject}
      initialSkillGroups={init.skillGroups}
    >
      <FiguresWorkspace
        project={init.initialProject}
        initialFigures={figures}
        initialFigId={initialFigId}
      />
    </DashboardShell>
  );
}
