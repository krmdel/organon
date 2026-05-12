import { resolveProjectFromRequest } from "@/lib/projects";
import { runClaude } from "@/lib/claude-runner";
import { extractArtifactsFromChunk } from "@/lib/artifacts/parser";
import { persistArtifact } from "@/lib/artifacts/persist";
import {
  classifyChatIntent,
  routeChatIntent,
  type ChatIntent,
} from "@/lib/data/chat-intent";
import { listFiles } from "@/lib/data/files";
import { streamTaskAsSse } from "@/lib/tasks/sse-helper";
import type { TaskEvent } from "@/lib/tasks/registry";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Body = {
  project?: string;
  file_id?: string;
  prompt?: string;
};

/**
 * Phase 21 (v1.1+) — D-6 chat-driven data analysis.
 *
 * Body: `{ project, file_id, prompt }`. Routes via classifyChatIntent
 * (keyword heuristic — v1.2 can swap in an LLM router) to either
 * sci-hypothesis (stat-test path) or sci-data-analysis (plot / summary
 * path), then streams stdout, persists emitted artifacts via the
 * existing parser + persister, and emits a `done` event.
 *
 * Decisions per v1.1 brief §9.3:
 *  - Heuristic classifier — small, deterministic, no LLM round-trip.
 *  - Transcript ephemeral — each call is one-shot; chat-panel state is
 *    in-memory only.
 *  - file_id required — no file → 400.
 *  - Reuse extractArtifactsFromChunk + persistArtifact (same path as
 *    /api/execute), so chat-emitted stat-results / figures show up in
 *    the existing Stats / Plots tabs without bespoke persistence.
 */
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
  if (!body.file_id) {
    return Response.json({ error: "file_id required" }, { status: 400 });
  }
  const prompt = (body.prompt ?? "").trim();
  if (!prompt) {
    return Response.json({ error: "prompt required" }, { status: 400 });
  }
  const dataframe = listFiles(project.path).find((f) => f.id === body.file_id);
  if (!dataframe) {
    return Response.json({ error: "file not found" }, { status: 404 });
  }

  // Phase 26 (v1.2) — D-6+ LLM-routed classification with keyword
  // fallback. The helper resolves `${baseUrl}/api/data/chat-intent`
  // off the inbound request URL so this works equally in dev + prod.
  // classifyChatIntent imported as a last-ditch safety net (and to
  // preserve the v1.1 import surface for static-text contract tests).
  const baseUrl = new URL(request.url).origin;
  let intent: ChatIntent;
  let intentSource: "llm" | "fallback";
  try {
    const routed = await routeChatIntent(prompt, fetch, {
      project: project.slug,
      baseUrl,
    });
    intent = routed.intent;
    intentSource = routed.source;
  } catch {
    intent = classifyChatIntent(prompt);
    intentSource = "fallback";
  }
  const skill = intent === "hypothesis" ? "sci-hypothesis" : "sci-data-analysis";

  const fullPrompt = [
    `Use the ${skill} skill to answer the researcher's question against the active dataframe.`,
    ``,
    `active_project_slug=${project.slug}`,
    `file_id=${body.file_id}`,
    `intent=${intent}`,
    `mode=chat`,
    ``,
    `dataframe_meta=${JSON.stringify({
      file_id: dataframe.id,
      filename: dataframe.filename,
      rows_total: dataframe.rows_total,
      columns: dataframe.columns.slice(0, 32).map((c) => ({ name: c.name, type: c.type })),
    })}`,
    ``,
    `researcher_question=${prompt}`,
    ``,
    intent === "hypothesis"
      ? `Run a single appropriate statistical test grounded in the question. Emit ONE \`{"_artifact":"stat-result", ...}\` JSON line on stdout.`
      : `Produce a single plot OR a summary statistics block. Emit ONE \`{"_artifact":"figure", ...}\` JSON line OR a summary in the response prose.`,
  ].join("\n");

  // Phase 44 (v1.5) — F7: registry-backed runner.
  const proj = project;
  async function* runner(): AsyncGenerator<TaskEvent, void, unknown> {
    const abort = new AbortController();
    let stdoutBuffer = "";
    let lastExit: { code: number | null; reason?: string; success?: boolean; message?: string } | null = null;
    yield { type: "intent", data: { intent, source: intentSource, skill, file_id: body.file_id } };
    try {
      for await (const evt of runClaude({
        projectPath: proj.path,
        projectSlug: proj.slug,
        prompt: fullPrompt,
        skill,
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
          intent,
          source: intentSource,
        },
      };
    } catch (err) {
      yield { type: "error", data: { message: err instanceof Error ? err.message : String(err) } };
    }
  }

  const fileId = body.file_id;
  return streamTaskAsSse({
    kind: "data-chat",
    project_slug: proj.slug,
    project_path: proj.path,
    scope: fileId,
    payload: { file_id: fileId, intent, source: intentSource },
    runner,
  });
}
