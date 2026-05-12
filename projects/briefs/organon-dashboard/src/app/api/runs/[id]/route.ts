import { resolveProjectFromRequest } from "@/lib/projects";
import { readRunDetail } from "@/lib/runs";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const project = resolveProjectFromRequest(request);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });
  const detail = readRunDetail(project.path, id);
  if (!detail) return Response.json({ error: "run not found" }, { status: 404 });
  return Response.json({ run: detail });
}
