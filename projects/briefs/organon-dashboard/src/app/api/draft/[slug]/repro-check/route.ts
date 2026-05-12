import { resolveProjectFromRequest } from "@/lib/projects";
import { getManuscript, listSections } from "@/lib/draft/store";
import { listLibrary } from "@/lib/lit/library";
import { listFigures } from "@/lib/figures/store";
import { listHypotheses } from "@/lib/hypothesis/store";
import { listFiles as listDataframes } from "@/lib/data/files";
import { runReproCheck } from "@/lib/draft/repro-check";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = { params: Promise<{ slug: string }> };

/**
 * Phase 54 (v2.0) — POST /api/draft/[slug]/repro-check
 *
 * Reads the manuscript + every project store, walks the cite/fig
 * references in section text, and returns a structured
 * { passed, checks } report. Designed to gate export — the UI may
 * choose to refuse the publish path when `passed === false`.
 */
export async function POST(request: Request, { params }: RouteContext) {
  const { slug } = await params;
  let body: { project?: string } = {};
  try {
    body = (await request.json()) as { project?: string };
  } catch {
    /* empty body is fine; project may come from query */
  }
  const project = resolveProjectFromRequest(request, body.project);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });
  const manuscript = getManuscript(project.path, slug);
  if (!manuscript) return Response.json({ error: "manuscript not found" }, { status: 404 });

  const sections = listSections(project.path, slug);
  const library = listLibrary(project.path);
  const figures = listFigures(project.path);
  const hypotheses = listHypotheses(project.path);
  const datasets = listDataframes(project.path);

  const report = runReproCheck({
    manuscript,
    sections,
    library,
    figures,
    hypotheses,
    datasets,
  });

  return Response.json({
    passed: report.passed,
    checks: report.checks,
    ran_at: report.ran_at,
    manuscript_slug: report.manuscript_slug,
  });
}
