import { resolveProjectFromRequest } from "@/lib/projects";
import {
  isSaved,
  listLibrary,
  removeBatchFromLibrary,
  removePaper,
  savePaper,
} from "@/lib/lit/library";
import type { PaperArtifact } from "@/lib/artifacts/types";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const project = resolveProjectFromRequest(request);
  if (!project) {
    return Response.json({ error: "Unknown project" }, { status: 404 });
  }
  const papers = listLibrary(project.path);
  return Response.json({
    project: project.slug,
    papers,
    total: papers.length,
  });
}

export async function POST(request: Request) {
  // Phase 38 (v1.4) — F1: optional `batch` field stamps every saved
  // paper with the same search_batch_id / query / added_at so the
  // library panel can group them. Back-compat: empty/missing batch is
  // a plain save.
  let body: {
    project?: string;
    paper?: PaperArtifact;
    batch?: { batch_id: string; query: string; added_at?: string };
  };
  try {
    body = (await request.json()) as typeof body;
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  const project = resolveProjectFromRequest(request, body.project);
  if (!project) {
    return Response.json({ error: "Unknown project" }, { status: 404 });
  }
  const paper = body.paper;
  if (!paper || !paper.id) {
    return Response.json({ error: "paper.id required" }, { status: 400 });
  }
  if (paper._artifact !== "paper") {
    return Response.json({ error: "paper._artifact must be 'paper'" }, { status: 400 });
  }

  const alreadySaved = isSaved(project.path, paper.id);
  const stamped: PaperArtifact = body.batch
    ? {
        ...paper,
        search_batch_id: body.batch.batch_id,
        search_batch_query: body.batch.query,
        search_batch_added_at: body.batch.added_at ?? new Date().toISOString(),
      }
    : paper;
  const libraryPath = savePaper(project.path, stamped);

  return Response.json(
    {
      saved: !alreadySaved,
      already_present: alreadySaved,
      library_path: libraryPath,
    },
    { status: alreadySaved ? 200 : 201 },
  );
}

export async function DELETE(request: Request) {
  // Phase 38 (v1.4) — F1: support three call shapes:
  //   1. ?batch=<batch_id>          → batch-delete every entry stamped
  //                                    with that batch_id
  //   2. ?ids=a,b,c                 → bulk-delete the listed entries
  //   3. body { paper_id: "..." }   → legacy single-entry delete
  //                                    (preserved for back-compat)
  const url = new URL(request.url);
  const batch = url.searchParams.get("batch");
  const idsRaw = url.searchParams.get("ids");

  if (batch || idsRaw) {
    const project = resolveProjectFromRequest(request);
    if (!project) {
      return Response.json({ error: "Unknown project" }, { status: 404 });
    }
    if (batch) {
      const removed = removeBatchFromLibrary(project.path, batch);
      return Response.json({
        removed_count: removed.length,
        removed_ids: removed,
        batch_id: batch,
      });
    }
    if (idsRaw !== null) {
      const ids = idsRaw.split(",").map((s) => s.trim()).filter(Boolean);
      const removed: string[] = [];
      for (const id of ids) {
        if (removePaper(project.path, id)) removed.push(id);
      }
      return Response.json({
        removed_count: removed.length,
        removed_ids: removed,
      });
    }
  }

  let body: { project?: string; paper_id?: string };
  try {
    body = (await request.json()) as { project?: string; paper_id?: string };
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  const project = resolveProjectFromRequest(request, body.project);
  if (!project) {
    return Response.json({ error: "Unknown project" }, { status: 404 });
  }
  if (!body.paper_id) {
    return Response.json({ error: "paper_id required" }, { status: 400 });
  }
  const removed = removePaper(project.path, body.paper_id);
  if (!removed) {
    return Response.json({ error: "Paper not in library" }, { status: 404 });
  }
  return Response.json({ removed: true });
}
