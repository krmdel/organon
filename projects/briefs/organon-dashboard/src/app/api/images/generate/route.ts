import path from "node:path";
import { resolveProjectFromRequest } from "@/lib/projects";
import { organonRoot } from "@/lib/paths";
import { runClaude } from "@/lib/claude-runner";
import { extractArtifactsFromChunk } from "@/lib/artifacts/parser";
import { allocateFigId } from "@/lib/data/id";
import { appendVersion, pngPath } from "@/lib/images/versions";
import { figureDir } from "@/lib/figures/store";
import type { FigureArtifact } from "@/lib/artifacts/types";
import { streamTaskAsSse } from "@/lib/tasks/sse-helper";
import type { TaskEvent } from "@/lib/tasks/registry";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Body = {
  project?: string;
  prompt?: string;
  style?: string;
  sub_style?: string | null;
  fig_id?: string;
};

export async function POST(request: Request) {
  let body: Body;
  try {
    body = (await request.json()) as Body;
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  const project = resolveProjectFromRequest(request, body.project);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });
  const prompt = body.prompt?.trim();
  if (!prompt) return Response.json({ error: "prompt required" }, { status: 400 });
  const style = body.style?.trim();
  if (!style) return Response.json({ error: "style required" }, { status: 400 });
  // Phase 7 T6.9 — sub_style is mandatory for the styles where the prompt
  // is otherwise too underspecified for viz-nano-banana to produce a
  // coherent figure. Keep this list in sync with style-picker.tsx
  // STYLES_REQUIRING_SUB.
  const STYLES_REQUIRING_SUB = ["scientific", "technical"];
  if (STYLES_REQUIRING_SUB.includes(style) && !body.sub_style?.trim()) {
    return Response.json(
      { error: `sub_style required when style is ${STYLES_REQUIRING_SUB.join("/")}` },
      { status: 400 },
    );
  }

  const figId = body.fig_id ?? allocateFigId();
  const subStyleHint = body.sub_style ? ` sub_style=${body.sub_style}` : "";
  // Phase 2 (fix-sprint): paths are computed from project.path, not slug-interpolated.
  // figureDirRel is e.g. "projects/briefs/dogfood-glp1-weight-regain/figures/<fig_id>"
  // for a brief project, "projects/<slug>/figures/<fig_id>" for a non-brief.
  const root = organonRoot();
  const figureDirAbs = figureDir(project.path, figId);
  const figureDirRel = path.relative(root, figureDirAbs);
  const pngRel = path.relative(root, pngPath(project.path, figId, 1));
  const thumbRel = `${figureDirRel}/v1.thumb.png`;
  const sidecarRel = `${figureDirRel}/v1.json`;
  const fullPrompt = [
    `Use the viz-nano-banana skill to generate ONE image.`,
    ``,
    `active_project_slug=${project.slug}`,
    `fig_id=${figId}`,
    `style=${style}${subStyleHint}`,
    ``,
    `Prompt: ${prompt}`,
    ``,
    `Save the image to ${pngRel}. Also write a thumbnail to ${thumbRel} and a sidecar at ${sidecarRel}.`,
    `Then emit ONE \`{"_artifact":"figure","schema_version":1,"id":"${figId}","project_slug":"${project.slug}","kind":"image","version":1,"format":"png","data_source":null,"params":{"prompt":"...","style":"${style}"${body.sub_style ? `,"sub_style":"${body.sub_style}"` : ""}},"caption":null,"alt_text":null,"code_path":null,"png_path":"${pngRel}","svg_path":null,"thumbnail_path":"${thumbRel}","library_path":"${pngRel}","backend":"gemini","cost_cents":4,"parent_version":null,"mask_path":null,"locked":false,"created_at":"<iso>"}\` JSON line on stdout (no code fence; one line). Schema in PHASE_4_TASKS.md §5.`,
  ].join("\n");

  // Phase 44 (v1.5) — F7: registry-backed runner. `proj` is a non-null
  // alias so TS narrowing carries into the closure.
  const proj = project;
  async function* runner(): AsyncGenerator<TaskEvent, void, unknown> {
    const abort = new AbortController();
    let stdoutBuffer = "";
    let lastExit: { code: number | null; reason?: string; success?: boolean; message?: string } | null = null;
    yield { type: "preallocated", data: { fig_id: figId } };
    try {
      for await (const evt of runClaude({
        projectPath: proj.path,
        projectSlug: proj.slug,
        prompt: fullPrompt,
        skill: "viz-nano-banana",
        abortSignal: abort.signal,
      })) {
        yield { type: evt.type, data: evt };
        if (evt.type === "exit") lastExit = evt;
        if (evt.type === "stdout") {
          const { artifacts, remainder } = extractArtifactsFromChunk(stdoutBuffer, evt.chunk);
          stdoutBuffer = remainder;
          for (const art of artifacts) {
            if (art._artifact === "figure") {
              const persisted = appendVersion(proj.path, art as FigureArtifact);
              yield { type: "artifact", data: { artifact: art, persisted_at: persisted } };
            } else {
              yield { type: "artifact", data: { artifact: art } };
            }
          }
        }
      }
      yield {
        type: "done",
        data: {
          fig_id: figId,
          success: lastExit?.success ?? false,
          reason: lastExit?.reason ?? "failed",
          exit_code: lastExit?.code ?? null,
          message: lastExit?.message,
        },
      };
    } catch (err) {
      yield { type: "error", data: { message: err instanceof Error ? err.message : String(err) } };
    }
  }

  return streamTaskAsSse({
    kind: "figure-generate",
    project_slug: proj.slug,
    project_path: proj.path,
    scope: figId,
    payload: { fig_id: figId, style },
    runner,
  });
}
