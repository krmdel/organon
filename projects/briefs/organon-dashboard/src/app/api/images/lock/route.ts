import { resolveProjectFromRequest } from "@/lib/projects";
import { runClaude } from "@/lib/claude-runner";
import { extractArtifactsFromChunk } from "@/lib/artifacts/parser";
import { readVersion, setLocked } from "@/lib/images/versions";
import type { FigureArtifact } from "@/lib/artifacts/types";
import { streamTaskAsSse } from "@/lib/tasks/sse-helper";
import type { TaskEvent } from "@/lib/tasks/registry";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Body = {
  project?: string;
  fig_id?: string;
  version?: number;
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
  const figId = body.fig_id;
  const version = body.version;
  if (!figId || typeof version !== "number") {
    return Response.json({ error: "fig_id + version required" }, { status: 400 });
  }

  const existing = readVersion(project.path, figId, version);
  if (!existing) return Response.json({ error: "version not found" }, { status: 404 });

  const figureContext = JSON.stringify({
    prompt: existing.params?.prompt ?? null,
    style: existing.params?.style ?? null,
    backend: existing.backend,
    parent_version: existing.parent_version ?? null,
  });
  const prompt = [
    `Use the sci-writing skill in CAPTION mode.`,
    ``,
    `active_project_slug=${project.slug}`,
    `fig_id=${figId}`,
    `version=${version}`,
    `image_path=${existing.png_path}`,
    `figure_context=${figureContext}`,
    ``,
    `Write a one-sentence figure caption (≤ 200 chars, scientific tone, present tense) AND an alt-text (≤ 140 chars, plain language for screen readers).`,
    `Emit ONE \`{"_artifact":"figure","schema_version":1,"id":"${figId}","project_slug":"${project.slug}","version":${version},"caption":"...","alt_text":"...","locked":true,...}\` JSON line on stdout. The dashboard will merge the patch onto the existing version sidecar.`,
    `Markdown reply for the human (caption + alt text in plain prose) is welcome alongside.`,
  ].join("\n");

  // Phase 44 (v1.5) — F7: registry-backed runner.
  const proj = project;
  const fid: string = figId;
  const ver: number = version;
  async function* runner(): AsyncGenerator<TaskEvent, void, unknown> {
    const abort = new AbortController();
    let stdoutBuffer = "";
    let captionLanded = false;
    let lastExit: { code: number | null; reason?: string; success?: boolean; message?: string } | null = null;
    try {
      for await (const evt of runClaude({
        projectPath: proj.path,
        projectSlug: proj.slug,
        prompt,
        skill: "sci-writing",
        abortSignal: abort.signal,
      })) {
        yield { type: evt.type, data: evt };
        if (evt.type === "exit") lastExit = evt;
        if (evt.type === "stdout") {
          const { artifacts, remainder } = extractArtifactsFromChunk(stdoutBuffer, evt.chunk);
          stdoutBuffer = remainder;
          for (const art of artifacts) {
            if (art._artifact === "figure") {
              const fig = art as FigureArtifact;
              const caption = (fig.caption ?? "").trim();
              const alt = (fig.alt_text ?? "").trim();
              if (caption && alt) {
                const updated = setLocked(proj.path, fid, ver, {
                  caption,
                  alt_text: alt,
                });
                if (updated) {
                  captionLanded = true;
                  yield { type: "artifact", data: { artifact: updated } };
                }
              }
            }
          }
        }
      }
      if (!captionLanded) {
        yield { type: "error", data: { message: "sci-writing did not emit a usable caption + alt_text" } };
      }
      yield {
        type: "done",
        data: {
          fig_id: fid,
          version: ver,
          locked: captionLanded,
          success: (lastExit?.success ?? false) && captionLanded,
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
    kind: "figure-lock",
    project_slug: proj.slug,
    project_path: proj.path,
    scope: `${fid}:v${ver}`,
    payload: { fig_id: fid, version: ver },
    runner,
  });
}
