import { resolveProjectFromRequest } from "@/lib/projects";
import { searchPapers } from "@/lib/lit/search";
import { getHypothesis, patchHypothesis } from "@/lib/hypothesis/store";
import { listPersonas } from "@/lib/hypothesis/personas";
import { isPersonaActive, slugifyPersona } from "@/lib/hypothesis/shared";
import { getPersonaQueries } from "@/lib/hypothesis/persona-queries";
import { streamTaskAsSse } from "@/lib/tasks/sse-helper";
import type { TaskEvent } from "@/lib/tasks/registry";
import type { PaperArtifact } from "@/lib/artifacts/types";

// Phase 48 (v1.6) — F11: per-persona deep literature research.
//
// For a hypothesis, runs each active persona's query templates through
// searchPapers (which itself uses Phase 45's paperclip-primary routing
// for biomedical claims and Phase 47's relevance scorer). Stores the
// merged + relevance-filtered results as additional_papers_by_persona
// on the hypothesis record so the persona-panel can render them.
//
// The brief calls for "3 personas × 3-5 queries × 5 results = ~45 search
// calls per council run, ~60-90s wall-clock". Phase 44's tasks registry
// keeps the run alive across navigation.
//
// Confidence scoring (Phase 47) applies — only papers with relevance ≥
// 0.5 (lower bar than the 0.6 UI chip; we want to keep some borderline
// material in case the persona prompt benefits) are stored.

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const MIN_RELEVANCE = 0.5;
const PER_QUERY_MAX = 5;

type Params = { params: Promise<{ hyp_id: string }> };

type Body = {
  project?: string;
};

export async function POST(request: Request, ctx: Params) {
  let body: Body = {};
  try {
    body = (await request.json()) as Body;
  } catch {
    // Empty body is fine — POST with no payload kicks off deep-research
    // for whatever's already on the hypothesis record.
  }

  const project = resolveProjectFromRequest(request, body.project);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });

  const { hyp_id } = await ctx.params;
  const hypothesis = getHypothesis(project.path, hyp_id);
  if (!hypothesis) {
    return Response.json({ error: "Hypothesis not found" }, { status: 404 });
  }
  if (hypothesis.status === "archived") {
    return Response.json(
      { error: "Cannot run deep-research on archived hypothesis" },
      { status: 409 },
    );
  }

  const personas = listPersonas(project.path);
  const active = personas.filter(isPersonaActive);
  if (active.length === 0) {
    return Response.json(
      { error: "No active personas — toggle one on first" },
      { status: 409 },
    );
  }

  const proj = project;
  // Phase 44 pitfall — TS narrowing inside detached generators: outer
  // null-guards don't carry into nested function closures. Aliasing the
  // narrowed value to a const keeps the type stable inside the runner.
  const hyp = hypothesis;
  const claim = hyp.claim;

  async function* runner(): AsyncGenerator<TaskEvent, void, unknown> {
    yield {
      type: "deep-research-started",
      data: {
        hypothesis_id: hyp.id,
        persona_count: active.length,
      },
    };

    const byPersona: Record<string, PaperArtifact[]> = {};

    for (const persona of active) {
      const slug = slugifyPersona(persona.name);
      const queries = getPersonaQueries(persona.name, claim);
      yield {
        type: "deep-research-persona-start",
        data: { persona: persona.name, slug, queries },
      };

      const merged: PaperArtifact[] = [];
      for (const q of queries) {
        try {
          const r = await searchPapers({
            query: q,
            maxResults: PER_QUERY_MAX,
            projectSlug: proj.slug,
          });
          merged.push(...r.results);
          for (const e of r.errors) {
            yield { type: "warn", data: { persona: slug, query: q, message: e } };
          }
        } catch (e) {
          yield {
            type: "warn",
            data: {
              persona: slug,
              query: q,
              message: e instanceof Error ? e.message : String(e),
            },
          };
        }
      }

      // Dedupe within the persona by id, then filter by relevance.
      const seen = new Set<string>();
      const accepted: PaperArtifact[] = [];
      for (const p of merged) {
        if (seen.has(p.id)) continue;
        seen.add(p.id);
        if ((p.relevance_score ?? 0) >= MIN_RELEVANCE) accepted.push(p);
      }
      byPersona[slug] = accepted;
      yield {
        type: "deep-research-persona-done",
        data: {
          persona: persona.name,
          slug,
          accepted_count: accepted.length,
          total_count: merged.length,
        },
      };
    }

    // Persist on the hypothesis record so the workspace can read it
    // back without re-running the searches.
    try {
      const patched = patchHypothesis(proj.path, hyp.id, {
        additional_papers_by_persona: byPersona,
      });
      yield {
        type: "deep-research-result",
        data: {
          hypothesis_id: hyp.id,
          additional_papers_by_persona: byPersona,
          updated_at: patched?.updated_at ?? null,
        },
      };
    } catch (e) {
      yield {
        type: "error",
        data: { message: e instanceof Error ? e.message : String(e) },
      };
    }

    yield { type: "done", data: { success: true } };
  }

  return streamTaskAsSse({
    kind: "hypothesis-deep-research",
    project_slug: proj.slug,
    project_path: proj.path,
    scope: hyp.id,
    payload: { hypothesis_id: hyp.id, persona_count: active.length },
    runner,
  });
}
