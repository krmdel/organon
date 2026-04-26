/**
 * arXiv API search client.
 * Uses the arXiv API to search for preprints by query.
 * No API key required. Rate limit: be polite (1 req/3sec recommended).
 */

import type { PaperResult } from "./pubmed.js";

const ARXIV_API_BASE = "http://export.arxiv.org/api/query";

/**
 * Extract text content between XML tags using regex.
 */
function extractTag(xml: string, tag: string): string {
  const regex = new RegExp(`<${tag}[^>]*>([\\s\\S]*?)</${tag}>`, "i");
  const match = xml.match(regex);
  return match ? match[1].trim() : "";
}

/**
 * Extract all occurrences of a tag's content from XML.
 */
function extractAllTags(xml: string, tag: string): string[] {
  const regex = new RegExp(`<${tag}[^>]*>([\\s\\S]*?)</${tag}>`, "gi");
  const results: string[] = [];
  let match;
  while ((match = regex.exec(xml)) !== null) {
    results.push(match[1].trim());
  }
  return results;
}

/**
 * Extract arXiv ID from an entry's <id> URL.
 * Example: "http://arxiv.org/abs/2301.12345v1" -> "2301.12345"
 */
function extractArxivId(idUrl: string): string {
  const match = idUrl.match(/abs\/(.+?)(?:v\d+)?$/);
  return match ? match[1] : idUrl;
}

/**
 * Parse a single arXiv <entry> block into a PaperResult.
 */
function parseArxivEntry(entryXml: string): PaperResult | null {
  const title = extractTag(entryXml, "title").replace(/\s+/g, " ");
  if (!title) return null;

  const idUrl = extractTag(entryXml, "id");
  const arxivId = extractArxivId(idUrl);

  // Extract author names from <author><name>...</name></author> blocks
  const authorBlocks = extractAllTags(entryXml, "author");
  const authors: string[] = [];
  for (const block of authorBlocks) {
    const name = extractTag(block, "name");
    if (name) {
      authors.push(name);
    }
  }

  const abstract = extractTag(entryXml, "summary").replace(/\s+/g, " ");
  const published = extractTag(entryXml, "published");
  const year = published ? parseInt(published.substring(0, 4), 10) : 0;

  return {
    id: `arxiv:${arxivId}`,
    title,
    authors,
    abstract,
    journal: "arXiv preprint",
    year,
    doi: null,
    url: `https://arxiv.org/abs/${arxivId}`,
    source: "arxiv",
    citation_count: null,
  };
}

/**
 * Search arXiv for papers matching the query.
 */
export async function searchArxiv(
  query: string,
  maxResults: number
): Promise<PaperResult[]> {
  const url =
    `${ARXIV_API_BASE}?search_query=all:${encodeURIComponent(query)}` +
    `&max_results=${maxResults}` +
    `&sortBy=relevance`;

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(
      `arXiv API failed: ${response.status} ${response.statusText}`
    );
  }

  const xml = await response.text();

  // Parse individual entries from Atom XML
  const entryRegex = /<entry>[\s\S]*?<\/entry>/gi;
  const results: PaperResult[] = [];
  let match;

  while ((match = entryRegex.exec(xml)) !== null) {
    const result = parseArxivEntry(match[0]);
    if (result) {
      results.push(result);
    }
  }

  return results;
}
