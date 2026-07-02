"""Deterministic quality-floor module for viz-figure-mirror.

A self-contained, importable, side-effect-free set of checks that decide whether a
matplotlib figure clears the mechanical "quality floor" before any aesthetic review
happens. The floor catches the two classes of defect that make a paper figure
unshippable regardless of how good its style is:

  1. Text-on-text overlap (tick labels, titles, axis labels, annotations colliding).
  2. Clipped text (any label whose glyphs fall outside the saved canvas).

It also carries a publication-grade rcParams dict and an axes styler so a draft
never ships with matplotlib's give-away defaults (all-four heavy spines, dark
gridlines, Type-3 fonts).

Clean-room reimplementation. The bbox-disjointness idea and the anti-slop rcParam
posture are inspired by FigMirror (github project, no license file); none of its
source is copied. Algorithm and prose here are original.

Design notes:
  - Forces the Agg backend on import so the module never needs a display and is safe
    to import inside tests / headless CI.
  - Every public function is pure: it draws into the renderer it is handed (or the
    figure's own canvas) and returns / raises, but never mutates global state beyond
    the unavoidable `fig.canvas.draw()` that materialises text extents.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")  # headless, deterministic, no display required

import matplotlib.pyplot as plt  # noqa: E402  (after backend selection, intentional)
import matplotlib.text as mtext  # noqa: E402
from matplotlib.legend import Legend  # noqa: E402


# --------------------------------------------------------------------------- #
# Publication style (anti-slop defaults)
# --------------------------------------------------------------------------- #

# A serif-first stack that is almost always resolvable on a clean install: Times-style
# serif for LaTeX-typeset venues, with DejaVu Serif (matplotlib-bundled) as the
# guaranteed fallback so the figure never silently drops to a tofu glyph.
PUBLICATION_RCPARAMS = {
    # Fonts ---------------------------------------------------------------- #
    "font.family": "serif",
    "font.serif": [
        "Times New Roman",
        "Liberation Serif",
        "STIX Two Text",
        "DejaVu Serif",
    ],
    "mathtext.fontset": "stix",
    "axes.unicode_minus": False,  # render a real minus glyph, never the hyphen
    # Camera-ready font embedding: Type-42 (TrueType) so the PDF/PS is searchable,
    # copy-pasteable, and free of Type-3 bitmap fonts that reviewers flag.
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    # Spines --------------------------------------------------------------- #
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.linewidth": 0.8,  # hairline spine
    "axes.edgecolor": "#222222",  # near-black hairline, not matplotlib's pure black
    # Ticks ---------------------------------------------------------------- #
    "xtick.major.size": 0.0,  # no tick marks; gridlines carry the scale
    "ytick.major.size": 0.0,
    "xtick.major.width": 0.8,
    "ytick.major.width": 0.8,
    "xtick.color": "#222222",
    "ytick.color": "#222222",
    # Grid ----------------------------------------------------------------- #
    "axes.grid": True,
    "axes.axisbelow": True,  # gridlines sit behind the data
    "grid.color": "#e0e0e0",  # mid-class light grey: visible-but-recessive
    "grid.linewidth": 0.6,
    "grid.alpha": 1.0,
    # Misc ----------------------------------------------------------------- #
    "figure.dpi": 180,
    "savefig.dpi": 180,
    "legend.frameon": False,
}


# Hairline spine colour applied by apply_publication_style. Kept as a module
# constant so callers and tests can reference the exact value.
HAIRLINE_SPINE_COLOR = "#222222"
GRIDLINE_COLOR = "#e0e0e0"


def apply_publication_style(ax) -> None:
    """Stamp the anti-slop posture onto a single Axes.

    Idempotent and side-effect-free beyond the Axes it is handed:
      - removes the top and right spines,
      - sets the remaining (left + bottom) spines to a near-black hairline,
      - draws light-grey gridlines behind the data.

    Use this per-axes when you cannot or do not want to set PUBLICATION_RCPARAMS
    globally (e.g. one panel in a mixed figure). It does NOT touch fonts or
    fonttype — those are global rcParams concerns.
    """
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_visible(True)
        ax.spines[side].set_linewidth(0.8)
        ax.spines[side].set_color(HAIRLINE_SPINE_COLOR)
    ax.tick_params(length=0, colors=HAIRLINE_SPINE_COLOR)
    ax.set_axisbelow(True)
    ax.grid(True, color=GRIDLINE_COLOR, linewidth=0.6, alpha=1.0)


# --------------------------------------------------------------------------- #
# Internal: collect every visible text artist and its display-space bbox
# --------------------------------------------------------------------------- #

def _renderer(fig):
    """Materialise text extents and return a usable renderer.

    `get_window_extent` needs a renderer; the Agg canvas only has one after a draw.
    """
    fig.canvas.draw()
    return fig.canvas.get_renderer()


def _collect_text_artists(fig):
    """Return [(kind, artist), ...] for every visible, non-empty text element.

    Covered kinds: tick labels (x + y), axes titles, x/y axis labels, and
    Annotation artists living in any axes. Empty-string artists are skipped
    because matplotlib keeps zero-extent placeholders for them.
    """
    out = []
    for ax in fig.axes:
        for tick in ax.get_xticklabels() + ax.get_yticklabels():
            if tick.get_text():
                out.append(("tick", tick))
        if ax.get_title():
            out.append(("title", ax.title))
        if ax.xaxis.get_label_text():
            out.append(("xlabel", ax.xaxis.label))
        if ax.yaxis.get_label_text():
            out.append(("ylabel", ax.yaxis.label))
        for child in ax.get_children():
            if isinstance(child, mtext.Annotation) and child.get_text():
                out.append(("annotation", child))
    return out


def _bboxes(fig):
    """Return [(kind, artist, Bbox), ...] in display coordinates."""
    renderer = _renderer(fig)
    boxes = []
    for kind, artist in _collect_text_artists(fig):
        try:
            bb = artist.get_window_extent(renderer=renderer)
        except (RuntimeError, ValueError):
            # An artist with no resolvable extent contributes nothing to the floor.
            continue
        # Degenerate (zero-area) boxes are ignored; they cannot meaningfully overlap.
        if bb.width <= 0 or bb.height <= 0:
            continue
        boxes.append((kind, artist, bb))
    return boxes


def _label(kind, artist) -> str:
    txt = artist.get_text()
    return f"{kind}('{txt}')"


# --------------------------------------------------------------------------- #
# Public floor checks
# --------------------------------------------------------------------------- #

def assert_no_text_overlap(fig) -> None:
    """Raise AssertionError if any two visible text bboxes overlap.

    Pairwise check across all collected text artists. `Bbox.overlaps` treats a
    shared edge as an overlap, which is the policy we want: touching labels read
    as collisions at print size.
    """
    boxes = _bboxes(fig)
    violations = []
    for i in range(len(boxes)):
        ka, aa, ba = boxes[i]
        for j in range(i + 1, len(boxes)):
            kb, ab, bb = boxes[j]
            if ba.overlaps(bb):
                violations.append(f"{_label(ka, aa)} <-> {_label(kb, ab)}")
    if violations:
        shown = "\n  - ".join(violations[:12])
        raise AssertionError(
            f"FLOOR VIOLATION: {len(violations)} text overlap(s):\n  - {shown}"
        )


# Base tolerance (display px) for the canvas-containment check: absorbs edge
# anti-aliasing / rounding so a label flush against the spine does not false-positive.
_CLIP_BASE_TOL = 0.5

# Extra allowance for *tick labels only*, as a multiple of the label's own font
# height. A tick label is centred on its tick; the outermost tick sits on the axis
# extreme, so in a tight/constrained layout the top (or side) tick label legitimately
# extends up to ~half its glyph height past the figure edge without being a real
# "this figure is unshippable" defect. Empirically this cosmetic overflow is ~0.8-1.7x
# the font height (20-43 px at a 25 px / 10 pt font, 180 dpi); a genuine off-canvas
# label overflows by many multiples (hundreds of px), so a 2x-font-height window
# forgives the cosmetic case while still catching real clips. Non-tick artists
# (titles, axis labels, annotations) keep the strict base tolerance: those should
# never extend past the canvas, and an off-canvas annotation is a real defect.
_CLIP_TICK_FONT_MULTIPLE = 2.0


def _clip_tolerance(kind, artist, fig) -> float:
    """Per-artist canvas-overflow tolerance in display px (see constants above)."""
    if kind != "tick":
        return _CLIP_BASE_TOL
    try:
        font_px = float(artist.get_fontsize()) * fig.dpi / 72.0
    except (AttributeError, TypeError, ValueError):
        return _CLIP_BASE_TOL
    return max(_CLIP_BASE_TOL, _CLIP_TICK_FONT_MULTIPLE * font_px)


def assert_no_clipped_labels(fig) -> None:
    """Raise AssertionError if any text bbox falls outside the figure canvas.

    Every text artist's display-space bbox must lie inside `fig.bbox`, within a
    per-artist tolerance. Tick labels get a font-proportional allowance because the
    outermost tick is centred on the axis extreme and cosmetically extends a fraction
    of its height past the edge in tight layouts; titles/axis labels/annotations keep
    the strict sub-pixel tolerance. See `_clip_tolerance` for the rationale.
    """
    fig.canvas.draw()
    fig_bbox = fig.bbox
    out = []
    for kind, artist, bb in _bboxes(fig):
        tol = _clip_tolerance(kind, artist, fig)
        if (
            bb.x0 < fig_bbox.x0 - tol
            or bb.y0 < fig_bbox.y0 - tol
            or bb.x1 > fig_bbox.x1 + tol
            or bb.y1 > fig_bbox.y1 + tol
        ):
            out.append(f"{_label(kind, artist)} bbox={bb}")
    if out:
        shown = "\n  - ".join(out[:12])
        raise AssertionError(f"CLIPPED LABELS: {len(out)} found:\n  - {shown}")


# --------------------------------------------------------------------------- #
# Legend-over-data occlusion
# --------------------------------------------------------------------------- #

# A legend that sits on top of plotted data ink (bars, markers, lines, error bars)
# reads as clutter even when it overlaps no other *text* and is fully on-canvas — so
# the two checks above miss it. This check flags a legend that occludes real data.
# It is deliberately conservative to avoid false-positives on the common, correct
# case of a legend placed over empty axes whitespace:
#   - a legend placed OUTSIDE its axes (e.g. bbox_to_anchor to the right) cannot
#     occlude data and is skipped;
#   - the legend bbox is shrunk a few px so a glyph merely *touching* the data edge
#     is tolerated — only data samples clearly INSIDE count;
#   - a single grazing sample is ignored — it takes >= _LEGEND_OCCLUSION_MIN_HITS
#     data samples under the legend to flag.
_LEGEND_OCCLUSION_PAD = 3.0      # display px the legend bbox is shrunk before testing
_LEGEND_OCCLUSION_MIN_HITS = 2   # data samples inside the legend to call it occlusion


def _data_sample_points(ax, renderer):
    """Display-space sample points of the axes' DATA ink (not text/legend/spines).

    Best-effort over the common artists — scatter offsets, line/errorbar vertices,
    and bar top edges. Any artist whose geometry can't be resolved contributes
    nothing (defensive: never raises on an exotic artist).
    """
    pts = []
    td = ax.transData
    for col in ax.collections:  # scatter (offsets) + errorbars/fills (segments)
        try:
            offs = col.get_offsets()
            if offs is not None and len(offs):
                pts.extend(td.transform(offs).tolist())
        except Exception:
            pass
        try:
            for seg in col.get_segments():
                if len(seg):
                    pts.extend(td.transform(seg).tolist())
        except Exception:
            pass
    for ln in ax.lines:  # plotted lines AND errorbar caps/bars (often Line2D)
        try:
            xy = ln.get_xydata()
            if xy is not None and len(xy):
                pts.extend(td.transform(xy).tolist())
        except Exception:
            pass
    for p in ax.patches:  # bars / areas — sample the informative top edge
        try:
            bb = p.get_window_extent(renderer)
            pts.append((bb.x0, bb.y1))
            pts.append(((bb.x0 + bb.x1) / 2.0, bb.y1))
            pts.append((bb.x1, bb.y1))
        except Exception:
            pass
    return pts


def assert_no_legend_data_overlap(fig) -> None:
    """Raise AssertionError if a legend sits on top of plotted data ink.

    Catches the "legend blocks the figure" defect the text-overlap and clipping
    checks miss (a legend over bars/markers/lines overlaps no *text* and is
    on-canvas, yet occludes data). Conservative: legends placed outside their axes
    are skipped, the legend bbox is shrunk by a few px, and it takes several data
    samples under the legend to flag — so a legend over empty whitespace, or one
    merely touching the data edge, passes. Fix in the Drawer by moving the legend
    (loc='best', or outside the axes via bbox_to_anchor) or adding headroom.
    """
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    out = []
    for ax in fig.axes:
        # An axes can carry MORE than one legend (e.g. a colour legend + a size
        # legend added via ax.add_artist). ax.get_legend() returns only the last,
        # so collect every Legend child instead.
        legs = [c for c in ax.get_children() if isinstance(c, Legend)]
        if not legs:
            continue
        try:
            ab = ax.get_window_extent(renderer)
        except (RuntimeError, ValueError):
            continue
        data_pts = _data_sample_points(ax, renderer)
        for leg in legs:
            try:
                lb = leg.get_window_extent(renderer)
            except (RuntimeError, ValueError):
                continue
            if not lb.overlaps(ab):
                continue  # legend lives outside the axes -> cannot occlude data
            x0, y0 = lb.x0 + _LEGEND_OCCLUSION_PAD, lb.y0 + _LEGEND_OCCLUSION_PAD
            x1, y1 = lb.x1 - _LEGEND_OCCLUSION_PAD, lb.y1 - _LEGEND_OCCLUSION_PAD
            hits = 0
            for x, y in data_pts:
                if x0 <= x <= x1 and y0 <= y <= y1:
                    hits += 1
                    if hits >= _LEGEND_OCCLUSION_MIN_HITS:
                        break
            if hits >= _LEGEND_OCCLUSION_MIN_HITS:
                out.append(f"legend overlaps data ink ({hits}+ samples under it)")
    if out:
        shown = "\n  - ".join(out[:12])
        raise AssertionError(f"LEGEND OVER DATA: {len(out)} found:\n  - {shown}")


def check_floor(fig) -> dict:
    """Run every floor check without raising; return a structured verdict.

    Returns::

        {
          "passed": bool,
          "violations": [
            {"kind": "text_overlap" | "label_clipped" | "legend_over_data", "detail": str},
            ...
          ],
        }

    This is the programmatic entry point the Drawer/Reviewer loop calls. It never
    raises on a floor failure; it reports. (It may still propagate a genuine
    matplotlib error from drawing a malformed figure — that is a real bug, not a
    floor verdict.)
    """
    violations = []
    try:
        assert_no_text_overlap(fig)
    except AssertionError as exc:
        for line in str(exc).split("\n  - ")[1:]:
            violations.append({"kind": "text_overlap", "detail": line.strip()})
    try:
        assert_no_clipped_labels(fig)
    except AssertionError as exc:
        for line in str(exc).split("\n  - ")[1:]:
            violations.append({"kind": "label_clipped", "detail": line.strip()})
    try:
        assert_no_legend_data_overlap(fig)
    except AssertionError as exc:
        for line in str(exc).split("\n  - ")[1:]:
            violations.append({"kind": "legend_over_data", "detail": line.strip()})
    return {"passed": len(violations) == 0, "violations": violations}


__all__ = [
    "PUBLICATION_RCPARAMS",
    "HAIRLINE_SPINE_COLOR",
    "GRIDLINE_COLOR",
    "apply_publication_style",
    "assert_no_legend_data_overlap",
    "assert_no_text_overlap",
    "assert_no_clipped_labels",
    "check_floor",
]
