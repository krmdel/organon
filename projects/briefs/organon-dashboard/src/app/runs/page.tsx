import { DashboardShell } from "@/components/shell/dashboard-shell";
import { RunsWorkspace } from "@/components/runs/runs-workspace";
import { initShell } from "@/lib/shell-init";
import { resolveProject } from "@/lib/projects";
import { listRuns } from "@/lib/runs";

export const dynamic = "force-dynamic";

type SearchParams = { [key: string]: string | string[] | undefined };

export default async function RunsPage(props: { searchParams: Promise<SearchParams> }) {
  const sp = await props.searchParams;
  const param = typeof sp.project === "string" ? sp.project : undefined;
  const init = initShell(param);
  const project = resolveProject(init.initialProject);
  const runs = project ? listRuns(project.path, 200) : [];

  return (
    <DashboardShell
      initialProjects={init.projects}
      initialProject={init.initialProject}
      initialSkillGroups={init.skillGroups}
    >
      <RunsWorkspace project={init.initialProject} initialRuns={runs} />
    </DashboardShell>
  );
}
