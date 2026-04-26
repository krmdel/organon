# Experiment Design Templates

Reference for Claude when generating experiment protocols in design mode. Each section provides a study type template with variables, sample size guidance, analysis plan, and common pitfalls.

---

## Randomized Controlled Trial

Gold standard for causal inference. Participants randomly assigned to treatment or control groups.

**When to Use:**
- Testing the effect of an intervention (drug, therapy, technique)
- You need strong causal evidence
- Random assignment is ethical and feasible

**Variables Template:**
- **IV:** Treatment condition (treatment vs control)
- **DV:** Primary outcome measure
- **Controls:** Baseline characteristics, confounders matched or randomized away

**Typical Sample Size Range:** 30-500 per group (depends on effect size)

**Recommended Analysis:** Independent t-test (2 groups), one-way ANOVA (3+ groups), with effect size (Cohen's d)

**Common Pitfalls:**
- Attrition bias if participants drop out unevenly between groups
- Hawthorne effect: participants behave differently because they know they are observed
- Failure to pre-register primary outcome leads to outcome switching

**Ethical Considerations:** IRB/ethics board approval required for human subjects. Informed consent. Consider equipoise -- is it ethical to withhold treatment from control group?

---

## Cohort Study

Observational design following groups over time to compare outcomes based on exposure.

**When to Use:**
- When random assignment is unethical or impractical
- Studying long-term effects of natural exposures (diet, environment, genetics)
- Prospective (forward) or retrospective (historical data)

**Variables Template:**
- **Exposure:** Naturally occurring factor (e.g., diet type, genetic variant)
- **DV:** Outcome measured over follow-up period
- **Controls:** Matched cohorts on key confounders (age, sex, baseline health)

**Typical Sample Size Range:** 100-10,000+ (larger to detect modest effects with confounders)

**Recommended Analysis:** Cox proportional hazards (survival), logistic regression (binary outcome), linear regression (continuous outcome)

**Common Pitfalls:**
- Confounding: unmeasured variables explain the observed association
- Loss to follow-up introduces selection bias
- Healthy worker effect: exposed group may be healthier than general population

**Ethical Considerations:** No intervention, so typically lower ethical burden. Privacy and data handling for long-term follow-up.

---

## Case-Control Study

Retrospective design comparing subjects with an outcome (cases) to those without (controls).

**When to Use:**
- Rare diseases or outcomes where prospective study would take too long
- Exploratory research to identify risk factors
- Cost-effective initial investigation

**Variables Template:**
- **Cases:** Subjects with the outcome of interest
- **Controls:** Matched subjects without the outcome
- **Exposure:** Measured retrospectively via records, interviews, biomarkers

**Typical Sample Size Range:** 50-500 per group (matching ratio 1:1 to 1:4 cases:controls)

**Recommended Analysis:** Odds ratio with logistic regression, chi-square test for association, McNemar's test for matched pairs

**Common Pitfalls:**
- Recall bias: cases remember exposures differently than controls
- Selection bias in choosing controls (must represent same source population)
- Cannot calculate incidence or relative risk directly (only odds ratio)

**Ethical Considerations:** Retrospective data use requires institutional approval. Sensitive health data handling.

---

## Cross-Sectional Study

Snapshot design measuring exposure and outcome at the same point in time.

**When to Use:**
- Estimating prevalence of a condition
- Exploring associations between variables (hypothesis-generating)
- Quick, low-cost initial investigation

**Variables Template:**
- **Variables:** All measured simultaneously (no clear IV/DV distinction)
- **Outcome:** Prevalence or association measure
- **Stratification:** Demographic or categorical groupings

**Typical Sample Size Range:** 100-5,000 (depends on population heterogeneity)

**Recommended Analysis:** Chi-square for categorical associations, Pearson/Spearman correlation for continuous, logistic regression for binary outcomes

**Common Pitfalls:**
- Cannot establish causation or temporal sequence
- Prevalence-incidence bias: only captures surviving/ongoing cases
- Non-response bias if survey-based

**Ethical Considerations:** Survey fatigue. Informed consent for data collection. Anonymization.

---

## Pre-Post Design

Measures the same subjects before and after an intervention or event.

**When to Use:**
- Evaluating change within the same group over time
- When a control group is not feasible
- Pilot studies before a full RCT

**Variables Template:**
- **IV:** Time point (pre vs post intervention)
- **DV:** Outcome measure at both time points
- **Controls:** Each subject serves as their own control

**Typical Sample Size Range:** 20-200 (paired design increases power)

**Recommended Analysis:** Paired t-test (continuous, normal), Wilcoxon signed-rank (non-normal), repeated measures ANOVA (3+ time points)

**Common Pitfalls:**
- Regression to the mean: extreme values at baseline naturally move toward the mean
- Maturation: natural changes over time confound treatment effect
- History: external events between pre and post measurements

**Ethical Considerations:** Same as RCT if intervention involved. Baseline data collection adds participant burden.

---

## Factorial Design

Tests two or more independent variables simultaneously, including their interactions.

**When to Use:**
- Multiple factors may influence the outcome
- Testing for interaction effects (does the effect of A depend on B?)
- Efficient: tests multiple hypotheses in one experiment

**Variables Template:**
- **IV1:** First factor (e.g., drug dose: low/medium/high)
- **IV2:** Second factor (e.g., delivery method: oral/injection)
- **DV:** Primary outcome
- **Controls:** Balanced assignment across all factor combinations

**Typical Sample Size Range:** 15-100 per cell (n_cells = levels_IV1 x levels_IV2)

**Recommended Analysis:** Two-way ANOVA (2 factors), three-way ANOVA (3 factors), with post-hoc comparisons (Tukey HSD) for significant effects

**Common Pitfalls:**
- Cell sizes shrink quickly with more factors (curse of dimensionality)
- Interpreting main effects is misleading when significant interactions exist
- Multiple comparisons inflate Type I error without correction

**Ethical Considerations:** More conditions means more participants. Ensure all factor combinations are ethically acceptable.
