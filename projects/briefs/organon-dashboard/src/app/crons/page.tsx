import { DashboardShell } from "@/components/shell/dashboard-shell";
import { CronsWorkspace } from "@/components/crons/crons-workspace";
import { initShell } from "@/lib/shell-init";
import { listCronJobs } from "@/lib/crons/reader";

export const dynamic = "force-dynamic";

type SearchParams = { [key: string]: string | string[] | undefined };

export default async function CronsPage(props: { searchParams: Promise<SearchParams> }) {
  const sp = await props.searchParams;
  const param = typeof sp.project === "string" ? sp.project : undefined;
  const init = initShell(param);
  const jobs = listCronJobs();

  return (
    <DashboardShell
      initialProjects={init.projects}
      initialProject={init.initialProject}
      initialSkillGroups={init.skillGroups}
    >
      <CronsWorkspace initialJobs={jobs} />
    </DashboardShell>
  );
}
