# Evidence Spectrum

Reference for Claude when interpreting hypothesis validation results. Uses a five-level spectrum instead of binary pass/fail to reflect the nuanced nature of scientific evidence.

---

## Overview

Scientific evidence is not binary. A single study rarely "proves" or "disproves" a hypothesis. This spectrum provides structured interpretation language that communicates both the statistical result and appropriate confidence in that result.

The five levels combine three indicators:
1. **p-value** -- statistical significance threshold
2. **Effect size** (Cohen's d or equivalent) -- practical significance
3. **Confidence interval** -- precision and direction of the estimate

All three must be considered together. A tiny p-value with a trivial effect size does not constitute strong support.

---

## Strong Support

**Criteria:** p < 0.01 AND |effect size| >= 0.5 AND confidence interval excludes zero

**Interpretation language:**
- "The data provide strong support for this hypothesis."
- "With a large effect size (d = X) and high statistical significance (p = Y), these results are consistent with the predicted relationship."
- "The 95% CI [lower, upper] excludes zero, indicating a reliable directional effect."

**Caveats to always include:** "Strong support from a single analysis warrants replication. Consider potential confounders and whether the sample is representative."

---

## Moderate Support

**Criteria:** p < 0.05 AND |effect size| >= 0.2 AND confidence interval excludes zero

**Interpretation language:**
- "The data provide moderate support for this hypothesis."
- "A statistically significant result (p = X) with a small-to-medium effect (d = Y) suggests a real but modest relationship."
- "The 95% CI [lower, upper] excludes zero, though the lower bound is close to it."

**Caveats to always include:** "Moderate support suggests the effect is likely real but may not be robust. Larger samples or different populations could yield different results."

---

## Inconclusive

**Criteria:** p near the 0.05 boundary (0.03-0.10) OR confidence interval is wide OR small effect with marginal significance

**Interpretation language:**
- "The evidence is inconclusive regarding this hypothesis."
- "While there is a trend in the predicted direction (p = X, d = Y), the result does not clearly distinguish signal from noise."
- "The wide confidence interval [lower, upper] means both meaningful and trivial effects are compatible with the data."

**Caveats to always include:** "An inconclusive result is not evidence against the hypothesis. It indicates insufficient power or effect size to draw a firm conclusion. Consider: increasing sample size, reducing measurement noise, or refining the hypothesis."

---

## Moderate Against

**Criteria:** p >= 0.05 AND |effect size| < 0.2 AND confidence interval includes zero

**Interpretation language:**
- "The data provide moderate evidence against this hypothesis."
- "No statistically significant effect was detected (p = X), and the effect size is small (d = Y)."
- "The 95% CI [lower, upper] includes zero, suggesting the true effect may be negligible."

**Caveats to always include:** "Absence of evidence is not evidence of absence. The study may have been underpowered. Check the power analysis: if power was below 0.80 for the hypothesized effect, insufficient sample size is a plausible explanation."

---

## Strong Against

**Criteria:** p >= 0.70 AND |effect size| < 0.1 AND confidence interval includes zero with narrow bounds

**Interpretation language:**
- "The data provide strong evidence against this hypothesis."
- "The effect is negligible (d = X) with a narrow confidence interval [lower, upper] tightly centered around zero."
- "With adequate power, this result suggests the hypothesized effect is unlikely to exist at a meaningful magnitude."

**Caveats to always include:** "Strong evidence against should be interpreted in context. Verify that the study had sufficient statistical power (>= 0.80) for the expected effect size. A well-powered null result is informative; an underpowered null result is not."

---

## Reporting Guidelines

When presenting results, always:
1. **State the verdict clearly** using the spectrum level name
2. **Report all three indicators** (p-value, effect size, confidence interval)
3. **Include the rationale** connecting the numbers to the verdict
4. **Add the standard caveat** for that level
5. **Never use "proves" or "disproves"** -- science accumulates evidence, it does not deliver proof
6. **Frame in terms of the hypothesis** -- "The data [support/do not support] the hypothesis that..."
7. **Suggest next steps** -- what would strengthen or clarify the evidence (more data, different design, refined hypothesis)
