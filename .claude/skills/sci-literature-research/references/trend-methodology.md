# Trend Detection Methodology

## Algorithm Overview

**Goal:** Detect publication volume surges in a scientific field (D-11).

**Data source:** OpenAlex API via MCP `search_papers` with `source: "openalex"`.

**Approach:** Compare paper counts in a recent time window against a prior window of the same length. Topics with the highest ratio of recent-to-prior counts are "trending."

## Step-by-Step

### Step 1: Define Parameters
- **Field/topic:** From user input (required -- ask if not provided)
- **Window length:** Default 12 months (D-13). User can override with `--months N`.
- **Recent window:** Last N months from today
- **Prior window:** N months before the recent window
- **Date format:** The `publication_date` parameter uses `YYYY-MM-DD:YYYY-MM-DD` (from:to). Either side can be omitted for open-ended ranges.

### Step 2: Query OpenAlex for Topic-Level Counts

**Primary approach** -- use `group_by=topics.id` if supported:

Search OpenAlex with the field query and `publication_date` filter for each window. If the API supports `group_by=topics.id`, use it to get per-topic paper counts in a single request.

Example query for recent window (last 12 months):
```
search_papers(query="cancer immunotherapy", source="openalex", publication_date="2025-04-01:")
```

Example query for prior window (12 months before the recent window):
```
search_papers(query="cancer immunotherapy", source="openalex", publication_date="2024-04-01:2025-03-31")
```

**Fallback approach** -- keyword extraction:

If `group_by=topics.id` returns errors or empty results:
1. Search the field in the recent window to get paper results
2. Extract top keywords/phrases from titles and abstracts (look for recurring 2-3 word phrases)
3. For each extracted keyword: search in both time windows and compare counts
4. This is slower (multiple API calls) but works without topic-level aggregation

### Step 3: Calculate Surge Ratios

For each topic or keyword:
```
surge_ratio = recent_count / max(prior_count, 1)
```

Use `max(prior_count, 1)` to avoid division by zero for entirely new topics.

### Step 4: Filter and Rank

1. **Minimum threshold:** Require at least 10 papers in the recent window (avoid noise from very small topics)
2. **Adjust for field size:**
   - Very niche fields (< 100 total papers): lower threshold to 3
   - Broad fields (> 10,000 total papers): raise threshold to 50
3. **Rank by surge_ratio descending**
4. **Take top 5-10 results**

### Step 5: Fetch Evidence

For each trending topic, fetch 1-2 representative papers:
- Highest-cited paper in the recent window for that topic
- Most recent paper for that topic

## Presentation Format (D-12)

```
[N]. **Topic Name** -- surge ratio: X.Xx
Paper count (recent window): N | Paper count (prior window): N
Key paper: [Title] (Author, Year)
Summary: [One-line description of why this topic is trending]
```

## Fallback Strategies

| Situation | Fallback |
|-----------|----------|
| `group_by=topics.id` returns error or empty | Use keyword extraction approach (Step 2 fallback) |
| Semantic Scholar date filter is year-granularity only | Use OpenAlex as primary source for precise date windows, Semantic Scholar as supplementary |
| Fewer than 5 trending topics found | Show what is available with a note: "Only N trending topics found for this field" |
| API rate limited or down | Report the error and suggest trying again later |

## Edge Cases

- **Very niche fields:** May have few papers total. Lower minimum threshold to 3 and note limited data.
- **Very broad fields:** May have too many topics. Increase minimum threshold to 50 and suggest narrowing the query.
- **New fields (< 2 years old):** No prior window exists for comparison. Note this limitation and show absolute paper counts instead of surge ratios.
- **Seasonal variation:** Some fields publish more at certain times (e.g., conference deadlines). A 12-month window smooths this, but shorter windows may show artifacts.
