import { resolveProjectFromRequest } from "@/lib/projects";
import { deleteSection, getSection, patchSection } from "@/lib/draft/store";
import { extractRefs } from "@/lib/draft/parse";
import { listLibrary } from "@/lib/lit/library";
import { listFigures } from "@/lib/figures/store";
import { listHypotheses } from "@/lib/hypothesis/store";
import { listFiles as listDataframes } from "@/lib/data/files";
import type { SectionStatus, SectionType } from "@/lib/artifacts/types";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type RouteContext = { params: Promise<{ slug: string; section_id: string }> };

const TYPES: SectionType[] = [
  "title", "abstract", "introduction", "methods", "results", "discussion", "references", "custom",
];
const STATUSES: SectionStatus[] = ["draft", "reviewed", "final"];

function projectFromQuery(request: Request) {
  return resolveProjectFromRequest(request);
}

export async function GET(request: Request, { params }: RouteContext) {
  const project = projectFromQuery(request);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });
  const { slug, section_id } = await params;
  const section = getSection(project.path, slug, section_id);
  if (!section) return Response.json({ error: "section not found" }, { status: 404 });
  return Response.json({ section });
}

export async function PATCH(request: Request, { params }: RouteContext) {
  const project = projectFromQuery(request);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });
  const { slug, section_id } = await params;
  let body: Record<string, unknown> = {};
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  const patch: Parameters<typeof patchSection>[3] = {};
  if (typeof body.content_md === "string") {
    patch.content_md = body.content_md;
    const refs = extractRefs(body.content_md);
    patch.linked_figure_ids = refs.figures;
    patch.linked_paper_ids = refs.citations;
  }
  if (typeof body.status === "string" && STATUSES.includes(body.status as SectionStatus)) {
    patch.status = body.status as SectionStatus;
  }
  if (typeof body.section_type === "string" && TYPES.includes(body.section_type as SectionType)) {
    patch.section_type = body.section_type as SectionType;
  }
  if (Array.isArray(body.linked_figure_ids)) {
    patch.linked_figure_ids = body.linked_figure_ids.filter((s): s is string => typeof s === "string");
  }
  if (Array.isArray(body.linked_paper_ids)) {
    patch.linked_paper_ids = body.linked_paper_ids.filter((s): s is string => typeof s === "string");
  }

  // Phase 51 (v2.0) — Per-section linkage overrides. Validate each
  // override_* array against its store; 404 with the unknown ids when
  // any id doesn't resolve. Empty arrays are allowed (= clear the
  // override; fall back to manuscript-level).
  const overrideChecks: Array<{
    bodyKey:
      | "override_linked_paper_ids"
      | "override_linked_figure_ids"
      | "override_linked_hypothesis_ids"
      | "override_linked_dataset_ids";
    field: "papers" | "figures" | "hypotheses" | "datasets";
  }> = [
    { bodyKey: "override_linked_paper_ids", field: "papers" },
    { bodyKey: "override_linked_figure_ids", field: "figures" },
    { bodyKey: "override_linked_hypothesis_ids", field: "hypotheses" },
    { bodyKey: "override_linked_dataset_ids", field: "datasets" },
  ];
  for (const { bodyKey, field } of overrideChecks) {
    if (!Array.isArray(body[bodyKey])) continue;
    const ids = (body[bodyKey] as unknown[]).filter(
      (x): x is string => typeof x === "string",
    );
    if (ids.length > 0) {
      let known: Set<string>;
      if (field === "papers") known = new Set(listLibrary(project.path).map((p) => p.id));
      else if (field === "figures") known = new Set(listFigures(project.path).map((f) => f.id));
      else if (field === "hypotheses") known = new Set(listHypotheses(project.path).map((h) => h.id));
      else known = new Set(listDataframes(project.path).map((d) => d.id));
      const unknown = ids.filter((id) => !known.has(id));
      if (unknown.length > 0) {
        return Response.json(
          { error: `unknown override ${field} ids`, field: bodyKey, unknown },
          { status: 404 },
        );
      }
    }
    patch[bodyKey] = ids;
  }

  const updated = patchSection(project.path, slug, section_id, patch);
  if (!updated) return Response.json({ error: "section not found" }, { status: 404 });
  return Response.json({ section: updated });
}

export async function DELETE(request: Request, { params }: RouteContext) {
  const project = projectFromQuery(request);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });
  const { slug, section_id } = await params;
  const removed = deleteSection(project.path, slug, section_id);
  if (!removed) return Response.json({ error: "section not found" }, { status: 404 });
  return Response.json({ removed: true });
}
