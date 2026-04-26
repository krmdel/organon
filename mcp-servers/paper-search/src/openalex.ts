/**
 * OpenAlex API search client.
 * Uses the OpenAlex REST API to search for academic works.
 * Free API key required since Feb 2026.
 */

import type { PaperResult } from "./pubmed.js";

const OPENALEX_BASE = "https://api.openalex.org";
const MAILTO = "organon@example.com";

/**
 * Reconstruct abstract text from OpenAlex inverted index format.
 * The inverted index maps words to their positions in the text.
 */
function reconstructAbstract(
  invertedIndex: Record<string, number[]> | null | undefined
): string {
  if (!invertedIndex) return "";

  const words: [number, string][] = [];
  for (const [word, positions] of Object.entries(invertedIndex)) {
    for (const pos of positions) {
      words.push([pos, word]);
    }
  }

  words.sort((a, b) => a[0] - b[0]);
  return words.map(([, word]) => word).join(" ");
}

interface OpenAlexWork {
  id: string;
  display_name: string;
  publication_year: number;
  doi: string | null;
  cited_by_count: number;
  abstract_inverted_index: Record<string, number[]> | null;
  authorships: Array<{
    author: {
      display_name: string;
    };
  }>;
  primary_location: {
    source: {
      display_name: string;
    } | null;
  } | null;
}

interface OpenAlexSearchResponse {
  results: OpenAlexWork[];
}

/**
 * Map an OpenAlex work object to a PaperResult.
 */
function mapWorkToResult(work: OpenAlexWork): PaperResult {
  const authors = work.authorships.map((a) => a.author.display_name);
  const abstract = reconstructAbstract(work.abstract_inverted_index);
  const journal =
    work.primary_location?.source?.display_name ?? "Unknown";

  // Strip https://doi.org/ prefix from DOI if present
  let doi: string | null = work.doi;
  if (doi && doi.startsWith("https://doi.org/")) {
    doi = doi.replace("https://doi.org/", "");
  }

  return {
    id: work.id,
    title: work.display_name,
    authors,
    abstract,
    journal,
    year: work.publication_year,
    doi,
    url: work.id,
    source: "openalex",
    citation_count: work.cited_by_count,
  };
}

/**
 * Search OpenAlex for papers matching the query.
 */
export async function searchOpenAlex(
  query: string,
  maxResults: number,
  apiKey?: string,
  publicationDate?: string
): Promise<PaperResult[]> {
  let url =
    `${OPENALEX_BASE}/works?search=${encodeURIComponent(query)}` +
    `&per_page=${maxResults}` +
    `&mailto=${MAILTO}`;

  if (apiKey) {
    url += `&api_key=${apiKey}`;
  }

  if (publicationDate) {
    const [fromDate, toDate] = publicationDate.split(":");
    const filters: string[] = [];
    if (fromDate) filters.push(`from_publication_date:${fromDate}`);
    if (toDate) filters.push(`to_publication_date:${toDate}`);
    if (filters.length > 0) {
      url += `&filter=${filters.join(",")}`;
    }
  }

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(
      `OpenAlex API failed: ${response.status} ${response.statusText}`
    );
  }

  const data = (await response.json()) as OpenAlexSearchResponse;
  return data.results.map(mapWorkToResult);
}

/**
 * Get detailed information about a paper by its DOI.
 */
export async function getWorkByDoi(
  doi: string,
  apiKey?: string
): Promise<PaperResult | null> {
  let url =
    `${OPENALEX_BASE}/works/https://doi.org/${encodeURIComponent(doi)}` +
    `?mailto=${MAILTO}`;

  if (apiKey) {
    url += `&api_key=${apiKey}`;
  }

  const response = await fetch(url);
  if (!response.ok) {
    if (response.status === 404) return null;
    throw new Error(
      `OpenAlex DOI lookup failed: ${response.status} ${response.statusText}`
    );
  }

  const work = (await response.json()) as OpenAlexWork;
  return mapWorkToResult(work);
}
