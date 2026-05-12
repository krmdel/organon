import { resolveProjectFromRequest } from "@/lib/projects";
import { buildIndex, searchIndex, type SearchHit } from "@/lib/search";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const VALID_TYPES: SearchHit["type"][] = ["paper", "hypothesis", "figure", "section", "manuscript"];

export async function GET(request: Request) {
  const u = new URL(request.url);
  const project = resolveProjectFromRequest(request);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });
  const q = u.searchParams.get("q") ?? "";
  const limit = Math.min(50, Math.max(1, Number(u.searchParams.get("limit") ?? "20")));
  const typesParam = u.searchParams.get("types");
  const types = typesParam
    ? typesParam.split(",").filter((t): t is SearchHit["type"] => VALID_TYPES.includes(t as SearchHit["type"]))
    : undefined;

  const index = buildIndex(project.path, project.slug);
  const results = q ? searchIndex(index, q, { types, limit }) : [];
  return Response.json({ project: project.slug, query: q, results, indexed: index.length });
}
