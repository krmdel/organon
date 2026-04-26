# Manuscript Section Writing Guides

Reference for drafting each section of a scientific manuscript. Each section includes its purpose, a structure template, do/don't examples, and citation density guidance.

---

## Introduction

### Purpose

The introduction establishes context, identifies a gap in current knowledge, and states how the present work addresses that gap. It answers: "Why should the reader care about this study?"

### Structure Template

1. **Broad context** (1-2 paragraphs) -- Establish the field and its significance. Start wide and accessible.
2. **Narrow to specific problem** (1 paragraph) -- Focus on the specific area this paper addresses. Introduce key concepts and terminology.
3. **Gap in current knowledge** (1 paragraph) -- What is missing, unknown, or unresolved? Why does this matter?
4. **Your contribution / objectives** (1 paragraph) -- State what this paper does and how. Be specific about aims.
5. **Paper organization** (optional, 1 sentence) -- "The remainder of this paper is organized as follows..." Common in CS/engineering, less so in biology.

### Do / Don't Examples

- DO: "Despite significant advances in single-cell RNA sequencing, the relationship between transcriptomic heterogeneity and treatment resistance remains poorly understood."
- DO: "Here, we present a computational framework that integrates multi-omics data to identify resistance-associated gene programs."
- DON'T: "Nobody has ever studied this before." (Almost never true; shows poor literature review.)
- DON'T: "In this groundbreaking study, we solve the problem of..." (Let the reader judge significance.)
- DON'T: "Since the dawn of time, scientists have wondered about..." (Too broad; get to the point.)

### Citation Density

**High** -- Nearly every claim about existing work needs a reference. The introduction is where you demonstrate awareness of the field. Aim for 2-4 citations per paragraph in the context and gap sections.

### Common Mistakes

- Starting too broad (wasting the first paragraph on obvious context)
- Failing to clearly state the gap (reader unsure why this study was needed)
- Burying the contribution statement (should be prominent, usually end of introduction)
- Overclaiming novelty ("first ever", "unprecedented") without thorough literature check

---

## Methods

### Purpose

The methods section provides enough detail for another researcher to reproduce the work. It answers: "What exactly did you do, and how?"

### Structure Template

1. **Study design / overview** (1 paragraph) -- High-level description of the experimental or computational approach.
2. **Data collection / materials** (1-2 paragraphs) -- Where data came from, how samples were obtained, inclusion/exclusion criteria. For computational work: datasets, versions, download dates.
3. **Specific procedures / algorithms** (2-4 paragraphs) -- Step-by-step description of what was done. Group logically (e.g., "Data preprocessing", "Feature extraction", "Model training").
4. **Statistical analysis plan** (1-2 paragraphs) -- Which tests, why those tests, significance thresholds, multiple comparison corrections.
5. **Software / tools used with versions** (1 paragraph or table) -- List software, packages, and their versions. Include hardware specs if computationally intensive.

### Do / Don't Examples

- DO: "We used a paired t-test (scipy v1.11, alpha = 0.05) to compare pre- and post-treatment expression levels across 48 matched patient samples."
- DO: "RNA was extracted using the Qiagen RNeasy Mini Kit (catalog #74104) following the manufacturer's protocol with the following modifications: ..."
- DO: "Analyses were performed using Python 3.10 with numpy 1.24, pandas 2.0, and scikit-learn 1.3."
- DON'T: "We analyzed the data using various statistical methods." (Which methods? The reader cannot reproduce this.)
- DON'T: "Standard procedures were followed." (Describe or cite the specific standard.)
- DON'T: "We used the latest version of R." (Specify the exact version number.)

### Citation Density

**Medium** -- Cite established methods, software tools, datasets, and any protocol you followed from another paper. Original methods you developed do not need citations (they are your contribution).

### Common Mistakes

- Insufficient detail for reproducibility (the cardinal sin of Methods)
- Missing software versions (results may differ across versions)
- Not specifying statistical test assumptions or corrections
- Mixing results into the methods section

---

## Results

### Purpose

The results section reports findings objectively, without interpretation. It answers: "What did you find?" Save the "so what?" for Discussion.

### Structure Template

1. **Overview of main findings** (1 paragraph) -- Brief summary of key results to orient the reader.
2. **Detailed results with statistics** (3-6 paragraphs) -- Present each finding with full statistical reporting: test statistic, degrees of freedom, p-value, confidence interval, effect size.
3. **Figures and tables referenced inline** -- Every figure and table must be referenced in the text. "As shown in Figure 2A, expression of..."
4. **Negative / null results included** -- Report what did NOT work or was not significant. This is scientifically valuable and ethically required.

### Do / Don't Examples

- DO: "Expression of BRCA1 was significantly higher in the treatment group (mean = 4.2, SD = 0.8) compared to the control group (mean = 2.1, SD = 0.6; t(48) = 3.14, p = 0.003, Cohen's d = 0.89)."
- DO: "No significant difference was observed between groups A and B (p = 0.42, d = 0.12), suggesting the intervention had no effect on this outcome."
- DO: "Figure 3 shows the dose-response curve for compound X (EC50 = 12.3 nM, 95% CI: 8.7-17.4 nM)."
- DON'T: "The results clearly demonstrate that our hypothesis is correct." (This is interpretation, not results.)
- DON'T: "As expected, gene X was upregulated." (Save expectations and interpretations for Discussion.)
- DON'T: "p < 0.05" without the exact p-value. (Report p = 0.003, not just p < 0.05, unless p < 0.001.)

### Citation Density

**Low** -- Primarily reference your own figures, tables, and supplementary materials. Occasionally cite a method referenced earlier ("Using the approach described in Methods, we found...").

### Common Mistakes

- Interpreting results instead of reporting them
- Omitting effect sizes (p-values alone are insufficient)
- Not reporting negative or null results
- Presenting results in a different order than the methods
- Describing figures/tables in text instead of letting them speak (avoid "Table 1 shows that..." for every entry)

---

## Discussion

### Purpose

The discussion interprets results in the context of existing literature, acknowledges limitations, and suggests future directions. It answers: "What do these findings mean?"

### Structure Template

1. **Summary of key findings** (1 paragraph) -- Restate the main results briefly (not a copy of the Results section).
2. **Interpretation in context of existing literature** (2-3 paragraphs) -- How do your findings compare to what others have reported? Do they confirm, extend, or contradict prior work?
3. **Implications** (1-2 paragraphs) -- What are the theoretical and practical implications? Why does this matter?
4. **Limitations** (1 paragraph) -- Be honest and specific. Acknowledge what could affect the interpretation: sample size, study design, confounders, generalizability.
5. **Future directions** (1 paragraph) -- What should be studied next? What questions remain?
6. **Conclusion** (1 paragraph) -- Concise take-home message. What should the reader remember?

### Do / Don't Examples

- DO: "Our finding that BRCA1 expression correlates with treatment response is consistent with Smith et al. (2023), who reported a similar association in a smaller cohort of breast cancer patients."
- DO: "A key limitation of our study is the relatively small sample size (n = 48), which may limit the generalizability of our findings to other cancer types."
- DO: "Future studies should investigate whether this association holds in prospective cohorts with longer follow-up periods."
- DON'T: "We proved that X causes Y." (Correlation does not equal causation; use appropriate hedging.)
- DON'T: "There are no limitations to this study." (Every study has limitations; ignoring them undermines credibility.)
- DON'T: "This is the most important finding in the field." (Let the community judge importance.)
- DON'T: Simply re-state results without interpretation. (The Discussion must add value beyond the Results section.)

### Citation Density

**High** -- Connect every interpretation to prior work. The discussion is where you demonstrate scholarly depth and position your work within the broader field. Aim for 3-5 citations per interpretive paragraph.

### Common Mistakes

- Re-stating results without interpretation (the most common Discussion problem)
- Overclaiming (turning correlations into causal claims)
- Generic limitations ("more research is needed" without specifics)
- Introducing new results not presented in the Results section
- Ignoring contradictory findings from the literature

---

## Abstract

### Purpose

The abstract is a self-contained summary of the entire paper. Many readers will only read the abstract, so it must convey the key message clearly and completely.

### Structure Template

Write 150-300 words following this sequence:

1. **Background** (1-2 sentences) -- Context and motivation.
2. **Objective** (1 sentence) -- What was the aim of this study?
3. **Methods** (2-3 sentences) -- How was it done? Key design choices.
4. **Results** (2-3 sentences) -- Main findings with key statistics.
5. **Conclusion** (1-2 sentences) -- Take-home message and significance.

### Do / Don't Examples

- DO: Include one or two specific numbers from your results (the strongest finding).
- DO: Use the same terminology as the rest of the paper (no new terms in the abstract).
- DON'T: Include citations in the abstract (most journals discourage or forbid this).
- DON'T: Include abbreviations not defined in the abstract itself.
- DON'T: Write vague conclusions ("These findings have implications for the field").
- DON'T: Include figures, tables, or references to them.

### Writing Tips

- Write the abstract LAST, after all other sections are complete.
- Match the structure to the target journal's requirements (structured vs. unstructured).
- Many journals require keywords -- select 4-6 terms not already in the title.

---

## Cross-Section Consistency Checklist

Before finalizing a manuscript, verify:

- [ ] Introduction objectives match Methods procedures
- [ ] Methods procedures match Results presentation order
- [ ] All Results are interpreted in Discussion
- [ ] Conclusions in Discussion are supported by specific Results
- [ ] Terminology is consistent across all sections
- [ ] Abbreviations defined on first use in each section (or just the first use in the paper, per journal style)
- [ ] All figures and tables referenced in text
- [ ] Abstract accurately reflects the final manuscript content
