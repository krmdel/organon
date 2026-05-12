import { resolveProjectFromRequest } from "@/lib/projects";
import { deleteFigure, readFigure } from "@/lib/figures/store";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = { params: Promise<{ fig_id: string }> };

/**
 * Phase 63 (v2.2) — M2: hard delete a figure + all its versions and
 * mask files. Mirrors Phase 62's manuscript DELETE wiring. Idempotent
 * cascade lives in `deleteFigure` (recursive rmSync). 400 on missing
 * project, 404 on unknown fig_id.
 */
export async function DELETE(request: Request, { params }: RouteContext) {
  const project = resolveProjectFromRequest(request);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 400 });
  const { fig_id } = await params;
  if (!readFigure(project.path, fig_id)) {
    return Response.json({ error: "figure not found" }, { status: 404 });
  }
  deleteFigure(project.path, fig_id);
  return Response.json({ ok: true, deleted: fig_id });
}
