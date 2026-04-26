# Research Methodology

> Adapted from [last30days by Ronnie-Nutrition](https://github.com/Ronnie-Nutrition/last30days-skill).
> Original approach used OpenAI Responses API (Reddit web_search) and xAI API (x_search)
> for direct platform access. This version uses WebSearch for a zero-dependency approach.

---

## Search Strategy by Query Type

Before searching, extract the **core subject** from the topic. Strip noise words:
- "emerging CRISPR delivery methods" → core: "CRISPR delivery"
- "hot topics in computational neuroscience" → core: "computational neuroscience"
- "what's happening with AlphaFold" → core: "AlphaFold"

Don't add terms from your own knowledge. If user says "spatial transcriptomics trends", search for exactly that — don't substitute "single-cell RNA-seq" or "Visium".

### BREAKTHROUGHS ("recent breakthroughs in X", "new discoveries")

| # | Query | Platform | Purpose |
|---|-------|----------|---------|
| 1 | `{topic} breakthrough site:reddit.com` | Reddit | Community reaction to discoveries |
| 2 | `{topic} site:reddit.com/r/science OR site:reddit.com/r/bioinformatics` | Reddit | Academic subreddit discussion |
| 3 | `{topic} breakthrough site:x.com OR site:twitter.com` | X | Researcher reactions |
| 4 | `{topic} site:biorxiv.org` | bioRxiv | Recent preprints |
| 5 | `{topic} site:arxiv.org` | arXiv | Recent preprints |
| 6 | `{topic} site:nature.com` | Nature | Journal coverage |
| 7 | `{topic} site:sciencedaily.com` | ScienceDaily | Science news |
| 8 | `{topic} breakthrough discovery 2026` | Web | Broad coverage |

### METHODS ("new techniques for X", "emerging methods")

| # | Query | Platform | Purpose |
|---|-------|----------|---------|
| 1 | `{topic} method protocol site:reddit.com` | Reddit | Community techniques |
| 2 | `{topic} site:reddit.com/r/bioinformatics OR site:reddit.com/r/labrats` | Reddit | Lab and bioinformatics communities |
| 3 | `{topic} new method site:x.com OR site:twitter.com` | X | Researcher announcements |
| 4 | `{topic} method site:biorxiv.org` | bioRxiv | Method preprints |
| 5 | `{topic} tool software site:github.com` | GitHub | Open-source tools |
| 6 | `{topic} protocol technique 2026` | Web | Published guides |
| 7 | `{topic} benchmark comparison` | Web | Method comparisons |

### DEBATES ("controversies in X", "what's the debate about X")

| # | Query | Platform | Purpose |
|---|-------|----------|---------|
| 1 | `{topic} debate controversy site:reddit.com` | Reddit | Community arguments |
| 2 | `{topic} site:reddit.com/r/science OR site:reddit.com/r/AskScience` | Reddit | Moderated discussion |
| 3 | `{topic} controversy site:x.com OR site:twitter.com` | X | Hot takes from researchers |
| 4 | `{topic} replication reproducibility` | Web | Replication concerns |
| 5 | `{topic} criticism limitations` | Web | Critical perspectives |
| 6 | `{topic} comment response site:pubmed.ncbi.nlm.nih.gov` | PubMed | Published responses/letters |

### GENERAL (default)

| # | Query | Platform | Purpose |
|---|-------|----------|---------|
| 1 | `{topic} site:reddit.com` | Reddit | Community discussion |
| 2 | `{topic} site:reddit.com/r/science OR site:reddit.com/r/MachineLearning` | Reddit | Academic subreddits |
| 3 | `{topic} site:reddit.com/r/bioinformatics OR site:reddit.com/r/neuroscience OR site:reddit.com/r/compsci` | Reddit | Domain-specific subreddits |
| 4 | `{topic} site:x.com OR site:twitter.com` | X | Real-time researcher sentiment |
| 5 | `{topic} site:biorxiv.org OR site:arxiv.org` | Preprints | Recent preprints |
| 6 | `{topic} site:pubmed.ncbi.nlm.nih.gov` | PubMed | Published literature |
| 7 | `{topic} site:nature.com OR site:science.org` | Journals | Journal news and commentary |
| 8 | `{topic} site:sciencedaily.com` | ScienceDaily | Science news |
| 9 | `{topic} 2026` | Web | Recent broad coverage |
| 10 | `{topic} review opinion` | Web | Expert perspectives |

---

## Academic Subreddit Reference

When the topic maps to a specific field, target these subreddits:

| Field | Subreddits |
|-------|-----------|
| General science | r/science, r/AskScience |
| Bioinformatics / Genomics | r/bioinformatics, r/genomics |
| Machine Learning / AI | r/MachineLearning, r/artificial, r/LocalLLaMA |
| Neuroscience | r/neuroscience, r/neuro |
| Biology / Lab work | r/labrats, r/biology, r/microbiology |
| Chemistry | r/chemistry, r/chempros |
| Physics | r/physics, r/AskPhysics |
| Computer Science | r/compsci, r/programming |
| Medicine / Clinical | r/medicine, r/medicalschool |
| Statistics | r/statistics, r/datascience |

---

## Depth Scaling

**Quick (5-8 searches):** Use the top 5-6 queries from the relevant table. Good for a fast pulse check.

**Balanced (8-12 searches, default):** Full query set plus 2-3 follow-up searches based on what the first results surface. If Reddit mentions a specific technique or tool, search for that specifically.

**Deep (12-18 searches):** Full query set plus targeted follow-ups. Add queries for:
- Specific subreddits that appeared in results (e.g., `{topic} site:reddit.com/r/specific_sub`)
- Specific labs/researchers that appeared as authorities
- Related topics that emerged from initial results
- Comparison queries ("method X vs method Y") if alternatives surfaced
- Preprint-specific searches on bioRxiv and arXiv

---

## Extracting Engagement Signals

WebSearch results often include engagement hints in snippets. Look for:

**Reddit:**
- "X upvotes" or "X points" in the snippet
- "X comments" — indicates active discussion
- Subreddit name — r/science (broad, heavily moderated) vs r/bioinformatics (niche but focused)
- Thread age — prefer threads from last 30 days

**X / Twitter:**
- Like counts, repost counts in snippets
- "viral" or high-engagement indicators
- Verified accounts or known researchers/PIs
- Quote tweets (indicates debate)

**Preprints / Publications:**
- Publication date — strongly prefer last 30 days
- Number of versions (preprints with v2, v3 indicate active revision)
- Whether it has editorial/news coverage alongside the paper
- Citation velocity if visible

**Web:**
- Publication date — strongly prefer last 30 days
- Author credibility — PIs, lab blogs, institutional sites
- Comment counts on articles
- "Updated" dates

---

## Source Quality Ranking

Not all sources are equal. Weight them:

| Source type | Weight | Why |
|------------|--------|-----|
| Published paper with editorial coverage | Very high | Peer-reviewed and deemed newsworthy |
| Preprint with 100+ tweets | High | Strong community attention pre-review |
| Reddit thread with 50+ upvotes in academic sub | High | Community-validated, real expert opinions |
| X post with high engagement from researchers | High | Trending in scientific community |
| Lab/PI blog post | Medium-High | Authority signal, first-hand expertise |
| Reddit thread with <10 upvotes | Medium | Real opinion but less validated |
| News article from science outlet | Medium | Current but may oversimplify |
| Generic science news article | Low-Medium | May be hype-driven or press-release rewrite |
| Press release without primary source link | Low | Often misleading or exaggerated |

**Cross-platform validation:** If the same insight appears on Reddit AND X AND a preprint server, that's the strongest possible signal. Prioritize these in synthesis.

---

## Common Pitfalls

1. **Adding your own knowledge to search terms.** Search for what the user said. Your training data may be outdated.
2. **Treating all sources equally.** A Reddit thread in r/bioinformatics with 500 upvotes matters more than a generic news article.
3. **Ignoring contradictions.** If Reddit says "method X is great" but a preprint shows limitations, report both. The contradiction IS the insight.
4. **Over-filtering by date.** Some evergreen threads get new comments recently. Include them if the discussion is current.
5. **Stopping at the first page.** If initial results are thin, reformulate and search again with different terms.
6. **Conflating preprint hype with validated findings.** Flag whether findings are peer-reviewed or preprint-only — this matters in science.
