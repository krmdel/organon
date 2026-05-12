// Phase 21 (v1.1+) — Chat-driven data analysis classifier (D-6).
//
// Routes a natural-language chat prompt to either the hypothesis path
// (statistical test) or the data-analysis path (plot / summary). v1.1
// uses a keyword heuristic — small, deterministic, tested. v1.2 can
// swap in a small LLM router behind the same interface.
//
// Default → "data-analysis": when no keyword fires, the safer fallback
// is exploratory rather than a stat test (which needs explicit groups).

export type ChatIntent = "hypothesis" | "data-analysis";

const HYPOTHESIS_KEYWORDS: RegExp[] = [
  /\bis\s+\w+\s+different\s+from\b/i,
  /\bcompare\b.*\bgroups?\b/i,
  /\bdoes\s+\w+\s+predict\b/i,
  /\bwhat\s+(explains|drives|causes)\b/i,
  /\bsignificant(ly)?\s+different\b/i,
  /\beffect\s+of\b/i,
  /\bvs\s+control\b/i,
  /\btest\s+(if|whether)\b/i,
  /\bgroup\s+(difference|effect)\b/i,
  /\bcorrelation\s+between\b/i,
  /\bp[-\s]?value\b/i,
];

const ANALYSIS_KEYWORDS: RegExp[] = [
  /\bplot\b/i,
  /\bchart\b/i,
  /\bgraph\b/i,
  /\bvisuali[sz]e\b/i,
  /\bhistogram\b/i,
  /\bscatter\b/i,
  /\bbox\s+plot\b/i,
  /\bheatmap\b/i,
  /\bmean\b/i,
  /\bmedian\b/i,
  /\bsummary\s+statistics\b/i,
  /\bdescribe\s+the\b/i,
];

export function classifyChatIntent(prompt: string): ChatIntent {
  const text = (prompt ?? "").trim();
  if (!text) return "data-analysis";
  for (const re of HYPOTHESIS_KEYWORDS) {
    if (re.test(text)) return "hypothesis";
  }
  for (const re of ANALYSIS_KEYWORDS) {
    if (re.test(text)) return "data-analysis";
  }
  return "data-analysis";
}

// Phase 26 (v1.2) — D-6+ LLM-routed router.
//
// Calls `/api/data/chat-intent` with the same prompt the chat route is
// about to send to a skill; on success returns the LLM's classification
// + source="llm". On failure (network error, non-200, parse failure)
// the route itself uses the keyword classifier and returns
// source="fallback" — the helper just unwraps the JSON.
//
// In-memory cache by trimmed prompt for the session lifetime saves the
// ~3 s round-trip on repeats. No disk persistence.

export type RoutedIntent = { intent: ChatIntent; source: "llm" | "fallback" };

type FetchLike = (
  input: string,
  init?: { method?: string; headers?: Record<string, string>; body?: string },
) => Promise<{ ok: boolean; status: number; json: () => Promise<unknown> }>;

const intentCache = new Map<string, RoutedIntent>();

/**
 * Phase 31 (v1.3) — D-6++ cache key composes model + prompt so a model
 * swap doesn't return cached results from the prior model. `default`
 * sentinel keeps the v1.2 cache surface intact for callers that don't
 * pass a model.
 */
function intentCacheKey(prompt: string, model?: string): string {
  return `${model ?? "default"}::${prompt.trim()}`;
}

export async function routeChatIntent(
  prompt: string,
  fetchFn: FetchLike,
  opts: { project?: string; baseUrl?: string; model?: string } = {},
): Promise<RoutedIntent> {
  const key = (prompt ?? "").trim();
  if (!key) return { intent: "data-analysis", source: "fallback" };
  const cacheKey = intentCacheKey(key, opts.model);
  const cached = intentCache.get(cacheKey);
  if (cached) return cached;

  const url = `${opts.baseUrl ?? ""}/api/data/chat-intent${
    opts.project ? `?project=${encodeURIComponent(opts.project)}` : ""
  }`;
  try {
    const res = await fetchFn(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: key, project: opts.project, model: opts.model }),
    });
    if (res.ok) {
      const json = (await res.json()) as Partial<RoutedIntent>;
      if (
        (json.intent === "hypothesis" || json.intent === "data-analysis") &&
        (json.source === "llm" || json.source === "fallback")
      ) {
        const result: RoutedIntent = { intent: json.intent, source: json.source };
        intentCache.set(cacheKey, result);
        return result;
      }
    }
  } catch {
    /* fall through to local fallback */
  }
  // Local fallback — same keyword classifier the route uses on its
  // own error path. Marked source="fallback" so the chat panel can
  // still surface the path that fired.
  const local: RoutedIntent = {
    intent: classifyChatIntent(prompt),
    source: "fallback",
  };
  intentCache.set(cacheKey, local);
  return local;
}
