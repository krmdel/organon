# Aesthetic library (the L2 convention layer)

Read by both the Drawer and the Reviewer at the start of every run. This is the
SECONDARY anchor: the cleaned reference crop (L1) is primary, and this library is
the fallback when the reference alone is insufficient — low-resolution screenshots,
anti-aliasing on thin elements, or a data shape that needs more series than the
reference shows.

Original clean-room distillation of the convention library used by FigMirror (open
project, no license file). The curated values below are my own selection within the
ranges the technique describes; no source was copied.

Each property section is structured the same way: **most likely classes** (a
categorical menu, not a single value), **range / dependencies**, **PIL reliability**
(reliable / partially / unreliable), and **L1-vs-L2 precedence**.

---

## Meta-principle 1 — compactness

Strong paper figures are tight, not airy. Compact composition reads as refined;
loose composition reads as a notebook export. When unsure about any density-related
property, bias toward tight.

- Inter-panel spacing: `wspace 0.05-0.15`, `hspace 0.15-0.30` for the tight (paper)
  class. Matplotlib's default `0.2 / 0.2` is the *moderate* class — falling back to
  it reads non-paper.
- Legend internal spacing: tight class — `handletextpad 0.3-0.4`,
  `columnspacing 0.8-1.4`, `borderpad 0.3-0.4`. Defaults (`0.8 / 2.0 / 0.4`) are
  moderate.
- Tick padding 4-6 pt; title-to-axes pad 4-6 pt; outer margins only enough for axis
  labels + legend bands.
- Per-point label band: stack-line gap 1-2 pt, packed close to markers.

Anti-pattern to call out by name: matplotlib defaults sit in the moderate class for
*every* density property. `plt.legend()` / `plt.subplots()` without explicit density
params produce moderate output that camera-ready review catches.

## Meta-principle 2 — hairline calibration (visible but recessive)

Spines, gridlines, and tick marks must be visible enough to read when looked for,
yet recessive enough to vanish while reading the data. Both extremes are wrong:

| failure | symptom |
|---|---|
| too pale / too thin | "I can't see any structure" — element is functionally absent |
| too dark / too thick | element competes with the data lines — figure reads busy |

Pick the **literal middle of the L2 class range**, not either boundary. For
gridlines that is `#e0e0e0`, not `#ededed` (renders invisible) and not `#d4d4d4`
(competes). A matplotlib correction: the same hex renders paler in matplotlib than
in the reference's source rendering due to anti-aliasing on thin lines, so if the
reference's measured gridline is at the pale end, pick one notch darker than the
*measurement* (not one notch darker than the whole class).

Hairline elements are exactly where eyeballing is unreliable in both directions —
the eye misses a faint line that is there and infers one that is not. Commit to a
hairline class (especially gridline direction) only with quoted PIL evidence, and
affirm one only after PIL-verifying it on the draft.

## Meta-principle 3 — measurement humility

A number's confidence comes from the heuristic that produced it, not its decimal
places. `per_panel_aspect = 1.92` from a brittle panel-bbox detector is NOT more
accurate than "looks roughly golden, around 1.5-1.7." False precision is worse than
acknowledged uncertainty: it locks the loop onto a wrong target.

For any brittle property, work the cycle **constrain -> perceive -> render ->
adjust**: narrow to an L2 class band, eyeball the reference into one class, pick the
middle, render, look again, adjust within the class next iter. Record such anchors
as `[L1-perceived]`, not `[L1-PIL]`.

Code measurement is appropriate only when the arithmetic is trivial (`W/H` for
full-image aspect), the sampled region is large and well-bounded (a filled marker,
not a thin spine), and the result has been eyeball-sanity-checked. It is NOT the
sole source for per-panel aspect, hairline widths, sub-pixel anti-aliased
properties, font family/weight, or gestalt properties like compactness.

---

## Spines

- **Classes:** near-black hairline `#000000`-`#444444` at `0.5-1.0pt`; soft mid-grey
  `#555555`-`#888888` at `0.4-0.8pt`. Anything lighter than `#aaaaaa` is almost
  always a mis-sample of background.
- **Sides:** left+bottom only (ML-venue default, most common); all four (Nature /
  Science default, paired with very thin weight).
- **PIL reliability:** colour/width UNRELIABLE via strip means (spines are 1-2 px;
  the mean is dominated by background). If you must measure colour, use
  min-along-line (darkest pixel per row). Count/sides are L1 visual-structure facts
  — count them on the reference, do not infer from L2.
- **L1 vs L2:** L1 for count/sides; L2 fallback class for colour/width.

## Gridlines

- **Classes:** solid mid-light grey `#dadada`-`#e6e6e6` (mid `#e0e0e0`) at
  `0.5-0.8pt`, alpha `0.8-1.0`; dashed light grey `#cecece`-`#dcdcdc` (mid
  `#d6d6d6`); or none.
- **Direction:** `horizontal-only` | `vertical-only` | `both` | `none`. **Default is
  `both`.** Deviating from `both` requires quoted PIL evidence (a row+col brightness
  profile showing strictly zero darker-than-threshold lines in one direction). Never
  call `ax.xaxis.grid(False)` on an eyeball alone — gridlines are the elements the eye
  reads least reliably.
- **Dependency:** always `ax.set_axisbelow(True)` so gridlines sit behind the data.
- **PIL reliability:** colour conditionally reliable via per-line-darkest median (not
  mean); width unreliable (L2 floor); direction reliable via row/col profiling.
- **L1 vs L2:** colour L1 if sampled correctly; width L2; direction L1 (default
  `both`).

## Type (font family, size, weight)

- **Serif vs sans is a commonly-missed call.** LaTeX-typeset papers default to serif
  (Times via mathptmx, or Computer Modern). Word-typeset papers and industry blog
  reproductions default to sans. Matplotlib's DejaVu Sans is wrong for roughly half
  of references — LOOK, do not assume. Serif cues: feet/serifs on `I M T`, variable
  stroke width, calligraphic math italics. Sans cues: clean stroke ends, uniform
  width.
- **Families (pick one per figure):**
  - Times-style serif: Times New Roman, Liberation Serif, DejaVu Serif (bundled),
    Nimbus Roman.
  - Computer Modern style: Latin Modern Roman, STIX Two Text, DejaVu Serif.
  - Sans: Helvetica / Arial, DejaVu Sans (bundled), Liberation Sans.
  - Monospace labels: JetBrains Mono, Source Code Pro.
- **Size / weight:** body 7-11 pt, title 9-13 pt (sometimes semibold), math italic
  for variables. Weight `regular` by default — bold body is almost always wrong.
- **matplotlib (set before any plotting):**
  ```python
  plt.rcParams["font.family"] = "serif"
  plt.rcParams["font.serif"] = ["Times New Roman", "Liberation Serif", "DejaVu Serif"]
  plt.rcParams["mathtext.fontset"] = "stix"
  ```
- **PIL reliability:** family by careful eye (not measurable directly); body size
  reliable via bbox height (+/-15%); weight unreliable (use L2 default).
- **L1 vs L2:** family — L1 narrows by eye, L2 picks the specific font. Default when
  truly ambiguous: Times-style serif, NOT DejaVu Sans.

## Inter-panel spacing (wspace / hspace / margins)

- **Classes:** tight `wspace 0.05-0.15, hspace 0.15-0.30` (paper default); moderate
  `0.15-0.25 / 0.30-0.45` (slide / workshop); generous `0.25-0.40 / 0.40-0.60` (raw
  matplotlib). Matplotlib's `0.2 / 0.2` is moderate, not tight.
- **Edge-label defense:** when a rightmost per-point label threatens cross-panel
  bleed, fix it with `xlim` padding + `ha='right'`, NOT by widening `wspace` (which
  makes the figure read loose).
- **PIL reliability:** reliable for `gap_px / panel_width_px` when measured in the
  data area (not titles / label bands / tick rows).
- **L1 vs L2:** L1 wins once measured (+/-5%); default class when ambiguous is tight.

## Aspect — figure-level vs per-panel (two distinct properties)

- **Figure aspect (W/H of the whole canvas):** typical by grid — 1x1 `1.3-1.8`, 1x3/1x4
  `2.4-3.2`, 2x3 `1.6-2.2`, 3x3 `1.0-1.4`. PIL-reliable via `img.size[0]/size[1]`. L1
  wins, +/-10% tolerance, no sub-pixel locking.
- **Per-panel aspect (W/H of one panel's data area):** classes — near golden 1.4-1.7
  (line-plot default), near square 0.9-1.2 (scatter / heatmap), tall 0.6-0.9 (bars),
  very wide 1.7+ (usually a smell — flat-wide panels read as slide-deck, not paper).
  PIL UNRELIABLE — eyeball-classify, record as `[L1-perceived]`. A common bug:
  inflating `hspace` "to make room for panel titles" — titles use `pad=` (in points),
  not `hspace`; `hspace 0.40+` flattens panels.

## Markers

- **Classes:** filled circle 4-8 pt no edge; x-cross 5-7 pt for baseline series;
  filled square/triangle 5-8 pt. Marker size scales with line width (~1.5x line_pt).
- **PIL reliability:** reliable for filled-region diameter; partial for edges.
- **L1 vs L2:** L1 for shape and approximate diameter; L2 default if the reference
  marker is too small to discern (<= 3 px).

## Colour palette

- The reference's PIL-sampled palette is always primary — sample the line/marker
  CENTER (not the anti-aliased edge), filter near-white background pixels, take the
  median.
- **Extension menu (when our data has more series than the reference):** Tableau-10;
  Seaborn-deep desaturated ~15%; ColorBrewer Set2 (colorblind-safe); viridis /
  plasma / cividis slices for sequential.
- **Constraints:** avoid red+green alone; keep hue separation >= 30 degrees between
  adjacent series.
- **L1 vs L2:** L1 for series 1..N where N is the reference's series count; L2 extends
  for N+1..M.

## Tick marks

- **Classes:** outward 3-5 pt (some venues); length 0 (no marks, gridlines carry the
  scale — common in modern figures); inward 3-4 pt (older, reads dated — avoid).
- **L1 vs L2:** L1 wins; L2 default is `length=0` when ambiguous.

## Legend treatment

- **Frame style:** rounded soft-tinted frame; no frame (`frameon=False`, common in
  body figures); or inline labels at line ends. L1 grounds the style.
- **Internal density:** default tight (`handletextpad 0.3-0.4`, `columnspacing
  0.8-1.4`, `borderpad 0.3-0.4`); matplotlib defaults are moderate. Prefer a single
  row (`ncol=N`) when the canvas allows. L2 grounds internal density (default tight).
- **PIL reliability:** presence/position reliable; frame colour partial; internal
  density visible via legend-ink-fraction.

## Per-point label band (stacked numeric labels)

- **Strategy classes:** value+delta stacked above marker with a second value below;
  single line above; or none.
- **Headroom:** band height in display points = `(lines * annot_pt + (lines-1) *
  line_gap_pt + pad)`, translated to data units via `ax.transData.inverted()`; set
  `ylim_top` to cover it. Compute from OUR data — do NOT copy the reference's `ylim`.
- **L1 vs L2:** L1 for which strategy; L2 for the headroom arithmetic.

---

## Extending this file

Add new sections under the right category, keeping the per-section template
(classes / range+dependencies / PIL reliability / L1-vs-L2). When a new reference
surfaces a property that does not fit an existing class, add a class rather than
rewriting the rule.
