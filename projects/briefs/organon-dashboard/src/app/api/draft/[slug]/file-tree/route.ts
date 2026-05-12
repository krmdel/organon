import { resolveProjectFromRequest } from "@/lib/projects";
import { getManuscript, listManuscripts, listSections } from "@/lib/draft/store";
import { listFigures } from "@/lib/figures/store";
import { listResults } from "@/lib/results/store";
import { listLibrary } from "@/lib/lit/library";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = { params: Promise<{ slug: string }> };

/**
 * Phase 29 (v1.2) — DR-6+ file-tree for the chat panel.
 *
 * GET /api/draft/[slug]/file-tree?project=<slug>
 *  → { sections, figures, stat_results, papers, manuscripts }
 *
 * Each entry is a slim `{ id, label, kind, hint? }` shape — the chat
 * panel uses it as a chip + label source. Content excerpts are fetched
 * lazily by the edit-with-chat route when the user actually pins one
 * (avoids streaming the full project on every panel open).
 */
type TreeEntry = { id: string; label: string; kind: string; hint?: string };

export async function GET(request: Request, { params }: RouteContext) {
  const { slug } = await params;
  const project = resolveProjectFromRequest(request);
  if (!project) {
    return Response.json({ error: "Unknown project" }, { status: 404 });
  }
  const manuscript = getManuscript(project.path, slug);
  if (!manuscript) {
    return Response.json({ error: "manuscript not found" }, { status: 404 });
  }

  const sections: TreeEntry[] = listSections(project.path, slug).map((s) => ({
    id: s.section_id,
    label: `${s.section_type ?? "section"} · ${s.section_id}`,
    kind: "section",
    hint: (s.content_md ?? "").slice(0, 120),
  }));
  const figures: TreeEntry[] = listFigures(project.path).map((f) => ({
    id: f.id,
    label: f.caption ?? f.id,
    kind: "figure",
    hint: f.alt_text ?? f.detailed_legend?.slice(0, 120) ?? undefined,
  }));
  const stat_results: TreeEntry[] = listResults(project.path)
    .filter((r) => !r.archived)
    .map((r) => ({
      id: r.id,
      label: r.test_label ?? r.test_name ?? r.id,
      kind: "stat-result",
      hint: r.interpretation?.slice(0, 120),
    }));
  const papers: TreeEntry[] = listLibrary(project.path).map((p) => ({
    id: p.id,
    label: p.cite_key ? `${p.cite_key} · ${p.title ?? "(untitled)"}` : (p.title ?? p.id),
    kind: "paper",
  }));
  const manuscripts: TreeEntry[] = listManuscripts(project.path).map((m) => ({
    id: m.slug,
    label: m.title ?? m.slug,
    kind: "manuscript",
  }));

  return Response.json(
    { sections, figures, stat_results, papers, manuscripts },
    { status: 200 },
  );
}
