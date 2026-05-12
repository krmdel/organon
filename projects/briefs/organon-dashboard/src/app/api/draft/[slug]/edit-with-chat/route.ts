import { resolveProjectFromRequest } from "@/lib/projects";
import { runClaude } from "@/lib/claude-runner";
import { extractArtifactsFromChunk } from "@/lib/artifacts/parser";
import {
  getManuscript,
  getSection,
  listManuscripts,
  listSections,
} from "@/lib/draft/store";
import { readFigure } from "@/lib/figures/store";
import { listResults } from "@/lib/results/store";
import { listLibrary } from "@/lib/lit/library";
import {
  buildContext,
  MAX_SIBLING_CHARS,
  MAX_LINKED_PAPERS,
  MAX_PRIOR_TURNS,
  MAX_DIFF_SUMMARY_CHARS,
  MAX_REFERENCED_FILES,
  MAX_REFERENCED_EXCERPT_CHARS,
  type ContextSelection,
  type PriorTurn,
  type ReferencedFile,
  type ReferencedFileKind,
} from "@/lib/draft/selection-context";
import { streamTaskAsSse } from "@/lib/tasks/sse-helper";
import type { TaskEvent } from "@/lib/tasks/registry";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = { params: Promise<{ slug: string }> };

type SelectionBody = { start?: number; end?: number; text?: string };
type PriorTurnBody = {
  prompt?: string;
  applied?: boolean;
  diff_summary?: string;
};
type ReferencedFileIdBody = {
  kind?: string;
  id?: string;
};
type Body = {
  project?: string;
  section_id?: string;
  prompt?: string;
  selection?: SelectionBody | null;
  // Phase 27 (v1.2) — prior conversation turns for multi-turn DR-6+.
  // Capped + summarised by the workspace before send; this route
  // re-applies the cap as a defensive measure.
  prior_turns?: PriorTurnBody[];
  // Phase 29 (v1.2) — researcher-pinned files for DR-6+ file-tree
  // context. The route resolves each via the matching store, trims
  // each excerpt to MAX_REFERENCED_EXCERPT_CHARS, caps to
  // MAX_REFERENCED_FILES at the buildContext boundary.
  referenced_file_ids?: ReferencedFileIdBody[];
};

/**
 * Phase 22 (v1.1+) — DR-6 whole-paper-aware AI editing.
 *
 * SSE route. Body: `{ project, section_id, prompt, selection? }`.
 * Builds a bounded context envelope (active section full content +
 * caps siblings to ~2k chars, library to 6 papers) and spawns
 * sci-writing in `mode=edit-with-chat` (Step 7.10). The skill emits
 * a `_artifact: section-diff` JSON line carrying before / after /
 * action / rationale; the dashboard's existing parser picks it up,
 * the chat-panel surfaces an Apply button, the workspace mutates
 * the section content on accept.
 *
 * v1.1 scope:
 *  - Single-turn chat — each call is independent. Multi-turn is v1.2.
 *  - Apply = accept full diff. Per-line accept is v1.2.
 *  - Context capped at the dashboard boundary, NOT the skill.
 */
export async function POST(request: Request, { params }: RouteContext) {
  const { slug } = await params;
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
  if (!body.section_id) {
    return Response.json({ error: "section_id required" }, { status: 400 });
  }
  const promptText = (body.prompt ?? "").trim();
  if (!promptText) {
    return Response.json({ error: "prompt required" }, { status: 400 });
  }

  const manuscript = getManuscript(project.path, slug);
  if (!manuscript) {
    return Response.json({ error: "manuscript not found" }, { status: 404 });
  }
  const section = getSection(project.path, slug, body.section_id);
  if (!section) {
    return Response.json({ error: "section not found" }, { status: 404 });
  }
  const siblings = listSections(project.path, slug)
    .filter((s) => s.section_id !== body.section_id);
  const library = listLibrary(project.path);

  let selection: ContextSelection | null = null;
  if (
    body.selection &&
    typeof body.selection.start === "number" &&
    typeof body.selection.end === "number" &&
    typeof body.selection.text === "string"
  ) {
    selection = {
      start: body.selection.start,
      end: body.selection.end,
      text: body.selection.text,
    };
  }

  // Phase 27 — sanitize prior_turns into the typed shape buildContext
  // expects. Drop entries missing a prompt; the dashboard caps further
  // inside buildContext via MAX_PRIOR_TURNS / MAX_DIFF_SUMMARY_CHARS.
  const prior_turns: PriorTurn[] = Array.isArray(body.prior_turns)
    ? body.prior_turns
        .filter((t): t is PriorTurnBody => !!t && typeof t.prompt === "string")
        .map((t) => ({
          prompt: String(t.prompt),
          applied: !!t.applied,
          diff_summary:
            typeof t.diff_summary === "string" ? t.diff_summary : undefined,
        }))
    : [];

  // Phase 29 — resolve referenced_file_ids via the matching store. The
  // kind discriminator is required so we know which store to hit; an
  // unknown kind drops the entry. Each excerpt is sourced from the
  // canonical content field for the artifact (section.content_md /
  // figure.detailed_legend ?? caption / stat_result.interpretation /
  // paper.abstract / manuscript.title + abstract).
  const referenced_files: ReferencedFile[] = [];
  if (Array.isArray(body.referenced_file_ids)) {
    for (const ref of body.referenced_file_ids.slice(0, MAX_REFERENCED_FILES)) {
      const kind = ref.kind as ReferencedFileKind | undefined;
      const id = ref.id;
      if (!kind || !id) continue;
      try {
        if (kind === "section") {
          const s = getSection(project.path, slug, id);
          if (s) {
            referenced_files.push({
              kind,
              id,
              label: `${s.section_type ?? "section"} · ${s.section_id}`,
              content_excerpt: (s.content_md ?? "").slice(
                0,
                MAX_REFERENCED_EXCERPT_CHARS,
              ),
            });
          }
        } else if (kind === "figure") {
          const f = readFigure(project.path, id);
          if (f) {
            const fig_excerpt = f.detailed_legend ?? f.caption ?? f.alt_text ?? "";
            referenced_files.push({
              kind,
              id,
              label: f.caption ?? f.id,
              content_excerpt: fig_excerpt.slice(0, MAX_REFERENCED_EXCERPT_CHARS),
            });
          }
        } else if (kind === "stat-result") {
          const r = listResults(project.path).find((x) => x.id === id);
          if (r) {
            referenced_files.push({
              kind,
              id,
              label: r.test_label ?? r.test_name ?? r.id,
              content_excerpt: (r.interpretation ?? "").slice(
                0,
                MAX_REFERENCED_EXCERPT_CHARS,
              ),
            });
          }
        } else if (kind === "paper") {
          const p = library.find((x) => x.id === id);
          if (p) {
            referenced_files.push({
              kind,
              id,
              label: p.cite_key ?? p.title ?? p.id,
              content_excerpt: (p.abstract ?? "").slice(
                0,
                MAX_REFERENCED_EXCERPT_CHARS,
              ),
            });
          }
        } else if (kind === "manuscript") {
          const m = listManuscripts(project.path).find((x) => x.slug === id);
          if (m) {
            referenced_files.push({
              kind,
              id,
              label: m.title ?? m.slug,
              content_excerpt: `${m.title ?? ""}\n${m.slug}`.slice(
                0,
                MAX_REFERENCED_EXCERPT_CHARS,
              ),
            });
          }
        }
      } catch {
        /* skip — never fail the chat turn over a missing reference */
      }
    }
  }

  const ctx = buildContext(
    section,
    siblings,
    library,
    selection,
    prior_turns,
    referenced_files,
  );

  const fullPrompt = [
    `Use the sci-writing skill in edit-with-chat mode (Step 7.10) to revise the active section.`,
    ``,
    `active_project_slug=${project.slug}`,
    `manuscript_slug=${slug}`,
    `section_id=${body.section_id}`,
    `mode=edit-with-chat`,
    ``,
    `researcher_prompt=${promptText}`,
    ``,
    selection && selection.text.trim()
      ? `selection_text=${JSON.stringify(selection.text)}`
      : `selection_text=(none — researcher did not select; treat the whole active section as the target)`,
    selection
      ? `selection_range=[${selection.start},${selection.end}]`
      : ``,
    ``,
    `active_section=${JSON.stringify(ctx.active)}`,
    ``,
    `siblings=${JSON.stringify(ctx.siblings)}  (each capped at ${MAX_SIBLING_CHARS} chars)`,
    ``,
    `linked_papers=${JSON.stringify(ctx.linked_papers)}  (capped at ${MAX_LINKED_PAPERS})`,
    ``,
    // Phase 27: conversation-so-far block. When prior_turns is empty
    // the section is omitted so the v1.1 single-turn shape is
    // preserved verbatim.
    ctx.prior_turns && ctx.prior_turns.length > 0
      ? `prior_turns=${JSON.stringify(ctx.prior_turns)}  (last ${MAX_PRIOR_TURNS} turns; each diff_summary capped at ${MAX_DIFF_SUMMARY_CHARS} chars; treat as conversation so far — the researcher_prompt is the latest turn, not a standalone request)`
      : ``,
    // Phase 29: researcher-pinned files for additional context. Cap
    // gates at the dashboard; the skill must NOT request more.
    ctx.referenced_files && ctx.referenced_files.length > 0
      ? `referenced_files=${JSON.stringify(ctx.referenced_files)}  (capped at ${MAX_REFERENCED_FILES} files; each content_excerpt capped at ${MAX_REFERENCED_EXCERPT_CHARS} chars)`
      : ``,
    ``,
    `Emit ONE \`{"_artifact":"section-diff", ...}\` JSON line on stdout (no code fence) carrying before / after / action / rationale. The dashboard renders the diff via Phase 7's <DiffView /> and the user accepts via an Apply button.`,
  ].filter(Boolean).join("\n");

  // Phase 44 (v1.5) — F7: registry-backed runner.
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
        skill: "sci-writing",
        abortSignal: abort.signal,
      })) {
        yield { type: evt.type, data: evt };
        if (evt.type === "exit") lastExit = evt;
        if (evt.type === "stdout") {
          const { artifacts, remainder } = extractArtifactsFromChunk(stdoutBuffer, evt.chunk);
          stdoutBuffer = remainder;
          for (const art of artifacts) {
            if (art._artifact === "section-diff") {
              yield { type: "artifact", data: { artifact: art } };
            }
          }
        }
      }
      yield {
        type: "done",
        data: {
          manuscript_slug: slug,
          section_id: body.section_id,
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

  const sectionId = body.section_id;
  return streamTaskAsSse({
    kind: "edit-with-chat",
    project_slug: proj.slug,
    project_path: proj.path,
    scope: `${slug}:${sectionId}`,
    payload: { manuscript_slug: slug, section_id: sectionId },
    runner,
  });
}
