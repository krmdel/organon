import { listProjects } from "@/lib/projects";

export const dynamic = "force-dynamic";

export async function GET() {
  return Response.json({
    projects: listProjects().map((p) => ({
      slug: p.slug,
      name: p.name,
      is_root: p.isRoot,
      is_brief: p.isBrief,
      brief: p.brief,
    })),
  });
}
