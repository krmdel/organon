import { notFound } from "next/navigation";
import { DashboardShell } from "@/components/shell/dashboard-shell";
import { ManuscriptWorkspace } from "@/components/draft/manuscript-workspace";
import { initShell } from "@/lib/shell-init";
import { resolveProject } from "@/lib/projects";
import { getManuscript, listSections } from "@/lib/draft/store";
import { listFigures } from "@/lib/figures/store";
import { listLibrary } from "@/lib/lit/library";
import { listHypotheses } from "@/lib/hypothesis/store";
import { listFiles as listDataframes } from "@/lib/data/files";

export const dynamic = "force-dynamic";

type SearchParams = { [key: string]: string | string[] | undefined };

export default async function DraftWorkspacePage(props: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<SearchParams>;
}) {
  const { slug } = await props.params;
  const sp = await props.searchParams;
  const param = typeof sp.project === "string" ? sp.project : undefined;
  const init = initShell(param);
  const project = resolveProject(init.initialProject);
  if (!project) notFound();

  const manuscript = getManuscript(project.path, slug);
  if (!manuscript) notFound();
  const sections = listSections(project.path, slug);
  const figures = listFigures(project.path);
  const library = listLibrary(project.path);
  const hypotheses = listHypotheses(project.path);
  const datasets = listDataframes(project.path).map((d) => ({
    id: d.id,
    filename: d.filename,
    rows_total: d.rows_total,
  }));
  const initialSectionId = typeof sp.section === "string" ? sp.section : undefined;

  return (
    <DashboardShell
      initialProjects={init.projects}
      initialProject={init.initialProject}
      initialSkillGroups={init.skillGroups}
    >
      <ManuscriptWorkspace
        project={init.initialProject}
        manuscript={manuscript}
        initialSections={sections}
        figures={figures}
        library={library}
        hypotheses={hypotheses}
        datasets={datasets}
        initialSectionId={initialSectionId}
      />
    </DashboardShell>
  );
}
