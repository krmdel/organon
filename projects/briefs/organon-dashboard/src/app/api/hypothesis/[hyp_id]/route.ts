import { resolveProjectFromRequest } from "@/lib/projects";
import {
  deleteHypothesis,
  getHypothesis,
  isValidTransition,
  patchHypothesis,
} from "@/lib/hypothesis/store";
import { listCritiques } from "@/lib/hypothesis/critiques";
import type { HypothesisArtifact, HypothesisStatus } from "@/lib/artifacts/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Params = { params: Promise<{ hyp_id: string }> };

export async function GET(request: Request, ctx: Params) {
  const project = resolveProjectFromRequest(request);
  const { hyp_id } = await ctx.params;
  if (!project) {
    return Response.json({ error: "Unknown project" }, { status: 404 });
  }
  const hypothesis = getHypothesis(project.path, hyp_id);
  if (!hypothesis) {
    return Response.json({ error: "Hypothesis not found" }, { status: 404 });
  }
  const critiques = listCritiques(project.path, hyp_id);
  return Response.json({ hypothesis, critiques });
}

type PatchBody = {
  project?: string;
  patch?: Partial<HypothesisArtifact>;
};

export async function PATCH(request: Request, ctx: Params) {
  let body: PatchBody;
  try {
    body = (await request.json()) as PatchBody;
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  const project = resolveProjectFromRequest(request, body.project);
  const { hyp_id } = await ctx.params;
  if (!project) {
    return Response.json({ error: "Unknown project" }, { status: 404 });
  }
  const current = getHypothesis(project.path, hyp_id);
  if (!current) {
    return Response.json({ error: "Hypothesis not found" }, { status: 404 });
  }

  const patch = body.patch ?? {};
  if (patch.status && patch.status !== current.status) {
    if (!isValidTransition(current.status, patch.status as HypothesisStatus, "user")) {
      return Response.json(
        { error: `Invalid status transition: ${current.status} → ${patch.status}` },
        { status: 409 },
      );
    }
  }

  // Whitelist user-patchable fields. Skill-only fields are ignored here.
  const safePatch: Partial<HypothesisArtifact> = {};
  if (patch.status !== undefined) safePatch.status = patch.status;
  if (patch.notes !== undefined) safePatch.notes = patch.notes;
  if (patch.tags !== undefined) safePatch.tags = patch.tags;
  if (patch.claim_short !== undefined) safePatch.claim_short = patch.claim_short;
  // Phase 43 (v1.5) — F6: per-persona discard list. User-driven; sci-
  // hypothesis never sets it on its own. Filtered to string[] to keep
  // skill-emitted noise from contaminating the field.
  if (Array.isArray(patch.excluded_persona_ids)) {
    safePatch.excluded_persona_ids = patch.excluded_persona_ids
      .filter((s): s is string => typeof s === "string");
  }

  const updated = patchHypothesis(project.path, hyp_id, safePatch);
  if (!updated) {
    return Response.json({ error: "Hypothesis not found" }, { status: 404 });
  }
  return Response.json({ hypothesis: updated });
}

export async function DELETE(request: Request, ctx: Params) {
  let body: { project?: string };
  try {
    body = (await request.json()) as { project?: string };
  } catch {
    body = {};
  }
  const project = resolveProjectFromRequest(request, body.project);
  const { hyp_id } = await ctx.params;
  if (!project) {
    return Response.json({ error: "Unknown project" }, { status: 404 });
  }
  deleteHypothesis(project.path, hyp_id);
  return Response.json({ removed: true });
}
