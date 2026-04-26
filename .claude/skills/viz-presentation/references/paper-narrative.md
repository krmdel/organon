# Paper-to-Slides Narrative Structuring

How to turn an academic PDF into a narrative-coherent slide deck. Inspired by ArcDeck's Rhetorical Structure Theory (RST) + multi-agent critique loop, adapted for inline Claude reasoning — no separate LLM processes, no extra API keys.

The `extract_paper.py` script produces:
- `paper.md` — full text
- `assets/fig-*.png`, `assets/tbl-*.md`
- `assets.json` — `{id, type, caption, page, path}`

Use this reference to turn those artifacts into a Marp deck.

---

## Pipeline

```
PDF → extract_paper.py → paper.md + assets.json
                              ↓
                    Step A: Discourse parse
                              ↓
                    Step B: Commitments contract
                              ↓
                    Step C: Slide plan (grouping)
                              ↓
                    Step D: Self-critique (pass / revise, max 2 rounds)
                              ↓
                    Step E: Figure matching
                              ↓
                    Step F: Marp markdown → render
```

Do each step inline — don't skip. They build on each other.

---

## Step A: Discourse parse

Read `paper.md` and for each major section (Intro, Methods, Results, Discussion), tag paragraphs with their **rhetorical role** using a subset of RST relations:

| Relation | Tag | What it signals |
|----------|-----|-----------------|
| **Thesis** | `[THESIS]` | The paper's central claim — usually last paragraph of intro |
| **Gap / problem** | `[GAP]` | What prior work misses — usually mid-intro |
| **Elaboration** | `[ELAB]` | Paragraph expanding a prior point — group with its parent |
| **Evidence** | `[EVID]` | Data/experiment supporting a claim — belongs on a results slide |
| **Contrast** | `[CONTR]` | "Unlike X, our Y..." — valuable for positioning slides |
| **Justification** | `[JUST]` | Why a design choice was made — speaker-notes material |
| **Background** | `[BG]` | Context the audience may already know — candidate to cut |
| **Conclusion** | `[CONCL]` | Summary / implications — belongs on take-home slide |

Output a tagged outline:
```
[INTRO]
  ¶1 [BG]   Long-read sequencing context
  ¶2 [GAP]  Current assemblers miss structural variants in repeats
  ¶3 [ELAB] Specific failure modes
  ¶4 [THESIS] We present SVLine, which...
```

This takes ~2 minutes of reading per paper. Do it in your head or in a scratch block — you don't need to write the tagged outline to disk unless the paper is long (>15 pages).

---

## Step B: Commitments contract

**This is the single most important step.** Before planning slides, write a short contract — ArcDeck calls it `commitments.md`. Claude writes this inline as a thinking block, not a file.

Structure:

```markdown
## Commitments

**Thesis (one sentence):** {the paper's core claim — what the reader must leave with}

**3-5 takeaways (ranked by importance):**
1. {most important finding — the one sentence to remember}
2. {key method contribution}
3. {limitation or caveat the honest presenter must flag}
...

**Narrative spine (how the talk flows):**
Hook: {what makes the audience care}
→ Gap: {what was broken}
→ Approach: {the key insight in one line}
→ Evidence: {the 2-3 results that prove it}
→ Implication: {so what}

**Slide budget (at target duration):**
- 15-min talk → 12-15 content slides + title + ack
- 20-min talk → 16-20 content slides + title + ack
- 5-min lightning → 6-8 content slides + title

**What to cut ruthlessly:**
- {2-3 specific sections/topics from the paper that won't make the cut}
```

Every later step must stay true to this contract. If a slide doesn't serve a takeaway or the narrative spine, cut it.

---

## Step C: Slide plan via RST grouping

Walk the tagged outline and group paragraphs into slides using RST relations:

**Grouping rules:**
- `[ELAB]` paragraphs join their parent `[THESIS]` / `[EVID]` / `[CONTR]`
- `[JUST]` paragraphs go to speaker notes, never a slide body
- Multiple `[EVID]` on the same claim → one slide with the strongest, others in speaker notes
- `[BG]` only survives if the audience needs it — otherwise cut
- `[CONTR]` is great slide material — leads with the positioning
- One `[THESIS]` or finding per slide; no multi-finding mega-slides

**Title rule:** every slide title must be a **statement, not a topic**. "Results" is a topic; "SVLine recovers 40% more insertions than {baseline}" is a statement. Audience should be able to reconstruct the talk from just the titles.

Output a plan like:
```
Slide 2: "Repeat-region SVs are invisible to short reads"
  ¶ GAP(intro-2), ELAB(intro-3)
  Figure: fig-01 (pipeline diagram)

Slide 3: "Our insight: consensus assembly at SV breakpoints"
  ¶ THESIS(intro-4)
  No figure

Slide 5: "SVLine recovers 40% more insertions than {baseline}"
  ¶ EVID(results-2), ELAB(results-3)
  Figure: fig-03 (benchmark bar chart)
  Table: tbl-01 in speaker notes
```

---

## Step D: Self-critique (pass / revise)

Before rendering, critique your own plan. This replaces ArcDeck's Narrative Critic + Judge loop — you do it yourself in one pass, then revise if any check fails. Max two revision rounds; if a third is needed, the commitments are wrong — go back to Step B.

Run through each check:

| Check | Fail condition |
|-------|----------------|
| **Thesis coverage** | Is the thesis explicit on at least one non-title slide? |
| **Takeaway coverage** | Is each ranked takeaway traceable to a specific slide? |
| **Monotone flow** | Does each slide build on the last, or does the deck zig-zag? |
| **Title statements** | Is every title a claim, not a topic noun? |
| **Figure grounding** | Does every figure slide have a clear sentence-level claim the figure supports? |
| **Density** | Does any slide have >5 bullets or >40 words of body text? |
| **Cut discipline** | Are any cut sections from Commitments still sneaking in? |
| **Limitations honesty** | Is there at least one slide flagging the real limitation? |

If any fails, revise the slide plan **once**. Re-check. If it still fails, revise the commitments contract itself — the brief may be wrong.

---

## Step E: Figure matching

For each slide in the plan, pick the best asset from `assets.json`. Matching heuristics:

1. **Caption keyword match** — compare the slide title keywords to `asset.caption`
2. **Page proximity** — figures on the same page as the quoted paragraph usually belong together
3. **One figure per slide, never two** — if two compete, pick the stronger; the other goes to an appendix slide or speaker notes
4. **Tables:** prefer to retype the 2-3 rows that matter into a clean markdown table in the slide body. Full tables from `tbl-*.md` go to appendix / speaker notes.
5. **No figure available?** — generate a Mermaid diagram via `viz-diagram-code`, or a schematic via `viz-nano-banana`, rather than a text-heavy slide.

Embed with Marp size directives:
```markdown
![w:720](assets/fig-03.png)
```

Credit the figure in the speaker notes: `Figure 3 from {paper citation}.`

---

## Step F: Marp markdown

Apply `references/marp-syntax.md`. Specific to paper-to-slides mode:

- **Title slide body**: paper title, first-author *et al.*, year, venue, talk date, presenter
- **Abstract slide**: skip — your hook slide replaces it
- **Math**: preserve LaTeX from `paper.md` verbatim in `$...$` / `$$...$$`
- **Citations**: one references slide at the end with 4-6 key refs, not the full bib
- **Speaker notes**: every slide gets notes — this is where all the `[JUST]`, `[ELAB]`, and cut material lives
- **Paper DOI on final slide** for the audience to find it

Save to `projects/viz-presentation/{paper-slug}/{paper-slug}.md` and render per SKILL Step 5.

---

## Quality bar

A good paper-to-slides deck should pass this test: **a colleague who hasn't read the paper can reconstruct the thesis, the method's key insight, and the headline result from just the slide titles and figures — without reading any body bullets.** If they can't, the titles are topics not statements, or the figure matching is off.
