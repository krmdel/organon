#!/usr/bin/env python3
"""End-to-end mechanical smoke test for viz-figure-mirror.

Builds a real figure, applies the publication style, runs the floor check, and
prints PASS / FAIL. Proves the quality-floor mechanics work headlessly without a
vision model, a network call, or any reference image.

Run::

    .venv/bin/python .claude/skills/viz-figure-mirror/scripts/smoke_test.py
"""

import sys
from pathlib import Path

# Make the sibling modules importable whether run as a script or from elsewhere.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from figure_quality import (  # noqa: E402
    PUBLICATION_RCPARAMS,
    apply_publication_style,
    check_floor,
)


def build_figure():
    """A small, clean, well-spaced 2-series line plot in publication style."""
    with plt.rc_context(PUBLICATION_RCPARAMS):
        fig, ax = plt.subplots(figsize=(5.0, 3.2))
        x = [1, 2, 4, 8, 16]
        ax.plot(x, [0.10, 0.22, 0.41, 0.63, 0.78], marker="o", label="method A")
        ax.plot(x, [0.08, 0.18, 0.35, 0.55, 0.70], marker="s", label="method B")
        ax.set_xlabel(r"$\varepsilon$")
        ax.set_ylabel("accuracy")
        ax.set_title("smoke-test figure")
        ax.set_xticks(x)
        ax.legend()
        apply_publication_style(ax)
        fig.tight_layout()
    return fig


def main() -> int:
    fig = build_figure()
    result = check_floor(fig)
    if result["passed"]:
        print("PASS: figure cleared the quality floor (no overlaps, no clipping).")
        return 0
    print("FAIL: floor violations detected:")
    for v in result["violations"]:
        print(f"  - [{v['kind']}] {v['detail']}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
