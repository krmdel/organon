import { resolveProjectFromRequest } from "@/lib/projects";
import { runClaude } from "@/lib/claude-runner";
import { extractArtifactsFromChunk } from "@/lib/artifacts/parser";
import { persistArtifact } from "@/lib/artifacts/persist";
import { streamTaskAsSse } from "@/lib/tasks/sse-helper";
import type { TaskEvent } from "@/lib/tasks/registry";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Body = {
  project?: string;
  skill?: string;
  prompt?: string;
};

export async function POST(request: Request) {
  let body: Body;
  try {
    body = (await request.json()) as Body;
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const project = resolveProjectFromRequest(request, body.project);
  if (!project) {
    return Response.json({ error: "Unknown project" }, { status: 404 });
  }
  const userPrompt = (body.prompt ?? "").trim();
  if (!userPrompt) {
    return Response.json({ error: "Prompt is required" }, { status: 400 });
  }

  // If a skill was selected, prepend an explicit invocation so claude code
  // routes deterministically. Keeps the user's textarea clean.
  const prompt = body.skill ? `Use the ${body.skill} skill on the following:\n\n${userPrompt}` : userPrompt;

  // Phase 44 (v1.5) — F7: registry-backed runner.
  const proj = project;
  async function* runner(): AsyncGenerator<TaskEvent, void, unknown> {
    const abort = new AbortController();
    let stdoutBuffer = "";
    let lastExit: { code: number | null; reason?: string; success?: boolean; message?: string } | null = null;
    try {
      for await (const evt of runClaude({
        projectPath: proj.path,
        projectSlug: proj.slug,
        prompt,
        skill: body.skill,
        abortSignal: abort.signal,
      })) {
        yield { type: evt.type, data: evt };
        if (evt.type === "exit") lastExit = evt;
        if (evt.type === "stdout") {
          const { artifacts, remainder } = extractArtifactsFromChunk(stdoutBuffer, evt.chunk);
          stdoutBuffer = remainder;
          for (const art of artifacts) {
            const persistedAt = persistArtifact(proj.path, art);
            yield { type: "artifact", data: { artifact: art, persisted_at: persistedAt } };
          }
        }
      }
      yield {
        type: "done",
        data: {
          success: lastExit?.success ?? false,
          reason: lastExit?.reason ?? "failed",
          exit_code: lastExit?.code ?? null,
          message: lastExit?.message,
        },
      };
    } catch (err) {
      yield { type: "error", data: { message: err instanceof Error ? err.message : String(err) } };
    }
  }

  return streamTaskAsSse({
    kind: "execute",
    project_slug: proj.slug,
    project_path: proj.path,
    scope: body.skill ?? "free-form",
    payload: { skill: body.skill ?? null },
    runner,
  });
}
