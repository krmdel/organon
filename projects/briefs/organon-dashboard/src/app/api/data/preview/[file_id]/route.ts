import { resolveProjectFromRequest } from "@/lib/projects";
import { rawFilePath, readPreview, removeFile } from "@/lib/data/files";
import { loadAndProfile, ProfileError } from "@/lib/data/load";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type RouteContext = { params: Promise<{ file_id: string }> };

function projectFromQuery(request: Request) {
  return resolveProjectFromRequest(request);
}

export async function GET(request: Request, { params }: RouteContext) {
  const project = projectFromQuery(request);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });
  const { file_id } = await params;
  const preview = readPreview(project.path, file_id);
  if (!preview) return Response.json({ error: "preview not found" }, { status: 404 });
  return Response.json({ dataframe: preview });
}

export async function POST(request: Request, { params }: RouteContext) {
  const project = projectFromQuery(request);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });
  const { file_id } = await params;

  let body: { column_overrides?: Record<string, string> } = {};
  try {
    body = (await request.json()) as { column_overrides?: Record<string, string> };
  } catch {
    /* empty body is fine — re-runs preview with no overrides */
  }

  const existing = readPreview(project.path, file_id);
  if (!existing) return Response.json({ error: "preview not found" }, { status: 404 });

  const raw = rawFilePath(project.path, file_id);
  if (!raw) {
    return Response.json({ error: "raw file missing — re-upload required" }, { status: 410 });
  }

  try {
    const artifact = await loadAndProfile({
      rawPath: raw,
      fileId: file_id,
      filename: existing.filename,
      projectSlug: project.slug,
      projectPath: project.path,
      uploadedAt: existing.uploaded_at,
      columnOverrides: body.column_overrides ?? {},
    });
    return Response.json({ dataframe: artifact });
  } catch (err) {
    if (err instanceof ProfileError) {
      return Response.json({ error: err.message }, { status: err.status });
    }
    return Response.json(
      { error: err instanceof Error ? err.message : "profile failed" },
      { status: 500 },
    );
  }
}

export async function DELETE(request: Request, { params }: RouteContext) {
  const project = projectFromQuery(request);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });
  const { file_id } = await params;
  const removed = removeFile(project.path, file_id);
  if (!removed) return Response.json({ error: "file not found" }, { status: 404 });
  return Response.json({ removed: true });
}
