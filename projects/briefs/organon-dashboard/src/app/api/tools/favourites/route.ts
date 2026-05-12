import { resolveProjectFromRequest } from "@/lib/projects";
import { readFavourites, writeFavourites } from "@/lib/tools/favourites";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function projectFromQuery(request: Request) {
  return resolveProjectFromRequest(request);
}

export async function GET(request: Request) {
  const project = projectFromQuery(request);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });
  return Response.json({ favourites: readFavourites(project.path) });
}

export async function PUT(request: Request) {
  const project = projectFromQuery(request);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });
  let body: { favourites?: string[] } = {};
  try {
    body = (await request.json()) as { favourites?: string[] };
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  const favs = Array.isArray(body.favourites)
    ? body.favourites.filter((s): s is string => typeof s === "string")
    : [];
  writeFavourites(project.path, favs);
  return Response.json({ favourites: favs });
}
