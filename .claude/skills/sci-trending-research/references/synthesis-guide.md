# Synthesis Guide

> Adapted from [last30days by Ronnie-Nutrition](https://github.com/Ronnie-Nutrition/last30days-skill).
> Original "Judge Agent" concept — weighting sources by engagement and cross-validating across platforms.

---

## The Synthesis Process

After all searches complete, you have raw results from Reddit, X, preprint servers, and the web. The synthesis turns noise into signal.

### Phase 1: Ground in Actual Research

**Read the results carefully. Do NOT substitute your pre-existing knowledge.**

Pay attention to:
- **Exact method/tool/gene/protein names** mentioned — if research mentions "CRISPRoff", that's different from "CRISPRi" even if they seem related
- **Specific quotes and insights** from sources — use THESE, not generic knowledge
- **What the sources actually say**, not what you assume the topic is about

Anti-pattern: User asks about "single-cell RNA-seq trends" and research returns specific techniques. Don't synthesize as generic genomics advice — report the specific methods and tools the community discusses.

### Phase 2: Weight by Engagement

Not all mentions are equal:

| Signal | Weight | Why |
|--------|--------|-----|
| Reddit thread, 100+ upvotes, 50+ comments | Very high | Community-validated, deep discussion |
| X post, 500+ likes from research accounts | Very high | Viral in scientific community |
| Same insight on Reddit + X + preprint | Very high | Cross-platform validation |
| Published paper with editorial coverage | Very high | Peer-reviewed and deemed newsworthy |
| Preprint with 100+ tweets | High | Strong community attention before peer review |
| Reddit thread, 20-50 upvotes | High | Solid community interest |
| Blog post from recognized PI or lab | High | Authority signal |
| Reddit thread, <10 upvotes | Medium | Real opinion, less validated |
| X post, <50 likes | Medium | Fresh take, limited reach |
| Generic science news article | Low-Medium | May be oversimplified or hype |
| Press release without primary source | Low | Often misleading or exaggerated |

### Phase 3: Extract Patterns

Look for:
1. **Consensus** — what does the research community agree on? (strongest signal)
2. **Contradictions** — where do sources or studies disagree? (often the most interesting finding)
3. **Emerging trends** — what's new that only a few groups are working on? (opportunity signal)
4. **Specific methods and tools** — named techniques, software, protocols (actionable signal)
5. **Warnings and limitations** — what are researchers cautioning against? (risk signal)

### Phase 4: Synthesize by Query Type

**BREAKTHROUGHS:**
Extract specific discoveries. Identify the lab/group. Note significance and reception.

```
1. [Discovery] — [Lab/Group], [Journal/Preprint]
   - r/science (200 upvotes): "This changes how we think about X"
   - @researcher (1.2K likes): "Finally someone showed Y"
   - Nature News: "Breakthrough in Z field"

2. [Discovery] — [Lab/Group], [Source]
   - r/bioinformatics (45 upvotes): "Interesting but needs replication"
   - bioRxiv preprint, posted [date]
```

**METHODS:**
Extract techniques ranked by community adoption and discussion.

```
Trending methods (by community validation):
1. [Method/Tool] — discussed in 4 sources, 300+ combined upvotes
   - What: [brief explanation]
   - Advantage: [over existing methods]
   - Caveat: [limitations noted]

2. [Method/Tool] — discussed in 3 sources
   - What: [brief explanation]

Common pitfalls:
- [Anti-pattern] — multiple researchers warn against this
```

**DEBATES:**
Map the disagreement. Identify the camps and their evidence.

```
Core debate: [What the disagreement is about]
- Camp A: [Position] — supported by [evidence/sources]
- Camp B: [Position] — supported by [evidence/sources]
- What would resolve it: [what data or experiments are needed]
```

**GENERAL:**
Summarize the landscape. What's the community's current state of mind?

```
Current sentiment: [excited/cautious/debating/converging]
Key themes:
1. [Theme] — [what researchers are saying]
2. [Theme] — [what researchers are saying]
Open questions: [where evidence is still needed]
```

---

## Research Implications

After synthesis, identify 2-3 research implications that could inform next steps. Frame these as opportunities:

- **The gap** — if everyone assumes X, there may be an untested hypothesis worth investigating
- **The review opportunity** — if many papers converge on a theme, that's a review or perspective piece
- **The methods tutorial** — if a technique is trending, that's educational content for `sci-communication`
- **The debate** — if there's genuine disagreement, deeper investigation or a systematic comparison is warranted
- **The replication** — if results are new and surprising, replication or validation is high-value work

---

## Self-Check Before Presenting

Before showing results to the user:

1. Does your synthesis match what the research ACTUALLY says? Re-read your output against the raw findings.
2. Did you attribute specific findings to specific sources?
3. Are engagement numbers real (from the search results) or estimated?
4. Did you identify at least one contradiction or nuance? If everything agrees perfectly, you may be over-simplifying.
5. Are the research implications specific to THIS topic, not generic advice?
