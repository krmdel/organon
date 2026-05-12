import { DashboardShell } from "@/components/shell/dashboard-shell";
import {
  HypothesisWorkspace,
  type HydrationStatus,
} from "@/components/hypothesis/hypothesis-workspace";
import { initShell } from "@/lib/shell-init";
import { resolveProject } from "@/lib/projects";
import { getHypothesis, listHypotheses } from "@/lib/hypothesis/store";
import { listCritiques } from "@/lib/hypothesis/critiques";
import { listPersonas } from "@/lib/hypothesis/personas";
import { listLibrary } from "@/lib/lit/library";

export const dynamic = "force-dynamic";

type SearchParams = { [key: string]: string | string[] | undefined };

export default async function HypothesisPage(props: {
  searchParams: Promise<SearchParams>;
}) {
  const sp = await props.searchParams;
  const param = typeof sp.project === "string" ? sp.project : undefined;
  const init = initShell(param);

  const project = resolveProject(init.initialProject);
  const hypotheses = project ? listHypotheses(project.path) : [];
  const personas = project ? listPersonas(project.path) : [];
  const library = project ? listLibrary(project.path) : [];

  const initialHypId = typeof sp.hyp === "string" ? sp.hyp : undefined;
  const initialPrefillPaperId =
    typeof sp.prefill_paper === "string" ? sp.prefill_paper : undefined;

  // Phase 11 (v1.0.1) — server-computed hydrationStatus for the active
  // hypothesis. Surfaces a "loaded data is complete" badge before the client
  // pulls critiques, so a researcher can tell at a glance whether a 2/3
  // critique state means "still loading" or "council never finished".
  let initialHydrationStatus: HydrationStatus | null = null;
  if (project && initialHypId) {
    const active = getHypothesis(project.path, initialHypId);
    if (active) {
      const critiqueCount = listCritiques(project.path, initialHypId).length;
      const expected = personas.length;
      initialHydrationStatus = {
        critiques: critiqueCount,
        expected,
        synthesis: active.synthesis_text ? "present" : "absent",
      };
    }
  }

  return (
    <DashboardShell
      initialProjects={init.projects}
      initialProject={init.initialProject}
      initialSkillGroups={init.skillGroups}
    >
      <HypothesisWorkspace
        project={init.initialProject}
        initialHypotheses={hypotheses}
        initialLibrary={library}
        initialPersonas={personas}
        initialHypId={initialHypId}
        initialPrefillPaperId={initialPrefillPaperId}
        initialHydrationStatus={initialHydrationStatus}
      />
    </DashboardShell>
  );
}
