"""figure_iter1.py — viz-figure-mirror Drawer, iteration 1.

Renders the USER's data (epoch, ResNet, ViT) in the VISUAL STYLE of
inputs/reference.png (a teal/orange two-series line+marker model-comparison
plot). Style choices trace to L1 (the reference) or L2 (aesthetic-library.md);
no L3 taste.

Self-contained: data is inline in the DATA SECTOR below.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# --- Print-quality boilerplate (always present, never debated) ------------- #
plt.rcParams["pdf.fonttype"] = 42       # camera-ready: no Type 3
plt.rcParams["ps.fonttype"] = 42
plt.rcParams["axes.unicode_minus"] = False

# === DATA SECTOR (edit here) ===
EPOCH = [1, 2, 3, 4, 5, 6, 7, 8]
RESNET = [0.52, 0.61, 0.66, 0.70, 0.73, 0.745, 0.755, 0.76]
VIT    = [0.47, 0.58, 0.65, 0.71, 0.755, 0.79, 0.815, 0.83]
SERIES = [
    # (label, y-values, hex color, marker)   color/marker grounded below
    ("ResNet", RESNET, "#2a9d8f", "o"),   # L1 teal  (42,157,143), filled circle
    ("ViT",    VIT,    "#e76f51", "s"),   # L1 orange(231,111,81), filled square
]
XLABEL = "Training epoch"
YLABEL = "Validation accuracy"
TITLE  = "Model comparison"
# === END DATA SECTOR ===

# --- Style anchors (cite L1 / L2) ------------------------------------------ #
# L1 full-image aspect = 780/510 = 1.529 → 1x1 line-plot class (L2: 1.3-1.8).
#   Reproduce at figsize 6.2x4.05 (W/H = 1.531, within +/-10% of 1.529).
# L1 palette: teal #2a9d8f, orange #e76f51 (PIL median of filled line/marker px).
# L1 spines: top+right despined, left+bottom shown in soft grey → 2 spines.
#   Reference spines read mid-grey hairline (L2 spine class #555-#888); use #888888.
# L1 gridlines: HORIZONTAL-ONLY, dashed, light grey. y-grid only, dashed, #cccccc
#   (L2 dashed-light class #cecece-#dcdcdc; pick mid, one notch darker for AA).
# L1 legend: frameless, upper-left, inside axes, one entry per line.
# L1 ticks: no visible tick marks (gridlines carry scale) → length 0 (L2 default).
# L1 type: clean sans-serif (Word/blog register) → DejaVu Sans (L2 sans family).
# L1 x ticks: integer epochs.

# --- Font class: pull the typeface into the SANS class (L1: reference is a
#     clean uniform-width sans, not serif). Set EXPLICITLY here, after any
#     rcParams/PUBLICATION_RCPARAMS application, so a serif font.family default
#     cannot override it. DejaVu Sans leads the stack: matplotlib-bundled, always
#     resolves to a true sans, so the figure never silently falls back to serif.
#     Regular (not bold) weight kept so labels stay recessive (iter-1 focus 2).
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Helvetica", "Arial", "Liberation Sans"]
plt.rcParams["font.weight"] = "normal"
plt.rcParams["axes.titleweight"] = "normal"
plt.rcParams["axes.labelweight"] = "normal"

SPINE_GREY = "#888888"   # L2 soft mid-grey spine class
GRID_GREY  = "#cccccc"   # L2 dashed-light gridline class (one notch darker for AA)

fig, ax = plt.subplots(figsize=(6.2, 4.05))   # W/H = 1.531 ≈ L1 1.529

for label, yvals, color, marker in SERIES:
    ax.plot(
        EPOCH, yvals,
        color=color, marker=marker,
        linewidth=2.0, markersize=6.5,
        markeredgecolor=color, markerfacecolor=color,
        label=label, zorder=3,
    )

# Despine top+right; soft-grey hairline left+bottom (L1: 2 spines).
for side in ("top", "right"):
    ax.spines[side].set_visible(False)
for side in ("left", "bottom"):
    ax.spines[side].set_visible(True)
    ax.spines[side].set_linewidth(0.9)
    ax.spines[side].set_color(SPINE_GREY)

# Horizontal-only dashed light grid behind data (L1).
ax.set_axisbelow(True)
ax.yaxis.grid(True, linestyle="--", linewidth=0.7, color=GRID_GREY, alpha=1.0)
ax.xaxis.grid(False)

# No tick marks; gridlines carry the scale (L1 / L2 default length 0).
ax.tick_params(length=0, colors="#333333", labelsize=11)

# Integer x ticks at every epoch (L1).
ax.set_xticks(EPOCH)
ax.set_xlim(EPOCH[0] - 0.4, EPOCH[-1] + 0.4)

# Headroom so the top series + top tick label clear the canvas edge (floor).
ymin = min(min(s[1]) for s in SERIES)
ymax = max(max(s[1]) for s in SERIES)
pad = (ymax - ymin) * 0.10
ax.set_ylim(ymin - pad, ymax + pad)

ax.set_xlabel(XLABEL, fontsize=12, color="#222222")
ax.set_ylabel(YLABEL, fontsize=12, color="#222222")
ax.set_title(TITLE, fontsize=13, color="#222222", pad=8)

# Frameless legend, upper-left inside axes (L1), tight internal density (L2).
ax.legend(
    frameon=False, loc="upper left",
    fontsize=11, handletextpad=0.4, borderpad=0.3, labelspacing=0.4,
)

fig.tight_layout()
fig.savefig("img_iter1.png", dpi=180, bbox_inches="tight")

if __name__ == "__main__":
    print("Saved img_iter1.png")
