# Statistical Test Selection Guide

Reference for choosing the right statistical test based on data type, design, and assumptions.

## Quick Selection Table

| Test | When to Use | Assumptions | Non-parametric Alternative | Effect Size |
|------|-------------|-------------|---------------------------|-------------|
| Independent t-test | 2 independent groups, continuous DV | Normality, homogeneity of variance | Mann-Whitney U | Cohen's d |
| Paired t-test | Same subjects, 2 conditions | Normality of differences | Wilcoxon signed-rank | Cohen's d |
| One-way ANOVA | 3+ independent groups, continuous DV | Normality per group, homogeneity | Kruskal-Wallis | Eta-squared |
| Chi-square | 2 categorical variables | Expected freq >= 5 per cell | Fisher's exact (2x2) | Cramer's V |
| Pearson correlation | 2 continuous, linear relationship | Normality, linearity | Spearman | r |
| Spearman correlation | 2 variables, monotonic relationship | None (nonparametric) | -- | rho |
| Linear regression (OLS) | Continuous DV, continuous/categorical IV | Linearity, normality of residuals, homoscedasticity | -- | R-squared |
| Logistic regression | Binary DV, continuous/categorical IV | Independence, no multicollinearity | -- | McFadden's R-squared |

---

## Independent t-test (`ttest_ind`)

**When to use:** Compare means of a continuous variable between two independent groups.
**Example:** "Is there a significant difference in gene expression between treatment and control?"

**Assumptions:**
1. **Normality** -- each group's data is normally distributed
   - Test: Shapiro-Wilk (`_shapiro_check`)
   - If violated: consider Mann-Whitney U
2. **Homogeneity of variance** -- groups have similar spread
   - Test: Levene's test
   - If violated: Welch's t-test is used automatically (does not assume equal variance)

**Pros:** Well-understood, powerful when assumptions met, provides confidence intervals.
**Cons:** Only 2 groups, sensitive to outliers, requires normality for small samples.

**Effect size:** Cohen's d. Small: 0.2, Medium: 0.5, Large: 0.8.

**Interpretation:** "The difference between groups was [significant/not significant], t(df) = X, p = Y. Cohen's d = Z indicates a [small/medium/large] effect."

---

## Paired t-test (`ttest_paired`)

**When to use:** Compare means from the same subjects under two conditions (before/after, matched pairs).
**Example:** "Did the treatment significantly change patient blood pressure?"

**Assumptions:**
1. **Normality of differences** -- the difference scores should be normally distributed
   - Test: Shapiro-Wilk on (data_a - data_b)
   - If violated: consider Wilcoxon signed-rank test

**Pros:** More powerful than independent t-test (controls for individual variability).
**Cons:** Requires paired data, sensitive to outliers in differences.

**Effect size:** Cohen's d on difference scores.

---

## One-way ANOVA (`anova`)

**When to use:** Compare means across 3 or more independent groups.
**Example:** "Does protein concentration differ across three cell lines?"

**Assumptions:**
1. **Normality** -- each group's data is normally distributed
   - Test: Shapiro-Wilk per group
2. **Homogeneity of variance** -- groups have similar spread
   - Test: Levene's test
   - If violated: consider Kruskal-Wallis H test

**Pros:** Tests multiple groups simultaneously, controls Type I error.
**Cons:** Only tells you "something differs" -- need post-hoc (Tukey HSD) to find which groups.

**Effect size:** Eta-squared. Small: 0.01, Medium: 0.06, Large: 0.14.

**Post-hoc:** If significant, run Tukey HSD or pairwise t-tests with Bonferroni correction.

---

## Chi-square Test (`chi_square`)

**When to use:** Test association between two categorical variables.
**Example:** "Is there a relationship between treatment group and outcome (cured/not cured)?"

**Assumptions:**
1. **Expected frequency >= 5** in each cell of the contingency table
   - If violated (any cell < 5): use Fisher's exact test (only available for 2x2 tables)

**Pros:** Works with categorical data, no distributional assumptions on the data itself.
**Cons:** Only detects association (not direction), sensitive to sample size.

**Effect size:** Cramer's V. Small: 0.1, Medium: 0.3, Large: 0.5.

---

## Pearson Correlation (`pearson`)

**When to use:** Measure linear relationship between two continuous variables.
**Example:** "Is there a linear correlation between gene expression and protein level?"

**Assumptions:**
1. **Normality** -- both variables should be normally distributed
2. **Linearity** -- relationship should be linear (check scatter plot)
   - If non-linear: consider Spearman (monotonic) or polynomial regression

**Pros:** Quantifies strength and direction of linear relationship, provides CI via Fisher z-transform.
**Cons:** Only detects linear relationships, sensitive to outliers.

**Effect size:** r itself. Small: 0.1, Medium: 0.3, Large: 0.5.

---

## Spearman Correlation (`spearman`)

**When to use:** Measure monotonic relationship between two variables (ranked data or non-normal).
**Example:** "Is there a monotonic relationship between tumor stage and survival time?"

**Assumptions:** None (nonparametric -- works on ranks).

**Pros:** Robust to outliers, works with ordinal data, no normality requirement.
**Cons:** Less powerful than Pearson when linear assumptions are actually met.

**Effect size:** rho (same interpretation as Pearson r).

---

## Linear Regression (`linear`)

**When to use:** Model the relationship between predictor(s) and a continuous outcome.
**Example:** "How well does temperature predict enzyme activity?"

**Assumptions:**
1. **Linearity** -- relationship between X and Y is linear
2. **Normality of residuals** -- residuals should be normally distributed
3. **Homoscedasticity** -- residual variance should be constant across X
4. **Independence** -- observations are independent

**Outputs:** Slope, intercept, R-squared, p-value, residual standard error, 95% CI for slope.
Supports both simple (1 predictor) and multiple (2+ predictors) regression.

---

## Logistic Regression (`logistic`)

**When to use:** Model the probability of a binary outcome.
**Example:** "Can biomarker levels predict disease presence (yes/no)?"

**Assumptions:**
1. **Independence** -- observations are independent
2. **No multicollinearity** -- predictors should not be highly correlated with each other

**Outputs:** Coefficients, odds ratios, p-values, log-likelihood, convergence status.
Uses scipy.optimize.minimize with BFGS method (lightweight alternative to statsmodels).

---

## Shapiro-Wilk Normality Test -- Important Caveats

The Shapiro-Wilk test is used for assumption checking but has known limitations:

- **n < 3:** Cannot run the test. Report "n < 3, cannot test."
- **n > 5000:** Test becomes unreliable (nearly always rejects normality due to high power). Use visual inspection (Q-Q plot) or D'Agostino-Pearson test instead. Report "n > 5000, use visual inspection."
- **3 <= n <= 5000:** Test is valid and reliable. Report statistic, p-value, and pass/fail.

**General guidance:** For large samples, mild departures from normality are usually tolerable due to the Central Limit Theorem. Focus on effect sizes and practical significance rather than just p-values.
