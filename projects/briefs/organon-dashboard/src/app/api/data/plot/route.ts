import { resolveProjectFromRequest } from "@/lib/projects";
import { rawFilePath, readPreview } from "@/lib/data/files";
import { allocateFigId } from "@/lib/data/id";
import { generatePlot, PlotError } from "@/lib/data/plot";
import { validateParams, type PlotKind } from "@/lib/data/plot-schemas";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const maxDuration = 90;

type Body = {
  project?: string;
  file_id?: string;
  kind?: PlotKind;
  params?: Record<string, unknown>;
};

export async function POST(request: Request) {
  let body: Body;
  try {
    body = (await request.json()) as Body;
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  const project = resolveProjectFromRequest(request, body.project);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });
  if (!body.file_id) return Response.json({ error: "file_id required" }, { status: 400 });
  if (!body.kind) return Response.json({ error: "kind required" }, { status: 400 });

  const preview = readPreview(project.path, body.file_id);
  if (!preview) return Response.json({ error: "preview not found" }, { status: 404 });
  const raw = rawFilePath(project.path, body.file_id);
  if (!raw) return Response.json({ error: "raw file missing" }, { status: 410 });

  const params = body.params ?? {};
  const validation = validateParams(body.kind, params, preview);
  if (!validation.ok) {
    return Response.json({ error: "Invalid params", details: validation.errors }, { status: 400 });
  }

  const figId = allocateFigId();
  try {
    const artifact = await generatePlot({
      rawPath: raw,
      fileId: body.file_id,
      figId,
      projectSlug: project.slug,
      projectPath: project.path,
      kind: body.kind,
      params,
    });
    return Response.json({ figure: artifact }, { status: 201 });
  } catch (err) {
    if (err instanceof PlotError) {
      return Response.json({ error: err.message }, { status: err.status });
    }
    return Response.json(
      { error: err instanceof Error ? err.message : "plot failed" },
      { status: 500 },
    );
  }
}
