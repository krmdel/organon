import { resolveProjectFromRequest } from "@/lib/projects";
import { listResults } from "@/lib/results/store";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: Request) {
  const project = resolveProjectFromRequest(request);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });
  const results = listResults(project.path);
  return Response.json({ project: project.slug, results, total: results.length });
}
