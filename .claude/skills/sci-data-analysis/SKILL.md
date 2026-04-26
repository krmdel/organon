---
name: sci-data-analysis
description: >
  Load, analyze, clean, and visualize scientific data. Natural language
  invocation -- describe what you need and the skill routes to the right
  operation. Supports CSV, Excel, JSON loading with profiling. Statistical
  tests (t-test, ANOVA, chi-square, correlation, regression) with assumption
  checking. Data cleaning (missing values, outliers, normalization). Dual
  output plots: publication-quality Matplotlib + interactive Plotly HTML.
  Triggers on: "load data", "analyze", "statistics", "t-test", "ANOVA",
  "correlation", "regression", "clean data", "plot", "chart", "graph",
  "scatter", "histogram", "box plot", "heatmap", "visualize".
  Does NOT trigger for: literature search, paper writing, hypothesis generation,
  explaining data patterns (use sci-hypothesis), group differences interpretation
  (use sci-hypothesis), AI image generation (use viz-nano-banana).
---

# Data Analysis & Visualization

## Outcome

Load any dataset, run statistical analyses with assumption checking, clean data, and generate publication-quality plots -- all from natural language. Every operation logs to the reproducibility ledger.

Outputs go to `projects/sci-data-analysis/` with date-stamped filenames.

## Context Needs

| File | Load level | Purpose |
|------|-----------|---------|
| `research_context/research-profile.md` | full | Personalize analysis suggestions to scientist's field |
| `context/learnings.md` | `## sci-data-analysis` section | Apply previous feedback |

## Dependencies

| Skill | Required? | What it provides | Without it |
|-------|-----------|-----------------|------------|
| None | -- | All scripts are bundled | -- |

Requires: Python venv with pandas, scipy, numpy, matplotlib, seaborn, SciencePlots, plotly, openpyxl.
Run `.claude/skills/sci-data-analysis/scripts/setup.sh` if packages missing.

## Step 0: Detect Intent (per D-01)

Parse the user's natural language request into an operation:
- **load** -- "load", "open", "read", "import", file paths mentioned
- **analyze** -- "test", "t-test", "ANOVA", "correlation", "regression", "statistics", "compare"
- **clean** -- "clean", "missing", "outlier", "normalize", "standardize", "handle NaN"
- **plot** -- "plot", "chart", "graph", "visualize", "scatter", "bar", "heatmap", "box", "violin"
- **profile** -- "describe", "summary", "shape", "columns", "info"

If ambiguous, ask. If multiple operations implied ("load and plot"), chain them.

**Session state (per D-03):** Remember the current dataset path and DataFrame. If the user says "now run a t-test", use the last loaded dataset. If no dataset loaded, ask for a file path.

## Step 1: Load & Profile Data (DATA-01)

When the user provides a file:
1. Run setup.sh if needed (first invocation only)
2. Execute `data_ops.load_and_profile(filepath)` via `.venv/bin/python`
3. Display the profile: shape, columns with types + null counts, summary stats
4. Store the file path and note it as "current dataset"

Supported: .csv, .xlsx, .xls, .json

## Step 1.5: Pre-Analysis Advisor — propose method BEFORE running

**Always run this when the user's request is open-ended** ("analyze this", "what can you tell me about this dataset", "look at this data") OR when loading without a specified next step. Skip only when the user already named a specific test/plot/operation.

The goal is to be a scientific collaborator, not a button the user pushes. Based on the profile from Step 1, propose the top 2–3 operations *from this skill* that fit the data shape, plus one escalation hint.

Checks to run on the profile:

| Signal | What it suggests |
|--------|------------------|
| Two numeric columns + one categorical group column (≤ 5 groups) | group comparison → `ttest_ind` (2 groups, normal) / `mannwhitney` (2 groups, non-normal) / `anova` (3+ groups) |
| Two numeric columns, no grouping | correlation → `pearson` (linear, normal) / `spearman` (monotonic, non-normal) |
| Wide time-indexed numeric | trend / seasonality plot (line), then regression if a predictor is named |
| One outcome numeric + 2+ numeric predictors | `regression` (linear) or `logistic` if outcome is binary |
| Sparse / many NaN / obvious outliers | Step 3 (cleaning) before analysis — say so explicitly |
| Biomedical domain markers (gene/drug/disease columns, dosage, clinical fields) | Also hint: `sci-tools` browse mode may have a specialised tool for this (per CLAUDE.md Task Routing cascade) |
| Data pattern asking *why* (e.g. "what explains the trend?") | Hand off to `sci-hypothesis` — that's its domain, not ours |

**Normality / shape checks** (fast, non-blocking): for any numeric column the advisor recommends testing, run a Shapiro–Wilk on a 500-row sample via `data_ops` and note whether the parametric assumption holds. That drives the parametric-vs-non-parametric recommendation above.

**Output format** — one compact proposal, not a menu dump:

```
Profile says: 480 rows, 2 numeric (expression, dose), 1 grouping (treatment, 3 levels).
Treatment is skewed (Shapiro p=0.003) — non-parametric route is safer.

Recommended next step:
  1. Kruskal–Wallis across treatments (non-parametric ANOVA)   ← I'll do this
  2. Post-hoc Dunn's test if #1 is significant                 ← follow-up
  3. Box plot per group                                        ← for the Results figure

Alt path: if you want to know *why* treatments differ, that's sci-hypothesis territory.
Alt path: biomedical drug/dose data — sci-tools may have a domain-specific tool.

Proceed with #1, pick another, or skip the advisor?
```

Respect the choice. If the user says "just do it" or "go", run #1. If they pick a different test, run that. If they say "skip advisor", jump straight to the raw operation and don't re-offer this session.

## Step 2: Statistical Analysis (DATA-02, DATA-04)

When the user wants to test a hypothesis:

1. **Ask what they want to compare** (if not clear from context)
2. **Present methods overview** (per D-05): Read `references/statistical-tests.md` and show a comparison table of relevant tests with pros/cons. Let the scientist choose.
3. **Run the test** with assumption checking (per D-06):
   - Execute `data_ops.run_statistical_test(df, test_type, columns, alpha)`
   - Supported test_type values: `ttest_ind`, `ttest_paired`, `anova`, `chi_square`, `pearson`, `spearman`
   - columns dict keys vary by test: `group_col`/`value_col` for t-test/ANOVA, `col_a`/`col_b` for chi-square/correlation
   - If assumptions violated, explain which failed and suggest alternative
   - Let scientist decide whether to proceed or switch
4. **Generate report** (per D-07): Execute `data_ops.generate_report(results, test_type)`
5. **Save report** to `projects/sci-data-analysis/{YYYY-MM-DD}_{test-name}-results.md`
6. Show clickable absolute file path

For regression (per D-08): Execute `data_ops.run_regression(df, x_cols, y_col, reg_type)`.
Supported reg_type: `linear`, `logistic`.

## Step 3: Data Cleaning (DATA-03)

When the user wants to clean data:
1. Show current data issues (nulls, potential outliers per IQR)
2. Read `references/cleaning-methods.md` for options
3. Present options and let scientist choose
4. Execute `data_ops.clean_data(df, operations)` where operations is a list of dicts with:
   - `type`: `drop_missing`, `fill_missing`, `interpolate_missing`, `remove_outliers`, `normalize`
   - `columns`: list of column names
   - Additional params per type (method, factor, value)
5. Show before/after comparison
6. Save cleaned data to `projects/sci-data-analysis/{YYYY-MM-DD}_cleaned-{name}.csv`
7. Update "current dataset" to cleaned version

## Step 4: Plot Generation (VIZ-01, VIZ-03, VIZ-04, VIZ-05)

When the user wants a visualization:
1. **Auto-detect or accept explicit type** (per D-10): Read `references/plot-types.md` for auto-detection rules
2. **Generate BOTH static + interactive** (per D-12):
   - Use `plot_ops.generate_dual_plot(df, plot_type, x_col, y_col, base_path, style, title, xlabel, ylabel, hue_col)`
   - Returns dict with `static` (list of SVG/PDF/PNG paths) and `interactive` (HTML path)
3. **Style**: Default `science` + `no-latex`. Accept style override: nature, ieee, grid (per D-11)
4. **Save all formats** (per D-13): PNG 300dpi, SVG, PDF, HTML to `projects/sci-data-analysis/`
5. Copy non-markdown files to `~/Downloads/`
6. Show clickable absolute file paths

Supported plot types: scatter, bar, line, heatmap, box, violin.

## Step 5: Feedback

After any operation: "How do these results look? Want to adjust parameters, try a different test, or visualize the results?"
Log feedback to `context/learnings.md` under `## sci-data-analysis`.

## Rules

*Updated when the user flags issues. Read before every run.*

---

## Self-Update

If the user flags an issue, update the ## Rules section with the correction and today's date.
