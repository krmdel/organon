import Link from "next/link";
import { DashboardShell } from "@/components/shell/dashboard-shell";
import { initShell } from "@/lib/shell-init";

export const dynamic = "force-dynamic";

type SearchParams = { [key: string]: string | string[] | undefined };

export default async function Home(props: { searchParams: Promise<SearchParams> }) {
  const sp = await props.searchParams;
  const projectParam = typeof sp.project === "string" ? sp.project : undefined;
  const init = initShell(projectParam);

  return (
    <DashboardShell
      initialProjects={init.projects}
      initialProject={init.initialProject}
      initialSkillGroups={init.skillGroups}
    >
      <HomePanel currentProject={init.initialProject} />
    </DashboardShell>
  );
}

function HomePanel({ currentProject }: { currentProject: string }) {
  return (
    <div className="px-8 py-10 max-w-4xl">
      <div className="mono text-[11px] tracking-[0.2em] text-text-muted uppercase mb-2">
        Welcome to Organon
      </div>
      <h1 className="text-3xl font-semibold mb-4">Pick a workspace to start</h1>
      <p className="text-text-dim mb-8 leading-relaxed max-w-2xl">
        Phase 1 ships the literature-research workspace. Hypothesis, data, figures, drafting,
        tools, and runs land in later phases — sidebar links resolve to placeholder pages until
        each ships.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <WorkspaceCard
          href={`/lit?project=${encodeURIComponent(currentProject)}`}
          label="Literature"
          status="Ready"
          description="Federated PubMed / arXiv / OpenAlex / Semantic Scholar search. Save to project library, export BibTeX."
          ready
        />
        <WorkspaceCard
          href={`/hypothesis?project=${encodeURIComponent(currentProject)}`}
          label="Hypothesis"
          status="Phase 2"
          description="Three-persona research council fanout (Gauss / Erdős / Tao or domain-tuned)."
        />
        <WorkspaceCard
          href={`/data?project=${encodeURIComponent(currentProject)}`}
          label="Data"
          status="Phase 3"
          description="CSV / XLSX upload, dataframe preview, statistical test wizard, plot picker."
        />
        <WorkspaceCard
          href={`/figures?project=${encodeURIComponent(currentProject)}`}
          label="Figures"
          status="Phase 4"
          description="Generate via Gemini 3 Pro Image; circle-and-regenerate via FAL FLUX.1 [pro] Fill."
        />
        <WorkspaceCard
          href={`/draft?project=${encodeURIComponent(currentProject)}`}
          label="Draft"
          status="Phase 5"
          description="Manuscript editor with embedded figures, citation autoresolve, live preview."
        />
        <WorkspaceCard
          href={`/tools?project=${encodeURIComponent(currentProject)}`}
          label="Tools / Crons / Runs"
          status="Phase 6"
          description="ToolUniverse browser, scheduled-job dashboard, full run history with drill-down."
        />
      </div>

      <div className="mt-10 text-xs mono text-text-muted tracking-[0.16em] uppercase">
        Press <span className="text-text">⌘K</span> for the command palette
      </div>
    </div>
  );
}

function WorkspaceCard({
  href,
  label,
  status,
  description,
  ready,
}: {
  href: string;
  label: string;
  status: string;
  description: string;
  ready?: boolean;
}) {
  return (
    <Link
      href={href}
      className="block p-5 border border-border rounded hover:border-accent transition group"
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-text font-semibold">{label}</span>
        <span
          className={`mono text-[10px] uppercase tracking-wider ${
            ready ? "text-good" : "text-text-muted"
          }`}
        >
          {status}
        </span>
      </div>
      <p className="text-sm text-text-dim leading-relaxed">{description}</p>
    </Link>
  );
}
