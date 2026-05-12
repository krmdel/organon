import { resolveProjectFromRequest } from "@/lib/projects";
import { listVersions } from "@/lib/images/versions";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ fig_id: string }> },
) {
  const { fig_id } = await params;
  const project = resolveProjectFromRequest(request);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });
  const versions = listVersions(project.path, fig_id);
  if (versions.length === 0) {
    return Response.json({ error: "fig_id has no versions" }, { status: 404 });
  }
  return Response.json({ fig_id, versions, total: versions.length });
}
