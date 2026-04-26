# Plot Type Selection Guide

Reference for auto-detecting the best plot type from data structure and for manual overrides.

## Auto-Detection Rules

When the user asks for a visualization without specifying the type, use these rules to suggest the best plot:

| Data Pattern | Recommended Plot | Why | Example |
|-------------|-----------------|-----|---------|
| 2 continuous columns | scatter | Shows relationship/correlation | Weight vs height |
| 1 categorical + 1 continuous | box or violin | Shows distribution per group | Treatment group vs response |
| 1 categorical (counts) | bar | Shows frequency/count comparison | Species counts |
| Time series (date + continuous) | line | Shows trend over time | Temperature over months |
| Correlation matrix (all numeric) | heatmap | Shows all pairwise relationships | Gene expression matrix |
| 1 continuous (distribution) | box (single) | Shows distribution shape and outliers | Measurement distribution |

**Detection logic:**
1. Count numeric vs categorical columns selected
2. Check if any column is datetime-like (parse with pd.to_datetime)
3. If user selects 2 numeric columns -> scatter
4. If user selects 1 categorical + 1 numeric -> box
5. If user selects only 1 column -> bar (categorical) or box (numeric)
6. If user wants "all correlations" -> heatmap on numeric subset

---

## Plot Types Reference

### Scatter (`scatter`)

**Best for:** Showing relationships between two continuous variables.
**Data requirements:** x_col (numeric), y_col (numeric), optional hue_col for grouping.
**Common customizations:** Color by group (hue_col), trend line overlay, log scale.
**When NOT to use:** Categorical x-axis (use bar/box instead), too many overlapping points (consider heatmap or density).

### Bar (`bar`)

**Best for:** Comparing values across categories, showing frequency counts.
**Data requirements:** x_col (categorical), optional y_col (numeric for aggregated values).
**Common customizations:** Horizontal orientation, stacked bars, error bars.
**When NOT to use:** Continuous x-axis (use line), too many categories (>15 -- consider grouping).

### Line (`line`)

**Best for:** Showing trends over a continuous or time-based axis.
**Data requirements:** x_col (numeric/datetime), y_col (numeric), optional hue_col for multiple series.
**Common customizations:** Multiple series, confidence bands, markers at data points.
**When NOT to use:** Unordered categorical data (use bar), no meaningful connection between points.

### Heatmap (`heatmap`)

**Best for:** Visualizing correlation matrices, 2D intensity data.
**Data requirements:** Numeric DataFrame (auto-computes correlation matrix). x_col is ignored for correlation heatmaps.
**Common customizations:** Annotation values, color scale, clustering.
**When NOT to use:** Few variables (<3 -- just report numbers), mixed data types.

### Box (`box`)

**Best for:** Comparing distributions across groups, spotting outliers.
**Data requirements:** x_col (categorical grouping), y_col (numeric values).
**Common customizations:** Notched boxes (CI for median), overlay data points.
**When NOT to use:** Very few data points per group (<5 -- show raw data instead).

### Violin (`violin`)

**Best for:** Showing full distribution shape across groups (more detail than box plot).
**Data requirements:** x_col (categorical grouping), y_col (numeric values).
**Common customizations:** Split violins for two-condition comparisons, inner box plot.
**When NOT to use:** Audiences unfamiliar with violin plots (use box for broader audiences).

---

## Style Presets

Available SciencePlots styles for publication-quality output:

| Style | Best for | Journal |
|-------|----------|---------|
| `science` (default) | General scientific plots | Any |
| `nature` | Nature family journals | Nature, Nature Methods, etc. |
| `ieee` | IEEE publications | IEEE Transactions |
| `grid` | Presentations, posters | Any (higher contrast) |

Pass style name to `generate_static_plot(style="nature")` or `generate_dual_plot(style="nature")`.
Default: `['science', 'no-latex']` -- clean academic style without requiring LaTeX installation.

---

## Output Formats

Every plot generates 4 files (per D-12, D-13):
1. **SVG** -- vector, editable in Illustrator/Inkscape (saved first per Pitfall 5)
2. **PDF** -- vector, ready for journal submission
3. **PNG** -- raster at 300 DPI, for presentations and quick viewing
4. **HTML** -- interactive Plotly chart with zoom, hover, filter
