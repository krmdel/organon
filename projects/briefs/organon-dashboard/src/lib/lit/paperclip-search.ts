/**
 * Phase 45 (v1.6) — F8: paperclip MCP wrapper.
 * Phase 55 (v2.1) — A1: bearer auth via PAPERCLIP_API_KEY + soft-disable
 *   via PAPERCLIP_DISABLED so a noisy 401 banner can be silenced when the
 *   researcher knows credentials aren't available locally.
 * Phase 55b (v2.1) — A1 follow-up after live-walk against gxl.ai docs:
 *   the public MCP server expects `X-API-Key: gxl_…` (NOT `Authorization:
 *   Bearer …`), exposes a single tool named `paperclip` (NOT `search`)
 *   that takes `{ command: "<cli string>" }`, and returns CLI text in
 *   `result.content[0].text` (NOT structured JSON). Wrapper rewritten
 *   accordingly; PAPERCLIP_API_KEY semantics unchanged.
 *
 * Talks to https://paperclip.gxl.ai/mcp via JSON-RPC 2.0. Returns
 * PaperResult[] with the same shape as pubmed/arxiv/openalex/s2 handlers
 * so the routing layer in search.ts can merge results uniformly.
 *
 * Fail-soft: any error raises a typed error that search.ts catches and
 * routes to the soft_errors[] surface; the API tier handles the result.
 */

import type { PaperResult } from "../paper-search/pubmed";
import { paperclipApiKey, paperclipDisabled } from "../env";

const PAPERCLIP_MCP_URL = "https://paperclip.gxl.ai/mcp";

/**
 * Phase 55 — sentinel error class so search.ts can recognise the soft-disable
 * branch and silently fall back without recording a noisy soft_errors entry.
 */
export class PaperclipDisabledError extends Error {
  constructor() {
    super("paperclip disabled");
    this.name = "PaperclipDisabledError";
  }
}

interface MCPResponse {
  jsonrpc?: string;
  id?: number | string;
  result?: {
    content?: Array<{ type?: string; text?: string }>;
  };
  error?: { code?: number; message?: string };
}

interface ParsedPaper {
  paperclip_id: string | null;
  title: string;
  authors: string[];
  source: string | null;
  date: string | null;
  doi: string | null;
  url: string;
  abstract: string;
}

/**
 * Wraps the paperclip MCP `paperclip` tool with a CLI-style `search`
 * command. Maps each parsed result to the shared PaperResult shape.
 *
 * @throws PaperclipDisabledError when PAPERCLIP_DISABLED is set — caller
 *   recognises this and skips the soft_errors banner entirely.
 * @throws Error on transport / protocol / auth failures — caller surfaces a
 *   "temporarily unavailable" soft_error and falls back to the API tier.
 */
export async function searchPaperclip(
  query: string,
  maxResults: number,
): Promise<PaperResult[]> {
  if (paperclipDisabled()) {
    throw new PaperclipDisabledError();
  }

  // Build a CLI-style command. Quote the query (escape any embedded
  // double quotes) so multi-word queries land as a single argument.
  const safeQuery = query.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
  const command = `search "${safeQuery}" -n ${Math.max(1, Math.floor(maxResults))}`;

  const body = {
    jsonrpc: "2.0",
    id: 1,
    method: "tools/call",
    params: {
      name: "paperclip",
      arguments: { command },
    },
  };

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "application/json, text/event-stream",
  };
  // Phase 55b — paperclip's gxl.ai endpoint authenticates via X-API-Key,
  // not Authorization: Bearer. Keys generated at https://paperclip.gxl.ai/keys
  // start with `gxl_` and validate against this header only.
  const apiKey = paperclipApiKey();
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }

  let resp: Response;
  try {
    resp = await fetch(PAPERCLIP_MCP_URL, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });
  } catch (e) {
    throw new Error(
      `paperclip transport: ${e instanceof Error ? e.message : String(e)}`,
    );
  }

  if (!resp.ok) {
    // Phase 55 — collapse 401/403 into a single "temporarily unavailable"
    // signal at the wrapper layer. The caller (search.ts) already strips
    // raw HTTP plumbing from the user-facing banner.
    if (resp.status === 401 || resp.status === 403) {
      throw new Error(`paperclip temporarily unavailable (HTTP ${resp.status})`);
    }
    throw new Error(`paperclip HTTP ${resp.status}`);
  }

  let payload: MCPResponse;
  try {
    payload = (await resp.json()) as MCPResponse;
  } catch (e) {
    throw new Error(
      `paperclip JSON parse: ${e instanceof Error ? e.message : String(e)}`,
    );
  }

  if (payload.error) {
    throw new Error(`paperclip MCP error: ${payload.error.message ?? "unknown"}`);
  }

  const text = payload.result?.content?.[0]?.text ?? "";
  if (!text) return [];

  return parsePaperclipText(text).map(toPaperResult);
}

/**
 * Phase 55b — parse paperclip's CLI-format `search` output.
 *
 * Each result block looks like:
 *
 *     1. <title>
 *        <authors, may end with "...">
 *        <paperclip_id> · <source> · <date>
 *        https://doi.org/<doi>
 *        "<abstract...>"
 *
 * Blocks separated by blank line(s). Header line ("Found N papers
 * [s_xxxxxxxx]") and trailing hints are skipped.
 */
export function parsePaperclipText(text: string): ParsedPaper[] {
  const blocks: string[][] = [];
  let current: string[] = [];
  for (const rawLine of text.split(/\r?\n/)) {
    if (/^\s{2}\d+\.\s/.test(rawLine)) {
      if (current.length > 0) blocks.push(current);
      current = [rawLine];
    } else if (current.length > 0) {
      current.push(rawLine);
    }
  }
  if (current.length > 0) blocks.push(current);

  const out: ParsedPaper[] = [];
  for (const lines of blocks) {
    const titleMatch = lines[0]?.match(/^\s{2}\d+\.\s+(.*)$/);
    if (!titleMatch) continue;
    const title = titleMatch[1].trim();
    const indented = lines
      .slice(1)
      .map((l) => l.replace(/^\s+/, ""))
      .filter((l) => l.length > 0);

    let authorsLine = "";
    let metaLine = "";
    let urlLine = "";
    const abstractParts: string[] = [];
    let inAbstract = false;
    for (const line of indented) {
      if (inAbstract) {
        abstractParts.push(line);
        continue;
      }
      if (/^https?:\/\//.test(line)) {
        urlLine = line;
        continue;
      }
      // The metadata line is the first ` · `-separated line we see — it
      // always carries paperclip_id · source · date, so 2+ separators is
      // a reliable distinguisher from author lists (which use ", "
      // commas, never ` · `). Authors may span multiple lines and end
      // with "..." when truncated; we never append after the meta line
      // is set.
      if (!metaLine && /\s·\s/.test(line)) {
        const segs = line.split(/\s·\s/);
        if (segs.length >= 2) {
          metaLine = line;
          continue;
        }
      }
      if (line.startsWith('"')) {
        inAbstract = true;
        abstractParts.push(line);
        continue;
      }
      if (!metaLine) {
        // Pre-meta lines belong to authors (paperclip wraps long author
        // lists across multiple lines).
        authorsLine = authorsLine ? `${authorsLine} ${line}` : line;
      }
    }

    const authors = authorsLine
      .replace(/\s*\.\.\.$/, "")
      .split(/,\s*/)
      .map((a) => a.trim())
      .filter((a) => a.length > 0);

    const metaSegs = metaLine.split(/\s·\s/).map((s) => s.trim());
    const paperclip_id = metaSegs[0] ?? null;
    const source = metaSegs[1] ?? null;
    const date = metaSegs[2] ?? null;

    let doi: string | null = null;
    const doiMatch = urlLine.match(/doi\.org\/(.+)$/i);
    if (doiMatch) doi = doiMatch[1].trim();

    const abstract = abstractParts
      .join(" ")
      .replace(/^"+|"+$/g, "")
      .trim();

    out.push({ paperclip_id, title, authors, source, date, doi, url: urlLine, abstract });
  }
  return out;
}

function toPaperResult(p: ParsedPaper): PaperResult {
  // Year extraction from the date string (YYYY-MM-DD or YYYY).
  let year = 0;
  if (p.date) {
    const m = p.date.match(/(\d{4})/);
    if (m) year = Number.parseInt(m[1], 10) || 0;
  }
  // Map paperclip's source labels to a journal-shaped string for the UI.
  const journal = p.source ?? "";

  // ID priority: prefer paperclip_id (paperclip-native), fall back to
  // doi-derived, then a random shrug. Stays compatible with the
  // computeArtifactId routing in search.ts which already handles
  // paperclip > doi > generic ordering.
  const id = p.paperclip_id ?? doiToId(p.doi);

  return {
    id,
    title: p.title,
    authors: p.authors,
    abstract: p.abstract,
    journal,
    year,
    doi: p.doi,
    url: p.url || (p.doi ? `https://doi.org/${p.doi}` : ""),
    source: "paperclip",
    citation_count: null,
  };
}

function doiToId(doi: string | null | undefined): string {
  if (!doi) return `paperclip-${Math.random().toString(36).slice(2, 10)}`;
  return doi.replace(/[^A-Za-z0-9]/g, "_");
}
