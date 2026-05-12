import { resolveProjectFromRequest } from "@/lib/projects";
import { listSkillGroups } from "@/lib/skills";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const project = resolveProjectFromRequest(request);
  if (!project) {
    return Response.json({ error: "Unknown project" }, { status: 404 });
  }
  return Response.json({
    project: project.slug,
    groups: listSkillGroups(project.path),
  });
}
