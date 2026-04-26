---
name: sci-trending-research
description: >
  Research what's trending in science — emerging topics, publication surges,
  community discussions on academic Reddit (r/science, r/bioinformatics,
  r/MachineLearning, etc.), science Twitter/X, preprint servers, and the web.
  Surface real discussions, breakthroughs, and debates scientists are talking
  about right now. Produces a research brief other sci-* skills can consume.
  Triggers on: "what's trending in", "emerging research", "hot topics in",
  "recent breakthroughs", "what are researchers saying about", "field pulse",
  "research trends", "community sentiment on".
  Does NOT trigger for literature search (use sci-literature-research),
  data analysis, or manuscript writing.
---

# Trending Research

> Adapted from [last30days by Ronnie-Nutrition](https://github.com/Ronnie-Nutrition/last30days-skill).
> Original skill focused on research + prompt generation. This version strips the prompt layer
> and focuses purely on research synthesis — designed as a backend that other sci-* skills consume.

## Outcome

A research brief saved to `projects/sci-trending-research/{topic}_{YYYY-MM-DD}.md` containing:
- What researchers are actually discussing, publishing, and debating right now
- Engagement-weighted insights (upvotes, likes, citations signal what resonates)
- Patterns across platforms (strongest signals appear everywhere)
- Actionable takeaways for research direction and hypothesis generation

Other skills (sci-hypothesis, sci-writing, sci-communication, etc.) can read the latest research brief for timely, relevant context.

## Context Needs

| File | Load level | How it shapes this skill |
|------|-----------|--------------------------|
| `research_context/research-profile.md` | Field + interests | Helps frame research through the scientist's domain lens |
| `context/learnings.md` | `## sci-trending-research` section | Apply previous feedback |

Load if they exist. Proceed without them if not.

---

## Before You Start

1. Check `projects/sci-trending-research/` for recent research on the same topic. If a brief exists from the last 7 days, show the user: "I researched [topic] on [date]. Want to use that, refresh it, or research something new?"

2. **Check API keys.** Read `.env` for `OPENAI_API_KEY` and `XAI_API_KEY`. If either is missing, tell the user once before starting:
   - **Both missing:** "I'll use web search for this research. For much richer results with real engagement data (upvotes, likes, comments), add `OPENAI_API_KEY` (for Reddit — get one at platform.openai.com) and `XAI_API_KEY` (for X — get one at console.x.ai) to your `.env` file."
   - **Only OpenAI missing:** "I have X data but not Reddit. Add `OPENAI_API_KEY` to `.env` for Reddit threads with real upvotes and comments."
   - **Only xAI missing:** "I have Reddit data but not X. Add `XAI_API_KEY` to `.env` for X posts with real likes and reposts."
   - **Both present:** Skip this — say nothing, just proceed.

   This is informational only. Never block work because keys are missing.

---

## Step 1: Parse the Request

Extract from the user's input:

- **TOPIC** — what scientific area or question they want to research
- **QUERY TYPE** — what kind of research:
  - **BREAKTHROUGHS** — "recent breakthroughs in X", "new discoveries in X" → wants key findings and developments
  - **METHODS** — "new techniques for X", "emerging methods in X" → wants trending tools, protocols, techniques
  - **DEBATES** — "controversies in X", "what's the debate about X" → wants disagreements and open questions
  - **GENERAL** — anything else → wants broad understanding of community sentiment and emerging directions
- **SCOPE** — quick (5-8 searches) or deep (12-18 searches). Default: balanced (8-12).

If the topic is vague, ask one clarifying question. Don't over-ask — get moving.

---

## Step 2: Run the Research

Read `references/research-methodology.md` for the full search strategy.

### Primary: Python Script (requires API keys)

The `scripts/last30days.py` script uses external APIs to search Reddit and X with real engagement data:

```bash
python3 .claude/skills/sci-trending-research/scripts/last30days.py "{topic}" --emit=compact
```

- **Reddit** via OpenAI Responses API (`web_search` tool, domain-locked to reddit.com) — returns threads with real upvotes, comments, and top comment insights
- **X / Twitter** via xAI API (`x_search` tool) — returns posts with real likes, reposts, and reply counts
- Supports `--quick` (fewer sources) and `--deep` (comprehensive) flags
- Supports `--sources=reddit|x|both|auto` to control which platforms to search
- Supports `--include-web` to add general web search alongside Reddit/X

**Requires:** `OPENAI_API_KEY` (for Reddit) and/or `XAI_API_KEY` (for X) in `.env`. Script auto-detects available keys and adapts.

### Fallback: WebSearch (no API keys needed)

If neither API key is configured, use Claude's built-in WebSearch:

#### Reddit (academic community discussions)
Search for: `{topic} site:reddit.com` targeting academic subreddits (r/science, r/bioinformatics, r/MachineLearning, etc.).

#### X / Twitter (science community pulse)
Search for: `{topic} site:x.com OR site:twitter.com` targeting science accounts and discussions.

#### Preprints and publications
Search for: `{topic} site:biorxiv.org`, `{topic} site:arxiv.org`, `{topic} site:pubmed.ncbi.nlm.nih.gov`.

#### Science news and journals
Search for: `{topic} site:nature.com`, `{topic} site:sciencedaily.com`, `{topic} site:science.org`.

#### Web (blogs, docs, news)
Search for: `{topic}` with time-filtered queries. Exclude reddit.com and x.com.

WebSearch works but lacks real engagement metrics (upvotes, likes). The script provides much richer data.

---

## Step 3: Synthesize Findings

Read `references/synthesis-guide.md` for the full methodology.

**Weight sources by engagement signals:**
- Reddit threads with 50+ upvotes and active discussion = strong signal
- X posts with high engagement (likes, reposts) from researchers = trending signal
- Preprints with significant social media attention = emerging signal
- Published papers with editorial/news coverage = validated signal
- Multiple sources saying the same thing = strongest signal

**Synthesize by query type:**

**BREAKTHROUGHS** → Extract specific findings, methods, and their significance:
```
Key breakthroughs:
1. [Discovery/finding] — [lab/group], [journal/preprint]
   - Community reaction: [sentiment from Reddit/X]
2. [Discovery/finding] — [lab/group], [source]
```

**METHODS** → Top techniques, tools, protocols ranked by adoption and discussion:
```
Trending methods:
1. [Technique] — discussed in 4 sources, gaining traction in [subfields]
   - Why: [what problem it solves]
   - Caveat: [limitations noted by community]
```

**DEBATES** → Key disagreements, open questions, competing hypotheses

**GENERAL** → Key themes, community sentiment, emerging directions

---

## Step 4: Show Results

Display the synthesis in this format:

```
## What I found — {TOPIC} (last 30 days)

[2-4 sentence synthesis of the key insight]

### Key findings
1. [Finding with source attribution]
2. [Finding with source attribution]
3. [Finding with source attribution]

### Sources scanned
- Reddit: {n} threads across r/{sub1}, r/{sub2}
- X: {n} posts from @{handle1}, @{handle2}
- Preprints/Papers: {n} from bioRxiv, arXiv, PubMed
- Web: {n} pages from {domain1}, {domain2}
```

---

## Step 5: Save the Brief

Save to `projects/sci-trending-research/{topic-slug}_{YYYY-MM-DD}.md`.

The brief format is defined in `references/brief-template.md`. Include:
- Research metadata (topic, date, query type, sources scanned)
- Synthesis (findings, patterns, emerging directions)
- Raw source list (URLs, engagement metrics where available)
- Research implications (how this research could inform next steps)

This file is what other skills consume. Keep it structured and scannable.

---

## Step 6: Offer Next Steps

Based on the research and installed skills, recommend one action:

- "This could inform a new hypothesis — want me to generate testable hypotheses with `sci-hypothesis`?"
- "There's enough convergence here for a review or perspective piece — want me to draft a section with `sci-writing`?"
- "This would make a good tutorial or explainer — want me to route to `sci-communication`?"
- "I found [X] trending hard — want me to research deeper on that angle?"

---

## Rules

*Updated automatically when the user flags issues. Read before every run.*

---

## Self-Update

If the user flags an issue — bad sources, irrelevant results, wrong synthesis — update the `## Rules` section immediately with the correction and today's date.

---

## Troubleshooting

**Too few results:** Broaden the search terms. Strip modifiers and search for the core noun. Try `--deep` flag.
**Results feel outdated:** Add year to search queries. Use "2026" or "this month" qualifiers.
**Platform-specific content missing:** Some topics are discussed more on Reddit vs X. Use `--sources=reddit` or `--sources=x` to focus.
**Preprint-heavy topics:** Add explicit bioRxiv/arXiv searches. Some fields discuss primarily on preprint servers.
**User wants real engagement metrics:** Use the Python script with API keys. WebSearch fallback lacks exact counts.
**Script errors:** Check `.env` has valid `OPENAI_API_KEY` and/or `XAI_API_KEY`. Fall back to WebSearch if scripts fail.
