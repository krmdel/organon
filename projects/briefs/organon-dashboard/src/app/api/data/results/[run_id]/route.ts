import { resolveProjectFromRequest } from "@/lib/projects";
import { archiveResult, unarchiveResult } from "@/lib/results/store";

/**
 * Phase 12a (v1.0.1) — D-7 stat-result archive endpoint.
 *
 *   DELETE /api/data/results/[run_id]?project=<slug>
 *     → soft-archive: flips `archived: true` on disk, file is NEVER unlinked.
 *
 *   POST   /api/data/results/[run_id]?project=<slug>  { unarchive: true }
 *     → flips `archived: false`. Verb-on-resource keeps the surface tight.
 *
 * Hard-delete is intentionally OUT of scope for v1.0.1 — researcher data
 * should not be one-click-destroyable. A separate "Permanently delete"
 * action is queued for v1.1+.
 */

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type RouteContext = { params: Promise<{ run_id: string }> };

export async function DELETE(request: Request, { params }: RouteContext) {
  const project = resolveProjectFromRequest(request);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });
  const { run_id } = await params;
  if (!run_id) return Response.json({ error: "run_id required" }, { status: 400 });
  const updated = archiveResult(project.path, run_id);
  if (!updated) return Response.json({ error: "result not found" }, { status: 404 });
  return Response.json({ project: project.slug, result: updated });
}

export async function POST(request: Request, { params }: RouteContext) {
  const project = resolveProjectFromRequest(request);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });
  const { run_id } = await params;
  if (!run_id) return Response.json({ error: "run_id required" }, { status: 400 });
  let body: { unarchive?: boolean } = {};
  try {
    body = (await request.json()) as { unarchive?: boolean };
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  if (body.unarchive !== true) {
    return Response.json(
      { error: "POST requires { unarchive: true }; DELETE archives" },
      { status: 400 },
    );
  }
  const updated = unarchiveResult(project.path, run_id);
  if (!updated) return Response.json({ error: "result not found" }, { status: 404 });
  return Response.json({ project: project.slug, result: updated });
}
