import { resolveProjectFromRequest } from "@/lib/projects";
import { readFigure, saveFigure } from "@/lib/figures/store";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Params = { params: Promise<{ fig_id: string; legend_version: string }> };

type Body = {
  project?: string;
  /** Required gate. POST without revert:true is rejected. */
  revert?: boolean;
};

/**
 * Phase 24 (v1.2) — F-5+ legend revert.
 *
 * POST /api/data/figures/[fig_id]/legend/[legend_version] with body
 * `{ revert: true }` reverts `figure.detailed_legend` to the named
 * history entry's text. Routing under a [legend_version] sub-segment
 * keeps the intent unambiguous (the parent POST = generate; this POST
 * = revert) and reserves the segment for future per-version actions
 * (e.g. delete, export, pin).
 *
 * The history entry is NEVER deleted — soft-archive over hard-delete
 * (per Phase 19 / 24 brief decision; entries only drop via the
 * MAX_LEGEND_HISTORY cap on append).
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
  if (body.revert !== true) {
    return Response.json(
      { error: "Body must include revert: true" },
      { status: 400 },
    );
  }
  const { fig_id, legend_version } = await ctx.params;
  const targetVersion = Number.parseInt(legend_version, 10);
  if (!Number.isFinite(targetVersion) || targetVersion < 1) {
    return Response.json(
      { error: "legend_version must be a positive integer" },
      { status: 400 },
    );
  }
  const figure = readFigure(project.path, fig_id);
  if (!figure) {
    return Response.json({ error: "figure not found" }, { status: 404 });
  }
  const history = figure.legend_history ?? [];
  const entry = history.find((e) => e.version === targetVersion);
  if (!entry) {
    return Response.json(
      { error: `legend_history entry v${targetVersion} not found` },
      { status: 404 },
    );
  }
  const next = { ...figure, detailed_legend: entry.text };
  saveFigure(project.path, next);
  return Response.json({
    fig_id: figure.id,
    reverted_to: targetVersion,
    detailed_legend: entry.text,
  });
}
