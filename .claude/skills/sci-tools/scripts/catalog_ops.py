"""Catalog operations for the sci-tools skill.

Provides local ToolUniverse catalog search, category filtering,
catalog refresh via tu CLI, tool detail retrieval, and results formatting.
Per D-01: local JSON snapshot for instant offline-capable browsing.
Per D-02: refresh on demand via tu CLI.
Per D-03: compact table display with truncated descriptions.
Per D-04: keyword matching against name + description fields.
"""

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Path Resolution (same parents[4] pattern as sci-writing scripts)
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[4]
assert (PROJECT_ROOT / "CLAUDE.md").exists(), f"PROJECT_ROOT wrong: {PROJECT_ROOT}"

CATALOG_PATH = PROJECT_ROOT / "data" / "tooluniverse-catalog.json"


# ---------------------------------------------------------------------------
# Local Catalog Search (TOOL-01, TOOL-04)
# ---------------------------------------------------------------------------

def search_catalog(
    query: str,
    category: Optional[str] = None,
    limit: int = 20,
) -> list:
    """Search local catalog by keyword matching against name + description.

    Args:
        query: Space-separated keywords to search for.
        category: Optional category filter (fuzzy match via substring).
        limit: Maximum number of results to return.

    Returns:
        List of tool dicts sorted by relevance score, without internal _score key.
    """
    keywords = re.findall(r"\w+", query.lower())
    if not keywords:
        return []

    with open(CATALOG_PATH) as f:
        catalog = json.load(f)

    results = []
    for tool in catalog["tools"]:
        # Category filter with fuzzy matching (Pitfall 2)
        if category and category.lower() not in tool.get("category", "").lower():
            continue

        text = f"{tool['name']} {tool['description']}".lower()
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            results.append({**tool, "_score": score})

    results.sort(key=lambda x: x["_score"], reverse=True)

    # Strip internal _score key before returning
    for r in results:
        r.pop("_score", None)

    return results[:limit]


# ---------------------------------------------------------------------------
# Category Listing
# ---------------------------------------------------------------------------

def list_categories(catalog_path: Optional[Path] = None) -> list:
    """Return sorted list of unique category strings from catalog.

    Args:
        catalog_path: Optional override for catalog file path.

    Returns:
        Sorted list of unique category strings.
    """
    path = catalog_path or CATALOG_PATH
    with open(path) as f:
        catalog = json.load(f)

    categories = sorted(set(tool.get("category", "") for tool in catalog["tools"]))
    # Remove empty strings if any
    return [c for c in categories if c]


# ---------------------------------------------------------------------------
# Catalog Refresh (D-02)
# ---------------------------------------------------------------------------

def refresh_catalog() -> dict:
    """Re-download catalog from tu CLI and write to CATALOG_PATH.

    Runs uvx --from tooluniverse tu list with custom fields and writes
    the result as JSON. Adds a refreshed_at timestamp per Pitfall 1.

    Returns:
        The catalog dict with refreshed_at timestamp.

    Raises:
        RuntimeError: If tu CLI returns non-zero exit code.
    """
    result = subprocess.run(
        [
            "uvx", "--from", "tooluniverse", "tu", "list",
            "--raw", "--mode", "custom",
            "--fields", "name", "description", "type", "category",
            "--limit", "9999",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0:
        raise RuntimeError(f"tu list failed: {result.stderr}")

    catalog = json.loads(result.stdout)
    catalog["refreshed_at"] = datetime.now().isoformat()

    # Create data/ dir if not exists
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(CATALOG_PATH, "w") as f:
        json.dump(catalog, f, indent=2)

    return catalog


# ---------------------------------------------------------------------------
# Tool Detail Retrieval (TOOL-04)
# ---------------------------------------------------------------------------

def get_tool_details(tool_name: str) -> dict:
    """Get full tool info via tu CLI (includes params, examples, schema).

    Args:
        tool_name: Exact name of the tool to look up.

    Returns:
        Dict with full tool details from tu info --json.

    Raises:
        RuntimeError: If tu CLI returns non-zero exit code.
    """
    result = subprocess.run(
        ["uvx", "--from", "tooluniverse", "tu", "info", tool_name, "--json"],
        capture_output=True,
        text=True,
        timeout=30,
    )

    if result.returncode != 0:
        raise RuntimeError(f"tu info failed: {result.stderr}")

    return json.loads(result.stdout)


# ---------------------------------------------------------------------------
# Results Formatting (D-03)
# ---------------------------------------------------------------------------

def format_results_table(results: list, max_desc: int = 60) -> str:
    """Format search results as an aligned text table.

    Columns: Name, Category, Type, Description (truncated).

    Args:
        results: List of tool dicts from search_catalog.
        max_desc: Maximum description length before truncation.

    Returns:
        Formatted table string with header and separator.
    """
    if not results:
        return "No results found."

    # Calculate column widths
    headers = ["Name", "Category", "Type", "Description"]
    rows = []
    for r in results:
        desc = r.get("description", "")
        if len(desc) > max_desc:
            desc = desc[:max_desc] + "..."
        rows.append([
            r.get("name", ""),
            r.get("category", ""),
            r.get("type", ""),
            desc,
        ])

    # Calculate max widths per column
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    # Build table
    def _fmt_row(cells):
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells))

    lines = [
        _fmt_row(headers),
        "  ".join("-" * w for w in widths),
    ]
    for row in rows:
        lines.append(_fmt_row(row))

    return "\n".join(lines)
