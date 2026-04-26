"""RED phase test for plot_ops.py - Task 1 TDD."""

import sys
from pathlib import Path

# Add scripts dir to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".claude" / "skills" / "sci-data-analysis" / "scripts"))

from plot_ops import (
    PLOT_TYPES,
    DEFAULT_STYLE,
    generate_static_plot,
    generate_interactive_plot,
    generate_dual_plot,
    save_publication_plot,
)


def test_plot_types_has_six_entries():
    assert len(PLOT_TYPES) == 6
    for key in ["scatter", "bar", "line", "heatmap", "box", "violin"]:
        assert key in PLOT_TYPES


def test_default_style():
    assert DEFAULT_STYLE == ["science", "no-latex"]
