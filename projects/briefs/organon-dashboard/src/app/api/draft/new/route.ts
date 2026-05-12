import { resolveProjectFromRequest } from "@/lib/projects";
import { createManuscript, existingSlugs, type CitationStyle } from "@/lib/draft/store";
import { allocateManuscriptSlug } from "@/lib/draft/slug";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const STYLES: CitationStyle[] = ["apa", "nature", "ieee", "vancouver"];

type Body = {
  project?: string;
  title?: string;
  authors?: string[];
  target_journal?: string | null;
  citation_style?: CitationStyle;
  /** Phase 41 (v1.5) — F4: optional source linkage arrays. */
  linked_hypothesis_ids?: string[];
  linked_paper_ids?: string[];
  linked_figure_ids?: string[];
  linked_dataset_ids?: string[];
};

function sanitizeIds(v: unknown): string[] {
  if (!Array.isArray(v)) return [];
  return v.filter((x): x is string => typeof x === "string");
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
  const title = body.title?.trim();
  if (!title) return Response.json({ error: "title required" }, { status: 400 });
  const style = body.citation_style && STYLES.includes(body.citation_style)
    ? body.citation_style
    : "apa";

  const slug = allocateManuscriptSlug(title, existingSlugs(project.path));
  const { meta, sections } = createManuscript(project.path, slug, {
    title,
    authors: body.authors ?? [],
    target_journal: body.target_journal ?? null,
    citation_style: style,
    linked_hypothesis_ids: sanitizeIds(body.linked_hypothesis_ids),
    linked_paper_ids: sanitizeIds(body.linked_paper_ids),
    linked_figure_ids: sanitizeIds(body.linked_figure_ids),
    linked_dataset_ids: sanitizeIds(body.linked_dataset_ids),
  });
  return Response.json({ manuscript: meta, sections }, { status: 201 });
}
