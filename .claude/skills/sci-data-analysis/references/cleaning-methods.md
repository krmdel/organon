# Data Cleaning Methods Guide

Reference for choosing and applying data cleaning operations.

## Operations Reference

### Drop Missing (`drop_missing`)

**When to use:** Few missing rows, data is Missing Completely At Random (MCAR), or the specific rows are not critical.
**Parameters:** `columns` -- list of columns to check for NaN.
**Behavior:** Removes entire rows where any of the specified columns have NaN values.
**Default:** Drop rows with any NaN in specified columns.

**When NOT to use:** Large proportion of data is missing (>10%), data is Missing Not At Random (MNAR), or missingness carries information.

### Fill Missing (`fill_missing`)

**When to use:** Want to preserve all rows, reasonable imputation strategy exists.
**Parameters:** `columns`, `method` (mean, median, mode, value), optional `value` for constant fill.
**Behavior:** Replaces NaN with the computed or specified value.

| Method | Best for | Caveat |
|--------|----------|--------|
| `mean` | Symmetric numeric data | Sensitive to outliers |
| `median` | Skewed numeric data | Preserves distribution better |
| `mode` | Categorical data | May not be meaningful if multimodal |
| `value` | Known default (e.g., 0 for counts) | Requires domain knowledge |

**Default:** Mean for numeric columns, mode for categorical.

### Interpolate Missing (`interpolate_missing`)

**When to use:** Time series or ordered data where neighboring values are informative.
**Parameters:** `columns`, `method` (linear, polynomial, spline).
**Behavior:** Fills NaN by interpolating between existing values.
**Default:** Linear interpolation.

**When NOT to use:** Data is not ordered, gaps are very large, or missingness is systematic.

### Remove Outliers (`remove_outliers`)

**When to use:** Extreme values are distorting statistical results or visualizations.
**Parameters:** `columns`, `method` (iqr), `factor` (default 1.5).
**Behavior:** Removes rows where values fall outside Q1 - factor*IQR to Q3 + factor*IQR.

| Factor | Sensitivity | Removes |
|--------|-------------|---------|
| 1.5 (default) | Standard | Mild + extreme outliers |
| 3.0 | Conservative | Only extreme outliers |

**When NOT to use:**
- Outliers are meaningful (e.g., rare disease cases, extreme environmental events)
- Small sample size (removing points dramatically changes results)
- Data is naturally skewed (log-transform first instead)

### Normalize (`normalize`)

**When to use:** Variables are on different scales and need to be comparable.
**Parameters:** `columns`, `method` (zscore, minmax).
**Behavior:**

| Method | Formula | Range | Best for |
|--------|---------|-------|----------|
| `zscore` | (x - mean) / std | Unbounded (mean=0, std=1) | Most statistical analyses, PCA |
| `minmax` | (x - min) / (max - min) | [0, 1] | Neural networks, distance-based methods |

**Default:** Z-score normalization.

---

## Before/After Comparison Checklist

After any cleaning operation, verify:
- [ ] Row count change is reasonable (not losing >50% of data unexpectedly)
- [ ] Summary statistics still make sense for the research question
- [ ] No new NaN values introduced (e.g., by normalization of constant columns)
- [ ] Cleaning operations are logged to reproducibility ledger

---

## When NOT to Clean

Not all data issues require cleaning. Preserve raw data when:

1. **Outliers carry scientific meaning** -- extreme measurements may be the finding, not noise
2. **Missingness is informative** -- in clinical data, missing values may indicate a pattern (e.g., patients too sick to complete follow-up)
3. **Data is already clean** -- avoid over-processing; each transformation loses some information
4. **You need to report on raw data characteristics** -- journals may require raw data descriptions

**Best practice:** Always keep the original dataset. Clean a copy and document every operation in the reproducibility ledger.
