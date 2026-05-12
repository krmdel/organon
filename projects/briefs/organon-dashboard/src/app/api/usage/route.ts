import { resolveProjectFromRequest } from "@/lib/projects";
import { computeUsageReport, getClaudePlanUsage } from "@/lib/usage";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const project = resolveProjectFromRequest(request);
  if (!project) {
    return Response.json({ error: "Unknown project" }, { status: 404 });
  }
  try {
    const report = computeUsageReport(project.path);
    // Phase 66 (v2.2) — M5: structured plan-usage cascade. Path A reads
    // a local cache file Claude Code may persist (returns null when
    // absent); the chip falls back to the report's daily/weekly token
    // totals. The `report` field stays for backward compat with any
    // downstream consumer.
    const plan = getClaudePlanUsage();
    return Response.json({ project: project.slug, report, plan });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return Response.json({ error: msg }, { status: 500 });
  }
}
