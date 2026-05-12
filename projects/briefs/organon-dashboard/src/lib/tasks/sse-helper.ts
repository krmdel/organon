// Phase 44 (v1.5) — F7: shared registry-backed SSE helper.
//
// Boilerplate-eliminator for the 11 SSE routes that retrofit Phase 36's
// detachable-runner pattern. Each route shrinks to:
//
//   return streamTaskAsSse({
//     kind: "...",
//     project_slug, project_path, scope, payload,
//     runner: async function*() {
//       // existing per-route work, yielding TaskEvent
//     },
//   });
//
// Dropping `request.signal.addEventListener("abort", …)` is implicit —
// this helper never binds to it. Client disconnect closes the SSE
// subscriber but the registered runner drains to completion.

import {
  registerTask,
  subscribeToTask,
  type TaskEvent,
} from "./registry";

export function streamTaskAsSse(opts: {
  kind: string;
  project_slug: string;
  project_path: string;
  scope: string;
  payload?: Record<string, unknown> | null;
  runner: () => AsyncGenerator<TaskEvent, void, unknown>;
}): Response {
  const task_id = registerTask({
    kind: opts.kind,
    project_slug: opts.project_slug,
    project_path: opts.project_path,
    scope: opts.scope,
    payload: opts.payload ?? null,
    source: opts.runner(),
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
      send("task-started", {
        task_id,
        kind: opts.kind,
        scope: opts.scope,
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
