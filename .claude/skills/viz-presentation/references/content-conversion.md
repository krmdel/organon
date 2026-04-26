# Content Conversion Guide

How to convert existing content (blog posts, tutorials, manuscripts) into presentation slides.

## The Conversion Process

1. **Extract the spine** — identify the 5-8 key ideas in the source content
2. **One idea = one slide** — each key idea becomes a slide title
3. **Trim to bullets** — convert paragraphs to 3-5 bullet points max
4. **Preserve specifics** — keep exact numbers, key findings, important quotes
5. **Move prose to speaker notes** — detailed explanations become what you say, not what's shown
6. **Identify visual moments** — where would a diagram, plot, or image strengthen the point?
7. **Add transitions** — between sections, add a "roadmap" slide showing where you are

## What to Keep from Blog Posts

- The hook (becomes your second slide after title)
- Key findings with specific numbers
- Analogies (great for verbal delivery)
- Code examples (keep short, highlight key lines)
- Conclusion / takeaway

## What to Cut

- Background context the audience already knows
- Detailed methodology (keep to 1 "methods" slide)
- Lengthy explanations (move to speaker notes)
- Transition sentences ("In the next section...")
- Most citations (keep 2-3 key ones, put the rest on a references slide)

## Blog Post Section to Slide Mapping

| Blog section | Slide equivalent |
|-------------|-----------------|
| Hook paragraph | Slide 2: "Why this matters" |
| Background | 1-2 context slides (or skip if audience knows) |
| Core idea explanation | 2-3 slides with diagrams |
| Supporting evidence | 1-2 results/data slides |
| "Why it matters" | 1 implications slide |
| "What comes next" | 1 future directions slide |
| Code walkthrough | 1-2 slides with highlighted code blocks |
| Conclusion | Take-home message slide |

## Tutorial to Slides

Tutorials convert differently from blog posts — they need interaction points:

| Tutorial section | Slide equivalent |
|-----------------|-----------------|
| Prerequisites | Skip (mention verbally or on a setup slide) |
| Step-by-step instructions | 1 slide per major step, code blocks only |
| Explanations between steps | Speaker notes |
| Screenshots / output examples | Background images or side-by-side |
| Exercises | "Try this" slides with prompts |
| Troubleshooting | "Common issues" slide at the end |

## Manuscript to Talk

> **For PDF papers, use paper mode (Step 2b in SKILL.md).** That path runs `extract_paper.py` to pull figures and tables automatically, then applies the RST discourse + commitments pipeline in `paper-narrative.md`. This section stays useful for markdown manuscripts (sci-writing drafts, preprint sources, typed notes).

**Commitment contract first.** Before cutting anything, write a one-paragraph contract with yourself: the thesis in one sentence, the top 3 takeaways ranked, and what you're *refusing* to include. Every later cut decision traces back to this contract — if something doesn't serve a takeaway, it goes. This discipline is what separates a 15-minute talk that lands from one that drifts.

Converting a research paper into a conference talk requires the most aggressive trimming:

| Paper section | Talk equivalent |
|--------------|----------------|
| Abstract | Not used (you have a title slide instead) |
| Introduction paragraphs 1-2 | "Why this matters" slide — the gap/motivation |
| Introduction paragraph 3 (contributions) | Skip — your results will show this |
| Related work | 1 slide: "What's been tried" with 3-4 key references |
| Methods (full) | 1-2 slides: overview diagram + key design choice |
| Results table 1 | 1 slide: highlight the winning row |
| Results table 2 | 1 slide: the comparison that matters most |
| Results figures | 1 slide each: annotate what to see |
| Discussion | 1 slide: "What this means" |
| Limitations | 1 slide: be brief and honest |
| Future work | Combine with limitations or skip |
| References | 1 slide at the end with key citations only |

### Key Rules for Manuscript Conversion

- **Never read your paper aloud.** The talk is a trailer for the paper, not a recitation.
- **Lead with the finding, not the method.** "X improves Y by 40%" not "We conducted an experiment using..."
- **One figure per slide.** Never show a multi-panel figure on one slide — split them.
- **Annotate everything.** Circle the important number. Arrow to the key trend. Highlight the winning row.
- **Cut the literature review.** Your audience knows the field — give them 1 context slide max.
- **Your speaker notes ARE the paper.** The detailed methodology, nuances, and caveats go in notes.

## Conversion Checklist

Before rendering, verify:

- [ ] No slide has more than 5 bullet points
- [ ] No bullet point has more than ~10 words
- [ ] Every slide has a meaningful title (not "Results" but "Treatment Reduces Error by 40%")
- [ ] Speaker notes contain the prose that was trimmed from slides
- [ ] Code blocks are under 15 lines each
- [ ] Figures/diagrams are referenced where they strengthen the point
- [ ] There is a clear take-home message on the final content slide
- [ ] The presentation flows as a story, not a list of facts
- [ ] Every surviving slide traces back to a takeaway in the commitment contract (manuscript mode)
