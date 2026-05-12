import path from "node:path";
import { resolveProjectFromRequest } from "@/lib/projects";
import {
  getManuscript,
  getSection,
  listSections,
  saveSection,
  updateManuscript,
} from "@/lib/draft/store";
import { organonRoot } from "@/lib/paths";
import { parseNotebook } from "@/lib/draft/notebook-import";
import type { SectionDraftArtifact } from "@/lib/artifacts/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = { params: Promise<{ slug: string }> };

type Body = {
  project?: string;
  /** Optional target section_id. When omitted, a new "imported-<n>"
   *  section is appended to the manuscript ordering. */
  section_id?: string;
  /** Either the parsed Jupyter JSON or the raw `.ipynb` text. */
  notebook?: unknown;
};

function nextImportSlug(existing: string[]): string {
  let n = 1;
  const used = new Set(existing);
  while (used.has(`imported-notebook-${n}`)) n += 1;
  return `imported-notebook-${n}`;
}

/**
 * Phase 52 (v2.0) — POST /api/draft/[slug]/import-notebook
 *
 * Body: `{ project, section_id?, notebook }` where `notebook` is either
 * the parsed Jupyter JSON or the raw text. Parses via parseNotebook,
 * then either replaces the body of an existing section (when section_id
 * is present + resolves) or appends a new section to the manuscript
 * ordering. Returns the final SectionDraftArtifact.
 */
export async function POST(request: Request, { params }: RouteContext) {
  const { slug } = await params;
  let body: Body;
  try {
    body = (await request.json()) as Body;
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  const project = resolveProjectFromRequest(request, body.project);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });
  if (body.notebook === undefined || body.notebook === null) {
    return Response.json({ error: "notebook required" }, { status: 400 });
  }

  const manuscript = getManuscript(project.path, slug);
  if (!manuscript) {
    return Response.json({ error: "manuscript not found" }, { status: 404 });
  }

  const parsed = parseNotebook(body.notebook);
  if (parsed.cell_count === 0) {
    return Response.json(
      { error: "notebook had no cells (parse failed?)" },
      { status: 400 },
    );
  }

  const existingSections = listSections(project.path, slug);
  const targetId = body.section_id?.trim();

  let artifact: SectionDraftArtifact;
  const now = new Date().toISOString();

  if (targetId) {
    const existing = getSection(project.path, slug, targetId);
    if (!existing) {
      return Response.json({ error: "section not found" }, { status: 404 });
    }
    artifact = {
      ...existing,
      content_md: parsed.markdown,
      version: existing.version + 1,
      updated_at: now,
    };
  } else {
    const newId = nextImportSlug(existingSections.map((s) => s.section_id));
    const file = path.join(
      project.path,
      "manuscripts",
      slug,
      "sections",
      `${newId}.md`,
    );
    artifact = {
      _artifact: "section-draft",
      schema_version: 1,
      id: `sect-${slug}-${newId}`,
      manuscript_slug: slug,
      section_id: newId,
      section_type: "custom",
      status: "draft",
      content_md: parsed.markdown,
      linked_figure_ids: [],
      linked_paper_ids: [],
      version: 1,
      library_path: path.relative(organonRoot(), file),
      updated_at: now,
    };
    updateManuscript(project.path, slug, {
      ordering: [...manuscript.ordering, newId],
    });
  }

  saveSection(project.path, artifact);
  return Response.json(
    {
      section: artifact,
      cell_count: parsed.cell_count,
      has_outputs: parsed.has_outputs,
    },
    { status: targetId ? 200 : 201 },
  );
}
