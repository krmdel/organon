import { resolveProjectFromRequest } from "@/lib/projects";
import {
  getManuscript,
  listSections,
  saveSection,
  updateManuscript,
} from "@/lib/draft/store";
import path from "node:path";
import { organonRoot } from "@/lib/paths";
import type { SectionDraftArtifact, SectionType } from "@/lib/artifacts/types";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type RouteContext = { params: Promise<{ slug: string }> };

const TYPES: SectionType[] = [
  "title", "abstract", "introduction", "methods", "results", "discussion", "references", "custom",
];

export async function GET(request: Request, { params }: RouteContext) {
  const project = resolveProjectFromRequest(request);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });
  const { slug } = await params;
  const sections = listSections(project.path, slug);
  return Response.json({ slug, sections, total: sections.length });
}

type CreateBody = { project?: string; section_id: string; section_type?: SectionType; content_md?: string };

export async function POST(request: Request, { params }: RouteContext) {
  const { slug } = await params;
  let body: CreateBody;
  try {
    body = (await request.json()) as CreateBody;
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  const project = resolveProjectFromRequest(request, body.project);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });
  if (!body.section_id?.trim()) return Response.json({ error: "section_id required" }, { status: 400 });
  const sectionType = body.section_type && TYPES.includes(body.section_type) ? body.section_type : "custom";

  const meta = getManuscript(project.path, slug);
  if (!meta) return Response.json({ error: "manuscript not found" }, { status: 404 });

  const existing = listSections(project.path, slug);
  if (existing.some((s) => s.section_id === body.section_id)) {
    return Response.json({ error: "section_id already exists" }, { status: 409 });
  }

  const now = new Date().toISOString();
  const content = body.content_md ?? `## ${body.section_id}\n\n_Drafting…_\n`;
  const file = path.join(project.path, "manuscripts", slug, "sections", `${body.section_id}.md`);

  const artifact: SectionDraftArtifact = {
    _artifact: "section-draft",
    schema_version: 1,
    id: `sect-${slug}-${body.section_id}`,
    manuscript_slug: slug,
    section_id: body.section_id,
    section_type: sectionType,
    status: "draft",
    content_md: content,
    linked_figure_ids: [],
    linked_paper_ids: [],
    version: 1,
    library_path: path.relative(organonRoot(), file),
    updated_at: now,
  };
  saveSection(project.path, artifact);
  updateManuscript(project.path, slug, {
    ordering: [...meta.ordering, body.section_id],
  });
  return Response.json({ section: artifact }, { status: 201 });
}
