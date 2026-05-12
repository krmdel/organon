import { DashboardShell } from "@/components/shell/dashboard-shell";
import { DraftList } from "@/components/draft/draft-list";
import { initShell } from "@/lib/shell-init";
import { resolveProject } from "@/lib/projects";
import { listManuscripts } from "@/lib/draft/store";
import { listHypotheses } from "@/lib/hypothesis/store";

export const dynamic = "force-dynamic";

type SearchParams = { [key: string]: string | string[] | undefined };

export default async function DraftPage(props: { searchParams: Promise<SearchParams> }) {
  const sp = await props.searchParams;
  const param = typeof sp.project === "string" ? sp.project : undefined;
  const init = initShell(param);
  const project = resolveProject(init.initialProject);
  const manuscripts = project ? listManuscripts(project.path) : [];
  const hypotheses = project ? listHypotheses(project.path) : [];

  return (
    <DashboardShell
      initialProjects={init.projects}
      initialProject={init.initialProject}
      initialSkillGroups={init.skillGroups}
    >
      <DraftList
        project={init.initialProject}
        manuscripts={manuscripts}
        hypotheses={hypotheses}
      />
    </DashboardShell>
  );
}
