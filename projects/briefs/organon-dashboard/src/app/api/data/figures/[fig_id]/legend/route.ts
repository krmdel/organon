import { resolveProjectFromRequest } from "@/lib/projects";
import { runClaude } from "@/lib/claude-runner";
import { readFigure, listFigures, saveFigure } from "@/lib/figures/store";
import type { LegendHistoryEntry } from "@/lib/artifacts/types";
import { streamTaskAsSse } from "@/lib/tasks/sse-helper";
import type { TaskEvent } from "@/lib/tasks/registry";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Phase 24 (v1.2) — legend history cap. Older entries drop on append.
 * Constant lives at the route boundary; legend-card never hides
 * entries.
 */
export const MAX_LEGEND_HISTORY = 20;

type Params = { params: Promise<{ fig_id: string }> };

type Body = {
  project?: string;
  /** Optional steering prompt for the "Refine with prompt" affordance. */
  refine_prompt?: string;
};

/**
 * Phase 19 (v1.1+) — F-5 detailed-legend generator.
 *
 * SSE route. Spawns sci-writing in `mode=generate-figure-legend` with
 * the figure metadata + neighbouring figure context. Persists the
 * emitted multi-paragraph legend onto `figure.detailed_legend` via
 * the existing saveFigure round-trip so the version + sidecar stay
 * consistent.
 *
 * Decisions per the v1.1 brief §7.3:
 *  - Only LOCKED figures generate legends (409 otherwise). An unlocked
 *    figure could mutate via a future edit pass, invalidating the
 *    legend.
 *  - Iterative-edit reuses the same route — `Refine with prompt` sends
 *    a `refine_prompt` body field; the skill takes it as a follow-up
 *    directive.
 *  - Legend lives on the figure artifact (not a sibling file). Sister
 *    figures already share `figure.json` schema; legend belongs there.
 */
export async function POST(request: Request, ctx: Params) {
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
  const { fig_id } = await ctx.params;
  const figure = readFigure(project.path, fig_id);
  if (!figure) {
    return Response.json({ error: "figure not found" }, { status: 404 });
  }
  if (!figure.locked) {
    return Response.json(
      {
        error: "Figure must be locked before a detailed legend can be generated. Lock the active version first.",
        fig_id,
      },
      { status: 409 },
    );
  }

  // Sister figure context — pulls captions + alt_text + kind from the
  // other figures in the project so the legend can reference them by
  // shape (e.g. "Figure 2 shows the same metric over the cohort split").
  const sisterFigures = listFigures(project.path)
    .filter((f) => f.id !== figure.id)
    .map((f) => ({
      id: f.id,
      version: f.version,
      kind: f.kind,
      caption: f.caption ?? null,
      alt_text: f.alt_text ?? null,
    }));

  const refinePrompt = (body.refine_prompt ?? "").trim();

  const fullPrompt = [
    `Use the sci-writing skill in figure-legend-generate mode (Step 7.9) to draft a detailed multi-paragraph legend.`,
    ``,
    `active_project_slug=${project.slug}`,
    `fig_id=${figure.id}`,
    `version=${figure.version}`,
    `mode=generate-figure-legend`,
    ``,
    `figure_meta=${JSON.stringify({
      kind: figure.kind,
      caption: figure.caption ?? null,
      alt_text: figure.alt_text ?? null,
      data_source: figure.data_source ?? null,
      backend: figure.backend,
    })}`,
    ``,
    `sister_figures=${JSON.stringify(sisterFigures)}`,
    ``,
    refinePrompt
      ? `refine_prompt=${refinePrompt}`
      : `refine_prompt=(none — produce a balanced, hedged 2–4 paragraph legend grounded in the figure metadata.)`,
    ``,
    `Emit ONE \`{"_artifact":"figure-legend","fig_id":"${figure.id}","detailed_legend":"<multi-paragraph markdown>"}\` JSON line on stdout (no code fence). The dashboard will persist it onto figure.detailed_legend.`,
  ].join("\n");

  // Phase 44 (v1.5) — F7: registry-backed runner.
  const proj = project;
  const fig = figure;
  async function* runner(): AsyncGenerator<TaskEvent, void, unknown> {
    const abort = new AbortController();
    let stdoutAccumulated = "";
    let lastExit: { code: number | null; reason?: string; success?: boolean; message?: string } | null = null;
    let persistedLegend: string | null = null;

    const tryPersistLegend = (rawLegend: string): boolean => {
      const cleaned = rawLegend.trim();
      if (!cleaned) return false;
      const prior = fig.legend_history ?? [];
      const next_version =
        prior.length === 0 ? 1 : Math.max(...prior.map((e) => e.version)) + 1;
      const newEntry: LegendHistoryEntry = {
        version: next_version,
        text: cleaned,
        refine_prompt: refinePrompt || null,
        created_at: new Date().toISOString(),
      };
      const merged = [...prior, newEntry].slice(-MAX_LEGEND_HISTORY);
      const next = {
        ...fig,
        detailed_legend: cleaned,
        legend_history: merged,
      };
      saveFigure(proj.path, next);
      persistedLegend = cleaned;
      return true;
    };

    try {
      for await (const evt of runClaude({
        projectPath: proj.path,
        projectSlug: proj.slug,
        prompt: fullPrompt,
        skill: "sci-writing",
        abortSignal: abort.signal,
      })) {
        yield { type: evt.type, data: evt };
        if (evt.type === "exit") lastExit = evt;
        if (evt.type === "stdout") stdoutAccumulated += evt.chunk;
      }

      if (lastExit?.success) {
        for (const line of stdoutAccumulated.split("\n")) {
          const trimmed = line.trim();
          if (!trimmed.startsWith('{"_artifact":"figure-legend"')) continue;
          try {
            const obj = JSON.parse(trimmed) as { fig_id?: string; detailed_legend?: string };
            if (obj.fig_id === fig.id && typeof obj.detailed_legend === "string") {
              if (tryPersistLegend(obj.detailed_legend)) {
                yield { type: "artifact", data: { fig_id: fig.id, detailed_legend: persistedLegend } };
              }
              break;
            }
          } catch { /* malformed JSON line — ignore */ }
        }
      }

      const reason = lastExit?.success
        ? persistedLegend
          ? "succeeded"
          : "succeeded-no-artifact"
        : (lastExit?.reason ?? "failed");

      yield {
        type: "done",
        data: {
          fig_id: fig.id,
          success: lastExit?.success ?? false,
          persisted: persistedLegend !== null,
          reason,
          exit_code: lastExit?.code ?? null,
          message: lastExit?.message,
        },
      };
    } catch (err) {
      yield { type: "error", data: { message: err instanceof Error ? err.message : String(err) } };
    }
  }

  return streamTaskAsSse({
    kind: "figure-legend",
    project_slug: proj.slug,
    project_path: proj.path,
    scope: fig.id,
    payload: { fig_id: fig.id, version: fig.version },
    runner,
  });
}
