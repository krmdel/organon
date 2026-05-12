"""Phase 3 T26 — generates a plot from a dataframe + params and emits a
`_artifact: figure` JSON line on stdout.

Writes:
  <out_dir>/<fig_id>/v1.png
  <out_dir>/<fig_id>/v1.svg
  <out_dir>/<fig_id>/v1.thumb.png
  <out_dir>/<fig_id>/v1.py    -- self-contained reproducer

Usage:
    python generate_plot.py \\
      --path <abs csv/xlsx/json> --fig-id fig-YYYYMMDD-XXXXXX \\
      --project-slug <slug> --file-id <data-id> \\
      --out-dir <abs path to figures/<fig_id>/> \\
      --kind histogram \\
      --params '{"x_col":"age","bins":30,"log_scale":false,"group_col":null}' \\
      --library-path projects/{slug}/figures/<fig_id>/v1.png \\
      --code-path    projects/{slug}/figures/<fig_id>/v1.py \\
      --png-path     projects/{slug}/figures/<fig_id>/v1.png \\
      --svg-path     projects/{slug}/figures/<fig_id>/v1.svg \\
      --thumb-path   projects/{slug}/figures/<fig_id>/v1.thumb.png
"""

import argparse
import json
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")
warnings.filterwarnings("ignore", category=UserWarning, module="pandas")

THUMB_MAX_PX = 220


def _load(path: Path) -> pd.DataFrame:
    ext = path.suffix.lower()
    if ext == ".csv":
        return pd.read_csv(path)
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(path)
    if ext == ".json":
        return pd.read_json(path)
    raise ValueError(f"Unsupported format: {ext}")


def _save_thumb(src_png: Path, dest: Path) -> None:
    try:
        from PIL import Image  # type: ignore

        img = Image.open(src_png)
        img.thumbnail((THUMB_MAX_PX, THUMB_MAX_PX))
        img.save(dest)
    except Exception:
        # Pillow optional — fall back to copying the full PNG.
        dest.write_bytes(src_png.read_bytes())


# ---------------------------------------------------------------------------
# Plotters
# ---------------------------------------------------------------------------

def _plot_histogram(df: pd.DataFrame, p: dict, ax) -> None:
    x = df[p["x_col"]].dropna()
    bins = int(p.get("bins") or 30)
    if p.get("group_col"):
        for name, sub in df.groupby(p["group_col"]):
            ax.hist(sub[p["x_col"]].dropna(), bins=bins, alpha=0.55, label=str(name))
        ax.legend()
    else:
        ax.hist(x, bins=bins)
    if p.get("log_scale"):
        ax.set_yscale("log")
    ax.set_xlabel(p["x_col"])
    ax.set_ylabel("count")
    ax.set_title(f"Histogram of {p['x_col']}")


def _plot_scatter(df: pd.DataFrame, p: dict, ax) -> None:
    sub = df[[p["x_col"], p["y_col"]] + ([p["color_col"]] if p.get("color_col") else [])].dropna()
    if p.get("color_col"):
        cats = sub[p["color_col"]]
        if pd.api.types.is_numeric_dtype(cats):
            sc = ax.scatter(sub[p["x_col"]], sub[p["y_col"]], c=cats, cmap="viridis", alpha=0.7)
            plt.colorbar(sc, ax=ax, label=p["color_col"])
        else:
            for name, grp in sub.groupby(p["color_col"]):
                ax.scatter(grp[p["x_col"]], grp[p["y_col"]], alpha=0.7, label=str(name))
            ax.legend()
    else:
        ax.scatter(sub[p["x_col"]], sub[p["y_col"]], alpha=0.7)
    ax.set_xlabel(p["x_col"])
    ax.set_ylabel(p["y_col"])
    ax.set_title(f"{p['y_col']} vs {p['x_col']}")


def _plot_box(df: pd.DataFrame, p: dict, ax) -> None:
    if p.get("group_col"):
        groups = [grp[p["value_col"]].dropna().values for _, grp in df.groupby(p["group_col"])]
        labels = [str(name) for name, _ in df.groupby(p["group_col"])]
        ax.boxplot(groups, labels=labels)
        ax.set_xlabel(p["group_col"])
    else:
        ax.boxplot(df[p["value_col"]].dropna().values)
    ax.set_ylabel(p["value_col"])
    ax.set_title(f"{p['value_col']}")


def _plot_violin(df: pd.DataFrame, p: dict, ax) -> None:
    if p.get("group_col"):
        groups = [grp[p["value_col"]].dropna().values for _, grp in df.groupby(p["group_col"])]
        labels = [str(name) for name, _ in df.groupby(p["group_col"])]
        ax.violinplot(groups, showmeans=True)
        ax.set_xticks(np.arange(1, len(labels) + 1))
        ax.set_xticklabels(labels, rotation=20, ha="right")
        ax.set_xlabel(p["group_col"])
    else:
        ax.violinplot(df[p["value_col"]].dropna().values, showmeans=True)
    ax.set_ylabel(p["value_col"])
    ax.set_title(f"{p['value_col']}")


def _plot_heatmap(df: pd.DataFrame, p: dict, ax) -> None:
    feats = p.get("feature_cols")
    if not feats:
        feats = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    if len(feats) < 2:
        raise ValueError("heatmap needs ≥ 2 numeric columns")
    corr = df[feats].corr(numeric_only=True)
    im = ax.imshow(corr.values, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(np.arange(len(feats)))
    ax.set_yticks(np.arange(len(feats)))
    ax.set_xticklabels(feats, rotation=45, ha="right")
    ax.set_yticklabels(feats)
    for i in range(len(feats)):
        for j in range(len(feats)):
            ax.text(j, i, f"{corr.values[i, j]:.2f}", ha="center", va="center", color="k", fontsize=8)
    plt.colorbar(im, ax=ax, label="Pearson r")
    ax.set_title("Correlation matrix")


def _plot_pca(df: pd.DataFrame, p: dict, ax) -> None:
    feats = p.get("feature_cols") or []
    if len(feats) < 2:
        raise ValueError("PCA needs ≥ 2 feature columns")
    X = df[feats].dropna().values
    if X.shape[0] < 2:
        raise ValueError("PCA needs ≥ 2 rows after drop-na")
    Xc = X - X.mean(axis=0)
    # Use SVD to avoid the sklearn dependency.
    _, _, vt = np.linalg.svd(Xc, full_matrices=False)
    pcs = Xc @ vt[:2].T
    if p.get("color_col"):
        labels = df.dropna(subset=feats)[p["color_col"]]
        if pd.api.types.is_numeric_dtype(labels):
            sc = ax.scatter(pcs[:, 0], pcs[:, 1], c=labels, cmap="viridis", alpha=0.7)
            plt.colorbar(sc, ax=ax, label=p["color_col"])
        else:
            for name, mask in labels.groupby(labels):
                idx = labels.index.isin(mask.index)
                ax.scatter(pcs[idx, 0], pcs[idx, 1], alpha=0.7, label=str(name))
            ax.legend()
    else:
        ax.scatter(pcs[:, 0], pcs[:, 1], alpha=0.7)
    ax.set_xlabel("PC1")
    ax.set_ylabel("PC2")
    ax.set_title(f"PCA ({len(feats)} features → 2)")


def _plot_line(df: pd.DataFrame, p: dict, ax) -> None:
    sub = df[[p["x_col"], p["y_col"]] + ([p["group_col"]] if p.get("group_col") else [])].dropna().sort_values(p["x_col"])
    if p.get("group_col"):
        for name, grp in sub.groupby(p["group_col"]):
            ax.plot(grp[p["x_col"]], grp[p["y_col"]], label=str(name), alpha=0.85)
        ax.legend()
    else:
        ax.plot(sub[p["x_col"]], sub[p["y_col"]])
    ax.set_xlabel(p["x_col"])
    ax.set_ylabel(p["y_col"])
    ax.set_title(f"{p['y_col']} vs {p['x_col']}")


PLOTTERS = {
    "histogram": _plot_histogram,
    "scatter": _plot_scatter,
    "box": _plot_box,
    "violin": _plot_violin,
    "heatmap": _plot_heatmap,
    "pca": _plot_pca,
    "line": _plot_line,
}


# ---------------------------------------------------------------------------
# Code sidecar
# ---------------------------------------------------------------------------

def _build_sidecar(args, kind: str, params: dict) -> str:
    p_repr = json.dumps(params, indent=2)
    rel_data = args.data_path  # already relative to organon root in the route
    return f'''"""Reproduces figure {args.fig_id}.

Run from the Organon repo root:
    python {args.code_path}

Data dependency: {rel_data}
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def load(path: str) -> pd.DataFrame:
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".csv":
        return pd.read_csv(p)
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(p)
    if ext == ".json":
        return pd.read_json(p)
    raise ValueError(f"unsupported extension: {{ext}}")


PARAMS = json.loads(r"""{p_repr}""")
KIND = "{kind}"


def main() -> None:
    df = load("{rel_data}")
    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    # The plot logic below mirrors generate_plot.py for kind={kind}.
    # Edit freely; this file is yours.
    if KIND == "histogram":
        x = df[PARAMS["x_col"]].dropna()
        ax.hist(x, bins=int(PARAMS.get("bins") or 30))
        ax.set_xlabel(PARAMS["x_col"])
        ax.set_ylabel("count")
    elif KIND == "scatter":
        ax.scatter(df[PARAMS["x_col"]], df[PARAMS["y_col"]], alpha=0.7)
        ax.set_xlabel(PARAMS["x_col"])
        ax.set_ylabel(PARAMS["y_col"])
    elif KIND == "box":
        ax.boxplot(df[PARAMS["value_col"]].dropna().values)
        ax.set_ylabel(PARAMS["value_col"])
    elif KIND == "violin":
        ax.violinplot(df[PARAMS["value_col"]].dropna().values, showmeans=True)
        ax.set_ylabel(PARAMS["value_col"])
    elif KIND == "line":
        sub = df[[PARAMS["x_col"], PARAMS["y_col"]]].dropna().sort_values(PARAMS["x_col"])
        ax.plot(sub[PARAMS["x_col"]], sub[PARAMS["y_col"]])
        ax.set_xlabel(PARAMS["x_col"])
        ax.set_ylabel(PARAMS["y_col"])
    elif KIND == "heatmap":
        feats = PARAMS.get("feature_cols") or [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        corr = df[feats].corr(numeric_only=True)
        im = ax.imshow(corr.values, cmap="RdBu_r", vmin=-1, vmax=1)
        ax.set_xticks(np.arange(len(feats))); ax.set_yticks(np.arange(len(feats)))
        ax.set_xticklabels(feats, rotation=45, ha="right"); ax.set_yticklabels(feats)
        plt.colorbar(im, ax=ax)
    elif KIND == "pca":
        feats = PARAMS["feature_cols"]
        X = df[feats].dropna().values
        Xc = X - X.mean(axis=0)
        _, _, vt = np.linalg.svd(Xc, full_matrices=False)
        pcs = Xc @ vt[:2].T
        ax.scatter(pcs[:, 0], pcs[:, 1], alpha=0.7)
        ax.set_xlabel("PC1"); ax.set_ylabel("PC2")
    fig.tight_layout()
    fig.savefig("output.png", dpi=144)
    print("saved output.png")


if __name__ == "__main__":
    main()
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True)
    parser.add_argument("--fig-id", required=True)
    parser.add_argument("--project-slug", required=True)
    parser.add_argument("--file-id", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--kind", required=True)
    parser.add_argument("--params", required=True)
    parser.add_argument("--library-path", required=True)
    parser.add_argument("--code-path", required=True)
    parser.add_argument("--png-path", required=True)
    parser.add_argument("--svg-path", required=True)
    parser.add_argument("--thumb-path", required=True)
    parser.add_argument("--data-path", required=True)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    src = Path(args.path)
    if not src.exists():
        print(json.dumps({"error": f"file not found: {src}"}), file=sys.stderr)
        return 1

    try:
        params = json.loads(args.params)
    except json.JSONDecodeError:
        print(json.dumps({"error": "invalid --params JSON"}), file=sys.stderr)
        return 1
    if args.kind not in PLOTTERS:
        print(json.dumps({"error": f"unknown kind: {args.kind}"}), file=sys.stderr)
        return 1

    try:
        df = _load(src)
    except Exception as exc:
        print(json.dumps({"error": f"load failed: {exc}"}), file=sys.stderr)
        return 1

    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    try:
        PLOTTERS[args.kind](df, params, ax)
    except Exception as exc:
        plt.close(fig)
        print(json.dumps({"error": f"plot failed: {exc}"}), file=sys.stderr)
        return 1

    fig.tight_layout()
    png = out_dir / "v1.png"
    svg = out_dir / "v1.svg"
    thumb = out_dir / "v1.thumb.png"
    code = out_dir / "v1.py"
    fig.savefig(png, dpi=144)
    fig.savefig(svg)
    plt.close(fig)
    _save_thumb(png, thumb)
    code.write_text(_build_sidecar(args, args.kind, params))

    artifact = {
        "_artifact": "figure",
        "schema_version": 1,
        "id": args.fig_id,
        "project_slug": args.project_slug,
        "kind": "plot",
        "version": 1,
        "format": "png",
        "data_source": args.file_id,
        "params": {"plot_kind": args.kind, **params},
        "caption": None,
        "alt_text": None,
        "code_path": args.code_path,
        "png_path": args.png_path,
        "svg_path": args.svg_path,
        "thumbnail_path": args.thumb_path,
        "library_path": args.library_path,
        "backend": "matplotlib",
        "cost_cents": 0,
        "parent_version": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    print(json.dumps(artifact, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
