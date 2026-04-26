# Unified Trend Analysis Methodology

## Overview

Unified trend analysis combines **publication volume trends** (academic literature) with **social/web discussion trends** (Reddit, X, web) to give scientists a comprehensive view of what is emerging in their field.

Three scope modes are available. The scientist selects a scope with `--scope publications|social|combined` (default: `publications`).

---

## Scope: publications (default)

Uses the existing `trend-methodology.md` algorithm for publication surge detection.

### How it works

1. Define time windows using `--months N` (default 12).
2. Call `search_papers` with `source: "openalex"` and `publication_date` parameter for each window:
   - **Recent window:** `publication_date="YYYY-MM-DD:"` (from start of recent window to today)
   - **Prior window:** `publication_date="YYYY-MM-DD:YYYY-MM-DD"` (same length, immediately before recent)
3. Extract topics via `group_by=topics.id` or keyword extraction fallback.
4. Calculate surge ratio per topic:
   ```
   surge_ratio = recent_count / max(prior_count, 1)
   ```
5. Filter by minimum threshold (10 papers default, adjusted for field size).
6. Rank by surge_ratio descending, take top 5-10.
7. Fetch 1-2 representative papers per trending topic.

See `trend-methodology.md` for full details on each step.

---

## Scope: social

Invokes the `sci-trending-research` skill to gather social and web discussion trends for the same topic/field.

### How it works

1. Check `projects/sci-trending-research/` for a recent brief on the topic (< 7 days old). If found, offer to reuse it.
2. If no recent brief exists, run the `sci-trending-research` methodology for the topic:
   - Searches Reddit (via OpenAI API with `web_search` tool), X (via xAI API with `x_search` tool), and web
   - Produces engagement-weighted insights with real metrics (upvotes, likes, comments, reposts)
   - Identifies patterns across platforms -- strongest signals appear everywhere
3. Present the social/web trend results with platform attribution.

### API key handling

- **OPENAI_API_KEY** -- enables Reddit search with real engagement data
- **XAI_API_KEY** -- enables X/Twitter search with real engagement data
- If either or both keys are missing, `sci-trending-research` falls back to web search only
- Inform the user which data sources are available but never block execution

### Output format

```
## Community & Web Trends

[N]. **Topic** -- engagement score: X
Platforms: Reddit (N upvotes), X (N likes), Web
Key discussion: [Title or headline of top discussion]
Takeaway: [One-line insight from the discussion]
```

---

## Scope: combined (unified view)

Runs **both** publications and social scopes, then merges results into a unified report.

### Execution order

1. Run the publications scope (surge ratio analysis via OpenAlex)
2. Run the social scope (invoke `sci-trending-research` for the same topic)
3. Cross-reference results to find convergent trends
4. Produce the merged report

### Cross-signal matching

Compare topic names and keywords between publication trends and social trends. A topic is a **convergent trend** if:
- A publication trend keyword appears in social discussion titles/topics (case-insensitive, stemmed match)
- OR a social trend topic maps to an OpenAlex topic name with substantial overlap

Convergent trends are the strongest signal -- they indicate areas gaining momentum in both formal research and community discussion simultaneously.

### Integration mechanics

To invoke `sci-trending-research` from within `sci-literature-research`:
1. Note the current topic/field being analyzed
2. Execute the `sci-trending-research` methodology for that topic
3. Read the output brief from `projects/sci-trending-research/`
4. Extract key topics and engagement metrics from the brief
5. Merge with publication trend results using the cross-signal matching above

### Presentation format

```
## Publication Trends (last N months)

[N]. **Topic** -- surge ratio: X.Xx
Paper count: recent N / prior N
Key paper: [Title] (Author, Year)

## Community & Web Trends

[N]. **Topic** -- engagement score: X
Platforms: Reddit (N upvotes), X (N likes), Web
Key discussion: [Title/headline]

## Cross-Signal Highlights

These topics are trending in BOTH academic publications AND community discussions:

[N]. **Topic**
- Publication surge: X.Xx (N recent papers vs N prior)
- Community signal: [summary of social discussion]
- Why it matters: [one-line synthesis of convergence]
```

### When no cross-signal overlap is found

If publications and social trends do not overlap:
- Still present both sections independently
- Replace the Cross-Signal Highlights section with:
  ```
  ## Cross-Signal Highlights

  No convergent trends detected between publication surges and community discussions.
  This may indicate that academic and public interest are focused on different aspects
  of this field. Review both sections independently for a complete picture.
  ```

---

## Fallback Strategies

| Situation | Fallback |
|-----------|----------|
| `sci-trending-research` skill not installed | Social scope unavailable -- inform user, run publications only |
| API keys missing (OPENAI_API_KEY, XAI_API_KEY) | Social scope uses web search only -- reduced engagement data |
| OpenAlex API down or rate limited | Publications scope unavailable -- inform user, offer social only |
| Both sources unavailable | Report error, suggest trying again later |
| Very niche field with no social discussion | Social section shows "No significant community discussions found" |
| Very niche field with few publications | Lower minimum threshold per trend-methodology.md edge cases |

---

## Notes

- The `publication_date` parameter format is `YYYY-MM-DD:YYYY-MM-DD` (from:to). Either side can be omitted for open-ended ranges.
- Social trends cover the last 30 days by default (sci-trending-research default window).
- Publication trends cover the last N months (default 12, configurable with `--months`).
- The time windows differ by design: publications need longer windows for statistically meaningful surge detection, while social discussions move faster and a 30-day window captures current momentum.
