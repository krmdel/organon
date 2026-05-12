import { resolveProjectFromRequest } from "@/lib/projects";
import { searchPapers, type SearchSource } from "@/lib/lit/search";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const VALID_SOURCES: SearchSource[] = ["pubmed", "arxiv", "openalex", "semanticscholar", "paperclip"];

type Body = {
  project?: string;
  query?: string;
  sources?: string[];
  max_results?: number;
  publication_date?: string;
};

export async function POST(request: Request) {
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

  const query = (body.query ?? "").trim();
  if (!query) {
    return Response.json({ error: "query required" }, { status: 400 });
  }

  const sources = (body.sources ?? VALID_SOURCES).filter((s): s is SearchSource =>
    VALID_SOURCES.includes(s as SearchSource),
  );
  const maxResults = Math.min(50, Math.max(1, Number(body.max_results ?? 10)));

  try {
    const result = await searchPapers({
      query,
      sources,
      maxResults,
      publicationDate: body.publication_date,
      projectSlug: project.slug,
    });
    const payload: {
      project: string;
      query: string;
      total: number;
      results: typeof result.results;
      errors?: string[];
      soft_errors?: string[];
    } = {
      project: project.slug,
      query,
      total: result.total,
      results: result.results,
    };
    if (result.errors.length > 0) payload.errors = result.errors;
    // Phase 37 (v1.4) — B4: forward soft per-source conditions
    // (rate-limit) so the workspace can render the yellow info banner
    // distinct from red error toasts.
    if (result.soft_errors.length > 0) payload.soft_errors = result.soft_errors;
    return Response.json(payload);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return Response.json({ error: msg }, { status: 500 });
  }
}
