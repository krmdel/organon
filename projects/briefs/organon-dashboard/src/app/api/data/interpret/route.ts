import { resolveProjectFromRequest } from "@/lib/projects";
import { readResult } from "@/lib/results/store";
import { runClaude } from "@/lib/claude-runner";
import { streamTaskAsSse } from "@/lib/tasks/sse-helper";
import type { TaskEvent } from "@/lib/tasks/registry";

// Phase 6 (fix-sprint): opt-in LLM narrative for a stat result.
// /api/data/analyze runs the deterministic numeric path; this route is fired
// only when the user clicks "Interpret" on a result card. Streams a plain-
// English narrative back via SSE; the response is transient and not persisted.

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Body = {
  project?: string;
  run_id?: string;
};

function summarisePicked(result: ReturnType<typeof readResult>): string {
  if (!result) return "(missing result)";
  const stat = result.test_statistic ?? null;
  const eff = result.effect_size
    ? `${result.effect_size.name}=${Number(result.effect_size.value).toFixed(3)}`
    : "(no effect size)";
  const checks = (result.assumption_checks ?? [])
    .map((a) => `${a.name}=${a.verdict}${a.p_value !== undefined ? ` (p=${a.p_value.toFixed(3)})` : ""}`)
    .join(", ");
  return [
    `test=${result.test_name} (${result.test_label})`,
    `n=${result.n}`,
    `statistic=${stat}`,
    `p=${result.p_value}`,
    `effect=${eff}`,
    `assumptions=${checks || "(none recorded)"}`,
    `params=${JSON.stringify(result.params)}`,
  ].join("\n");
}

export async function POST(request: Request) {
  let body: Body;
  try {
    body = (await request.json()) as Body;
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  const project = resolveProjectFromRequest(request, body.project);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });
  if (!body.run_id) return Response.json({ error: "run_id required" }, { status: 400 });

  const result = readResult(project.path, body.run_id);
  if (!result) return Response.json({ error: "result not found" }, { status: 404 });

  const summary = summarisePicked(result);
  const prompt = [
    `Use the sci-data-analysis skill on this run.`,
    ``,
    `active_project_slug=${project.slug}`,
    `run_id=${body.run_id}`,
    `mode=interpret`,
    ``,
    `A statistical test has already been executed in the dashboard's deterministic`,
    `numeric path; below is the structured result. Write ONE plain-English paragraph`,
    `(3-5 sentences) explaining what the test means in domain terms: what hypothesis`,
    `it addresses, whether the result supports or refutes it at α=0.05, what the effect`,
    `size implies practically, and any limitation flagged by the assumption checks.`,
    `Do NOT re-run the test. Do NOT emit any JSON. Plain prose only.`,
    ``,
    `Result:`,
    summary,
  ].join("\n");

  // Phase 44 (v1.5) — F7: registry-backed runner. Streams as
  // text/event-stream via the shared streamTaskAsSse helper so client
  // disconnect no longer kills the underlying skill subprocess.
  const proj = project;
  async function* runner(): AsyncGenerator<TaskEvent, void, unknown> {
    const abort = new AbortController();
    let lastExit: { code: number | null; reason?: string; success?: boolean; message?: string } | null = null;
    try {
      for await (const evt of runClaude({
        projectPath: proj.path,
        projectSlug: proj.slug,
        prompt,
        skill: "sci-data-analysis",
        abortSignal: abort.signal,
      })) {
        yield { type: evt.type, data: evt };
        if (evt.type === "exit") lastExit = evt;
      }
      yield {
        type: "done",
        data: {
          run_id: body.run_id,
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

  const runId = body.run_id;
  return streamTaskAsSse({
    kind: "data-interpret",
    project_slug: proj.slug,
    project_path: proj.path,
    scope: runId,
    payload: { run_id: runId },
    runner,
  });
}
