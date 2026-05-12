import { resolveProjectFromRequest } from "@/lib/projects";
import { getHypothesis, patchHypothesis } from "@/lib/hypothesis/store";
import { listLibrary } from "@/lib/lit/library";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Params = { params: Promise<{ hyp_id: string }> };

type ApplyBody = {
  project?: string;
  drop?: string[];
  retain?: string[];
};

/**
 * Phase 13c (v1.0.1) — H-7 apply-recommendation.
 *
 * POST { drop?: string[], retain?: string[] }
 *
 * Mutates the hypothesis's `paper_ids` per the synthesis recommendation.
 * - `drop` ids must currently be in `paper_ids`. Unknown drops → 422.
 * - `retain` ids must exist in the project's library. Adds any retain
 *   not already present in `paper_ids`. Unknown retains → 422.
 *
 * The route is destructive of paper_ids — the UI surfaces a confirm
 * before the POST. Atomic write via patchHypothesis (tmp+rename).
 *
 * Refuses on archived hypotheses (paper_ids should be frozen once a
 * hypothesis exits the active loop).
 */
export async function POST(request: Request, ctx: Params) {
  let body: ApplyBody;
  try {
    body = (await request.json()) as ApplyBody;
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const project = resolveProjectFromRequest(request, body.project);
  if (!project) {
    return Response.json({ error: "Unknown project" }, { status: 404 });
  }
  const { hyp_id } = await ctx.params;

  const current = getHypothesis(project.path, hyp_id);
  if (!current) {
    return Response.json({ error: "Hypothesis not found" }, { status: 404 });
  }
  if (current.status === "archived") {
    return Response.json(
      { error: "Cannot apply recommendation to archived hypothesis" },
      { status: 409 },
    );
  }

  const drop = Array.isArray(body.drop) ? body.drop.filter((s) => typeof s === "string") : [];
  const retain = Array.isArray(body.retain) ? body.retain.filter((s) => typeof s === "string") : [];
  if (drop.length === 0 && retain.length === 0) {
    return Response.json(
      { error: "No drop or retain ids provided" },
      { status: 400 },
    );
  }

  const currentSet = new Set(current.paper_ids);
  const unknownDrops = drop.filter((id) => !currentSet.has(id));
  if (unknownDrops.length > 0) {
    return Response.json(
      { error: "Unknown drop ids", unknown: unknownDrops },
      { status: 422 },
    );
  }

  const librarySet = new Set(listLibrary(project.path).map((p) => p.id));
  const unknownRetains = retain.filter((id) => !librarySet.has(id));
  if (unknownRetains.length > 0) {
    return Response.json(
      { error: "Unknown retain ids", unknown: unknownRetains },
      { status: 422 },
    );
  }

  const dropSet = new Set(drop);
  const after = current.paper_ids.filter((id) => !dropSet.has(id));
  for (const id of retain) {
    if (!after.includes(id)) after.push(id);
  }

  const updated = patchHypothesis(project.path, hyp_id, { paper_ids: after });
  if (!updated) {
    return Response.json({ error: "Hypothesis not found" }, { status: 404 });
  }

  return Response.json({
    hypothesis: updated,
    applied: { dropped: drop, retained: retain },
  });
}
