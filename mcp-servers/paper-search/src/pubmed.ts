/**
 * PubMed E-utilities search client.
 * Uses NCBI E-utils esearch + efetch to find and retrieve paper metadata.
 * Rate limiting: 3 req/sec without API key, 10 req/sec with key.
 */

export interface PaperResult {
  id: string;
  title: string;
  authors: string[];
  abstract: string;
  journal: string;
  year: number;
  doi: string | null;
  url: string;
  source: "pubmed" | "arxiv" | "openalex" | "semanticscholar";
  citation_count: number | null;
  // Optional code repository metadata, populated by code-links enrichment
  github_url?: string;
  code_available?: boolean;
}

const EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils";
const TOOL_NAME = "organon";
const TOOL_EMAIL = "organon@example.com";

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Extract text content from an XML element by tag name.
 * Returns empty string if not found.
 */
function extractXmlText(xml: string, tag: string): string {
  const regex = new RegExp(`<${tag}[^>]*>([\\s\\S]*?)</${tag}>`, "i");
  const match = xml.match(regex);
  return match ? match[1].trim() : "";
}

/**
 * Extract all text values for a given tag from XML.
 */
function extractAllXmlText(xml: string, tag: string): string[] {
  const regex = new RegExp(`<${tag}[^>]*>([\\s\\S]*?)</${tag}>`, "gi");
  const results: string[] = [];
  let match;
  while ((match = regex.exec(xml)) !== null) {
    results.push(match[1].trim());
  }
  return results;
}

/**
 * Parse a single PubmedArticle XML block into a PaperResult.
 */
function parsePubmedArticle(articleXml: string): PaperResult | null {
  const title = extractXmlText(articleXml, "ArticleTitle");
  if (!title) return null;

  // Extract authors
  const authorBlocks = extractAllXmlText(articleXml, "Author");
  const authors: string[] = [];
  for (const block of authorBlocks) {
    const lastName = extractXmlText(block, "LastName");
    const foreName = extractXmlText(block, "ForeName");
    if (lastName) {
      authors.push(foreName ? `${foreName} ${lastName}` : lastName);
    }
  }

  const abstract = extractXmlText(articleXml, "AbstractText");
  const journal = extractXmlText(articleXml, "Title");
  const yearStr = extractXmlText(articleXml, "Year");
  const year = yearStr ? parseInt(yearStr, 10) : 0;

  // Extract PMID
  const pmidMatch = articleXml.match(/<PMID[^>]*>(\d+)<\/PMID>/);
  const pmid = pmidMatch ? pmidMatch[1] : "";

  // Extract DOI from ArticleIdList
  const articleIdList = extractXmlText(articleXml, "ArticleIdList");
  const doiMatch = articleIdList.match(
    /<ArticleId IdType="doi">([^<]+)<\/ArticleId>/
  );
  const doi = doiMatch ? doiMatch[1] : null;

  return {
    id: `pmid:${pmid}`,
    title,
    authors,
    abstract,
    journal,
    year,
    doi,
    url: `https://pubmed.ncbi.nlm.nih.gov/${pmid}`,
    source: "pubmed",
    citation_count: null,
  };
}

/**
 * Search PubMed for papers matching the query.
 * Uses E-utilities: esearch to get PMIDs, then efetch to get full records.
 */
export async function searchPubMed(
  query: string,
  maxResults: number,
  apiKey?: string
): Promise<PaperResult[]> {
  // Step 1: esearch to get PMIDs
  let searchUrl =
    `${EUTILS_BASE}/esearch.fcgi?db=pubmed` +
    `&term=${encodeURIComponent(query)}` +
    `&retmax=${maxResults}` +
    `&retmode=json` +
    `&tool=${TOOL_NAME}` +
    `&email=${TOOL_EMAIL}`;

  if (apiKey) {
    searchUrl += `&api_key=${apiKey}`;
  }

  const searchResponse = await fetch(searchUrl);
  if (!searchResponse.ok) {
    throw new Error(
      `PubMed esearch failed: ${searchResponse.status} ${searchResponse.statusText}`
    );
  }

  const searchData = (await searchResponse.json()) as {
    esearchresult?: { idlist?: string[] };
  };
  const pmids = searchData.esearchresult?.idlist ?? [];

  if (pmids.length === 0) {
    return [];
  }

  // Rate limiting delay: 350ms between calls (safe for 3 req/sec without API key)
  await delay(350);

  // Step 2: efetch to get full records
  let fetchUrl =
    `${EUTILS_BASE}/efetch.fcgi?db=pubmed` +
    `&id=${pmids.join(",")}` +
    `&retmode=xml` +
    `&tool=${TOOL_NAME}` +
    `&email=${TOOL_EMAIL}`;

  if (apiKey) {
    fetchUrl += `&api_key=${apiKey}`;
  }

  const fetchResponse = await fetch(fetchUrl);
  if (!fetchResponse.ok) {
    throw new Error(
      `PubMed efetch failed: ${fetchResponse.status} ${fetchResponse.statusText}`
    );
  }

  const xml = await fetchResponse.text();

  // Parse individual articles from XML
  const articleRegex =
    /<PubmedArticle>[\s\S]*?<\/PubmedArticle>/gi;
  const articles: PaperResult[] = [];
  let match;

  while ((match = articleRegex.exec(xml)) !== null) {
    const result = parsePubmedArticle(match[0]);
    if (result) {
      articles.push(result);
    }
  }

  return articles;
}
