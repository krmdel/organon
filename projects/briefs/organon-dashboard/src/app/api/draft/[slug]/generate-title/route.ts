import { resolveProjectFromRequest } from "@/lib/projects";
import { runClaude } from "@/lib/claude-runner";
import {
  diagnoseUnparsedArtifact,
  extractArtifactsFromChunk,
} from "@/lib/artifacts/parser";
import { getManuscript } from "@/lib/draft/store";
import { listLibrary } from "@/lib/lit/library";
import { listResults } from "@/lib/results/store";
import { listHypotheses } from "@/lib/hypothesis/store";
import type { PaperArtifact } from "@/lib/artifacts/types";
import {
  registerTask,
  subscribeToTask,
  type TaskEvent,
} from "@/lib/tasks/registry";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Phase 10 (v1.0.1) — DR-5 propose-title route. Spawns sci-writing in
 * `mode=generate-title` and surfaces 3–5 candidate titles with rationales.
 * SSE shape mirrors generate-section: stdout/stderr passthrough + a
 * Phase 4 done event with structured exit. The candidate list arrives as
 * a `title-candidates` artifact (UnknownArtifact in the parser; the route
 * narrows it locally).
 */

type RouteContext = { params: Promise<{ slug: string }> };

type Body = { project?: string };

type TitleCandidate = { title: string; rationale: string };
type TitleCandidatesArtifact = {
  _artifact: "title-candidates";
  schema_version: 1;
  manuscript_slug: string;
  candidates: TitleCandidate[];
};

function isTitleCandidatesArtifact(v: unknown): v is TitleCandidatesArtifact {
  if (!v || typeof v !== "object") return false;
  const obj = v as Record<string, unknown>;
  if (obj._artifact !== "title-candidates") return false;
  if (typeof obj.manuscript_slug !== "string") return false;
  if (!Array.isArray(obj.candidates)) return false;
  return obj.candidates.every(
    (c) => c && typeof c === "object" &&
      typeof (c as { title?: unknown }).title === "string" &&
      typeof (c as { rationale?: unknown }).rationale === "string",
  );
}

function trimPaper(p: PaperArtifact) {
  return {
    cite_key: p.cite_key ?? p.id,
    title: p.title,
    year: p.year,
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

  const manuscript = getManuscript(project.path, slug);
  if (!manuscript) {
    return Response.json({ error: "manuscript not found" }, { status: 404 });
  }

  // Phase 41 (v1.5) — F4: narrow to manuscript.linked_paper_ids when
  // non-empty; backward-compat fallback to full library otherwise.
  const linkedPaperIds = manuscript.linked_paper_ids ?? [];
  const allPapers = listLibrary(project.path);
  const narrowed = linkedPaperIds.length > 0
    ? (() => {
        const set = new Set(linkedPaperIds);
        return allPapers.filter((p) => set.has(p.id));
      })()
    : allPapers;
  const linkedPapers = narrowed.slice(0, 12).map(trimPaper);
  const linkedStatResults = listResults(project.path).slice(0, 12).map((r) => ({
    test_label: r.test_label,
    p_value: r.p_value,
    interpretation: r.interpretation,
    n: r.n,
  }));

  const briefSummary = [
    `title=${manuscript.title}`,
    `target_journal=${manuscript.target_journal ?? "(unset)"}`,
    `citation_style=${manuscript.citation_style}`,
  ].join(" / ");

  // Phase 49 (v1.6) — F12: zero-state fallback. When linkedPapers AND
  // linkedStatResults are both empty (the manuscript has no body
  // sections drafted yet, no library entries linked, no stat results),
  // surface manuscript.title + linked_hypothesis_ids[] (Phase 41
  // substrate) as the seed material. Without this, the prompt would be
  // skeletal and sci-writing would refuse — but the user's whole point
  // is "give me starting ideas before I've drafted anything".
  const linkedHypothesisIds = manuscript.linked_hypothesis_ids ?? [];
  const isZeroState =
    linkedPapers.length === 0 && linkedStatResults.length === 0;

  // Phase 60 (v2.1) — A5: ALWAYS thread linked hypotheses into the
  // prompt as rich context, not just as IDs. The dogfood walk hit a
  // case with 14 linked papers AND a linked supported hypothesis — the
  // zero-state branch didn't fire (papers were non-empty) and the
  // skill never saw the hypothesis claim, so it returned no candidates.
  // Resolve the IDs against listHypotheses() so the skill sees
  // claim_short + status + council_confidence per linked hypothesis.
  const allHypotheses = listHypotheses(project.path);
  const hypIdSet = new Set(linkedHypothesisIds);
  const linkedHypotheses = allHypotheses
    .filter((h) => hypIdSet.has(h.id))
    .slice(0, 8)
    .map((h) => ({
      id: h.id,
      claim_short: h.claim_short ?? h.claim.slice(0, 120),
      status: h.status,
      council_confidence: h.council_confidence ?? null,
    }));

  const fullPrompt = [
    `Use the sci-writing skill in title-generate mode (Step 7.8) to propose 3–5 candidate titles.`,
    ``,
    `active_project_slug=${project.slug}`,
    `manuscript_slug=${slug}`,
    `mode=generate-title`,
    ``,
    `manuscript_brief=${briefSummary}`,
    ``,
    `linked_papers=${JSON.stringify(linkedPapers)}`,
    ``,
    `linked_stat_results=${JSON.stringify(linkedStatResults)}`,
    ``,
    `linked_hypothesis_ids=${JSON.stringify(linkedHypothesisIds)}`,
    ``,
    // Phase 60 (v2.1) — A5: rich hypothesis block.
    `linked_hypotheses=${JSON.stringify(linkedHypotheses)}`,
    ``,
    isZeroState
      ? `zero_state_fallback=true — neither library entries nor stat results exist for this manuscript yet. Treat this as a "starting-ideas" pass: anchor on manuscript.title + linked_hypotheses (claim_short + status + council_confidence) alone and emit 3-5 generic-but-grounded candidate framings the researcher can sharpen later.`
      : `zero_state_fallback=false`,
    ``,
    `Respect the contract in Step 7.8: 3 to 5 distinct framings, 6–18 words each, plain text (no markdown), no subjective superlatives.`,
    `When linked_hypotheses is non-empty, anchor at least 2 of the 3-5 candidates on the supported / refuted claim_short(s) — these are first-class title evidence regardless of whether papers / stat_results exist.`,
    ``,
    `Emit ONE \`{"_artifact":"title-candidates","schema_version":1,"manuscript_slug":"${slug}","candidates":[{"title":"...","rationale":"..."}, ...]}\` JSON line on stdout (no code fence). The dashboard renders the candidates and lets the user pick one.`,
  ].join("\n");

  // Phase 44 (v1.5) — F7: runner generator owns the AbortController and
  // outlives the request. No request.signal binding here.
  const proj = project;
  async function* runner(): AsyncGenerator<TaskEvent, void, unknown> {
    const abort = new AbortController();
    let stdoutBuffer = "";
    let stdoutAccumulated = "";
    let lastExit: {
      code: number | null;
      reason?: string;
      success?: boolean;
      message?: string;
    } | null = null;
    let candidatesArt: TitleCandidatesArtifact | null = null;
    let anyTitleArtifactParsed = false;
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
              isTitleCandidatesArtifact(art) &&
              art.manuscript_slug === slug &&
              art.candidates.length >= 3 &&
              art.candidates.length <= 5
            ) {
              anyTitleArtifactParsed = true;
              candidatesArt = art;
              yield { type: "artifact", data: { artifact: art } };
            }
          }
        }
      }
      const debug = diagnoseUnparsedArtifact(stdoutAccumulated, anyTitleArtifactParsed);
      if (debug) {
        yield {
          type: "parse-debug",
          data: { manuscript_slug: slug, ...debug },
        };
      }
      yield {
        type: "done",
        data: {
          manuscript_slug: slug,
          success: lastExit?.success ?? false,
          reason: lastExit?.reason ?? "failed",
          exit_code: lastExit?.code ?? null,
          message: lastExit?.message,
          candidates: candidatesArt?.candidates ?? null,
        },
      };
    } catch (err) {
      yield {
        type: "error",
        data: { message: err instanceof Error ? err.message : String(err) },
      };
    }
  }

  const task_id = registerTask({
    kind: "generate-title",
    project_slug: proj.slug,
    project_path: proj.path,
    scope: slug,
    payload: { manuscript_slug: slug },
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
        kind: "generate-title",
        scope: slug,
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
