import { resolveProjectFromRequest } from "@/lib/projects";
import {
  readAnnotations,
  writeAnnotations,
  type AnnotationStroke,
} from "@/lib/figures/annotations";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Params = { params: Promise<{ fig_id: string }> };

/**
 * Phase 14b (v1.0.1) — F-2 annotations GET/POST.
 *
 * GET  → { annotations: FigureAnnotationsArtifact }
 * POST { strokes: AnnotationStroke[] } → { annotations: FigureAnnotationsArtifact }
 *
 * The route accepts the FULL stroke array on every POST — the workspace
 * sends the new state as a complete list rather than a diff so an
 * ERASER click is just a smaller list. Order is load-bearing for the
 * ERASER's last-drawn-first hit test, so strokes round-trip in the
 * order the caller sent them.
 */
export async function GET(request: Request, ctx: Params) {
  const project = resolveProjectFromRequest(request);
  if (!project) {
    return Response.json({ error: "Unknown project" }, { status: 404 });
  }
  const { fig_id } = await ctx.params;
  const annotations = readAnnotations(project.path, fig_id);
  return Response.json({ annotations });
}

type PostBody = {
  project?: string;
  strokes?: unknown;
};

export async function POST(request: Request, ctx: Params) {
  let body: PostBody;
  try {
    body = (await request.json()) as PostBody;
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  const project = resolveProjectFromRequest(request, body.project);
  if (!project) {
    return Response.json({ error: "Unknown project" }, { status: 404 });
  }
  const { fig_id } = await ctx.params;
  if (!Array.isArray(body.strokes)) {
    return Response.json({ error: "strokes must be an array" }, { status: 400 });
  }
  // Permissive narrowing — we trust the workspace shape but reject
  // obviously malformed entries so a bad client doesn't poison the
  // file. Each stroke must carry kind + id at minimum.
  const cleaned: AnnotationStroke[] = [];
  for (const raw of body.strokes) {
    if (!raw || typeof raw !== "object") continue;
    const s = raw as Record<string, unknown>;
    if (typeof s.id !== "string") continue;
    if (s.kind === "pen" && Array.isArray(s.points)) {
      cleaned.push(s as unknown as AnnotationStroke);
    } else if (s.kind === "arrow" && s.from && s.to) {
      cleaned.push(s as unknown as AnnotationStroke);
    } else if (s.kind === "text" && typeof s.text === "string" && s.at) {
      cleaned.push(s as unknown as AnnotationStroke);
    }
  }
  const annotations = writeAnnotations(project.path, fig_id, cleaned);
  return Response.json({ annotations });
}
