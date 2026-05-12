import path from "node:path";
// paper-search modules — copied from mcp-servers/paper-search/src/ at scaffold time.
// Re-sync via `cp ../../../../mcp-servers/paper-search/src/{pubmed,arxiv,openalex,semanticscholar,code-links}.ts ../paper-search/`
// when the MCP server's source changes. Direct file copy avoids Turbopack's
// external-file resolution issue (works for prod builds but not dev).
import { searchPubMed } from "../paper-search/pubmed";
import { searchArxiv } from "../paper-search/arxiv";
import { searchOpenAlex } from "../paper-search/openalex";
import { searchSemanticScholar, RateLimitedError } from "../paper-search/semanticscholar";
import { checkPapersWithCode } from "../paper-search/code-links";
import type { PaperResult } from "../paper-search/pubmed";
import type { PaperArtifact } from "../artifacts/types";
import { ncbiApiKey, openalexApiKey, s2ApiKey } from "../env";
import { organonRoot } from "../paths";
import { isBiomedicalQuery, rerankByDomain } from "./query-class";
import { searchPaperclip, PaperclipDisabledError } from "./paperclip-search";
import { scoreRelevance } from "./relevance";

export type SearchSource = "pubmed" | "arxiv" | "openalex" | "semanticscholar" | "paperclip";

/**
 * Phase 45 (v1.6) — F8: when biomedical detection fires AND the caller didn't
 * pin sources, paperclip is the primary source. If paperclip returns at least
 * this many hits, the API tier (PubMed / OpenAlex / S2) is skipped — that's
 * "enough triage material for the researcher". Below the threshold, we fan
 * out to the API tier and merge.
 */
const PAPERCLIP_FALLBACK_THRESHOLD = 8;

export interface SearchOptions {
  query: string;
  sources?: SearchSource[];
  maxResults?: number;
  publicationDate?: string;
  /** Project slug — controls library_path field in returned artifacts. */
  projectSlug: string;
  /** Optional brief metadata. When set, overrides the keyword classifier
   *  for biomedical-vs-not detection (controls arXiv default + rerank). */
  field?: string | null;
}

export interface SearchResult {
  total: number;
  results: PaperArtifact[];
  /** Hard per-source failures — render as red error toast. */
  errors: string[];
  /**
   * Phase 37 (v1.4) — soft per-source conditions (rate-limit, partial
   * timeout). Render as a yellow info banner; results are usable but
   * may be incomplete. Distinct from `errors` so the UI rendering
   * stays semantic-aware (red vs yellow).
   */
  soft_errors: string[];
  /** Diagnostic — true if the query was classified biomedical, surfaced
   *  to the UI so the caller can render the "arXiv off by default" hint. */
  biomedical: boolean;
}

const DEFAULT_SOURCES: SearchSource[] = ["pubmed", "arxiv", "openalex", "semanticscholar"];
// Phase 7 T6.10 — when the caller doesn't pin sources AND the query
// classifies as biomedical, drop arXiv from the default federation. The
// UI keeps arXiv as a one-click toggle so researchers can opt back in.
// Phase 45 (v1.6) — paperclip is auto-included on biomedical queries; the
// router below short-circuits to paperclip-primary when the threshold hits.
const BIOMEDICAL_DEFAULT_SOURCES: SearchSource[] = ["paperclip", "pubmed", "openalex", "semanticscholar"];

/**
 * Federated search across PubMed / arXiv / OpenAlex / Semantic Scholar.
 * Direct import of the paper-search modules per PHASE_1_TASKS.md D4 — no MCP
 * roundtrip, no `claude -p` spawn.
 *
 * Steps:
 *  1. Fan out per source in parallel.
 *  2. Dedupe by normalized DOI; merge `sources` arrays for matched pairs.
 *  3. Rank by composite score `0.4·norm_citations + 0.3·position + 0.3·recency`.
 *  4. Enrich top 5 by citations with code-link metadata (best-effort).
 *  5. Map to PaperArtifact (the wire + on-disk shape).
 */
export async function searchPapers(opts: SearchOptions): Promise<SearchResult> {
  const biomedical = isBiomedicalQuery(opts.query, opts.field);
  // Phase 7 T6.10 — biomedical queries default arXiv off; explicit `sources`
  // override (caller still owns the choice).
  const sources = opts.sources && opts.sources.length > 0
    ? opts.sources
    : (biomedical ? BIOMEDICAL_DEFAULT_SOURCES : DEFAULT_SOURCES);
  const maxResults = opts.maxResults ?? 10;

  const errors: string[] = [];
  // Phase 37 (v1.4) — B4: rate-limit cases land here, not in errors.
  const soft_errors: string[] = [];
  const allResults: PaperResult[] = [];

  // Phase 45 (v1.6) — F8: paperclip routing layer.
  // When biomedical AND paperclip is in the source set (auto-on or
  // user-toggled), run paperclip first. If it clears the fallback
  // threshold we skip the API tier entirely; otherwise we fan out and
  // merge. Non-biomedical queries fall straight through to the API tier
  // even if the user explicitly toggled paperclip on (it joins as a
  // peer source rather than the primary).
  const paperclipEnabled = sources.includes("paperclip");
  let skipPaperclipPeer = false;
  if (biomedical && paperclipEnabled) {
    try {
      const paperclipResults = await searchPaperclip(opts.query, maxResults);
      allResults.push(...paperclipResults);
      if (paperclipResults.length >= PAPERCLIP_FALLBACK_THRESHOLD) {
        // Skip the API tier — paperclip already returned enough triage
        // material. The merged path below still runs dedupeByDoi over
        // these hits in case any future call adds peers.
        return finishRanking(opts, biomedical, sources, allResults, errors, soft_errors, maxResults);
      }
      if (paperclipResults.length < PAPERCLIP_FALLBACK_THRESHOLD) {
        // Below threshold — fan out to API tier and merge. Skip the
        // paperclip peer-source call inside the fanout to avoid double-fetch.
        skipPaperclipPeer = true;
      }
    } catch (e) {
      // Phase 55 (v2.1) — A1: PAPERCLIP_DISABLED short-circuits silently
      // (no banner). Other failures surface a researcher-readable
      // "temporarily unavailable" line instead of leaking HTTP plumbing.
      if (e instanceof PaperclipDisabledError) {
        skipPaperclipPeer = true;
      } else {
        const msg = e instanceof Error ? e.message : String(e);
        const auth = /HTTP\s4(0[13])/i.test(msg) || /temporarily unavailable/i.test(msg);
        soft_errors.push(
          auth
            ? "paperclip: temporarily unavailable — using PubMed/arXiv/OpenAlex/S2 instead"
            : `paperclip: ${msg} — falling back to API tier`,
        );
        skipPaperclipPeer = true;
      }
    }
  }

  const fanoutSources = paperclipEnabled
    ? sources.filter((s) => s !== "paperclip" || !skipPaperclipPeer)
    : sources;

  await Promise.all(
    fanoutSources.map(async (source) => {
      try {
        const r = await runSource(source, opts.query, maxResults, opts.publicationDate);
        allResults.push(...r);
      } catch (e) {
        if (e instanceof RateLimitedError) {
          soft_errors.push(
            `${e.source}: rate-limited (${e.attempts} attempt${e.attempts === 1 ? "" : "s"} — results may be incomplete)`,
          );
        } else {
          errors.push(`${source}: ${e instanceof Error ? e.message : String(e)}`);
        }
      }
    }),
  );

  return finishRanking(opts, biomedical, sources, allResults, errors, soft_errors, maxResults);
}

/**
 * Phase 45 (v1.6) — F8: extracted from searchPapers so the paperclip
 * primary-only short-circuit can re-use the dedupe + rank + enrich + map
 * pipeline without duplicating ~50 lines.
 */
async function finishRanking(
  opts: SearchOptions,
  biomedical: boolean,
  sources: SearchSource[],
  allResults: PaperResult[],
  errors: string[],
  soft_errors: string[],
  maxResults: number,
): Promise<SearchResult> {
  // 1) Capture per-source order (used in ranking) before dedupe shuffles things.
  const positions = new Map<string, number>();
  allResults.forEach((p, i) => positions.set(`${p.source}:${p.id}`, i));

  // 2) Dedupe by normalized DOI; otherwise keep distinct.
  const deduped = dedupeByDoi(allResults);

  // 3) Rank.
  const maxCitations = Math.max(1, ...deduped.map((p) => p.citation_count ?? 0));
  const currentYear = new Date().getFullYear();
  let ranked = deduped
    .map((p) => {
      const norm = (p.citation_count ?? 0) / maxCitations;
      const pos = positions.get(`${p.source}:${p.id}`) ?? maxResults;
      const posScore = 1 - pos / Math.max(1, maxResults);
      const recencyScore = p.year ? Math.max(0, 1 - (currentYear - p.year) / 20) : 0;
      const score = 0.4 * norm + 0.3 * posScore + 0.3 * recencyScore;
      return { paper: p, score };
    })
    .sort((a, b) => b.score - a.score)
    .map((x) => x.paper);

  // 3.5) Phase 7 T6.11 — biomedical queries with arXiv enabled push
  // arXiv-only hits below PubMed/OpenAlex/S2. Multi-source matches (e.g.
  // arXiv + OpenAlex on a math-bio paper) keep their original rank since
  // sources_merged.length > 1.
  if (sources.includes("arxiv")) {
    ranked = rerankByDomain(ranked, biomedical);
  }

  // 4) Best-effort code enrichment for top-5 by citations.
  const topByCitations = [...ranked]
    .sort((a, b) => (b.citation_count ?? 0) - (a.citation_count ?? 0))
    .slice(0, 5);
  await Promise.all(
    topByCitations.map(async (paper) => {
      try {
        const link = await checkPapersWithCode(paper.title, paper.doi);
        if (link) {
          paper.github_url = link.github_url;
          paper.code_available = true;
        } else {
          paper.code_available = false;
        }
      } catch {
        // ignore — enrichment is best-effort
      }
    }),
  );

  // 5) Map to PaperArtifact.
  const artifacts = ranked.map((p) => toPaperArtifact(p, opts.projectSlug));

  // 6) Phase 47 (v1.6) — F10: stamp relevance_score on each artifact so
  //    the UI can render the chip + threshold filter. Cheap (O(query×paper))
  //    so we can run it inline on every search.
  for (const a of artifacts) {
    const rel = scoreRelevance(opts.query, { title: a.title, abstract: a.abstract });
    a.relevance_score = rel.score;
    a.relevance_breakdown = rel.breakdown;
  }

  return { total: artifacts.length, results: artifacts, errors, soft_errors, biomedical };
}

async function runSource(
  source: SearchSource,
  query: string,
  maxResults: number,
  publicationDate?: string,
): Promise<PaperResult[]> {
  switch (source) {
    case "pubmed":
      return searchPubMed(query, maxResults, ncbiApiKey());
    case "arxiv":
      return searchArxiv(query, maxResults);
    case "openalex":
      return searchOpenAlex(query, maxResults, openalexApiKey(), publicationDate);
    case "semanticscholar":
      return searchSemanticScholar(query, maxResults, s2ApiKey(), publicationDate);
    case "paperclip":
      // Phase 45 (v1.6) — F8: paperclip as a peer source. The biomedical
      // primary path runs in searchPapers BEFORE the fanout; this branch
      // only fires when the user explicitly toggles paperclip on a
      // non-biomedical query.
      return searchPaperclip(query, maxResults);
  }
}

function normalizeDoi(doi: string | null | undefined): string | null {
  if (!doi) return null;
  return doi
    .toLowerCase()
    .replace(/^https?:\/\/(dx\.)?doi\.org\//, "")
    .replace(/^doi:/, "")
    .trim();
}

interface MergedPaper extends PaperResult {
  sources_merged: SearchSource[];
}

function dedupeByDoi(results: PaperResult[]): MergedPaper[] {
  const byDoi = new Map<string, MergedPaper>();
  const noDoi: MergedPaper[] = [];

  for (const p of results) {
    const norm = normalizeDoi(p.doi);
    if (!norm) {
      noDoi.push({ ...p, sources_merged: [p.source] });
      continue;
    }
    const existing = byDoi.get(norm);
    if (!existing) {
      byDoi.set(norm, { ...p, sources_merged: [p.source] });
    } else {
      // Keep the one with more citations and a longer abstract; union sources.
      const better = pickBetter(existing, p);
      const sources = Array.from(new Set([...existing.sources_merged, p.source]));
      byDoi.set(norm, { ...better, sources_merged: sources });
    }
  }

  return [...byDoi.values(), ...noDoi];
}

function pickBetter(a: MergedPaper, b: PaperResult): MergedPaper {
  const aScore = (a.citation_count ?? 0) + (a.abstract?.length ?? 0) / 1000;
  const bScore = (b.citation_count ?? 0) + (b.abstract?.length ?? 0) / 1000;
  if (bScore > aScore) {
    return { ...b, sources_merged: a.sources_merged };
  }
  return a;
}

function toPaperArtifact(p: MergedPaper, projectSlug: string): PaperArtifact {
  // Per PHASE_1_TASKS.md §5.1, id = {source}-{source_id} with priority
  // pmid > arxiv > openalex > s2 > paperclip > doi.
  const ids: PaperArtifact["source_ids"] = {
    pmid: p.source === "pubmed" ? p.id : null,
    arxiv: p.source === "arxiv" ? p.id : null,
    openalex: p.source === "openalex" ? p.id : null,
    s2: p.source === "semanticscholar" ? p.id : null,
    // Phase 45 (v1.6) — paperclip results stamp their id here. When DOI
    // dedupe matches against a peer source, computeArtifactId still
    // prefers the higher-priority id — paperclip is fallback below s2.
    paperclip: p.source === "paperclip" ? p.id : null,
    doi: normalizeDoi(p.doi),
  };

  const id = computeArtifactId(ids);
  const libraryPath = path.posix.join(
    "projects",
    projectSlug === "__root__" ? "__root__" : projectSlug,
    "papers",
    `${id}.json`,
  );

  const artifact: PaperArtifact = {
    _artifact: "paper",
    schema_version: 1,
    id,
    source_ids: ids,
    title: p.title,
    authors: p.authors,
    year: p.year || -1,
    journal: p.journal || "",
    abstract: p.abstract || "",
    url: p.url,
    doi_url: ids.doi ? `https://doi.org/${ids.doi}` : null,
    pdf_url: null,
    citation_count: p.citation_count ?? null,
    sources: p.sources_merged,
    library_path: libraryPath,
    saved_at: null,
  };

  if (p.code_available !== undefined) {
    artifact.code = {
      available: p.code_available,
      github_url: p.github_url,
    };
  }

  return artifact;
}

function computeArtifactId(ids: PaperArtifact["source_ids"]): string {
  if (ids.pmid) return `pmid-${ids.pmid}`;
  if (ids.arxiv) return `arxiv-${ids.arxiv}`;
  if (ids.openalex) return `openalex-${ids.openalex}`;
  if (ids.s2) return `s2-${ids.s2}`;
  if (ids.paperclip) return `paperclip-${ids.paperclip}`;
  if (ids.doi) return `doi-${ids.doi.replace(/[^A-Za-z0-9]/g, "_")}`;
  // Fallback — unlikely but keeps the type safe.
  return `paper-${Math.random().toString(36).slice(2, 10)}`;
}

void organonRoot;
