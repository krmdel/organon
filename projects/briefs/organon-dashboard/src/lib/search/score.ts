/**
 * PHASE_6_TASKS.md T26 — substring + prefix scoring.
 *
 * Score is in [0, 1] where 1 = exact match. Tokens contribute additively.
 * Designed for ≤ 500 candidates; ranks via descending score then ascending
 * (id length, lower-case id) for deterministic tiebreaks.
 */

export type Scored<T> = { item: T; score: number; matched: string[] };

const tokenize = (s: string): string[] =>
  s.toLowerCase().split(/[^\p{L}\p{N}]+/u).filter(Boolean);

export function scoreText(text: string, query: string): { score: number; matched: string[] } {
  const ql = query.trim().toLowerCase();
  if (!ql) return { score: 0, matched: [] };
  const t = text.toLowerCase();
  if (!t) return { score: 0, matched: [] };
  // Exact id / prefix match boosts.
  if (t === ql) return { score: 1, matched: [ql] };
  if (t.startsWith(ql)) return { score: 0.92, matched: [ql] };
  if (t.includes(ql)) return { score: 0.7, matched: [ql] };
  const queryTokens = tokenize(ql);
  if (queryTokens.length === 0) return { score: 0, matched: [] };
  const textTokens = new Set(tokenize(text));
  const matched = queryTokens.filter((q) => {
    if (textTokens.has(q)) return true;
    for (const tt of textTokens) if (tt.startsWith(q)) return true;
    return false;
  });
  if (matched.length === 0) return { score: 0, matched: [] };
  return { score: 0.45 * (matched.length / queryTokens.length), matched };
}
