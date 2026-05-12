import { resolveProjectFromRequest } from "@/lib/projects";
import {
  listPersonas,
  savePersonas,
  validatePersonas,
  type Persona,
} from "@/lib/hypothesis/personas";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const project = resolveProjectFromRequest(request);
  if (!project) {
    return Response.json({ error: "Unknown project" }, { status: 404 });
  }
  const personas = listPersonas(project.path);
  return Response.json({ project: project.slug, personas });
}

export async function PUT(request: Request) {
  let body: { project?: string; personas?: Persona[] };
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  const project = resolveProjectFromRequest(request, body.project);
  if (!project) {
    return Response.json({ error: "Unknown project" }, { status: 404 });
  }
  if (!Array.isArray(body.personas)) {
    return Response.json({ error: "personas array required" }, { status: 400 });
  }
  try {
    validatePersonas(body.personas);
  } catch (err) {
    const msg = err instanceof Error ? err.message : "invalid personas";
    return Response.json({ error: msg }, { status: 400 });
  }
  savePersonas(project.path, body.personas);
  const personas = listPersonas(project.path);
  return Response.json({ project: project.slug, personas });
}
