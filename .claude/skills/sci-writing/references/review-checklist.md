# AI Peer Review Checklist

Reference for the sci-writing skill's peer review mode. Provides structured criteria, severity definitions, reviewer personas, and the report output template.

---

## Review Process Overview

The review mode reads a manuscript (or section) and produces a structured markdown report. Each criterion is scored with a severity rating. The review identifies specific issues with actionable suggestions, referenced to the relevant section or paragraph.

**Input:** Manuscript text (pasted, file path, or from projects/sci-writing/)
**Output:** Structured review report saved to projects/sci-writing/

---

## Severity Definitions

| Severity | Symbol | Meaning | Action Required |
|----------|--------|---------|-----------------|
| **CRITICAL** | [!!!] | Fundamental flaw that invalidates conclusions or methodology | Must fix before submission. Paper likely rejected without correction. |
| **MAJOR** | [!!] | Significant weakness that reviewers will flag | Should fix. Likely results in major revision request. |
| **MINOR** | [!] | Improvement opportunity that strengthens the paper | Nice to fix. May appear in reviewer comments but unlikely to block acceptance. |
| **PASS** | [OK] | Criterion adequately met | No action needed. |

---

## Review Criteria

### 1. Methodology Soundness

**What to check:**
- Study design is appropriate for the research question
- Sample size is adequate (flag if power analysis is missing for clinical/experimental studies)
- Controls are present and appropriate (positive controls, negative controls, vehicle controls)
- Statistical tests match data type and distributional assumptions
- Methods description is sufficient for independent reproduction
- Data preprocessing steps are documented (normalization, filtering, outlier handling)
- Randomization and blinding described (for experimental studies)

**Severity guide:**
- CRITICAL: Wrong statistical test for data type (e.g., parametric test on non-normal small sample without justification)
- CRITICAL: No control group in an experimental study
- MAJOR: Missing power analysis for clinical study
- MAJOR: Insufficient detail to reproduce key steps
- MINOR: Software version not specified
- MINOR: Minor clarity issue in method description

### 2. Logical Flow

**What to check:**
- Introduction leads naturally from broad context to specific research question
- Research question / hypothesis is clearly stated
- Methods directly address each stated objective
- Results are presented in the same order as methods
- Each result addresses at least one stated objective
- Discussion interprets results (does not just re-state them)
- Conclusions follow logically from the presented evidence
- Transitions between sections are smooth

**Severity guide:**
- CRITICAL: Conclusions not supported by the data presented
- CRITICAL: Results address questions not mentioned in Introduction
- MAJOR: Missing logical connection between stated objectives and results
- MAJOR: Discussion introduces new results not in Results section
- MINOR: Awkward transition between paragraphs
- MINOR: Results presented in different order than Methods

### 3. Missing References

**What to check:**
- Key claims about existing work have citations
- Seminal / foundational papers in the field are cited
- Methods borrowed from other work are properly attributed
- Recent relevant work (last 2-3 years) is cited
- Self-citation balance (not excessive, not absent when relevant)
- Competing or contradictory findings from the literature are acknowledged

**Severity guide:**
- MAJOR: Major claim about existing knowledge without any citation
- MAJOR: Obvious omission of a key paper that directly relates to the work
- MINOR: Known seminal paper missing but claim is still supported
- MINOR: Slight self-citation imbalance

### 4. Clarity and Readability

**What to check:**
- Jargon and technical terms defined on first use
- Sentence length (flag sentences exceeding 40 words)
- Paragraph coherence (one main idea per paragraph)
- Every figure and table is referenced in the text
- Abbreviations defined on first use
- Consistent terminology throughout (no switching between synonyms for the same concept)
- Active voice used where appropriate (unless journal requires passive)
- No ambiguous pronoun references ("it", "this", "these" without clear antecedent)

**Severity guide:**
- MAJOR: Undefined jargon critical to understanding the paper
- MAJOR: Ambiguous description that could be misinterpreted
- MINOR: Long sentences that could be split
- MINOR: Inconsistent abbreviation usage
- MINOR: Figure or table not referenced in text

### 5. Statistical Reporting

**What to check:**
- Test statistic reported (not just p-value): t, F, chi-squared, r, etc.
- Degrees of freedom included: t(48), F(2, 45)
- Effect sizes reported for all significant results
- Confidence intervals included where appropriate
- Exact p-values given (not just "p < 0.05", unless p < 0.001)
- Multiple comparison correction applied when needed (Bonferroni, FDR, Tukey)
- Sample sizes reported for each analysis
- Descriptive statistics included (mean, SD, median, IQR as appropriate)

**Severity guide:**
- CRITICAL: Statistical result reported without the test used
- MAJOR: Missing test statistic (only p-value reported)
- MAJOR: No multiple comparison correction with 5+ comparisons
- MINOR: Missing effect size for significant result
- MINOR: "p < 0.05" instead of exact value

### 6. Claims vs Evidence Alignment

**What to check:**
- Each claim in Discussion is traceable to a specific result in Results
- No overclaiming: correlation described as causation
- No underclaiming: strong evidence presented with excessive hedging
- Hedging level appropriate for strength of evidence
- Limitations acknowledged honestly and specifically
- Generalizability claims match the study population
- "First to show" claims verified against cited literature

**Severity guide:**
- CRITICAL: Causal claim from purely correlational data without acknowledgment
- CRITICAL: Conclusion contradicted by the paper's own data
- MAJOR: Missing significant limitation that affects interpretation
- MAJOR: Claim extends well beyond what the data supports
- MINOR: Hedging too conservative for strong evidence
- MINOR: Minor limitation not mentioned

---

## Reviewer Persona Modes

Each persona emphasizes different criteria. The persona affects the weight given to each criterion and the tone of feedback.

### Balanced (Default)

**Emphasis:** Equal weight across all 6 criteria.
**Tone:** Constructive and specific. Identifies strengths before weaknesses.
**Best for:** General pre-submission review, self-assessment.
**Output style:** "This is a well-structured study. The following points would strengthen the manuscript: ..."

### Strict Methodologist

**Emphasis:** Extra weight on Criterion 1 (Methodology) and Criterion 5 (Statistical Reporting).
**Tone:** Rigorous and detail-oriented. Flags every unstated assumption.
**Best for:** Methods-heavy papers, clinical trials, papers with complex statistical analyses.
**Additional checks:**
- Are all statistical assumptions explicitly verified?
- Is the analysis plan pre-registered?
- Are sensitivity analyses reported?
- Is the code/data availability statement present?

### Clarity Editor

**Emphasis:** Extra weight on Criterion 4 (Clarity) and Criterion 2 (Logical Flow).
**Tone:** Reader-focused. Identifies where a reader might get lost or confused.
**Best for:** Early drafts, papers aimed at broad audiences, interdisciplinary work.
**Additional checks:**
- Can a researcher outside this specific subfield follow the argument?
- Are analogies or explanations provided for complex concepts?
- Is the abstract a self-contained summary?
- Does the title accurately reflect the content?

### Journal Reviewer

**Emphasis:** Balanced criteria plus novelty, significance, and field impact.
**Tone:** Mimics typical anonymous peer review. Direct but professional.
**Best for:** Final pre-submission check, simulating the review process.
**Additional checks:**
- Is the work sufficiently novel for the target journal?
- Is the scope appropriate for the journal's audience?
- Are there ethical concerns (consent, data privacy, conflicts of interest)?
**Ends with recommendation:** Accept / Minor Revision / Major Revision / Reject (with justification).

---

## Report Template

The review output follows this exact structure:

```markdown
# Peer Review Report

**Manuscript:** [Title or filename]
**Reviewer Persona:** [Balanced / Strict Methodologist / Clarity Editor / Journal Reviewer]
**Date:** [YYYY-MM-DD]

## Summary

[2-3 sentence overall assessment. State the paper's main contribution and general quality level.]

## Criterion Scores

| # | Criterion | Rating | Issues |
|---|-----------|--------|--------|
| 1 | Methodology Soundness | [PASS/MINOR/MAJOR/CRITICAL] | [count] |
| 2 | Logical Flow | [PASS/MINOR/MAJOR/CRITICAL] | [count] |
| 3 | Missing References | [PASS/MINOR/MAJOR/CRITICAL] | [count] |
| 4 | Clarity and Readability | [PASS/MINOR/MAJOR/CRITICAL] | [count] |
| 5 | Statistical Reporting | [PASS/MINOR/MAJOR/CRITICAL] | [count] |
| 6 | Claims vs Evidence | [PASS/MINOR/MAJOR/CRITICAL] | [count] |

## Detailed Findings

### Criterion 1: Methodology Soundness -- [RATING]

**Strengths:**
- [What was done well]

**Issues:**
- [SEVERITY] [Section/paragraph reference]: [Specific issue]. **Suggestion:** [How to fix it].
- [SEVERITY] [Section/paragraph reference]: [Specific issue]. **Suggestion:** [How to fix it].

[Repeat for each criterion with issues]

## Strengths

[3-5 bullet points highlighting what the paper does well. Every review should acknowledge positive aspects.]

## Priority Actions

1. [Most critical fix needed -- what and where]
2. [Second most critical fix]
3. [Third most critical fix]

[If Journal Reviewer persona:]
## Recommendation

**Decision:** [Accept / Minor Revision / Major Revision / Reject]
**Justification:** [2-3 sentences explaining the recommendation]
```

---

## Review Quality Standards

The review itself should meet these standards:

- **Specific:** Every issue points to a specific section, paragraph, or sentence. Never "the methods need improvement" without saying what specifically.
- **Actionable:** Every issue includes a concrete suggestion for how to fix it.
- **Balanced:** Acknowledge strengths alongside weaknesses. A review that only criticizes is not helpful.
- **Evidence-based:** Cite specific text from the manuscript when pointing out issues.
- **Proportionate:** The number and severity of issues should match the actual quality of the work.
