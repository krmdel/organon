import { resolveProjectFromRequest } from "@/lib/projects";
import { rawFilePath, readPreview } from "@/lib/data/files";
import { allocateRunId } from "@/lib/data/id";
import { runStatTest, StatTestError } from "@/lib/data/stat-test";

// Phase 6 (fix-sprint): /api/data/analyze pivoted from runClaude (60s+ LLM)
// to direct-Python child_process subprocess (~5s, deterministic).
// The optional LLM narrative now lives at /api/data/interpret as an opt-in
// "Interpret" button on the StatResultCard. This route returns plain JSON
// (no SSE) so the client renders the result card immediately.

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 90;

type Body = {
  project?: string;
  file_id?: string;
  recommendation: {
    test_name: string;
    test_label: string;
    params: Record<string, unknown>;
  };
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
  if (!body.recommendation?.test_name) {
    return Response.json({ error: "recommendation.test_name required" }, { status: 400 });
  }

  const isPower = body.recommendation.test_name.startsWith("power_");
  let dataPath = "";
  let fileId = "";
  if (!isPower) {
    if (!body.file_id) return Response.json({ error: "file_id required" }, { status: 400 });
    fileId = body.file_id;
    const preview = readPreview(project.path, fileId);
    if (!preview) return Response.json({ error: "preview not found" }, { status: 404 });
    const raw = rawFilePath(project.path, fileId);
    if (!raw) return Response.json({ error: "raw file missing" }, { status: 410 });
    dataPath = raw;
  }

  const runId = allocateRunId("stat");
  try {
    const result = await runStatTest({
      dataPath,
      fileId,
      runId,
      projectSlug: project.slug,
      projectPath: project.path,
      testName: body.recommendation.test_name,
      testLabel: body.recommendation.test_label,
      params: body.recommendation.params ?? {},
    });
    return Response.json({ result }, { status: 201 });
  } catch (err) {
    if (err instanceof StatTestError) {
      return Response.json({ error: err.message }, { status: err.status });
    }
    return Response.json(
      { error: err instanceof Error ? err.message : "stat test failed" },
      { status: 500 },
    );
  }
}
