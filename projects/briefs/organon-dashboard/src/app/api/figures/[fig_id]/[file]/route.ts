import { existsSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { resolveProjectFromRequest } from "@/lib/projects";
import { figureDir } from "@/lib/figures/store";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const MIME_BY_EXT: Record<string, string> = {
  png: "image/png",
  svg: "image/svg+xml",
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  py: "text/plain; charset=utf-8",
};

const FILE_RE = /^v(\d+)\.(png|svg|jpg|jpeg|py|thumb\.png)$/;

export async function GET(
  request: Request,
  { params }: { params: Promise<{ fig_id: string; file: string }> },
) {
  const { fig_id, file } = await params;
  if (!FILE_RE.test(file)) {
    return Response.json({ error: "invalid file" }, { status: 400 });
  }
  const project = resolveProjectFromRequest(request);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });

  const target = path.join(figureDir(project.path, fig_id), file);
  // Defence-in-depth: ensure resolved path stays inside the figure dir.
  const expectedPrefix = figureDir(project.path, fig_id) + path.sep;
  if (!path.resolve(target).startsWith(path.resolve(expectedPrefix))) {
    return Response.json({ error: "path traversal" }, { status: 400 });
  }
  if (!existsSync(target)) {
    return Response.json({ error: "not found" }, { status: 404 });
  }
  const buf = readFileSync(target);
  const ext = file.endsWith(".thumb.png") ? "png" : file.split(".").pop()!;
  return new Response(buf, {
    headers: {
      "Content-Type": MIME_BY_EXT[ext] ?? "application/octet-stream",
      "Content-Length": String(statSync(target).size),
      "Cache-Control": "private, max-age=300",
    },
  });
}
