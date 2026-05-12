import { resolveProjectFromRequest } from "@/lib/projects";
import { runClaude } from "@/lib/claude-runner";
import {
  diagnoseUnparsedArtifact,
  extractArtifactsFromChunk,
} from "@/lib/artifacts/parser";
import {
  effectiveSectionLinkage,
  getManuscript,
  getSection,
  listSections,
  saveSection,
} from "@/lib/draft/store";
import { listFigures } from "@/lib/figures/store";
import { listLibrary } from "@/lib/lit/library";
import { listResults } from "@/lib/results/store";
import type {
  PaperArtifact,
  SectionDraftArtifact,
  SectionType,
} from "@/lib/artifacts/types";
import { extractRefs } from "@/lib/draft/parse";
import {
  extractFallbackContent,
  validateGeneratedContent,
} from "@/lib/draft/validate";
import {
  registerTask,
  subscribeToTask,
  type TaskEvent,
} from "@/lib/tasks/registry";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Phase 10 (v1.0.1) — DR-3 per-section "Generate with AI" route. Spawns the
 * sci-writing skill in `mode=generate-section` with project artifacts as
 * context. Captures the emitted `section-draft` artifact and persists it
 * via the same store path as section PATCH so version + sidecar stay
 * consistent.
 *
 * Phase 4 contract: emits a `done` event whose payload carries
 * `success / reason / exit_code / message` so the runner state card can
 * classify the run. Same pattern as data/interpret + draft/[slug]/action.
 *
 * Phase 10 hotfix (B1 + B2 — researcher-found regressions on 2026-05-07):
 *   - section_type validation: emitted content must match the section's
 *     heading shape (h1 for title, `## <type>` for body sections). Mismatch
 *     → reject + send `validation` warning + done.reason="validation-failed".
 *     Closes the "rewriting the title produces an abstract" surprise.
 *   - Honest done-state: if the skill exits clean but emits no valid
 *     section-draft, attempt a fallback content extraction; if that also
 *     fails, send done.reason="succeeded-no-artifact" so the UI surfaces
 *     "ran but no draft" instead of a fake "drafted" success.
 *   - Optional user_instructions: lets the researcher pass intent
 *     ("emphasize the regain rate", "include limitations") without
 *     architecturally adopting DR-6's chat panel.
 */

const SECTION_TYPES: SectionType[] = [
  "title",
  "abstract",
  "introduction",
  "methods",
  "results",
  "discussion",
  "references",
  "custom",
];

type RouteContext = { params: Promise<{ slug: string }> };

type Body = {
  project?: string;
  section_id?: string;
  /** Phase 10 hotfix (N2-lite): optional user-supplied steering. */
  instructions?: string;
};

function trimPaper(p: PaperArtifact) {
  return {
    cite_key: p.cite_key ?? p.id,
    title: p.title,
    authors: Array.isArray(p.authors) ? p.authors.slice(0, 6) : [],
    year: p.year,
    abstract: typeof p.abstract === "string" ? p.abstract.slice(0, 1200) : "",
  };
}

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
  if (!body.section_id) {
    return Response.json({ error: "section_id required" }, { status: 400 });
  }

  const manuscript = getManuscript(project.path, slug);
  if (!manuscript) {
    return Response.json({ error: "manuscript not found" }, { status: 404 });
  }
  const section = getSection(project.path, slug, body.section_id);
  if (!section) {
    return Response.json({ error: "section not found" }, { status: 404 });
  }
  const sectionType: SectionType = SECTION_TYPES.includes(section.section_type)
    ? section.section_type
    : "custom";

  // Phase 10: pull artifacts the skill needs as context.
  const allSections = listSections(project.path, slug);
  const otherSections = allSections
    .filter((s) => s.section_id !== body.section_id)
    .map((s) => ({
      section_id: s.section_id,
      section_type: s.section_type,
      content_md: s.content_md.slice(0, 4000),
    }));

  // Phase 41 (v1.5) — F4: narrow source artifacts to manuscript linkage
  // when non-empty; backward-compat fallback to full project lists when
  // the linkage arrays are empty (legacy + new "everything" case).
  // Phase 51 (v2.0) — per-section override wins over manuscript linkage
  // via effectiveSectionLinkage(section, manuscript, kind).
  const paperIds = effectiveSectionLinkage(section, manuscript, "paper");
  const figureIds = effectiveSectionLinkage(section, manuscript, "figure");

  const allPapers = listLibrary(project.path);
  const linkedPapers = (
    paperIds && paperIds.length > 0
      ? (() => {
          const set = new Set(paperIds);
          return allPapers.filter((p) => set.has(p.id));
        })()
      : allPapers
  ).map(trimPaper);

  const allFigures = listFigures(project.path);
  const linkedFigures = (
    figureIds && figureIds.length > 0
      ? (() => {
          const set = new Set(figureIds);
          return allFigures.filter((f) => set.has(f.id));
        })()
      : allFigures
  ).map((f) => ({
    id: f.id,
    version: f.version,
    caption: f.caption ?? null,
    alt_text: f.alt_text ?? null,
    kind: f.kind,
  }));
  const linkedStatResults = listResults(project.path).map((r) => ({
    id: r.id,
    test_name: r.test_name,
    test_label: r.test_label,
    p_value: r.p_value,
    effect_size: r.effect_size ?? null,
    n: r.n,
    interpretation: r.interpretation,
  }));

  const briefSummary = [
    `title=${manuscript.title}`,
    `target_journal=${manuscript.target_journal ?? "(unset)"}`,
    `citation_style=${manuscript.citation_style}`,
    `authors=${(manuscript.authors ?? []).join("; ") || "(unset)"}`,
  ].join(" / ");

  const userInstructions = (body.instructions ?? "").trim();

  // Phase 10 hotfix (B2): explicit per-section_type heading shape so the
  // skill cannot bleed body content into the title slot. This is repeated
  // in SKILL.md Step 7.7's per-section table; the route validates after.
  const sectionShapeHint = sectionType === "title"
    ? "Title slot: emit a single h1 line `# <new manuscript title>` (≤ 500 chars total). NO `## ...` body — that belongs to abstract/introduction/etc. Optionally add an Authors / Affiliation line."
    : sectionType === "references"
      ? "References is auto-populated from \\cite{} blocks at export time — do not generate."
      : sectionType === "custom"
        ? "Custom section: any heading shape OK, but lead with a `## <Custom Heading>` line."
        : `Body section: must lead with \`## ${sectionType.charAt(0).toUpperCase()}${sectionType.slice(1)}\` and stay within that section's scope. Do NOT include other sections' headings (\`## Methods\` inside an introduction-slot draft is a hard reject).`;

  const fullPrompt = [
    `Use the sci-writing skill in section-generate mode (Step 7.7) to draft this manuscript section.`,
    ``,
    `active_project_slug=${project.slug}`,
    `manuscript_slug=${slug}`,
    `section_id=${body.section_id}`,
    `section_type=${sectionType}`,
    `mode=generate-section`,
    ``,
    `SECTION_SHAPE: ${sectionShapeHint}`,
    ``,
    `manuscript_brief=${briefSummary}`,
    ``,
    `linked_papers=${JSON.stringify(linkedPapers)}`,
    ``,
    `linked_stat_results=${JSON.stringify(linkedStatResults)}`,
    ``,
    `linked_figures=${JSON.stringify(linkedFigures)}`,
    ``,
    `existing_sections=${JSON.stringify(otherSections)}`,
    ``,
    userInstructions
      ? `user_instructions=${userInstructions}`
      : `user_instructions=(none — researcher did not provide steering. Default to a balanced, hedged draft grounded in the linked artifacts.)`,
    ``,
    `Respect the contract in Step 7.7: use \\cite{cite_key} (only keys from linked_papers), \\fig{fig_id} (only ids from linked_figures), KaTeX-subset math, no raw <span> HTML, preserve hedging.`,
    ``,
    `Emit ONE \`{"_artifact":"section-draft", ...}\` JSON line on stdout (no code fence) carrying the full content_md. The dashboard will persist it as the new section body.`,
  ].join("\n");

  // Phase 44 (v1.5) — F7: runner generator, drops the request.signal binding.
  // `proj` + `sec` are non-null aliases so TS narrowing carries inside.
  const proj = project;
  const sec: SectionDraftArtifact = section;
  async function* runner(): AsyncGenerator<TaskEvent, void, unknown> {
    const abort = new AbortController();
    let stdoutBuffer = "";
    let stdoutAccumulated = "";
    let lastExit: { code: number | null; reason?: string; success?: boolean; message?: string } | null = null;
    let persisted: SectionDraftArtifact | null = null;
    const validationFailures: string[] = [];
    let anySectionArtifactParsed = false;

    const persistContent = (rawContent: string, fromFallback: boolean): boolean => {
      const verdict = validateGeneratedContent(rawContent, sectionType);
      if (!verdict.ok) {
        validationFailures.push(verdict.reason);
        return false;
      }
      const refs = extractRefs(rawContent);
      const next: SectionDraftArtifact = {
        ...sec,
        section_type: sectionType,
        status: "draft",
        content_md: rawContent,
        linked_paper_ids: refs.citations,
        linked_figure_ids: refs.figures,
        version: sec.version + 1,
      };
      saveSection(proj.path, next);
      persisted = next;
      return !fromFallback;
    };

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
          stdoutAccumulated += evt.chunk;
          const { artifacts, remainder } = extractArtifactsFromChunk(stdoutBuffer, evt.chunk);
          stdoutBuffer = remainder;
          for (const art of artifacts) {
            if (
              art._artifact === "section-draft" &&
              art.manuscript_slug === slug &&
              art.section_id === body.section_id
            ) {
              anySectionArtifactParsed = true;
            }
            if (
              art._artifact === "section-draft" &&
              art.manuscript_slug === slug &&
              art.section_id === body.section_id &&
              !persisted
            ) {
              const ok = persistContent(art.content_md, false);
              if (ok && persisted) {
                yield { type: "artifact", data: { artifact: persisted } };
              } else {
                yield {
                  type: "warning",
                  data: {
                    kind: "validation-failed",
                    section_id: body.section_id,
                    section_type: sectionType,
                    reason: validationFailures[validationFailures.length - 1],
                  },
                };
              }
            }
          }
        }
      }

      let usedFallback = false;
      if (!persisted && lastExit?.success) {
        const fb = extractFallbackContent(stdoutAccumulated, sectionType);
        if (fb) {
          const ok = persistContent(fb, true);
          if (ok || persisted) {
            usedFallback = true;
            yield { type: "artifact", data: { artifact: persisted, recovered: "fallback" } };
            yield {
              type: "warning",
              data: {
                kind: "fallback-content",
                section_id: body.section_id,
                section_type: sectionType,
                reason: "Skill emitted prose without a section-draft JSON line; recovered the largest matching markdown body. Review carefully.",
              },
            };
          }
        }
      }

      let reason = lastExit?.reason ?? "failed";
      if (lastExit?.success && !persisted) {
        reason = validationFailures.length > 0 ? "validation-failed" : "succeeded-no-artifact";
      } else if (lastExit?.success && usedFallback) {
        reason = "succeeded-via-fallback";
      }

      const debug = diagnoseUnparsedArtifact(stdoutAccumulated, anySectionArtifactParsed);
      if (debug) {
        yield {
          type: "parse-debug",
          data: { manuscript_slug: slug, section_id: body.section_id, ...debug },
        };
      }

      yield {
        type: "done",
        data: {
          manuscript_slug: slug,
          section_id: body.section_id,
          success: lastExit?.success ?? false,
          persisted: persisted ? { section_id: (persisted as SectionDraftArtifact).section_id, version: (persisted as SectionDraftArtifact).version } : null,
          reason,
          exit_code: lastExit?.code ?? null,
          message: lastExit?.message,
          validation_failures: validationFailures.length > 0 ? validationFailures : undefined,
          used_fallback: usedFallback,
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
  const task_id = registerTask({
    kind: "generate-section",
    project_slug: proj.slug,
    project_path: proj.path,
    scope: `${slug}:${sectionId}`,
    payload: { manuscript_slug: slug, section_id: sectionId },
    source: runner(),
  });

  const encoder = new TextEncoder();
  let unsubscribe: (() => void) | null = null;

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const send = (event: string, data: unknown) => {
        try {
          controller.enqueue(
            encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`),
          );
        } catch { /* controller closed */ }
      };
      send("task-started", {
        task_id,
        kind: "generate-section",
        scope: `${slug}:${body.section_id}`,
      });
      const handle = subscribeToTask(task_id, (evt) => {
        send(evt.type, evt.data);
        if (evt.type === "task-completed") {
          try { controller.close(); } catch { /* ignore */ }
        }
      });
      unsubscribe = handle;
      if (!handle) {
        send("done", { success: false, reason: "task-vanished" });
        try { controller.close(); } catch { /* ignore */ }
      }
    },
    cancel() {
      if (unsubscribe) unsubscribe();
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
