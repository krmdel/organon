# Academic Writing Conventions

Reference for academic writing style options used by the sci-writing skill. Covers hedging language, voice options, citation placement, number formatting, and common academic phrases.

---

## Hedging Levels

Hedging language expresses the degree of certainty in scientific claims. The appropriate level depends on the strength of evidence and the nature of the claim.

### Conservative (Maximum Hedging)

**Use for:** Controversial claims, preliminary results, small sample sizes, single-study findings, speculation about mechanisms, cross-disciplinary claims.

**Phrases:**
- "may potentially"
- "appears to suggest"
- "could be indicative of"
- "it is possible that"
- "one interpretation is that"
- "these preliminary findings hint at"
- "it is tempting to speculate that"
- "cannot be ruled out"
- "warrants further investigation"

**Example:** "These preliminary findings may suggest a potential association between dietary intervention and cognitive performance, though further investigation with larger cohorts is warranted before drawing firm conclusions."

**When to dial back:** If your evidence is strong (large n, replicated, multiple converging methods), conservative hedging undersells your work. Move to moderate.

### Moderate (Default)

**Use for:** Standard scientific writing, established methods applied to new data, results consistent with prior literature, most Discussion paragraphs.

**Phrases:**
- "suggests"
- "indicates"
- "appears to"
- "is consistent with"
- "our results support"
- "likely"
- "points to"
- "is associated with"
- "provides evidence for"
- "these data indicate"

**Example:** "Our results suggest an association between BRCA1 expression and treatment response, consistent with previous findings by Smith et al. (2023) in a smaller cohort."

**This is the default for all drafting operations.** Users can override with `conservative` or `minimal` hedging.

### Minimal (Low Hedging)

**Use for:** Well-established facts, strong statistical evidence (large effect sizes, replicated findings), mathematical proofs, literature reviews summarizing consensus, describing methods.

**Phrases:**
- "shows"
- "demonstrates"
- "reveals"
- "confirms"
- "establishes"
- "is"
- "are"

**Example:** "Our analysis demonstrates a significant correlation between X and Y (r = 0.85, p < 0.001, n = 500), replicating the findings of three independent studies."

**Warning:** Minimal hedging is appropriate only when evidence is truly strong. Using it for weak evidence is overclaiming.

### Forbidden Patterns (Overreach)

**Never use these in scientific writing:**

| Pattern | Problem |
|---------|---------|
| "It is definitively proven that..." | Science does not "prove" -- it provides evidence |
| "This conclusively demonstrates..." | Even strong evidence is not conclusive |
| "It is an undeniable fact that..." | Overly absolute |
| "We have solved the problem of..." | Overclaiming; science progresses incrementally |
| "This groundbreaking discovery..." | Let the community assess significance |
| "For the first time ever..." | Almost certainly wrong; avoid without exhaustive search |

**Double hedging (also avoid):**

| Pattern | Problem |
|---------|---------|
| "It may potentially be the case that possibly..." | Redundant hedging; pick one hedge |
| "It cannot be denied that it is not impossible..." | Triple negative; unreadable |
| "Perhaps it might suggest that maybe..." | Too many hedges; weakens the claim to meaninglessness |

---

## Voice Options

### Active Voice (Default)

Active voice is the modern convention in scientific writing. Most journals now prefer or require it.

**Examples:**
- "We analyzed the data using a linear mixed-effects model."
- "The model predicts a 15% reduction in error rate."
- "Our results indicate a significant effect of treatment."
- "Smith et al. (2024) demonstrated that gene X..."
- "Figure 3 shows the dose-response relationship."

**When to use:** Default for all sections. Particularly important in Methods ("We performed...") and Results ("We found...").

### Passive Voice (When Requested)

Passive voice de-emphasizes the agent and emphasizes the action or object. Still used in some fields and by some journals.

**Examples:**
- "The data were analyzed using a linear mixed-effects model."
- "Gene expression was measured by quantitative PCR."
- "Samples were collected from 48 patients over a 6-month period."
- "A significant difference was observed between groups (p = 0.003)."

**When to use:**
- When the journal explicitly requires passive voice
- When the agent is truly unknown or irrelevant ("The samples were stored at -80C")
- In Methods section if the field convention is passive (some biomedical journals)
- When shifting emphasis to the object is important

**When NOT to use:**
- When it creates ambiguity about who did what
- When it makes sentences unnecessarily long or convoluted
- Throughout an entire paper (even passive-preferring journals accept some active voice)

### Mixing Voice

Most well-written papers use primarily active voice with occasional passive construction. This is natural and readable. Do not force all-active or all-passive.

---

## Citation Placement Rules

### End of Sentence (Most Common)

Place the citation before the period, after the claim it supports:

- CORRECT: "Gene X is upregulated in breast cancer (Smith, 2024)."
- CORRECT: "Previous studies have shown similar results (Doe, 2023; Lee, 2024)."

### Mid-Sentence (After Specific Claim)

Place the citation immediately after the specific claim it supports:

- CORRECT: "Gene X is upregulated in cancer (Smith, 2024), while gene Y is downregulated (Doe, 2023)."
- CORRECT: "The standard protocol (Lee, 2022) was modified to include..."

### Narrative Citation (Author as Subject)

Use the author's name as part of the sentence:

- CORRECT: "Smith (2024) demonstrated that gene X is upregulated..."
- CORRECT: "According to Smith (2024), the effect size was..."
- CORRECT: "In their seminal work, Smith and Doe (2023) established..."

### Common Placement Errors

- WRONG: "According to (Smith, 2024), the results show..." -- Use "According to Smith (2024),..."
- WRONG: "Smith et al. showed that gene X is important (Smith et al., 2024)." -- Redundant; use one form.
- WRONG: "It has been shown [1] that results are significant [2]." -- Place citation after the specific claim it supports, not scattered.

---

## Numbers and Statistics

### Numbers in Text

| Rule | Example |
|------|---------|
| Spell out numbers below 10 | "three samples", "eight participants" |
| Use digits for 10 and above | "12 patients", "150 genes", "42 experiments" |
| Always use digits with units | "5 mL", "3 hours", "2 cm" |
| Always use digits for statistics | "a mean of 4.2", "p = 0.003" |
| Start a sentence with a word | "Twelve patients..." (not "12 patients...") |

### Statistical Reporting

**Always report:**
- Test statistic with degrees of freedom: t(48) = 3.14, F(2, 45) = 7.82, chi-squared(1) = 12.3
- Exact p-value: p = 0.003 (not "p < 0.05" unless p < 0.001, then "p < 0.001")
- Effect size: Cohen's d = 0.89, r = 0.45, eta-squared = 0.12
- Confidence intervals where appropriate: 95% CI [2.1, 6.3]
- Sample size: n = 48 (or N for total, n for subgroup)

**Formatting conventions:**
- Italicize statistical symbols: *t*, *F*, *p*, *r*, *n*, *M*, *SD*
- No leading zero for values that cannot exceed 1: p = .003, r = .45
- Leading zero for values that can exceed 1: d = 0.89, M = 0.45

**Multiple comparisons:**
- Report correction method: "Bonferroni-corrected p < 0.008" or "FDR-adjusted q = 0.02"
- State the number of comparisons: "We performed 6 pairwise comparisons..."

---

## Common Academic Phrases

Organized by rhetorical function. Use these to improve flow between ideas.

### Addition / Extension

- "Furthermore,..."
- "Moreover,..."
- "In addition,..."
- "Building on this,..."
- "Extending these findings,..."
- "Consistent with this,..."

### Contrast / Comparison

- "However,..."
- "In contrast,..."
- "Conversely,..."
- "On the other hand,..."
- "Unlike previous studies,..."
- "While X showed..., Y demonstrated..."
- "Notwithstanding these findings,..."

### Causation / Consequence

- "Therefore,..."
- "Consequently,..."
- "As a result,..."
- "This suggests that..."
- "These findings imply..."
- "Given that..., it follows that..."

### Concession / Limitation

- "Although...,..."
- "Despite...,..."
- "Notwithstanding...,..."
- "While this approach has limitations,..."
- "It should be noted that..."
- "A caveat of this analysis is..."
- "One potential limitation is..."

### Summary / Conclusion

- "In summary,..."
- "Taken together,..."
- "Collectively, these results..."
- "Overall,..."
- "In conclusion,..."
- "To summarize,..."

### Referring to Evidence

- "As shown in Figure X,..."
- "Table Y summarizes..."
- "These data indicate..."
- "The results presented in Section X..."
- "As demonstrated above,..."

---

## Abbreviation Rules

1. **Define on first use:** "polymerase chain reaction (PCR)" -- then use "PCR" throughout.
2. **Re-define in Abstract** if the abstract is meant to stand alone (check journal policy).
3. **Do not abbreviate** terms used fewer than 3 times -- spell them out each time.
4. **Standard abbreviations** that need no definition: DNA, RNA, PCR, ANOVA, SD, CI, HIV, WHO.
5. **Gene symbols:** Italicize gene names (*BRCA1*, *TP53*); protein names are not italicized (BRCA1, p53).
6. **Species names:** Italicize and capitalize genus: *Escherichia coli*, then *E. coli* after first use.
