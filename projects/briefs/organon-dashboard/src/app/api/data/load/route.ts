import { resolveProjectFromRequest } from "@/lib/projects";
import { organonRoot } from "@/lib/paths";
import { validateAndStoreUpload } from "@/lib/data/upload";
import { loadAndProfile, ProfileError } from "@/lib/data/load";
import { removeFile } from "@/lib/data/files";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const maxDuration = 60;

export async function POST(request: Request) {
  let form: FormData;
  try {
    form = await request.formData();
  } catch {
    return Response.json({ error: "Invalid multipart body" }, { status: 400 });
  }

  const formProject = form.get("project");
  const project = resolveProjectFromRequest(
    request,
    typeof formProject === "string" ? formProject : null,
  );
  if (!project) {
    return Response.json({ error: "Unknown project" }, { status: 404 });
  }

  const file = form.get("file");
  if (!file || typeof file === "string") {
    return Response.json({ error: "Missing file field" }, { status: 400 });
  }

  const stored = await validateAndStoreUpload({
    file: file as File,
    projectPath: project.path,
    organonRoot: organonRoot(),
  });
  if (!stored.ok) {
    return Response.json({ error: stored.message }, { status: stored.status });
  }

  try {
    const artifact = await loadAndProfile({
      rawPath: stored.rawPath,
      fileId: stored.fileId,
      filename: stored.filename,
      projectSlug: project.slug,
      projectPath: project.path,
      uploadedAt: stored.uploadedAt,
    });
    return Response.json({ dataframe: artifact }, { status: 201 });
  } catch (err) {
    // Profile failed: roll back the raw upload so the data dir doesn't fill
    // with files that have no preview sidecar.
    removeFile(project.path, stored.fileId);
    if (err instanceof ProfileError) {
      return Response.json({ error: err.message }, { status: err.status });
    }
    return Response.json(
      { error: err instanceof Error ? err.message : "profile failed" },
      { status: 500 },
    );
  }
}
