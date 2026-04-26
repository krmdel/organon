# Slide Structure Templates

Templates for different scientific presentation types. Use these as starting scaffolds, then adapt to the specific content.

## Research Talk (15-20 min, ~15-20 slides)

1. **Title slide** — title, author, affiliation, date, conference
2. **Motivation / Why this matters** (1-2 slides) — the problem, its impact, the gap
3. **Background / Related work** (2-3 slides) — just enough for context, not a literature review
4. **Research question / Hypothesis** (1 slide) — clear, specific, testable
5. **Methods overview** (2-3 slides) — study design, data, analysis approach
6. **Key results** (3-5 slides) — one finding per slide, lead with the takeaway in the title
7. **Discussion / Implications** (1-2 slides) — what it means, why it matters
8. **Limitations & Future work** (1 slide) — honest, brief
9. **Conclusion / Take-home message** (1 slide) — the one thing the audience should remember
10. **Acknowledgments** (1 slide) — funding, collaborators, data sources
11. **Q&A / Contact slide** (1 slide) — email, lab website, paper DOI

## Tutorial / Lecture (30-60 min, ~25-40 slides)

1. **Title slide**
2. **What you'll learn / Learning objectives** (1 slide) — 3-4 concrete outcomes
3. **Overview / Roadmap** (1 slide) — visual outline of sections
4. **Section 1: Concept intro with analogy** (3-5 slides) — build intuition first
5. **Check-in / Quick question** (1 slide) — engage the audience
6. **Section 2: Deep dive with diagrams** (5-8 slides) — mechanics, details, theory
7. **Hands-on / Example walkthrough** (3-5 slides) — live code or worked example
8. **Section 3: Advanced topics** (3-5 slides) — extensions, edge cases, recent developments
9. **Common pitfalls / FAQ** (1-2 slides) — what people always get wrong
10. **Summary / Key takeaways** (1 slide) — revisit learning objectives
11. **Resources / Further reading** (1 slide) — papers, tutorials, tools

## Lab Meeting (10-15 min, ~10-12 slides)

1. **Title slide** — project name, date
2. **Recap: Where we were last time** (1 slide) — one-sentence context
3. **This week's goal** (1 slide) — what you set out to do
4. **Methods / What I did** (2-3 slides) — approach, tools, data
5. **Results** (3-4 slides) — figures with clear annotations
6. **Problems / Blockers** (1 slide) — what went wrong, what's unclear
7. **Next steps** (1 slide) — concrete plan for next week
8. **Discussion points** (1 slide) — questions for the group

## Short Talk / Lightning Talk (5-7 min, ~7-10 slides)

1. **Title slide**
2. **The problem** (1 slide) — hook the audience immediately
3. **Our approach** (1-2 slides) — the key insight, not all the details
4. **Main result** (1-2 slides) — the headline finding with one compelling figure
5. **Why it matters** (1 slide) — implications, applications
6. **Take-home** (1 slide) — one memorable statement
7. **Contact** (1 slide) — where to find the paper/code

## Conference Poster (1 slide, poster layout)

Special Marp layout for large-format posters. Use custom CSS for multi-column grid:

```markdown
---
marp: true
theme: uncover
paginate: false
style: |
  section {
    font-size: 1.2em;
    columns: 3;
    column-gap: 2em;
  }
  h1 { column-span: all; text-align: center; }
  h2 { color: #2d5986; break-before: avoid; }
---

<!-- _class: lead -->

# Poster Title
**Author** | Institution | conference@email.com

## Introduction
...

## Methods
...

## Results
...

## Conclusion
...

## References
...
```

For complex poster layouts, prefer generating HTML output and using a dedicated poster template.

## Journal Club (15-20 min, ~12-15 slides)

1. **Title slide** — paper title, authors, journal, year
2. **Why this paper?** (1 slide) — relevance to the group
3. **Background** (1-2 slides) — context the paper assumes
4. **Research question** (1 slide) — what they asked
5. **Methods** (2-3 slides) — study design, key technical details
6. **Main results** (3-4 slides) — reproduce key figures/tables
7. **Strengths** (1 slide) — what they did well
8. **Limitations / Critiques** (1 slide) — what could be better
9. **Relevance to our work** (1 slide) — how this connects
10. **Discussion questions** (1 slide) — seed the conversation

## Slide Design Principles for Science

- **One idea per slide** — if you need "and" in the title, it's two slides
- **Maximum 5 bullets per slide, maximum 7 words per bullet** — be ruthless
- **Every data slide answers three questions:**
  - Title = "What should I see?" (the finding, not "Results")
  - Figure = "What do I see?" (the evidence)
  - Annotation/caption = "So what?" (the takeaway)
- **Code blocks: max 15 lines.** Longer code should be split or highlight the key section only
- **Use speaker notes for everything you'd SAY** — the slide shows what you'd SHOW
- **Diagrams > bullet points.** If a concept can be a visual, make it visual
- **End with a concrete take-home message**, not "Thank you" or "Questions?"
- **Consistent color scheme throughout** — pick 2-3 colors and stick with them
- **Font size minimum 24pt equivalent** — if they can't read it from the back, cut it
- **One figure per slide** unless directly comparing two panels
- **Annotate your figures** — circle, arrow, or highlight what matters. Don't make the audience search
