/**
 * Code repository link resolution for papers.
 *
 * Queries the Papers With Code public API to find associated GitHub
 * repositories for academic papers. Best-effort: any failure returns null
 * and the paper result still flows through without code metadata.
 */

export interface CodeLink {
  github_url: string;
  framework?: string;
  stars?: number;
}

const PWC_BASE = "https://paperswithcode.com/api/v1";
const REQUEST_TIMEOUT_MS = 3000;

interface PwcPaper {
  id: string;
  title: string;
  url_pdf?: string;
  url_abs?: string;
}

interface PwcSearchResponse {
  count: number;
  results: PwcPaper[];
}

interface PwcRepository {
  url: string;
  framework?: string;
  stars?: number;
}

interface PwcRepoResponse {
  count: number;
  results: PwcRepository[];
}

/**
 * Fetch with a timeout. Aborts the request if it exceeds REQUEST_TIMEOUT_MS.
 */
async function fetchWithTimeout(
  url: string,
  ms: number = REQUEST_TIMEOUT_MS
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  try {
    return await fetch(url, { signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Look up code repository links for a paper by title (and optional DOI).
 *
 * Strategy:
 *   1. Search Papers With Code by title
 *   2. If a match is found, fetch its repositories list
 *   3. Return the highest-starred GitHub repo (if any)
 *
 * Returns null on any error or if no code is found.
 */
export async function checkPapersWithCode(
  title: string,
  _doi?: string | null
): Promise<CodeLink | null> {
  if (!title || title.trim().length === 0) return null;

  try {
    // Step 1: search Papers With Code by title
    const searchUrl =
      `${PWC_BASE}/papers/?q=${encodeURIComponent(title)}&items_per_page=3`;
    const searchRes = await fetchWithTimeout(searchUrl);
    if (!searchRes.ok) return null;

    const searchData = (await searchRes.json()) as PwcSearchResponse;
    if (!searchData.results || searchData.results.length === 0) return null;

    // Take the first result (PWC's relevance ranking)
    const paperId = searchData.results[0].id;

    // Step 2: fetch repositories for this paper
    const repoUrl = `${PWC_BASE}/papers/${encodeURIComponent(paperId)}/repositories/`;
    const repoRes = await fetchWithTimeout(repoUrl);
    if (!repoRes.ok) return null;

    const repoData = (await repoRes.json()) as PwcRepoResponse;
    if (!repoData.results || repoData.results.length === 0) return null;

    // Pick the highest-starred GitHub repo
    const githubRepos = repoData.results.filter((r) =>
      r.url?.includes("github.com")
    );
    if (githubRepos.length === 0) return null;

    githubRepos.sort((a, b) => (b.stars ?? 0) - (a.stars ?? 0));
    const top = githubRepos[0];

    return {
      github_url: top.url,
      framework: top.framework,
      stars: top.stars,
    };
  } catch (_e) {
    // Network error, timeout, parse error — fail gracefully
    return null;
  }
}
