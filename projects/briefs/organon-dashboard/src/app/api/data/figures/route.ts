import { resolveProjectFromRequest } from "@/lib/projects";
import { listFigures } from "@/lib/figures/store";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: Request) {
  const project = resolveProjectFromRequest(request);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });
  const figures = listFigures(project.path);
  return Response.json({ project: project.slug, figures, total: figures.length });
}
