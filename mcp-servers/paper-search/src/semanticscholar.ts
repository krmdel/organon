/**
 * Semantic Scholar API search client.
 * Uses the Semantic Scholar Academic Graph API to search for papers.
 * Rate limiting: 1 RPS without API key (shared pool), higher with key.
 */

import type { PaperResult } from "./pubmed.js";

const S2_BASE = "https://api.semanticscholar.org/graph/v1";
const S2_FIELDS =
  "title,authors,abstract,year,citationCount,journal,externalIds,url,publicationDate";

interface S2Paper {
  paperId: string;
  title: string;
  abstract: string | null;
  year: number | null;
  citationCount: number;
  journal: { name: string } | null;
  externalIds: {
    DOI?: string;
    ArXivId?: string;
    PubMedId?: string;
    CorpusId?: string;
  } | null;
  url: string;
  authors: Array<{ authorId: string; name: string }>;
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Map a Semantic Scholar paper object to a PaperResult.
 */
function mapS2PaperToResult(paper: S2Paper): PaperResult {
  const authors = paper.authors.map((a) => a.name);
  const doi = paper.externalIds?.DOI ?? null;
  return {
    id: `s2:${paper.paperId}`,
    title: paper.title,
    authors,
    abstract: paper.abstract ?? "",
    journal: paper.journal?.name ?? "Unknown",
    year: paper.year ?? 0,
    doi,
    url: paper.url,
    source: "semanticscholar",
    citation_count: paper.citationCount,
  };
}

/**
 * Search Semantic Scholar for papers matching the query.
 * Supports optional API key for dedicated rate limits.
 * Retries once on HTTP 429 with 2-second backoff.
 */
export async function searchSemanticScholar(
  query: string,
  maxResults: number,
  apiKey?: string,
  publicationDate?: string
): Promise<PaperResult[]> {
  let url =
    `${S2_BASE}/paper/search?query=${encodeURIComponent(query)}` +
    `&limit=${maxResults}` +
    `&fields=${S2_FIELDS}`;

  if (publicationDate) {
    const [fromDate, toDate] = publicationDate.split(":");
    const fromYear = fromDate ? fromDate.substring(0, 4) : undefined;
    const toYear = toDate ? toDate.substring(0, 4) : undefined;
    if (fromYear && toYear) {
      url += `&year=${fromYear}-${toYear}`;
    } else if (fromYear) {
      url += `&year=${fromYear}-`;
    } else if (toYear) {
      url += `&year=-${toYear}`;
    }
  }

  const headers: Record<string, string> = {};
  if (apiKey) {
    headers["x-api-key"] = apiKey;
  } else {
    // Respect shared rate pool without API key
    await delay(1000);
  }

  let response = await fetch(url, { headers });

  // Retry once on rate limit (HTTP 429)
  if (response.status === 429) {
    await delay(2000);
    response = await fetch(url, { headers });
  }

  if (!response.ok) {
    throw new Error(
      `Semantic Scholar API failed: ${response.status} ${response.statusText}`
    );
  }

  const data = (await response.json()) as { data?: S2Paper[] };
  return (data.data ?? []).map(mapS2PaperToResult);
}
