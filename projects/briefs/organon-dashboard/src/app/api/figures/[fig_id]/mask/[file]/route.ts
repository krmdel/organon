import { existsSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { resolveProjectFromRequest } from "@/lib/projects";
import { figureDir } from "@/lib/figures/store";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const FILE_RE = /^v(\d+)\.png$/;

export async function GET(
  request: Request,
  { params }: { params: Promise<{ fig_id: string; file: string }> },
) {
  const { fig_id, file } = await params;
  if (!FILE_RE.test(file)) return Response.json({ error: "invalid mask file" }, { status: 400 });

  const project = resolveProjectFromRequest(request);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });

  const target = path.join(figureDir(project.path, fig_id), "mask", file);
  const expectedPrefix = path.join(figureDir(project.path, fig_id), "mask") + path.sep;
  if (!path.resolve(target).startsWith(path.resolve(expectedPrefix))) {
    return Response.json({ error: "path traversal" }, { status: 400 });
  }
  if (!existsSync(target)) return Response.json({ error: "mask not found" }, { status: 404 });
  const buf = readFileSync(target);
  return new Response(buf, {
    headers: {
      "Content-Type": "image/png",
      "Content-Length": String(statSync(target).size),
      "Cache-Control": "private, max-age=300",
    },
  });
}
