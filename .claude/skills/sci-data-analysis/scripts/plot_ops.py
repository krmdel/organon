"""Plot generation module for Scientific OS.

Generates publication-quality static plots (Matplotlib + SciencePlots) and
interactive charts (Plotly) with dual output for every plot request.

Per VIZ-01: Publication-quality figures via SciencePlots styles.
Per VIZ-03: Interactive Plotly HTML with zoom, hover, filter.
Per VIZ-04: Multi-format export (PNG 300dpi + SVG + PDF).
Per VIZ-05: Journal-specific style presets (nature, ieee, etc.).
Per D-13: Save order SVG -> PDF -> PNG (Pitfall 5).
Per Pitfall 3: Always close figures after saving.
"""

import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')  # Headless backend for CLI - never call plt.show()

import matplotlib.pyplot as plt
import scienceplots  # noqa: F401 — registers styles on import
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go  # noqa: F401 — available for advanced plots
import pandas as pd
import numpy as np  # noqa: F401 — available for data manipulation

# Add project root to sys.path for repro_logger import
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from repro.repro_logger import log_operation


PLOT_TYPES = {
    "scatter": "Scatter plot for continuous x vs y relationships",
    "bar": "Bar chart for categorical comparisons",
    "line": "Line plot for trends over continuous/time axis",
    "heatmap": "Heatmap for correlation matrices or 2D data",
    "box": "Box plot for distribution comparison across groups",
    "violin": "Violin plot for distribution shape comparison",
}

DEFAULT_STYLE = ['science', 'no-latex']


def save_publication_plot(fig, base_path: str, dpi: int = 300) -> list[str]:
    """Save a matplotlib figure in publication formats.

    Save order: SVG first, then PDF, then PNG (per Pitfall 5 — rasterization
    artifacts if PNG is saved before vector formats).

    Args:
        fig: Matplotlib figure object.
        base_path: Base file path without extension.
        dpi: Resolution for PNG output (default 300).

    Returns:
        List of saved file paths.
    """
    base = Path(base_path)
    base.parent.mkdir(parents=True, exist_ok=True)
    saved = []

    # SVG first (Pitfall 5)
    svg_path = f"{base_path}.svg"
    fig.savefig(svg_path, format='svg', bbox_inches='tight')
    saved.append(svg_path)

    # PDF second
    pdf_path = f"{base_path}.pdf"
    fig.savefig(pdf_path, format='pdf', bbox_inches='tight')
    saved.append(pdf_path)

    # PNG last at specified DPI
    png_path = f"{base_path}.png"
    fig.savefig(png_path, format='png', dpi=dpi, bbox_inches='tight')
    saved.append(png_path)

    # Close figure to prevent memory leak (Pitfall 3)
    plt.close(fig)

    return saved


def generate_static_plot(
    df: pd.DataFrame,
    plot_type: str,
    x_col: str,
    y_col: str = None,
    base_path: str = None,
    style: str = None,
    title: str = None,
    xlabel: str = None,
    ylabel: str = None,
    hue_col: str = None,
) -> list[str]:
    """Generate a publication-quality static plot.

    Uses SciencePlots styles with optional journal-specific overrides.
    Saves as SVG + PDF + PNG 300dpi.

    Args:
        df: Input DataFrame.
        plot_type: One of PLOT_TYPES keys.
        x_col: Column name for x-axis.
        y_col: Column name for y-axis (optional for some plot types).
        base_path: Base file path without extension for output.
        style: Optional style override (e.g., 'nature', 'ieee').
        title: Plot title.
        xlabel: X-axis label.
        ylabel: Y-axis label.
        hue_col: Column for color grouping.

    Returns:
        List of saved file paths.
    """
    if plot_type not in PLOT_TYPES:
        raise ValueError(f"Unknown plot type '{plot_type}'. Choose from: {list(PLOT_TYPES.keys())}")

    if base_path is None:
        base_path = f"plot_{plot_type}"

    # Build style list
    if style:
        style_list = ['science', style, 'no-latex']
    else:
        style_list = list(DEFAULT_STYLE)

    with plt.style.context(style_list):
        fig, ax = plt.subplots(figsize=(6, 4))

        if plot_type == "scatter":
            if hue_col:
                sns.scatterplot(data=df, x=x_col, y=y_col, hue=hue_col, ax=ax)
            else:
                ax.scatter(df[x_col], df[y_col])

        elif plot_type == "bar":
            if y_col:
                sns.barplot(data=df, x=x_col, y=y_col, ax=ax)
            else:
                df[x_col].value_counts().plot.bar(ax=ax)

        elif plot_type == "line":
            if hue_col:
                sns.lineplot(data=df, x=x_col, y=y_col, hue=hue_col, ax=ax)
            else:
                ax.plot(df[x_col], df[y_col])

        elif plot_type == "heatmap":
            numeric_df = df.select_dtypes(include='number')
            sns.heatmap(numeric_df.corr(), annot=True, fmt='.2f', ax=ax)

        elif plot_type == "box":
            sns.boxplot(data=df, x=x_col, y=y_col, ax=ax)

        elif plot_type == "violin":
            sns.violinplot(data=df, x=x_col, y=y_col, ax=ax)

        if title:
            ax.set_title(title)
        if xlabel:
            ax.set_xlabel(xlabel)
        if ylabel:
            ax.set_ylabel(ylabel)

        saved_paths = save_publication_plot(fig, base_path)

    # Log to reproducibility ledger
    log_operation(
        skill="sci-data-analysis",
        operation="plot",
        params={
            "plot_type": plot_type,
            "x_col": x_col,
            "y_col": y_col,
            "style": style or "science",
        },
        output_files=saved_paths,
    )

    return saved_paths


def generate_interactive_plot(
    df: pd.DataFrame,
    plot_type: str,
    x_col: str,
    y_col: str = None,
    base_path: str = None,
    title: str = None,
    hue_col: str = None,
) -> str:
    """Generate an interactive Plotly HTML chart.

    Produces a self-contained HTML file with zoom, hover, and filter.

    Args:
        df: Input DataFrame.
        plot_type: One of PLOT_TYPES keys.
        x_col: Column name for x-axis.
        y_col: Column name for y-axis (optional for some types).
        base_path: Base file path without extension for output.
        title: Chart title.
        hue_col: Column for color grouping.

    Returns:
        Path to the saved HTML file.
    """
    if plot_type not in PLOT_TYPES:
        raise ValueError(f"Unknown plot type '{plot_type}'. Choose from: {list(PLOT_TYPES.keys())}")

    if base_path is None:
        base_path = f"plot_{plot_type}"

    if plot_type == "scatter":
        fig = px.scatter(df, x=x_col, y=y_col, color=hue_col,
                         hover_data=df.columns.tolist(), title=title)

    elif plot_type == "bar":
        fig = px.bar(df, x=x_col, y=y_col, color=hue_col, title=title)

    elif plot_type == "line":
        fig = px.line(df, x=x_col, y=y_col, color=hue_col, title=title)

    elif plot_type == "heatmap":
        numeric_df = df.select_dtypes(include='number')
        fig = px.imshow(numeric_df.corr(), text_auto='.2f',
                        title=title or 'Correlation Heatmap')

    elif plot_type == "box":
        fig = px.box(df, x=x_col, y=y_col, color=hue_col, title=title)

    elif plot_type == "violin":
        fig = px.violin(df, x=x_col, y=y_col, color=hue_col, title=title)

    fig.update_layout(
        template='plotly_white',
        font=dict(family='serif', size=12),
        title_font_size=14,
    )

    html_path = f"{base_path}.html"
    Path(html_path).parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(html_path, include_plotlyjs=True)

    # Log to reproducibility ledger
    log_operation(
        skill="sci-data-analysis",
        operation="interactive_plot",
        params={
            "plot_type": plot_type,
            "x_col": x_col,
            "y_col": y_col,
        },
        output_files=[html_path],
    )

    return html_path


def generate_dual_plot(
    df: pd.DataFrame,
    plot_type: str,
    x_col: str,
    y_col: str = None,
    base_path: str = None,
    style: str = None,
    title: str = None,
    xlabel: str = None,
    ylabel: str = None,
    hue_col: str = None,
) -> dict:
    """Generate both static and interactive plots for the same data.

    Every plot request produces PNG 300dpi + SVG + PDF + interactive HTML.

    Args:
        df: Input DataFrame.
        plot_type: One of PLOT_TYPES keys.
        x_col: Column name for x-axis.
        y_col: Column name for y-axis (optional for some types).
        base_path: Base file path without extension for output.
        style: Optional style override (e.g., 'nature', 'ieee').
        title: Plot title.
        xlabel: X-axis label.
        ylabel: Y-axis label.
        hue_col: Column for color grouping.

    Returns:
        Dict with 'static' (list of file paths) and 'interactive' (HTML path).
    """
    static_paths = generate_static_plot(
        df, plot_type, x_col, y_col,
        base_path=base_path, style=style, title=title,
        xlabel=xlabel, ylabel=ylabel, hue_col=hue_col,
    )
    interactive_path = generate_interactive_plot(
        df, plot_type, x_col, y_col,
        base_path=base_path, title=title, hue_col=hue_col,
    )

    return {"static": static_paths, "interactive": interactive_path}
