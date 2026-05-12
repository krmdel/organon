import { getTask, subscribeToTask } from "@/lib/tasks/registry";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Phase 36 (v1.4) — re-attach surface for detached background tasks.
 *
 * GET /api/tasks/[task_id]/stream
 *
 * Subscribes to the registered task; replays the buffered events
 * (last 200) on connect, then forwards live events until the task
 * completes. Returns 404 if the task_id is unknown (typically because
 * the dashboard restarted and the in-memory registry was lost — the
 * client falls back to "task expired — please re-run" copy).
 */

type RouteContext = { params: Promise<{ task_id: string }> };

export async function GET(_request: Request, { params }: RouteContext) {
  const { task_id } = await params;
  const task = getTask(task_id);
  if (!task) {
    return Response.json(
      { error: "task not found", task_id },
      { status: 404 },
    );
  }

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

      // First event identifies the re-attached task so the client can
      // confirm it landed on the right id.
      send("task-attached", {
        task_id,
        kind: task.kind,
        project_slug: task.project_slug,
        scope: task.scope,
        replay_count: task.events.length,
        done: task.done,
      });

      // Buffer of "task-completed" events arrives at the end of the
      // replay; the client closes the stream on that event.
      const handle = subscribeToTask(task_id, (evt) => {
        send(evt.type, evt.data);
        if (evt.type === "task-completed") {
          try { controller.close(); } catch { /* ignore */ }
        }
      });
      unsubscribe = handle;

      // If subscribeToTask returned null (race against eviction), close
      // immediately with a synthetic done.
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
