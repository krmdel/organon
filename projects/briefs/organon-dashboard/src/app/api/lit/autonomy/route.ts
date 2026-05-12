import { resolveProjectFromRequest } from "@/lib/projects";
import { runAutonomy } from "@/lib/lit/autonomy";
import { streamTaskAsSse } from "@/lib/tasks/sse-helper";
import type { TaskEvent } from "@/lib/tasks/registry";

// Phase 46 (v1.6) — F9: full-autonomy literature mode.
// User provides keywords + research_question; the orchestrator expands
// them into a fanout query set, runs searchPapers per variant (which
// itself does paperclip-primary routing for biomedical queries via
// Phase 45), merges + dedupes by DOI, and partitions by relevance
// threshold (Phase 47 populates the relevance_score; until then,
// everything lands in "borderline" — UI handles gracefully).

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Body = {
  project?: string;
  keywords?: string[];
  research_question?: string;
  threshold?: number;
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

  const keywords = Array.isArray(body.keywords)
    ? body.keywords.map((s) => String(s)).filter((s) => s.trim().length > 0)
    : [];
  const research_question = (body.research_question ?? "").trim();
  if (!research_question && keywords.length === 0) {
    return Response.json(
      { error: "either keywords[] or research_question is required" },
      { status: 400 },
    );
  }

  const threshold = typeof body.threshold === "number" ? body.threshold : undefined;

  const proj = project;
  // Phase 44 (v1.5) — F7: registry-backed runner. The autonomy run can
  // exceed 60s easily (4 query variants × 4 sources × network latency);
  // streamTaskAsSse keeps the runner alive across navigations.
  async function* runner(): AsyncGenerator<TaskEvent, void, unknown> {
    yield {
      type: "autonomy-started",
      data: { keywords, research_question, threshold: threshold ?? 0.6 },
    };
    try {
      const result = await runAutonomy({
        keywords,
        research_question,
        threshold,
        projectSlug: proj.slug,
      });
      yield { type: "autonomy-variants", data: { variants: result.variants } };
      for (const e of result.errors) yield { type: "error", data: { message: e } };
      for (const w of result.soft_errors) yield { type: "warn", data: { message: w } };
      yield {
        type: "autonomy-result",
        data: {
          accepted: result.accepted,
          borderline: result.borderline,
          accepted_count: result.accepted.length,
          borderline_count: result.borderline.length,
        },
      };
      yield { type: "done", data: { success: true } };
    } catch (err) {
      yield {
        type: "error",
        data: { message: err instanceof Error ? err.message : String(err) },
      };
      yield { type: "done", data: { success: false } };
    }
  }

  return streamTaskAsSse({
    kind: "lit-autonomy",
    project_slug: proj.slug,
    project_path: proj.path,
    scope: research_question || keywords.join(","),
    payload: { keywords, research_question },
    runner,
  });
}
