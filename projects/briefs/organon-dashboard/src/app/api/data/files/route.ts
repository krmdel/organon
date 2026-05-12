import { resolveProjectFromRequest } from "@/lib/projects";
import { listFiles } from "@/lib/data/files";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: Request) {
  const project = resolveProjectFromRequest(request);
  if (!project) {
    return Response.json({ error: "Unknown project" }, { status: 404 });
  }
  const files = listFiles(project.path);
  return Response.json({ project: project.slug, files, total: files.length });
}
