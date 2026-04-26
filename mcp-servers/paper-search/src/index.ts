/**
 * Paper Search MCP Server
 *
 * Provides two tools for searching and retrieving academic paper metadata:
 * - search_papers: Search across PubMed, arXiv, OpenAlex, and Semantic Scholar
 * - get_paper_details: Look up a paper by DOI via OpenAlex
 *
 * Environment variables:
 * - NCBI_API_KEY: Optional. Higher rate limits for PubMed (10 req/sec vs 3/sec).
 * - OPENALEX_API_KEY: Optional but recommended. Required for OpenAlex since Feb 2026.
 * - S2_API_KEY: Optional. Dedicated rate limit for Semantic Scholar (1 RPS vs shared pool).
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { searchPubMed } from "./pubmed.js";
import { searchArxiv } from "./arxiv.js";
import { searchOpenAlex, getWorkByDoi } from "./openalex.js";
import { searchSemanticScholar } from "./semanticscholar.js";
import { checkPapersWithCode } from "./code-links.js";
import type { PaperResult } from "./pubmed.js";

const NCBI_API_KEY = process.env.NCBI_API_KEY || undefined;
const OPENALEX_API_KEY = process.env.OPENALEX_API_KEY || undefined;
const S2_API_KEY = process.env.S2_API_KEY || undefined;

const server = new McpServer({
  name: "paper-search",
  version: "1.0.0",
});

/**
 * Tool: search_papers
 * Search for academic papers across PubMed, arXiv, OpenAlex, and/or Semantic Scholar.
 */
server.tool(
  "search_papers",
  "Search for academic papers across PubMed, arXiv, OpenAlex, and Semantic Scholar. Returns title, authors, abstract, journal, year, DOI, and citation count.",
  {
    query: z.string().describe("Search query for academic papers"),
    source: z
      .enum(["pubmed", "arxiv", "openalex", "semanticscholar", "all"])
      .default("all")
      .describe("Which database to search"),
    max_results: z
      .number()
      .min(1)
      .max(50)
      .default(10)
      .describe("Maximum results per source"),
    publication_date: z
      .string()
      .optional()
      .describe(
        "Filter by publication date range. Format: 'YYYY-MM-DD:YYYY-MM-DD' (from:to). Either side can be omitted for open-ended ranges: ':2024-12-31' (before date) or '2024-01-01:' (after date)."
      ),
  },
  async ({ query, source, max_results, publication_date }) => {
    const results: PaperResult[] = [];
    const errors: string[] = [];

    const searches: Promise<void>[] = [];

    if (source === "pubmed" || source === "all") {
      searches.push(
        searchPubMed(query, max_results, NCBI_API_KEY)
          .then((r) => {
            results.push(...r);
          })
          .catch((e: Error) => {
            errors.push(`PubMed: ${e.message}`);
          })
      );
    }

    if (source === "arxiv" || source === "all") {
      searches.push(
        searchArxiv(query, max_results)
          .then((r) => {
            results.push(...r);
          })
          .catch((e: Error) => {
            errors.push(`arXiv: ${e.message}`);
          })
      );
    }

    if (source === "openalex" || source === "all") {
      searches.push(
        searchOpenAlex(query, max_results, OPENALEX_API_KEY, publication_date)
          .then((r) => {
            results.push(...r);
          })
          .catch((e: Error) => {
            errors.push(`OpenAlex: ${e.message}`);
          })
      );
    }

    if (source === "semanticscholar" || source === "all") {
      searches.push(
        searchSemanticScholar(query, max_results, S2_API_KEY, publication_date)
          .then((r) => {
            results.push(...r);
          })
          .catch((e: Error) => {
            errors.push(`Semantic Scholar: ${e.message}`);
          })
      );
    }

    await Promise.all(searches);

    // Enrich top results with code repository links (best-effort, parallel).
    // Only the top 5 by citation count to avoid rate-limiting Papers With Code.
    const sortedForEnrichment = [...results]
      .sort((a, b) => (b.citation_count ?? 0) - (a.citation_count ?? 0))
      .slice(0, 5);

    await Promise.all(
      sortedForEnrichment.map(async (paper) => {
        const codeLink = await checkPapersWithCode(paper.title, paper.doi);
        if (codeLink) {
          paper.github_url = codeLink.github_url;
          paper.code_available = true;
        } else {
          paper.code_available = false;
        }
      })
    );

    const output: {
      total: number;
      results: PaperResult[];
      errors?: string[];
    } = {
      total: results.length,
      results,
    };

    if (errors.length > 0) {
      output.errors = errors;
    }

    return {
      content: [
        {
          type: "text" as const,
          text: JSON.stringify(output, null, 2),
        },
      ],
    };
  }
);

/**
 * Tool: get_paper_details
 * Look up detailed metadata for a paper by its DOI via OpenAlex.
 */
server.tool(
  "get_paper_details",
  "Get detailed metadata for a paper by its DOI. Returns title, authors, abstract, journal, year, citation count, and source URL.",
  {
    doi: z.string().describe("DOI of the paper to look up"),
  },
  async ({ doi }) => {
    try {
      const result = await getWorkByDoi(doi, OPENALEX_API_KEY);

      if (!result) {
        return {
          content: [
            {
              type: "text" as const,
              text: JSON.stringify(
                { error: `No paper found for DOI: ${doi}` },
                null,
                2
              ),
            },
          ],
        };
      }

      return {
        content: [
          {
            type: "text" as const,
            text: JSON.stringify(result, null, 2),
          },
        ],
      };
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e);
      return {
        content: [
          {
            type: "text" as const,
            text: JSON.stringify(
              { error: `DOI lookup failed: ${message}` },
              null,
              2
            ),
          },
        ],
      };
    }
  }
);

// Connect via stdio transport
const transport = new StdioServerTransport();
await server.connect(transport);
