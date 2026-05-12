import { resolveProjectFromRequest } from "@/lib/projects";
import { runClaude } from "@/lib/claude-runner";
import { extractArtifactsFromChunk } from "@/lib/artifacts/parser";
import { persistArtifact } from "@/lib/artifacts/persist";
import { getHypothesis } from "@/lib/hypothesis/store";
import { listCritiques } from "@/lib/hypothesis/critiques";
import {
  registerTask,
  subscribeToTask,
  type TaskEvent,
} from "@/lib/tasks/registry";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Body = {
  project?: string;
  hyp_id?: string;
};

/**
 * Phase 36 (v1.4) — runner generator. Owns the AbortController and the
 * artifact-persistence side effects. Yields TaskEvent values that the
 * registry buffers + forwards to subscribers. The route's request
 * lifetime is decoupled from this runner — navigating away does NOT
 * abort the underlying skill subprocess. The 10-minute eviction in the
 * registry handles cleanup when the user never re-attaches.
 */
async function* reconcileRunner(opts: {
  projectPath: string;
  projectSlug: string;
  prompt: string;
}): AsyncGenerator<TaskEvent, void, unknown> {
  const abort = new AbortController();
  let stdoutBuffer = "";
  let lastExit: {
    code: number | null;
    reason?: string;
    success?: boolean;
    message?: string;
  } | null = null;

  try {
    for await (const evt of runClaude({
      projectPath: opts.projectPath,
      projectSlug: opts.projectSlug,
      prompt: opts.prompt,
      skill: "sci-hypothesis",
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
          const persistedAt = persistArtifact(opts.projectPath, art);
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
  const hypId = body.hyp_id?.trim();
  if (!hypId) {
    return Response.json({ error: "hyp_id required" }, { status: 400 });
  }
  const hypothesis = getHypothesis(project.path, hypId);
  if (!hypothesis) {
    return Response.json({ error: "Hypothesis not found" }, { status: 404 });
  }
  const allCritiques = listCritiques(project.path, hypId);
  // Phase 43 (v1.5) — F6: filter out user-discarded personas from the
  // synthesis prompt. Discard is reversible — the on-disk critique
  // stays put; the reconcile prompt just doesn't see it. Hard requires
  // at least one INCLUDED critique to reconcile; if every critique was
  // excluded the user has effectively asked for nothing.
  const excluded = Array.isArray(hypothesis.excluded_persona_ids)
    ? hypothesis.excluded_persona_ids
    : [];
  const excludedSet = new Set(excluded);
  const critiques = allCritiques.filter(
    (c) => !excludedSet.has(c.persona_slug),
  );
  if (allCritiques.length === 0) {
    return Response.json(
      { error: "Hypothesis must have ≥1 critique to reconcile" },
      { status: 409 },
    );
  }
  if (critiques.length === 0) {
    return Response.json(
      {
        error: "All critiques are excluded — restore at least one before reconcile",
        excluded_personas: Array.from(excludedSet),
      },
      { status: 409 },
    );
  }

  const personasList = hypothesis.personas_used
    .filter((p) => {
      // personas_used carries display names; exclusion is by slug. The
      // critique loop above already enforced the slug-level filter, so
      // we mirror it here from the included critiques' display names.
      const included = new Set(critiques.map((c) => c.persona));
      return included.has(p);
    })
    .join(", ");
  const critiqueRefs = critiques
    .map((c) => `${c.persona}=${c.library_path}`)
    .join("; ");
  const promptLines = [
    "Use the sci-hypothesis skill to synthesize the hypothesis.",
    `Reconcile the per-persona critiques into one synthesis card per the dashboard contract.`,
    `active_project_slug=${project.slug}`,
    `hypothesis_id=${hypothesis.id}`,
    `claim=${hypothesis.claim}`,
    `personas_used=[${personasList}]`,
    `linked_papers=[${hypothesis.paper_ids.join(", ")}]`,
    `critique_files=[${critiqueRefs}]`,
  ];
  if (excludedSet.size > 0) {
    promptLines.push(
      `excluded_personas=[${Array.from(excludedSet).join(", ")}]  // user-discarded; do NOT consult these in the synthesis`,
      `note=Synthesis ran with ${critiques.length} of ${allCritiques.length} personas (excluded: ${Array.from(excludedSet).join(", ")}).`,
    );
  }
  promptLines.push(
    "Emit ONE _artifact: hypothesis JSON line at the end with status='synthesized', synthesis_text, open_questions[] (≥1), and experiment_design.",
  );
  const prompt = promptLines.join("\n");

  // Phase 36 (v1.4) — register the runner with the task registry. The
  // runner outlives this request; the user can re-attach via
  // /api/tasks/[task_id]/stream. NOTE: we deliberately do NOT bind the
  // runner to request.signal — that's the bug Phase 36 fixes.
  const task_id = registerTask({
    kind: "reconcile",
    project_slug: project.slug,
    project_path: project.path,
    scope: hypothesis.id,
    payload: { hypothesis_id: hypothesis.id },
    source: reconcileRunner({
      projectPath: project.path,
      projectSlug: project.slug,
      prompt,
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
        } catch { /* controller closed */ }
      };

      // First event identifies the task so the client can persist it
      // to localStorage and re-attach after navigation.
      send("task-started", {
        task_id,
        kind: "reconcile",
        scope: hypothesis.id,
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
