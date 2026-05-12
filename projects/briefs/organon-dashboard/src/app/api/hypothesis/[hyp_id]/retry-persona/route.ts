import { resolveProjectFromRequest } from "@/lib/projects";
import { runClaude } from "@/lib/claude-runner";
import { extractArtifactsFromChunk } from "@/lib/artifacts/parser";
import { persistArtifact } from "@/lib/artifacts/persist";
import { getHypothesis } from "@/lib/hypothesis/store";
import { listPersonas } from "@/lib/hypothesis/personas";
import { isPersonaActive, slugifyPersona } from "@/lib/hypothesis/shared";
import {
  registerTask,
  subscribeToTask,
  type TaskEvent,
} from "@/lib/tasks/registry";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Params = { params: Promise<{ hyp_id: string }> };

type RetryBody = {
  project?: string;
  persona_slug?: string;
};

/**
 * Phase 13b (v1.0.1) — H-5 + U4 per-persona retry.
 *
 * POST { persona_slug: string }
 *
 * Spawns sci-council in single-persona mode, streams SSE through the
 * same artifact-persister pipeline as /api/execute, and emits one
 * persona-critique JSON line for the targeted persona. The workspace
 * consumer replaces only the matching critique by slug — the existing
 * two siblings stay in place.
 *
 * Refuses on:
 *   - hypothesis archived  → 409 (council loop is closed)
 *   - hypothesis terminal  → 409 (synthesized/supported/refuted —
 *     retrying after synthesis would invalidate it without UX)
 *   - persona not in project's personas.json   → 404
 *   - persona inactive (Phase 13a)             → 409
 *
 * Phase 36 (v1.4): runner registers with the tasks registry so the
 * skill subprocess outlives the request. Drops `request.signal`
 * abort wiring — navigating away no longer kills the runner.
 */
async function* retryPersonaRunner(opts: {
  projectPath: string;
  projectSlug: string;
  prompt: string;
  personaSlug: string;
}): AsyncGenerator<TaskEvent, void, unknown> {
  const abort = new AbortController();
  const { projectPath, projectSlug, prompt, personaSlug } = opts;
  let stdoutBuffer = "";
  let lastExit: {
    code: number | null;
    reason?: string;
    success?: boolean;
    message?: string;
  } | null = null;

  try {
    for await (const evt of runClaude({
      projectPath,
      projectSlug,
      prompt,
      skill: "sci-council",
      abortSignal: abort.signal,
    })) {
      yield { type: evt.type, data: evt };
      if (evt.type === "exit") lastExit = evt;
      if (evt.type === "stdout") {
        const { artifacts, remainder } = extractArtifactsFromChunk(
          stdoutBuffer,
          evt.chunk,
        );
        stdoutBuffer = remainder;
        for (const art of artifacts) {
          // Phase 13b — single-persona-critique surgery (preserved).
          if (art._artifact !== "persona-critique") continue;
          if (art.persona_slug !== personaSlug) continue;
          const persistedAt = persistArtifact(projectPath, art);
          yield {
            type: "artifact",
            data: { artifact: art, persisted_at: persistedAt },
          };
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
    yield {
      type: "error",
      data: { message: err instanceof Error ? err.message : String(err) },
    };
  }
}

export async function POST(request: Request, ctx: Params) {
  let body: RetryBody;
  try {
    body = (await request.json()) as RetryBody;
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const project = resolveProjectFromRequest(request, body.project);
  if (!project) {
    return Response.json({ error: "Unknown project" }, { status: 404 });
  }
  const { hyp_id } = await ctx.params;
  const personaSlug = (body.persona_slug ?? "").trim();
  if (!personaSlug) {
    return Response.json({ error: "persona_slug is required" }, { status: 400 });
  }

  const hypothesis = getHypothesis(project.path, hyp_id);
  if (!hypothesis) {
    return Response.json({ error: "Hypothesis not found" }, { status: 404 });
  }
  if (hypothesis.status === "archived") {
    return Response.json(
      { error: "Cannot retry persona on archived hypothesis" },
      { status: 409 },
    );
  }
  if (
    hypothesis.status === "synthesized" ||
    hypothesis.status === "supported" ||
    hypothesis.status === "refuted"
  ) {
    return Response.json(
      {
        error: `Cannot retry persona on ${hypothesis.status} hypothesis (synthesis already produced)`,
      },
      { status: 409 },
    );
  }

  const personas = listPersonas(project.path);
  const target = personas.find((p) => slugifyPersona(p.name) === personaSlug);
  if (!target) {
    return Response.json(
      { error: `Persona not found in project: ${personaSlug}` },
      { status: 404 },
    );
  }
  if (!isPersonaActive(target)) {
    return Response.json(
      {
        error: `Persona '${target.name}' is inactive — toggle on before retrying`,
      },
      { status: 409 },
    );
  }

  // Use the persona's display name in the prompt (sci-council's
  // contract uses display names, not slugs).
  const prompt = [
    `Use the sci-council skill to retry a single persona on this hypothesis.`,
    `active_project_slug=${project.slug}`,
    `hypothesis_id=${hypothesis.id}`,
    `claim=${hypothesis.claim}`,
    `personas=[${target.name}]`,
    `linked_papers=[${hypothesis.paper_ids.join(", ")}]`,
    `Emit ONE _artifact: persona-critique JSON line on stdout for this persona only (schema: PHASE_2_TASKS.md §5.2). Do NOT emit a hypothesis artifact — the existing record already links the critique sidecars.`,
  ].join("\n");

  // Phase 36 (v1.4) — register runner with the task registry; runner
  // outlives the request. Drops the `request.signal` abort wiring.
  const task_id = registerTask({
    kind: "retry-persona",
    project_slug: project.slug,
    project_path: project.path,
    scope: `${hypothesis.id}:${personaSlug}`,
    payload: { hypothesis_id: hypothesis.id, persona_slug: personaSlug },
    source: retryPersonaRunner({
      projectPath: project.path,
      projectSlug: project.slug,
      prompt,
      personaSlug,
    }),
  });

  const encoder = new TextEncoder();
  let unsubscribe: (() => void) | null = null;

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const send = (event: string, data: unknown) => {
        try {
          controller.enqueue(
            encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`),
          );
        } catch { /* ignore */ }
      };

      send("task-started", {
        task_id,
        kind: "retry-persona",
        scope: `${hypothesis.id}:${personaSlug}`,
      });

      const handle = subscribeToTask(task_id, (evt) => {
        send(evt.type, evt.data);
        if (evt.type === "task-completed") {
          try { controller.close(); } catch { /* ignore */ }
        }
      });
      unsubscribe = handle;
      if (!handle) {
        send("done", { success: false, reason: "task-vanished" });
        try { controller.close(); } catch { /* ignore */ }
      }
    },
    cancel() {
      if (unsubscribe) unsubscribe();
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
