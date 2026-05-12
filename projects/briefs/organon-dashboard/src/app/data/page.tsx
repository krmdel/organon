import { DashboardShell } from "@/components/shell/dashboard-shell";
import { DataWorkspace } from "@/components/data/data-workspace";
import { initShell } from "@/lib/shell-init";
import { resolveProject } from "@/lib/projects";
import { listFiles } from "@/lib/data/files";
import { listFigures } from "@/lib/figures/store";
import { listResults } from "@/lib/results/store";

export const dynamic = "force-dynamic";

type SearchParams = { [key: string]: string | string[] | undefined };

export default async function DataPage(props: {
  searchParams: Promise<SearchParams>;
}) {
  const sp = await props.searchParams;
  const param = typeof sp.project === "string" ? sp.project : undefined;
  const init = initShell(param);

  const project = resolveProject(init.initialProject);
  const files = project ? listFiles(project.path) : [];
  const figures = project ? listFigures(project.path) : [];
  const results = project ? listResults(project.path) : [];
  const initialFileId = typeof sp.file === "string" ? sp.file : undefined;
  const initialTab =
    sp.tab === "stats" || sp.tab === "plots" || sp.tab === "preview" ? sp.tab : undefined;

  return (
    <DashboardShell
      initialProjects={init.projects}
      initialProject={init.initialProject}
      initialSkillGroups={init.skillGroups}
    >
      <DataWorkspace
        project={init.initialProject}
        initialFiles={files}
        initialFigures={figures}
        initialResults={results}
        initialFileId={initialFileId}
        initialTab={initialTab}
      />
    </DashboardShell>
  );
}
