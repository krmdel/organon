import { resolveProjectFromRequest } from "@/lib/projects";
import { runClaude } from "@/lib/claude-runner";
import { extractArtifactsFromChunk } from "@/lib/artifacts/parser";
import { getSection } from "@/lib/draft/store";
import type { SectionAction, SectionDiffArtifact } from "@/lib/artifacts/types";
import { streamTaskAsSse } from "@/lib/tasks/sse-helper";
import type { TaskEvent } from "@/lib/tasks/registry";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const ACTIONS: SectionAction[] = ["rewrite", "tighten", "check", "humanize"];

type RouteContext = { params: Promise<{ slug: string }> };

type Body = {
  project?: string;
  section_id?: string;
  action?: SectionAction;
  /** Phase 10 hotfix (N2-lite): optional researcher steering. */
  instructions?: string;
};

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
  if (!body.section_id) return Response.json({ error: "section_id required" }, { status: 400 });
  if (!body.action || !ACTIONS.includes(body.action)) {
    return Response.json({ error: "action must be rewrite|tighten|check|humanize" }, { status: 400 });
  }

  const section = getSection(project.path, slug, body.section_id);
  if (!section) return Response.json({ error: "section not found" }, { status: 404 });

  const skill = body.action === "humanize" ? "tool-humanizer" : "sci-writing";
  const action = body.action;
  const promptHeader = {
    rewrite: "Rewrite this section for clarity. Preserve all `\\fig{}` and `\\cite{}` references verbatim. Preserve hedging language. Do NOT introduce new claims or sources.",
    tighten: "Tighten this section by 15–25%. Preserve all `\\fig{}` and `\\cite{}` references verbatim. Drop redundancy, not content.",
    check: "Audit this section for unsupported claims, scope-creep, and citation gaps. Mark each issue inline as `[CHECK: …]` and return the annotated text.",
    humanize: "Run this section through the humanizer. Strip AI-tells, preserve all `\\fig{}` and `\\cite{}` references, preserve scientific hedging.",
  }[action];

  const userInstructions = (body.instructions ?? "").trim();
  const fullPrompt = [
    `Use the ${skill} skill on the following manuscript section.`,
    ``,
    `active_project_slug=${project.slug}`,
    `manuscript_slug=${slug}`,
    `section_id=${body.section_id}`,
    `section_type=${section.section_type}`,
    `action=${action}`,
    ``,
    promptHeader,
    ``,
    // Phase 10 hotfix (B2): explicit per-section_type guard so a Rewrite on
    // the title slot cannot bleed an h2-shaped body into the title.
    section.section_type === "title"
      ? `SECTION_SHAPE: This is the TITLE slot. The output must remain a single h1 (\`# ...\`); do NOT introduce \`## ...\` body markup.`
      : `SECTION_SHAPE: Stay within the \`## ${section.section_type}\` heading; do NOT introduce or rename to other sections' headings.`,
    ``,
    userInstructions
      ? `user_instructions=${userInstructions}`
      : `user_instructions=(none — researcher did not provide steering. Apply the action with default judgment.)`,
    ``,
    `--- BEFORE ---`,
    section.content_md,
    `--- END BEFORE ---`,
    ``,
    `Emit ONE \`{"_artifact":"section-diff","schema_version":1,"manuscript_slug":"${slug}","section_id":"${body.section_id}","action":"${action}","before":"<original>","after":"<your rewritten markdown>","rationale":"<one sentence>","warnings":[]}\` JSON line on stdout, no code fence. The dashboard renders it as a diff for the user to accept or reject; rejection means your rewrite is discarded.`,
  ].join("\n");

  // Phase 44 (v1.5) — F7: registry-backed runner via the shared helper.
  const proj = project;
  async function* runner(): AsyncGenerator<TaskEvent, void, unknown> {
    const abort = new AbortController();
    let stdoutBuffer = "";
    let lastExit: { code: number | null; reason?: string; success?: boolean; message?: string } | null = null;
    try {
      for await (const evt of runClaude({
        projectPath: proj.path,
        projectSlug: proj.slug,
        prompt: fullPrompt,
        skill,
        abortSignal: abort.signal,
      })) {
        yield { type: evt.type, data: evt };
        if (evt.type === "exit") lastExit = evt;
        if (evt.type === "stdout") {
          const { artifacts, remainder } = extractArtifactsFromChunk(stdoutBuffer, evt.chunk);
          stdoutBuffer = remainder;
          for (const art of artifacts) {
            if (art._artifact === "section-diff") {
              yield { type: "artifact", data: { artifact: art as SectionDiffArtifact } };
            }
          }
        }
      }
      yield {
        type: "done",
        data: {
          manuscript_slug: slug,
          section_id: body.section_id,
          action,
          success: lastExit?.success ?? false,
          reason: lastExit?.reason ?? "failed",
          exit_code: lastExit?.code ?? null,
          message: lastExit?.message,
        },
      };
    } catch (err) {
      yield {
        type: "error",
        data: { message: err instanceof Error ? err.message : String(err) },
      };
    }
  }

  const sectionId = body.section_id;
  return streamTaskAsSse({
    kind: "section-action",
    project_slug: proj.slug,
    project_path: proj.path,
    scope: `${slug}:${sectionId}:${action}`,
    payload: { manuscript_slug: slug, section_id: sectionId, action },
    runner,
  });
}
