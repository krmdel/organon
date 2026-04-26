"""Tests for plot_ops.py visualization module.

Covers all 6 static plot types, SVG/PNG content verification, style override,
interactive HTML output, dual plot generation, and reproducibility logging.
"""

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

# Add scripts dir to path
sys.path.insert(
    0,
    str(
        Path(__file__).resolve().parent.parent
        / ".claude"
        / "skills"
        / "sci-data-analysis"
        / "scripts"
    ),
)

from plot_ops import (
    DEFAULT_STYLE,
    PLOT_TYPES,
    generate_dual_plot,
    generate_interactive_plot,
    generate_static_plot,
    save_publication_plot,
)


@pytest.fixture
def sample_df():
    """Load the sample test data."""
    csv_path = Path(__file__).parent / "fixtures" / "sample_data.csv"
    return pd.read_csv(csv_path)


# --- PLOT_TYPES dict ---


def test_plot_types_dict():
    """PLOT_TYPES has exactly 6 entries with the expected keys."""
    assert len(PLOT_TYPES) == 6
    expected = {"scatter", "bar", "line", "heatmap", "box", "violin"}
    assert set(PLOT_TYPES.keys()) == expected


# --- Static plot tests for each type ---


def test_static_scatter(sample_df, tmp_path, tmp_repro_dir):
    """Scatter plot generates .png, .svg, .pdf files."""
    base = str(tmp_path / "scatter_test")
    paths = generate_static_plot(sample_df, "scatter", "value1", "value2", base_path=base)
    assert len(paths) == 3
    assert any(p.endswith(".png") for p in paths)
    assert any(p.endswith(".svg") for p in paths)
    assert any(p.endswith(".pdf") for p in paths)
    for p in paths:
        assert Path(p).exists()
        assert Path(p).stat().st_size > 0


def test_static_bar(sample_df, tmp_path, tmp_repro_dir):
    """Bar plot generates output files."""
    base = str(tmp_path / "bar_test")
    paths = generate_static_plot(sample_df, "bar", "group", "value1", base_path=base)
    assert len(paths) == 3
    for p in paths:
        assert Path(p).exists()


def test_static_line(sample_df, tmp_path, tmp_repro_dir):
    """Line plot generates output files."""
    base = str(tmp_path / "line_test")
    paths = generate_static_plot(sample_df, "line", "value1", "value2", base_path=base)
    assert len(paths) == 3
    for p in paths:
        assert Path(p).exists()


def test_static_heatmap(sample_df, tmp_path, tmp_repro_dir):
    """Heatmap generates output files."""
    base = str(tmp_path / "heatmap_test")
    paths = generate_static_plot(sample_df, "heatmap", "value1", base_path=base)
    assert len(paths) == 3
    for p in paths:
        assert Path(p).exists()


def test_static_box(sample_df, tmp_path, tmp_repro_dir):
    """Box plot generates output files."""
    base = str(tmp_path / "box_test")
    paths = generate_static_plot(sample_df, "box", "group", "value1", base_path=base)
    assert len(paths) == 3
    for p in paths:
        assert Path(p).exists()


def test_static_violin(sample_df, tmp_path, tmp_repro_dir):
    """Violin plot generates output files."""
    base = str(tmp_path / "violin_test")
    paths = generate_static_plot(sample_df, "violin", "group", "value1", base_path=base)
    assert len(paths) == 3
    for p in paths:
        assert Path(p).exists()


# --- Content verification ---


def test_static_png_dpi(sample_df, tmp_path, tmp_repro_dir):
    """PNG file is non-trivial size (> 10KB) indicating real 300dpi output."""
    base = str(tmp_path / "dpi_test")
    paths = generate_static_plot(sample_df, "scatter", "value1", "value2", base_path=base)
    png_path = [p for p in paths if p.endswith(".png")][0]
    assert Path(png_path).stat().st_size > 10_000


def test_static_svg_content(sample_df, tmp_path, tmp_repro_dir):
    """SVG file contains valid SVG markup."""
    base = str(tmp_path / "svg_test")
    paths = generate_static_plot(sample_df, "scatter", "value1", "value2", base_path=base)
    svg_path = [p for p in paths if p.endswith(".svg")][0]
    content = Path(svg_path).read_text()
    assert "<svg" in content


# --- Style override ---


def test_style_override(sample_df, tmp_path, tmp_repro_dir):
    """Style override with 'ieee' completes without error."""
    base = str(tmp_path / "style_test")
    paths = generate_static_plot(
        sample_df, "scatter", "value1", "value2", base_path=base, style="ieee"
    )
    assert len(paths) == 3
    for p in paths:
        assert Path(p).exists()


# --- Interactive plots ---


def test_interactive_scatter(sample_df, tmp_path, tmp_repro_dir):
    """Interactive scatter produces .html file with plotly content."""
    base = str(tmp_path / "interactive_scatter")
    html_path = generate_interactive_plot(
        sample_df, "scatter", "value1", "value2", base_path=base
    )
    assert html_path.endswith(".html")
    assert Path(html_path).exists()
    content = Path(html_path).read_text()
    assert "plotly" in content.lower()


def test_interactive_heatmap(sample_df, tmp_path, tmp_repro_dir):
    """Interactive heatmap produces .html file."""
    base = str(tmp_path / "interactive_heatmap")
    html_path = generate_interactive_plot(
        sample_df, "heatmap", "value1", base_path=base
    )
    assert html_path.endswith(".html")
    assert Path(html_path).exists()


# --- Dual plot ---


def test_dual_plot(sample_df, tmp_path, tmp_repro_dir):
    """generate_dual_plot returns dict with 'static' list and 'interactive' string."""
    base = str(tmp_path / "dual_test")
    result = generate_dual_plot(
        sample_df, "scatter", "value1", "value2", base_path=base
    )
    assert isinstance(result, dict)
    assert "static" in result
    assert "interactive" in result
    assert isinstance(result["static"], list)
    assert len(result["static"]) == 3
    assert isinstance(result["interactive"], str)
    assert result["interactive"].endswith(".html")


# --- Reproducibility logging ---


def test_repro_logging(sample_df, tmp_path, tmp_repro_dir):
    """After generate_static_plot, ledger has an entry with correct skill."""
    base = str(tmp_path / "repro_test")
    generate_static_plot(sample_df, "scatter", "value1", "value2", base_path=base)

    ledger_path = tmp_repro_dir / "ledger.jsonl"
    assert ledger_path.exists()
    entries = [json.loads(line) for line in ledger_path.read_text().strip().split("\n")]
    assert len(entries) >= 1
    last_entry = entries[-1]
    assert last_entry["skill"] == "sci-data-analysis"
    assert last_entry["operation"] == "plot"
    assert "plot_type" in last_entry["params"]
