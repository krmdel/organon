import { resolveProjectFromRequest } from "@/lib/projects";
import { listTasks } from "@/lib/tasks/registry";
import { evictOldTasks } from "@/lib/tasks/eviction";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Phase 44 (v1.5) — F7: GET /api/tasks?project=<slug>.
 *
 * Returns the on-disk view of background tasks for a project:
 *   { running: TaskRecord[], recent: TaskRecord[] }
 *
 * The header tasks-panel calls this on open + on a 5s interval. The
 * call is also a convenient hook for read-time eviction — sweep
 * stale + over-cap files BEFORE returning so the panel never sees
 * orphans the user has clearly forgotten about.
 */
export async function GET(request: Request) {
  const project = resolveProjectFromRequest(request);
  if (!project) {
    return Response.json({ error: "Unknown project" }, { status: 404 });
  }
  // Read-time eviction (idempotent; never throws — failures inside
  // evictOldTasks are caught locally).
  try { evictOldTasks(project.path); } catch { /* ignore */ }
  const result = listTasks(project.path);
  return Response.json(result);
}
