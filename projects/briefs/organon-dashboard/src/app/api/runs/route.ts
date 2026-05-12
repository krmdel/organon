import { resolveProjectFromRequest } from "@/lib/projects";
import { listRuns, runActivityByDay } from "@/lib/runs";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const limit = Math.min(500, Math.max(1, Number(searchParams.get("limit") ?? "20")));
  const project = resolveProjectFromRequest(request);
  if (!project) {
    return Response.json({ error: "Unknown project" }, { status: 404 });
  }
  return Response.json({
    project: project.slug,
    runs: listRuns(project.path, limit),
    weekly: runActivityByDay(project.path, 7),
  });
}
