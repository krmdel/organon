/**
 * Phase 47 (v1.6) — F10: deterministic relevance confidence scoring.
 *
 * Algorithm: tokenize query + paper title + paper abstract → IDF-weighted
 * overlap, normalised to [0, 1]. Title weight 0.4, abstract weight 0.6.
 *
 * The IDF table ships as a static JSON asset (relevance-corpus.json) so
 * scoring is O(query_tokens) per paper — no request-time corpus pass.
 *
 * Embeddings are deferred to v1.7+ per brief decision Q4. The interface
 * surface stays stable so a swap is local.
 *
 * Special cases:
 *   - Empty query → score 0 (caller knows it's not informative).
 *   - Empty abstract → exact-match-with-title heuristic: when every
 *     query token is present in the title, return ≥ 0.9 even though the
 *     0.4-weight title score alone would cap at 0.4.
 *   - Token-stop list is implicit — IDF for filler words (a, the, of)
 *     is 0 so they contribute nothing to the weighted sum.
 */

import corpusData from "./relevance-corpus.json" with { type: "json" };

interface Corpus {
  total_docs: number;
  tokens: Record<string, number>;
}

const CORPUS = corpusData as Corpus;
const TITLE_WEIGHT = 0.4;
const ABSTRACT_WEIGHT = 0.6;
const DEFAULT_IDF = 1.0;

export interface RelevanceScore {
  score: number;
  breakdown: { title: number; abstract: number };
}

export function scoreRelevance(
  query: string,
  paper: { title?: string; abstract?: string },
): RelevanceScore {
  const qTokens = tokenize(query);
  if (qTokens.length === 0) {
    return { score: 0, breakdown: { title: 0, abstract: 0 } };
  }

  const titleTokens = new Set(tokenize(paper.title ?? ""));
  const abstractTokens = new Set(tokenize(paper.abstract ?? ""));

  const titleScore = idfOverlap(qTokens, titleTokens);
  const abstractScore = idfOverlap(qTokens, abstractTokens);

  // Phase 47 — exactMatch heuristic: when the abstract is missing AND
  // every query token is in the title, scale the title score so the
  // user sees a high-confidence chip. Without this branch the empty-
  // abstract case caps at 0.4 (the title weight), which felt artifically
  // low for what is, in fact, a perfect topical match.
  // Phase 56 (v2.1) — A2: soften the heuristic. The previous "every token
  // must match" rule starved partial-coverage matches with empty abstracts
  // (most paperclip + some OpenAlex hits) — they capped at 0.4 × titleScore
  // and dropped below the 0.6 high-confidence threshold even when the
  // paper was clearly on-topic. New rule: when the abstract is empty AND
  // the IDF-weighted title overlap clears 0.8, surface a confident score.
  const allInTitle = qTokens.every((t) => titleTokens.has(t));
  if (abstractTokens.size === 0) {
    if (allInTitle) {
      return {
        score: Math.min(1, 0.9 + 0.1 * titleScore),
        breakdown: { title: titleScore, abstract: 0 },
      };
    }
    if (titleScore >= 0.8) {
      // 80%+ IDF coverage on the title with no abstract → score ≥ 0.7.
      return {
        score: Math.min(1, 0.7 + 0.2 * titleScore),
        breakdown: { title: titleScore, abstract: 0 },
      };
    }
  }

  const score = TITLE_WEIGHT * titleScore + ABSTRACT_WEIGHT * abstractScore;
  return {
    score: clamp01(score),
    breakdown: { title: titleScore, abstract: abstractScore },
  };
}

function tokenize(text: string): string[] {
  return text
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter((t) => t.length > 1);
}

function idf(token: string): number {
  return CORPUS.tokens[token] ?? DEFAULT_IDF;
}

/**
 * IDF-weighted overlap. Sum of IDFs for shared tokens divided by the sum
 * of the query's IDFs — gives [0, 1] where 1 is "every meaningful query
 * token appears in the candidate set".
 */
function idfOverlap(qTokens: string[], candidate: Set<string>): number {
  if (qTokens.length === 0) return 0;
  let queryWeight = 0;
  let sharedWeight = 0;
  for (const t of qTokens) {
    const w = idf(t);
    queryWeight += w;
    if (candidate.has(t)) sharedWeight += w;
  }
  return queryWeight > 0 ? sharedWeight / queryWeight : 0;
}

function clamp01(x: number): number {
  if (x < 0) return 0;
  if (x > 1) return 1;
  return x;
}
