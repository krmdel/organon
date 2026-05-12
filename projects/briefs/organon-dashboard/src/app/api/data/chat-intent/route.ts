import { resolveProjectFromRequest } from "@/lib/projects";
import { runClaude } from "@/lib/claude-runner";
import { classifyChatIntent, type ChatIntent } from "@/lib/data/chat-intent";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Phase 26 (v1.2) — D-6+ LLM-routed chat-intent classifier.
 *
 * POST `{ prompt }` → `{ intent, source }` where source is "llm" on the
 * happy path and "fallback" when the LLM round-trip fails or returns
 * a token we can't parse. The keyword classifier from v1.1 stays as
 * the fallback — see `src/lib/data/chat-intent.ts`.
 *
 * Decisions per the v1.2 brief §8.3:
 *  - Single round-trip, no streaming. The chat UX waits ~3 s at most.
 *  - Output capped to a single token; anything longer = parse failure
 *    → fallback.
 *  - source: "llm" | "fallback" exposed so the panel can surface
 *    "(routed by LLM)" vs "(routed by keywords)" debug info.
 */

type Body = { project?: string; prompt?: string; model?: string };

const VALID_INTENTS: ChatIntent[] = ["hypothesis", "data-analysis"];
const INTENT_TOKEN_TIMEOUT_MS = 30_000;

/**
 * Phase 31 (v1.3) — D-6++ resolve the model for the intent classifier.
 * Body wins over env. Empty string is treated as unset so a stray
 * `model: ""` in a request body falls through to the env default.
 */
function resolveIntentModel(body: Body): string | undefined {
  if (typeof body.model === "string" && body.model.length > 0) return body.model;
  const env = process.env.ORGANON_FAST_INTENT_MODEL;
  if (typeof env === "string" && env.length > 0) return env;
  return undefined;
}

function parseSingleToken(stdout: string): ChatIntent | null {
  // Take the first non-empty line; lowercase + trim. Reject anything
  // that's not a single recognised token (>1 word, punctuation, etc.).
  const lines = stdout
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l.length > 0);
  if (lines.length === 0) return null;
  // Last non-empty line is usually the model's actual answer (skill
  // banners often print to the head of stdout).
  const candidate = lines[lines.length - 1].toLowerCase();
  // Strip trailing punctuation and a leading dash list prefix.
  const cleaned = candidate.replace(/[.,!?]+$/g, "").replace(/^[-*]\s+/, "").trim();
  // Any number of words > 1 means the model didn't follow the
  // single-token directive — bail to fallback.
  if (/\s/.test(cleaned)) return null;
  if (VALID_INTENTS.includes(cleaned as ChatIntent)) {
    return cleaned as ChatIntent;
  }
  return null;
}

export async function POST(request: Request) {
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
  const prompt = (body.prompt ?? "").trim();
  if (!prompt) {
    return Response.json({ error: "prompt required" }, { status: 400 });
  }

  // LLM classifier round-trip. Single-shot, capped output, no streaming.
  const llmPrompt = [
    `You are a single-token classifier. Read the researcher question below.`,
    `Output exactly one token: \`hypothesis\` (if the question asks for a statistical test, group comparison, or causal claim)`,
    `or \`data-analysis\` (if the question asks for a plot, summary, or exploratory description).`,
    `Output ONLY the single token. No prose, no punctuation, no explanation.`,
    ``,
    `researcher_question=${prompt}`,
  ].join("\n");

  const abort = new AbortController();
  const timeout = setTimeout(() => abort.abort(), INTENT_TOKEN_TIMEOUT_MS);
  let stdout = "";
  let exitOk = false;
  // Phase 31 (v1.3) — body > env > runner default.
  const resolvedModel = resolveIntentModel(body);

  try {
    for await (const evt of runClaude({
      projectPath: project.path,
      projectSlug: project.slug,
      prompt: llmPrompt,
      abortSignal: abort.signal,
      model: resolvedModel,
    })) {
      if (evt.type === "stdout") stdout += evt.chunk;
      if (evt.type === "exit") exitOk = !!evt.success;
    }
  } catch {
    /* fall through to fallback */
  } finally {
    clearTimeout(timeout);
  }

  if (exitOk) {
    const parsed = parseSingleToken(stdout);
    if (parsed) {
      return Response.json(
        { intent: parsed, source: "llm" as const },
        { status: 200 },
      );
    }
  }

  // Fallback path — keyword classifier from v1.1.
  const fallbackIntent = classifyChatIntent(prompt);
  return Response.json(
    { intent: fallbackIntent, source: "fallback" as const },
    { status: 200 },
  );
}
