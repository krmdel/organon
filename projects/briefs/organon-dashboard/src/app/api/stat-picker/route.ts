import { resolveProjectFromRequest } from "@/lib/projects";
import { readPreview } from "@/lib/data/files";
import { recommendTests, type WizardAnswers } from "@/lib/data/stat-picker";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type Body = {
  project?: string;
  file_id?: string;
  answers?: WizardAnswers;
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
  if (!body.answers) return Response.json({ error: "answers required" }, { status: 400 });

  const preview = readPreview(project.path, body.file_id);
  if (!preview) return Response.json({ error: "preview not found" }, { status: 404 });

  const result = recommendTests(preview, body.answers);
  if ("error" in result) return Response.json(result, { status: 400 });
  return Response.json(result);
}
