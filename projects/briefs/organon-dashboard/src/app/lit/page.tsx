import { DashboardShell } from "@/components/shell/dashboard-shell";
import { LitWorkspace } from "@/components/lit/lit-workspace";
import { initShell } from "@/lib/shell-init";
import { listLibrary } from "@/lib/lit/library";
import { resolveProject } from "@/lib/projects";
import type { SearchSource } from "@/components/lit/search-bar";

export const dynamic = "force-dynamic";

type SearchParams = { [key: string]: string | string[] | undefined };

const VALID_SOURCES: SearchSource[] = ["pubmed", "arxiv", "openalex", "semanticscholar"];

export default async function LitPage(props: { searchParams: Promise<SearchParams> }) {
  const sp = await props.searchParams;
  const projectParam = typeof sp.project === "string" ? sp.project : undefined;
  const init = initShell(projectParam);

  const project = resolveProject(init.initialProject);
  const library = project ? listLibrary(project.path) : [];

  const initialQuery = typeof sp.q === "string" ? sp.q : undefined;
  const initialPaperId = typeof sp.paper === "string" ? sp.paper : undefined;
  const sourcesParam = typeof sp.sources === "string" ? sp.sources.split(",") : undefined;
  const initialSources = sourcesParam
    ? (sourcesParam.filter((s): s is SearchSource => VALID_SOURCES.includes(s as SearchSource)))
    : undefined;

  return (
    <DashboardShell
      initialProjects={init.projects}
      initialProject={init.initialProject}
      initialSkillGroups={init.skillGroups}
    >
      <LitWorkspace
        project={init.initialProject}
        initialLibrary={library}
        initialQuery={initialQuery}
        initialPaperId={initialPaperId}
        initialSources={initialSources}
      />
    </DashboardShell>
  );
}
