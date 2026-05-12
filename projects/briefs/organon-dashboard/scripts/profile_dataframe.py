"""Phase 3 T12 — produces a `_artifact: dataframe` JSON body for the dashboard.

Invoked by lib/data/load.ts via subprocess. Reads a CSV/XLSX/JSON file and
emits a single JSON line on stdout matching PHASE_3_TASKS.md §5.1.

Usage:
    python profile_dataframe.py \\
        --path  <abs path to raw file> \\
        --file-id  data-YYYYMMDD-XXXXXX \\
        --project-slug  <slug> \\
        --filename  <original filename> \\
        --library-path  <projects/{slug}/data/{file_id}.preview.json> \\
        --data-path     <projects/{slug}/data/{file_id}.{ext}> \\
        [--column-overrides '{"col":"numeric",...}']
"""

import argparse
import json
import math
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning, module="pandas")
warnings.filterwarnings("ignore", message=".*Could not infer format.*")


PREVIEW_ROW_LIMIT = 50
TOP_K_CATEGORICAL = 3


def _load(path: Path) -> pd.DataFrame:
    ext = path.suffix.lower()
    if ext == ".csv":
        return pd.read_csv(path)
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(path)
    if ext == ".json":
        return pd.read_json(path)
    raise ValueError(f"Unsupported format: {ext}. Supported: .csv, .xlsx, .xls, .json")


def _ext_to_format(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".csv":
        return "csv"
    if ext in (".xlsx", ".xls"):
        return "xlsx"
    if ext == ".json":
        return "json"
    return ext.lstrip(".") or "unknown"


def _infer_type(series: pd.Series) -> str:
    if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
        return "numeric"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if pd.api.types.is_bool_dtype(series):
        return "categorical"
    # Probe string columns for ISO-ish datetimes — if ≥ 80% of non-null values
    # parse, treat as datetime. Catches CSV columns that pandas leaves as object.
    if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
        nonnull = series.dropna()
        if len(nonnull) >= 3:
            sample = nonnull.head(min(50, len(nonnull)))
            parsed = pd.to_datetime(sample, errors="coerce", utc=False)
            if parsed.notna().mean() >= 0.8:
                return "datetime"
    nunique = series.nunique(dropna=True)
    n = len(series)
    if n > 0 and nunique > 0 and nunique <= max(20, n * 0.05):
        return "categorical"
    return "text"


def _safe_number(value) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    return None


def _stats_numeric(series: pd.Series) -> dict:
    nonnull = series.dropna()
    return {
        "count": int(nonnull.count()),
        "mean": _safe_number(nonnull.mean()) if len(nonnull) else None,
        "std": _safe_number(nonnull.std()) if len(nonnull) else None,
        "min": _safe_number(nonnull.min()) if len(nonnull) else None,
        "max": _safe_number(nonnull.max()) if len(nonnull) else None,
    }


def _stats_categorical(series: pd.Series) -> dict:
    nonnull = series.dropna().astype(str)
    counts = nonnull.value_counts().head(TOP_K_CATEGORICAL)
    return {
        "unique_count": int(nonnull.nunique()),
        "top": [[str(k), int(v)] for k, v in counts.items()],
    }


def _stats_datetime(series: pd.Series) -> dict:
    nonnull = pd.to_datetime(series, errors="coerce").dropna()
    if not len(nonnull):
        return {"count": 0, "min": None, "max": None}
    return {
        "count": int(len(nonnull)),
        "min": nonnull.min().isoformat(),
        "max": nonnull.max().isoformat(),
    }


def _stats_text(series: pd.Series) -> dict:
    nonnull = series.dropna().astype(str)
    out = {"count": int(len(nonnull))}
    if len(nonnull):
        out["unique_count"] = int(nonnull.nunique())
        out["avg_length"] = float(round(nonnull.str.len().mean(), 2))
    return out


def _column_record(name: str, series: pd.Series, override_type: str | None) -> dict:
    if override_type:
        col_type = override_type
        inferred_by = "user-override"
    else:
        col_type = _infer_type(series)
        inferred_by = "auto"

    if col_type == "numeric":
        coerced = pd.to_numeric(series, errors="coerce")
        stats = _stats_numeric(coerced)
        null_count = int(coerced.isna().sum())
    elif col_type == "datetime":
        coerced = pd.to_datetime(series, errors="coerce")
        stats = _stats_datetime(coerced)
        null_count = int(coerced.isna().sum())
    elif col_type == "categorical":
        stats = _stats_categorical(series)
        null_count = int(series.isna().sum())
    else:
        stats = _stats_text(series)
        null_count = int(series.isna().sum())

    return {
        "name": name,
        "type": col_type,
        "type_inferred_by": inferred_by,
        "null_count": null_count,
        "stats": stats,
    }


def _preview_rows(df: pd.DataFrame) -> list[dict[str, str]]:
    head = df.head(PREVIEW_ROW_LIMIT)
    rows: list[dict[str, str]] = []
    for _, r in head.iterrows():
        row: dict[str, str] = {}
        for col, val in r.items():
            if val is None or (isinstance(val, float) and math.isnan(val)):
                row[str(col)] = ""
            else:
                row[str(col)] = str(val)
        rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True)
    parser.add_argument("--file-id", required=True)
    parser.add_argument("--project-slug", required=True)
    parser.add_argument("--filename", required=True)
    parser.add_argument("--library-path", required=True)
    parser.add_argument("--data-path", required=True)
    parser.add_argument("--preview-path", required=True)
    parser.add_argument("--column-overrides", default="{}")
    parser.add_argument("--uploaded-at", default=None)
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(json.dumps({"error": f"file not found: {path}"}), file=sys.stderr)
        return 1

    try:
        overrides: dict[str, str] = json.loads(args.column_overrides) or {}
    except json.JSONDecodeError:
        print(json.dumps({"error": "invalid --column-overrides JSON"}), file=sys.stderr)
        return 1

    try:
        df = _load(path)
    except Exception as exc:
        print(json.dumps({"error": f"load failed: {exc}"}), file=sys.stderr)
        return 1

    columns = [
        _column_record(str(col), df[col], overrides.get(str(col)))
        for col in df.columns
    ]

    artifact = {
        "_artifact": "dataframe",
        "schema_version": 1,
        "id": args.file_id,
        "project_slug": args.project_slug,
        "filename": args.filename,
        "format": _ext_to_format(path),
        "size_bytes": int(path.stat().st_size),
        "rows_total": int(len(df)),
        "columns": columns,
        "preview_rows": _preview_rows(df),
        "data_path": args.data_path,
        "preview_path": args.preview_path,
        "uploaded_at": args.uploaded_at or datetime.now(timezone.utc).isoformat(),
        "library_path": args.library_path,
    }

    print(json.dumps(artifact, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
