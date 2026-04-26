# Paper-to-Code Linking

The paper-search MCP server enriches search results with code repository links via the **Papers With Code** public API. This makes it easy to find papers that have published, runnable code — useful for reproducing results, building on prior methods, and verifying claims.

## How It Works

1. After federated search returns results, the MCP server runs code-link enrichment on the top 5 results (by citation count) in parallel.
2. For each enriched paper, it queries Papers With Code by title.
3. If a match is found, it fetches the paper's repositories list and picks the **highest-starred GitHub repo**.
4. Failed lookups are silent — papers still return without code metadata.
5. The enrichment is rate-limited to top 5 to avoid hammering Papers With Code.

## Result Schema

When code is available, the `PaperResult` includes:
- `github_url` — direct link to the GitHub repository
- `code_available: true`

When no code is found:
- `code_available: false` (and no `github_url`)

When enrichment was skipped (paper not in top 5):
- Both fields are absent

## Display Format

In Step 1 search results, show a code badge after the Sources line:

```
[3]. **Attention Is All You Need** (2017)
Vaswani, Shazeer, Parmar, et al.
arXiv | Citations: 95234 | Sources: [arXiv] [S2]
DOI: 10.48550/arXiv.1706.03762
[Code ✓] https://github.com/tensorflow/tensor2tensor
Abstract: The dominant sequence transduction models...
```

Or:
```
[Code ✗] No code repository found
```

Or (not enriched):
```
(Code link not checked — paper outside top 5 by citation count)
```

## Offer to View Code

After listing results with code badges, offer:
> "Type `code N` to view repo N, or `summarize N` for the abstract."

When the user picks a code link, you can:
- Show a brief description ("[Code Available] {github_url}")
- Offer to open the URL in browser via WebFetch
- Offer to scan the README for usage examples

## Limitations

- **Coverage:** Papers With Code is strongest in ML/AI/CS papers. Biomedical papers are sparsely covered.
- **Rate limiting:** Only top 5 results are enriched per search to keep latency low.
- **No fallback:** If Papers With Code is down, results return without code metadata — this is a best-effort enhancement.
- **No GitHub API:** We don't fetch live repo stats (last commit, license, open issues). The Papers With Code data is what you get.
