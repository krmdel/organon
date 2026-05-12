import { resolveProjectFromRequest } from "@/lib/projects";
import { findManuscriptsByHypothesisId } from "@/lib/draft/store";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Params = { params: Promise<{ hyp_id: string }> };

/**
 * Phase 50 (v2.0) — Reverse linkage.
 *
 * GET /api/hypothesis/[hyp_id]/manuscripts → { manuscripts }
 *
 * Returns the manuscripts whose `linked_hypothesis_ids[]` includes the
 * given hypothesis id. The reverse of Phase 41's manuscript→hypothesis
 * linkage. Empty array means "no manuscripts link to this hypothesis";
 * does not check whether the hypothesis itself exists (cheap call).
 */
export async function GET(request: Request, ctx: Params) {
  const project = resolveProjectFromRequest(request);
  const { hyp_id } = await ctx.params;
  if (!project) {
    return Response.json({ error: "Unknown project" }, { status: 404 });
  }
  const manuscripts = findManuscriptsByHypothesisId(project.path, hyp_id);
  return Response.json({ manuscripts });
}
