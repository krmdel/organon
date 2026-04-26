---
name: sci-literature-research
description: >
  Search, summarize, cite, and analyze trends in scientific literature.
  Federated search across PubMed, arXiv, OpenAlex, and Semantic Scholar
  via the paper-search MCP server. AI-powered paper summaries personalized
  to your research profile. BibTeX citation export with AuthorYear keys.
  Trend analysis showing emerging research areas with evidence.
  Unified trend analysis combining publication surges with social/web
  signals (Reddit, X, web) via sci-trending-research integration.
  Scope options: publications, social, or combined.
  Triggers on: "search papers", "find papers", "literature search",
  "paper summary", "summarize paper", "cite", "bibtex", "export citation",
  "publication surge", "unified trends", "combined trends",
  "social trends", "publication trends",
  "parallel fanout", "fan out search", "concurrent literature search".
  Does NOT trigger for: data analysis, writing, hypothesis generation.
---

# Literature Research

## Outcome

Four capabilities from a single skill:
- **Search** -- federated search across 4 databases, deduplicated and ranked
- **Summarize** -- structured AI summaries personalized to your research profile
- **Cite** -- BibTeX export with AuthorYear keys to project .bib files
- **Trends** -- emerging research areas ranked by publication volume surge

Outputs go to `projects/sci-literature/`. BibTeX .bib files go to the active project folder if one exists (`projects/briefs/*/brief.md` with `status: active`), otherwise `projects/sci-literature/`.

## Context Needs

| File | Load level | How it shapes this skill |
|------|-----------|--------------------------|
| `research_context/research-profile.md` | full | Personalizes summaries with "Relevance to Your Work" section |
| `context/learnings.md` | `## sci-literature-research` section | Apply previous feedback |

Load if they exist. Proceed without them if not.

## Dependencies

| Skill / MCP | Required? | What it provides | Without it |
|-------------|-----------|-----------------|------------|
| `sci-research-profile` | Optional | Research profile for personalized summaries | Generic summaries without "Relevance to Your Work" section |
| `sci-trending-research` | Optional | Social/web trend data for combined scope | Publications-only trends (no social signals) |
| `tool-paperclip` skill (CLI) | Optional | Deep biomedical corpus search across 8M+ full-text papers from bioRxiv, medRxiv, PMC: hybrid search, regex grep, SQL queries on `documents` table, figure analysis (`ask-image`), supplements/CSV reading, `map` summarization across papers | Federated search via PubMed/arXiv/OpenAlex/S2 (broad coverage, less depth) |

Requires paper-search MCP server to be configured in .mcp.json. Paperclip is installed via `curl -fsSL https://paperclip.gxl.ai/install.sh | bash` (CLI binary at `~/.local/bin/paperclip`) — the `tool-paperclip` skill at `.claude/skills/tool-paperclip/SKILL.md` exposes it to Claude Code.

**IMPORTANT: MCP tools are deferred and must be loaded before first use.**
Before calling any `mcp__paper-search__*` tool, run `ToolSearch` with
query `select:mcp__paper-search__search_papers,mcp__paper-search__get_paper_details`
to load the tool schemas. Do NOT use `listMcpResources` — it returns empty for
this server. Call the search/detail tools directly after loading them via ToolSearch.

---

## Step 0: Detect Intent

Parse user request into one of 4 modes:
- **search** -- "search", "find", "papers about", "literature on"
- **summarize** -- "summarize", "summary of", "tell me about [paper]", "explain [paper]"
- **cite** -- "cite", "bibtex", "export", "citation", "add to bib"
- **trends** -- "trending", "trends", "emerging", "hot topics", "what's new in"

If unclear, ask which mode the scientist wants.

---

## Step 0.5: Source Routing (search mode only)

Choose **Paperclip** (biomedical depth), **federated** (cross-disciplinary breadth), or **both**. Full decision tree in `references/paperclip-routing.md`; calibration in `references/paperclip-coverage-test.md`.

Quick rule (updated 2026-04-14):
- Biomedical discovery / review / manuscript → **BOTH**, dedupe by DOI (paperclip=recency+full-text, OpenAlex=seminal canon).
- Biomedical deep ops (grep, `map`, `ask-image`, SQL, section reading) → **Paperclip only** (Step 1b).
- Non-biomedical (pure ML/physics/CS/math/econ) → **federated only** (Step 1).
- Cross-disciplinary → **BOTH**, dedupe by DOI.
- Paperclip unreachable → graceful fallback to federated, tell the user.

---

## Step 1: Search (mode=search)

1. Call MCP tool `search_papers` with `source: "all"` and `max_results: 10`.
2. **Dedupe by DOI** (D-03): group by normalized DOI (lowercase, strip `https://doi.org/`); keep highest citation_count + longest abstract + merged source lists. Papers without DOIs stay distinct with their source badge.
3. **Rank** using composite score `0.4·norm_citations + 0.3·relevance_position + 0.3·recency` and assign ranks 1..N.
4. **Display** as numbered list:
   ```
   [N]. **Title** (Year)
   Authors (first 3, then "et al." if more)
   Journal | Citations: N | Relevance: #N of M | Sources: [PubMed] [arXiv] [S2] [OpenAlex]
   DOI: 10.xxxx/xxxxx
   [Code ✓] https://github.com/org/repo   (or [Code ✗] if checked)
   Abstract snippet (first sentence)
   ```
   Code badge comes from `github_url`/`code_available` fields (top-5-by-citations enriched via Papers With Code — see `references/code-linking.md`). Year + Journal per LIT-05.
5. Offer: "Select a paper number to summarize, `cite N` to export BibTeX, or `code N` to view the repo."

**OPT-IN: parallel fan-out.** The default Step 1 flow is sequential. For wall-clock-critical workflows (big literature sweeps, CI-like pipelines), opt in to `scripts/fanout.py` — it fires PubMed / arXiv / OpenAlex / S2 concurrently via `ThreadPoolExecutor`, dedupes by DOI then arXiv ID, and gracefully degrades when one source fails. See the **Parallel Fan-out** section below and the TDD suite at `tests/test_fanout.py` for contract proofs.

---

## Step 1b: Deep Biomedical Search (Paperclip)

Routed from Step 0.5 for biomedical + deep-capability. **Delegate to `tool-paperclip`** — wraps the Paperclip CLI (`~/.local/bin/paperclip`), exposing 8M+ full-text papers from bioRxiv / medRxiv / PMC.

1. Print the skill-routing notice, then read `.claude/skills/tool-paperclip/SKILL.md` if needed.
2. Pick the right sub-command by intent:
   - Discovery → `paperclip search "query"` (hybrid BM25+vector)
   - Phrase/pattern across full text → `paperclip grep "pattern" /papers/`
   - Compare N papers on one question → `paperclip map "question"`
   - Figure analysis → `paperclip ask-image <id>/figures/<file> "question"`
   - Metadata filter → `paperclip sql "SELECT ..."` (read-only)
   - Lookup by DOI/PMC/PMID → `paperclip lookup doi/pmc/pmid <value>`
3. Display in Step 1 numbered format with `[Paperclip]` badge.
4. **Citations MUST use the `citations.gxl.ai/papers/<doc_id>#L<n>` format** (see tool-paperclip SKILL.md).
5. On CLI failure → fall back to Step 1 federated search, tell the user.
6. Offer next actions: paper number to read sections, `cite` to export BibTeX, or follow-up grep/map/figure.

---

## Step 2: Summarize (mode=summarize)

1. Get paper metadata -- from search results (if user selects a number) or via `get_paper_details` with a DOI.
2. Load `research_context/research-profile.md` if it exists.
3. Generate structured summary following `references/summary-template.md`:
   - Title, authors, journal, year, citations, DOI
   - **Key Findings** -- 2-4 bullet points from abstract
   - **Methods** -- methodology described in abstract
   - **Limitations** -- caveats or limitations mentioned
   - **Relevance to Your Work** (D-07) -- connects paper to scientist's research interests and active questions from research-profile.md. Omit if no profile exists.
   - **Sources** -- badges showing which databases found this paper
4. Offer: "Type 'cite' to export this paper as BibTeX, or search for more papers."

---

## Step 3: Cite (mode=cite)

1. Prompt scientist to select which papers to export (from current search results per D-10).
2. Generate BibTeX entries following `references/bibtex-format.md`:
   - Citation key: AuthorYear (D-09) -- first author last name + year, suffix a/b/c on collision
   - Escape LaTeX special characters: `& -> \&`, `% -> \%`, `# -> \#`, `_ -> \_`
   - Wrap title in `{}` for capitalization preservation
   - `@article` for journal papers, `@misc` with `eprint`/`archiveprefix=arXiv` for arXiv preprints
3. Append to project .bib file (D-08):
   - If active project exists: write to that project folder
   - Otherwise: write to `projects/sci-literature/{YYYY-MM-DD}_citations.bib`
   - Auto-deduplicate by DOI -- skip if citation with same DOI already exists in .bib
4. **Emit a `{bib-stem}.quotes.json` sidecar next to the .bib** (D-14). This is the upstream seed that downstream skills (sci-writer, sci-auditor) consume when building their draft citation sidecars — it prevents quote fabrication by giving writers real pre-fetched source text to work from.
   - Call `scripts/quotes_ops.py build_quotes_sidecar(entries, bib_path)`; each entry dict must include `key`, optional `doi`, `title`, `abstract`/`summary`. For Paperclip results, include `doc_id` and `content.lines` so the builder can emit `citations.gxl.ai/papers/<doc_id>#L<n>` anchors.
   - Schema is documented in `references/bibtex-format.md` § Quotes sidecar (v1). Do not hand-author the file; always go through `quotes_ops.build_quotes_sidecar` so the schema stays consistent.
5. Show generated BibTeX entries, the sidecar path, and confirm both files exist.

---

## Step 4: Trends (mode=trends)

1. Follow `references/unified-trends.md` for the full algorithm. Use `references/trend-methodology.md` for publication-specific surge ratio details.
2. Ask for field/topic if not provided. Accept optional flags:
   - `--months N` (default 12 per D-13) -- time window for publication trends
   - `--scope publications|social|combined` (default: publications) -- what signals to analyze
3. **Scope: publications** (default):
   - Use MCP tool `search_papers` with `source: "openalex"` and `publication_date` parameter for time-windowed searches
   - Compute surge ratios per trend-methodology.md
   - Present ranked list of 5-10 topics (D-12) with paper counts and key papers
4. **Scope: social**:
   - Invoke `sci-trending-research` skill for the same topic
   - Present engagement-weighted insights from Reddit, X, and web
   - If API keys missing, falls back to web search -- note to user
5. **Scope: combined**:
   - Run both publications and social scopes
   - Merge into unified report with "Publication Trends", "Community & Web Trends", and "Cross-Signal Highlights" sections
   - Cross-Signal Highlights show topics trending in BOTH academic literature AND community discussions
6. Present results in the format defined in `references/unified-trends.md`.
7. Offer to search deeper into any trend or export key papers as BibTeX.

---

## After Each Interaction

- Log the operation to reproducibility ledger via `repro/repro_logger.py` if available.
- Offer next actions based on mode (summarize after search, cite after summarize, etc.).

---

## Parallel Fan-out

Opt-in accelerator for Step 1. Sequential federated search stays the default — reach for `parallel_fanout` only when wall-clock matters (large literature sweeps, cron pipelines, batched trend audits). Contract proven by `tests/test_fanout.py` (18 tests, 99% coverage).

```python
from fanout import parallel_fanout, FanoutAllFailedError

# Each backend: callable(query) -> list[{"doi"/"arxiv_id", "title", "year", "authors", ...}]
backends = {
    "pubmed":   pubmed_search,
    "arxiv":    arxiv_search,
    "openalex": openalex_search,
    "s2":       s2_search,
}

try:
    out = parallel_fanout(
        "CAR-T toxicity",
        backends,
        timeout_per_source=30.0,
        max_results_per_source=50,
    )
except FanoutAllFailedError as err:
    # Every source failed; fall back to paperclip or inform the user.
    ...

# out = {"results": [...], "degraded": bool, "failed_sources": [...], "source_counts": {...}}
```

Guarantees:
- **Parallel**: ~1× slowest backend, not the sum.
- **Dedup**: DOI first (normalized), then arXiv ID; never cross-matches the two.
- **Graceful degradation**: individual timeout / exception flips `degraded=True` and records the source in `failed_sources`.
- **All-fail** raises `FanoutAllFailedError` with per-source messages.
- **No MCP at import** — safe for unit tests and headless CI.

`sequential_search(query, backends)` is also exported as the legacy path for parity tests; same return shape, no threads.

---

## Rules

*Updated automatically when the user flags issues. Read before every run.*

- **2026-04-04**: Never use `listMcpResources` to discover paper-search tools. They are deferred tools — load them with `ToolSearch(select:mcp__paper-search__search_papers,mcp__paper-search__get_paper_details)` before calling. Direct `curl` fallback to Semantic Scholar is slow and unreliable; always prefer MCP tools.

---

## Self-Update

If the user flags an issue with the output -- wrong parsing, bad format, missing context, incorrect assumption -- update the `## Rules` section in this SKILL.md immediately with the correction and today's date.
