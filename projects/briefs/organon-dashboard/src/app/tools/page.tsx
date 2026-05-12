import { DashboardShell } from "@/components/shell/dashboard-shell";
import { ToolsWorkspace } from "@/components/tools/tools-workspace";
import { initShell } from "@/lib/shell-init";
import { resolveProject } from "@/lib/projects";
import { buildCatalog } from "@/lib/tools/catalog";
import { readFavourites } from "@/lib/tools/favourites";

export const dynamic = "force-dynamic";

type SearchParams = { [key: string]: string | string[] | undefined };

export default async function ToolsPage(props: { searchParams: Promise<SearchParams> }) {
  const sp = await props.searchParams;
  const param = typeof sp.project === "string" ? sp.project : undefined;
  const init = initShell(param);
  const project = resolveProject(init.initialProject);
  const catalog = buildCatalog();
  const favourites = project ? readFavourites(project.path) : [];

  return (
    <DashboardShell
      initialProjects={init.projects}
      initialProject={init.initialProject}
      initialSkillGroups={init.skillGroups}
    >
      <ToolsWorkspace
        project={init.initialProject}
        initialCatalog={catalog}
        initialFavourites={favourites}
      />
    </DashboardShell>
  );
}
