import { resolveProjectFromRequest } from "@/lib/projects";
import {
  deleteManuscript,
  getManuscript,
  listSections,
  updateManuscript,
  type CitationStyle,
} from "@/lib/draft/store";
import { listLibrary } from "@/lib/lit/library";
import { listFigures } from "@/lib/figures/store";
import { listHypotheses } from "@/lib/hypothesis/store";
import { listFiles as listDataframes } from "@/lib/data/files";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const STYLES: CitationStyle[] = ["apa", "nature", "ieee", "vancouver"];

/**
 * Phase 41 (v1.5) — F4: validate linkage ids against the corresponding
 * store. Returns the list of unknown ids (empty when everything checks
 * out). Used by PATCH to short-circuit with a 404 before writing.
 */
function validateLinkageIds(
  projectPath: string,
  field: "hypotheses" | "papers" | "figures" | "datasets",
  ids: string[],
): string[] {
  if (ids.length === 0) return [];
  let known: Set<string>;
  if (field === "papers") {
    known = new Set(listLibrary(projectPath).map((p) => p.id));
  } else if (field === "figures") {
    known = new Set(listFigures(projectPath).map((f) => f.id));
  } else if (field === "hypotheses") {
    known = new Set(listHypotheses(projectPath).map((h) => h.id));
  } else {
    known = new Set(listDataframes(projectPath).map((d) => d.id));
  }
  return ids.filter((id) => !known.has(id));
}

function sanitizeIds(v: unknown): string[] {
  if (!Array.isArray(v)) return [];
  return v.filter((x): x is string => typeof x === "string");
}

type RouteContext = { params: Promise<{ slug: string }> };

function projectFromQuery(request: Request) {
  return resolveProjectFromRequest(request);
}

export async function GET(request: Request, { params }: RouteContext) {
  const project = projectFromQuery(request);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });
  const { slug } = await params;
  const meta = getManuscript(project.path, slug);
  if (!meta) return Response.json({ error: "manuscript not found" }, { status: 404 });
  const sections = listSections(project.path, slug);
  return Response.json({ manuscript: meta, sections });
}

export async function PATCH(request: Request, { params }: RouteContext) {
  const project = projectFromQuery(request);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });
  const { slug } = await params;
  let body: Record<string, unknown> = {};
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  const allowed: Record<string, unknown> = {};
  if (typeof body.title === "string") allowed.title = body.title.trim();
  if (Array.isArray(body.authors)) allowed.authors = body.authors.filter((a): a is string => typeof a === "string");
  if (body.target_journal === null || typeof body.target_journal === "string") {
    allowed.target_journal = body.target_journal as string | null;
  }
  if (typeof body.citation_style === "string" && STYLES.includes(body.citation_style as CitationStyle)) {
    allowed.citation_style = body.citation_style;
  }
  if (Array.isArray(body.ordering)) {
    allowed.ordering = body.ordering.filter((id): id is string => typeof id === "string");
  }

  // Phase 41 (v1.5) — F4: validate each linkage array against its store.
  // 404 with the unknown ids when any id doesn't resolve. Hard-validate
  // only on user-driven write; reads stay tolerant of stale ids that
  // surface as "missing" in the panel (Decision §5.3).
  const linkageChecks: Array<{
    bodyKey: "linked_hypothesis_ids" | "linked_paper_ids" | "linked_figure_ids" | "linked_dataset_ids";
    field: "hypotheses" | "papers" | "figures" | "datasets";
  }> = [
    { bodyKey: "linked_hypothesis_ids", field: "hypotheses" },
    { bodyKey: "linked_paper_ids", field: "papers" },
    { bodyKey: "linked_figure_ids", field: "figures" },
    { bodyKey: "linked_dataset_ids", field: "datasets" },
  ];
  for (const { bodyKey, field } of linkageChecks) {
    if (!Array.isArray(body[bodyKey])) continue;
    const ids = sanitizeIds(body[bodyKey]);
    const unknown = validateLinkageIds(project.path, field, ids);
    if (unknown.length > 0) {
      return Response.json(
        { error: `unknown ${field} ids`, field: bodyKey, unknown },
        { status: 404 },
      );
    }
    allowed[bodyKey] = ids;
  }

  const updated = updateManuscript(project.path, slug, allowed);
  if (!updated) return Response.json({ error: "manuscript not found" }, { status: 404 });
  return Response.json({ manuscript: updated });
}

/**
 * Phase 62 (v2.2) — M1: hard delete a manuscript and its section files.
 * Mirrors Phase 58's hypothesis DELETE wiring. The on-disk cascade lives
 * in `deleteManuscript` (recursive rmSync). 400 on missing project, 404
 * on unknown slug.
 */
export async function DELETE(request: Request, { params }: RouteContext) {
  const project = projectFromQuery(request);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 400 });
  const { slug } = await params;
  if (!getManuscript(project.path, slug)) {
    return Response.json({ error: "manuscript not found" }, { status: 404 });
  }
  deleteManuscript(project.path, slug);
  return Response.json({ ok: true, deleted: slug });
}
