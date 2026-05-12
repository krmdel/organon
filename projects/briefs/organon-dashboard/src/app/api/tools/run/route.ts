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
  tool_id?: string;
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
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });
  const toolId = body.tool_id?.trim();
  if (!toolId) return Response.json({ error: "tool_id required" }, { status: 400 });
  const userPrompt = (body.prompt ?? "").trim();
  if (!userPrompt) return Response.json({ error: "prompt required" }, { status: 400 });

  // MCP tools aren't directly invokable from the dashboard process — surface a
  // pointer to the CLI invocation. Local skills route through claude-runner.
  if (toolId.startsWith("mcp:")) {
    return Response.json(
      {
        error: "MCP tools are not directly invokable from the dashboard process. Invoke them through a skill that wraps the MCP, or use Claude Code's CLI.",
        hint: `claude -p "Use the ${toolId.slice(4)} MCP server to ${userPrompt}"`,
      },
      { status: 501 },
    );
  }

  const skillName = toolId; // Local skill ids are 1:1 with skill folder names.
  const fullPrompt = `Use the ${skillName} skill on the following:\n\n${userPrompt}\n\nactive_project_slug=${project.slug}`;

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
        prompt: fullPrompt,
        skill: skillName,
        abortSignal: abort.signal,
      })) {
        yield { type: evt.type, data: evt };
        if (evt.type === "exit") lastExit = evt;
        if (evt.type === "stdout") {
          const { artifacts, remainder } = extractArtifactsFromChunk(stdoutBuffer, evt.chunk);
          stdoutBuffer = remainder;
          for (const art of artifacts) {
            const persisted = persistArtifact(proj.path, art);
            yield { type: "artifact", data: { artifact: art, persisted_at: persisted } };
          }
        }
      }
      yield {
        type: "done",
        data: {
          tool_id: toolId,
          success: lastExit?.success ?? false,
          reason: lastExit?.reason ?? "failed",
          exit_code: lastExit?.code ?? null,
          message: lastExit?.message,
        },
      };
    } catch (err) {
      yield {
        type: "error",
        data: { message: err instanceof Error ? err.message : String(err) },
      };
    }
  }

  return streamTaskAsSse({
    kind: "tools-run",
    project_slug: proj.slug,
    project_path: proj.path,
    scope: toolId,
    payload: { tool_id: toolId },
    runner,
  });
}
