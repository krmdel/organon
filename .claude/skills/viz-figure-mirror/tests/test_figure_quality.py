"""Real pytest coverage for the quality-floor module.

No network, no vision model. Builds small matplotlib figures and asserts the floor
passes a clean figure and catches deliberately-broken ones.
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pytest

# Make scripts/ importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from figure_quality import (  # noqa: E402
    PUBLICATION_RCPARAMS,
    apply_publication_style,
    assert_no_clipped_labels,
    assert_no_legend_data_overlap,
    assert_no_text_overlap,
    check_floor,
)


def _kinds(fig):
    return [v["kind"] for v in check_floor(fig)["violations"]]


@pytest.fixture(autouse=True)
def _close_all_figures():
    yield
    plt.close("all")


def _clean_figure():
    """A comfortably-spaced figure that should clear the floor."""
    fig, ax = plt.subplots(figsize=(5.0, 3.2))
    x = [1, 2, 4, 8, 16]
    ax.plot(x, [0.10, 0.25, 0.42, 0.60, 0.80], marker="o")
    ax.set_xticks(x)
    ax.set_xlabel("epsilon")
    ax.set_ylabel("accuracy")
    ax.set_title("clean")
    apply_publication_style(ax)
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------- #
# Clean figure passes
# --------------------------------------------------------------------------- #

def test_clean_figure_check_floor_passes():
    fig = _clean_figure()
    result = check_floor(fig)
    assert result["passed"] is True
    assert result["violations"] == []


def test_clean_figure_assertions_do_not_raise():
    fig = _clean_figure()
    assert_no_text_overlap(fig)  # must not raise
    assert_no_clipped_labels(fig)  # must not raise


def test_publication_rcparams_are_anti_slop():
    # Sanity on the curated convention values the skill ships.
    assert PUBLICATION_RCPARAMS["pdf.fonttype"] == 42
    assert PUBLICATION_RCPARAMS["ps.fonttype"] == 42
    assert PUBLICATION_RCPARAMS["axes.unicode_minus"] is False
    assert PUBLICATION_RCPARAMS["axes.spines.top"] is False
    assert PUBLICATION_RCPARAMS["axes.spines.right"] is False
    assert PUBLICATION_RCPARAMS["axes.axisbelow"] is True
    # Gridline colour is a light grey in the visible-but-recessive band.
    assert PUBLICATION_RCPARAMS["grid.color"] == "#e0e0e0"


def test_apply_publication_style_removes_top_right_spines():
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    apply_publication_style(ax)
    assert ax.spines["top"].get_visible() is False
    assert ax.spines["right"].get_visible() is False
    assert ax.spines["left"].get_visible() is True
    assert ax.spines["bottom"].get_visible() is True


# --------------------------------------------------------------------------- #
# Overlapping text is caught
# --------------------------------------------------------------------------- #

def test_overlapping_tick_labels_are_caught():
    # Huge tick font on a small axis forces neighbouring tick labels to collide.
    fig, ax = plt.subplots(figsize=(2.0, 2.0))
    ax.plot(range(10), range(10))
    ax.set_xticks(range(10))
    ax.set_xticklabels([f"label_{i}" for i in range(10)], fontsize=40)

    with pytest.raises(AssertionError, match="FLOOR VIOLATION"):
        assert_no_text_overlap(fig)

    result = check_floor(fig)
    assert result["passed"] is False
    assert any(v["kind"] == "text_overlap" for v in result["violations"])


def test_overlapping_annotations_are_caught():
    # Two big annotations placed at the same point overlap by construction.
    fig, ax = plt.subplots(figsize=(4.0, 4.0))
    ax.plot([0, 1], [0, 1])
    ax.annotate("AAAAAAAA", xy=(0.5, 0.5), fontsize=30, ha="center", va="center")
    ax.annotate("BBBBBBBB", xy=(0.5, 0.5), fontsize=30, ha="center", va="center")
    with pytest.raises(AssertionError, match="FLOOR VIOLATION"):
        assert_no_text_overlap(fig)


# --------------------------------------------------------------------------- #
# Clipped (off-canvas) text is caught
# --------------------------------------------------------------------------- #

def test_offcanvas_annotation_is_caught():
    # Place an annotation far outside the axes / canvas in display space.
    fig, ax = plt.subplots(figsize=(3.0, 3.0))
    ax.plot([0, 1], [0, 1])
    # xytext in figure fraction well beyond the canvas (>1.0) -> clipped.
    ax.annotate(
        "off the canvas",
        xy=(0.5, 0.5),
        xytext=(1.8, 1.8),
        textcoords="figure fraction",
        fontsize=14,
    )
    with pytest.raises(AssertionError, match="CLIPPED LABELS"):
        assert_no_clipped_labels(fig)

    result = check_floor(fig)
    assert result["passed"] is False
    assert any(v["kind"] == "label_clipped" for v in result["violations"])


def test_data_at_top_ytick_does_not_false_positive():
    # Regression for C1: a figure whose data reaches the top y-tick under the
    # publication rcParams + a tight layout used to fail the clip check because the
    # outermost (top) y-tick label is centred on the axis extreme and extends a
    # fraction of its glyph height past the canvas (~20-43 px). That is cosmetic, not
    # a real clip, and must NOT burn a Drawer iteration. The font-proportional
    # tick-label tolerance absorbs it.
    with plt.rc_context(PUBLICATION_RCPARAMS):
        fig, ax = plt.subplots(figsize=(5.0, 3.2))
        x = [1, 2, 3, 4, 5]
        ax.plot(x, [0.3, 0.5, 0.6, 0.8, 1.0], marker="o")  # data max == top tick
        ax.set_xticks(x)
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        apply_publication_style(ax)
        fig.tight_layout()
    result = check_floor(fig)
    assert result["passed"] is True, result["violations"]
    assert_no_clipped_labels(fig)  # must not raise

    # Same pattern under constrained_layout (the worse cosmetic-overflow case).
    with plt.rc_context(PUBLICATION_RCPARAMS):
        fig2, ax2 = plt.subplots(figsize=(5.0, 3.2), layout="constrained")
        ax2.plot(x, [0.3, 0.5, 0.6, 0.8, 1.0], marker="o")
        ax2.set_xticks(x)
        ax2.set_xlabel("x")
        ax2.set_ylabel("y")
        apply_publication_style(ax2)
    assert check_floor(fig2)["passed"] is True


def test_grossly_offcanvas_tick_label_is_still_caught():
    # The tick-label tolerance is font-proportional (~2x glyph height), NOT a blanket
    # pass: a tick label dragged far off the canvas (many multiples of its height)
    # must still register as clipped, so the tolerance cannot be exploited to hide a
    # real layout failure.
    fig, ax = plt.subplots(figsize=(3.0, 3.0))
    ax.plot([0, 1], [0, 1])
    ax.set_yticks([0.5])
    # A very long tick label on a small axis overflows horizontally by >> its height.
    ax.set_yticklabels(["X" * 60])
    with pytest.raises(AssertionError, match="CLIPPED LABELS"):
        assert_no_clipped_labels(fig)


# --------------------------------------------------------------------------- #
# Legend-over-data occlusion is caught (and whitespace legends are NOT)
# --------------------------------------------------------------------------- #

def _upper_left_cluster():
    import numpy as np
    np.random.seed(1)
    return np.random.uniform(0, 3, 40), np.random.uniform(7, 10, 40)


def test_legend_over_data_is_caught():
    # Data clustered upper-left + a legend placed upper-left ON the points.
    x, y = _upper_left_cluster()
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.scatter(x, y, s=120, label="A")
    ax.scatter(x + 0.2, y - 0.2, s=120, label="B")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.legend(loc="upper left")
    with pytest.raises(AssertionError, match="LEGEND OVER DATA"):
        assert_no_legend_data_overlap(fig)
    assert "legend_over_data" in _kinds(fig)


def test_legend_outside_axes_does_not_false_positive():
    # Same data, but the legend is anchored OUTSIDE the axes (to the right).
    x, y = _upper_left_cluster()
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.scatter(x, y, s=120, label="A")
    ax.scatter(x + 0.2, y - 0.2, s=120, label="B")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1))
    assert_no_legend_data_overlap(fig)  # must not raise
    assert "legend_over_data" not in _kinds(fig)


def test_legend_over_whitespace_does_not_false_positive():
    # Data lives lower-right; legend sits upper-left over empty axes space.
    import numpy as np
    np.random.seed(2)
    xr, yr = np.random.uniform(6, 10, 40), np.random.uniform(0, 3, 40)
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.scatter(xr, yr, s=120, label="A")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.legend(loc="upper left")
    assert_no_legend_data_overlap(fig)  # must not raise
    assert "legend_over_data" not in _kinds(fig)


def test_tall_bars_under_top_legend_are_caught():
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.bar(["a", "b", "c"], [95, 93, 96], label="series")
    ax.set_ylim(0, 100)
    ax.legend(loc="upper left")
    assert "legend_over_data" in _kinds(fig)


def test_second_legend_over_data_is_caught():
    # ax.get_legend() returns only the LAST legend; the check must inspect ALL
    # Legend artists, so a colour legend placed over data (added via add_artist)
    # while a second size legend sits elsewhere is still caught.
    x, y = _upper_left_cluster()
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.scatter(x, y, s=120, label="A")
    leg1 = ax.legend(loc="upper left", title="type")  # over the data
    ax.add_artist(leg1)
    ax.legend(loc="lower right", title="size")          # the "current" legend
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    assert "legend_over_data" in _kinds(fig)


def test_check_floor_aggregates_multiple_violation_kinds():
    fig, ax = plt.subplots(figsize=(2.0, 2.0))
    ax.plot(range(6), range(6))
    ax.set_xticks(range(6))
    ax.set_xticklabels([f"tick_{i}" for i in range(6)], fontsize=36)  # overlap
    ax.annotate(
        "way off",
        xy=(1, 1),
        xytext=(2.0, 2.0),
        textcoords="figure fraction",
        fontsize=14,
    )  # clipped
    result = check_floor(fig)
    assert result["passed"] is False
    kinds = {v["kind"] for v in result["violations"]}
    assert "text_overlap" in kinds
    assert "label_clipped" in kinds
