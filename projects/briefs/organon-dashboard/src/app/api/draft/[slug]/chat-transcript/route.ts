import { resolveProjectFromRequest } from "@/lib/projects";
import {
  readTranscript,
  appendTurn,
  clearTranscript,
} from "@/lib/draft/chat-transcripts";
import type { ChatTurn } from "@/lib/draft/chat-turn-types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = { params: Promise<{ slug: string }> };

/**
 * Phase 34 (v1.3) — DR-6++ on-disk chat transcript route.
 *
 * GET    ?project=<slug>           → { turns: ChatTurn[] }
 * POST   ?project=<slug>  { turn } → appends the turn (cap at 200)
 * DELETE ?project=<slug>           → unlinks the transcript file
 *
 * All three resolve project via resolveProjectFromRequest, the
 * canonical helper. Hydration is non-blocking on the workspace side —
 * a 404/500 from any handler doesn't break the chat session.
 */

export async function GET(request: Request, { params }: RouteContext) {
  const { slug } = await params;
  const project = resolveProjectFromRequest(request);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });
  const turns = readTranscript(project.path, slug);
  return Response.json({ turns }, { status: 200 });
}

type PostBody = { project?: string; turn?: ChatTurn };

export async function POST(request: Request, { params }: RouteContext) {
  const { slug } = await params;
  let body: PostBody;
  try {
    body = (await request.json()) as PostBody;
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  const project = resolveProjectFromRequest(request, body.project);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });
  const turn = body.turn;
  if (
    !turn
    || typeof turn !== "object"
    || typeof turn.id !== "string"
    || typeof turn.prompt !== "string"
  ) {
    return Response.json({ error: "turn required (id + prompt)" }, { status: 400 });
  }
  appendTurn(project.path, slug, turn);
  return Response.json({ ok: true }, { status: 201 });
}

export async function DELETE(request: Request, { params }: RouteContext) {
  const { slug } = await params;
  const project = resolveProjectFromRequest(request);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });
  clearTranscript(project.path, slug);
  return Response.json({ ok: true }, { status: 200 });
}
