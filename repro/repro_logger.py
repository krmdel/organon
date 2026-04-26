"""Reproducibility logger for Scientific OS.

Logs every analysis operation to a JSONL ledger with timestamps, parameters,
data file hashes, and environment information. Generates markdown summaries
on demand.

Per D-04: Log everything -- every skill invocation with full parameters.
Per D-05: JSONL as source of truth, markdown summary on demand.
Per D-06: Ledger lives in repro/ directory at project root.
"""

import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

LEDGER_PATH = Path(__file__).parent / "ledger.jsonl"


def _get_package_version(package_name: str) -> str:
    """Get the version string of an installed package, or 'not installed'."""
    try:
        if package_name == "python":
            return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        import importlib.metadata
        return importlib.metadata.version(package_name)
    except Exception:
        return "not installed"


def _file_hash(filepath: str) -> str:
    """SHA-256 hash of a file for version tracking.

    Reads in 8192-byte chunks for memory efficiency with large files.
    """
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def log_operation(
    skill: str,
    operation: str,
    params: dict,
    data_files: list[str] | None = None,
    output_files: list[str] | None = None,
    notes: str = "",
) -> dict:
    """Append a reproducibility entry to the JSONL ledger.

    Args:
        skill: Name of the skill performing the operation.
        operation: Specific operation being performed.
        params: Parameters used for the operation.
        data_files: List of input file paths to hash for version tracking.
        output_files: List of output file paths produced.
        notes: Free-form notes about the operation.

    Returns:
        The complete entry dict that was logged.
    """
    now = datetime.now(timezone.utc)
    session_id = now.strftime("%Y-%m-%d") + "-S1"

    entry = {
        "timestamp": now.isoformat(),
        "session_id": session_id,
        "skill": skill,
        "operation": operation,
        "params": params,
        "data_files": [
            {"path": f, "sha256": _file_hash(f)} for f in (data_files or [])
        ],
        "output_files": output_files or [],
        "environment": {
            "python": _get_package_version("python"),
            "pandas": _get_package_version("pandas"),
            "scipy": _get_package_version("scipy"),
        },
        "notes": notes,
    }

    with open(LEDGER_PATH, "a") as fh:
        fh.write(json.dumps(entry) + "\n")

    return entry


def generate_summary(output_path: str | None = None) -> str:
    """Read the JSONL ledger and produce a markdown summary.

    Groups entries by date and formats as a markdown table.

    Args:
        output_path: If provided, writes the summary to this file path.

    Returns:
        The markdown summary string.
    """
    if not LEDGER_PATH.exists():
        return "# Reproducibility Summary\n\nNo operations logged yet."

    entries = []
    with open(LEDGER_PATH, "r") as fh:
        for line in fh:
            line = line.strip()
            if line:
                entries.append(json.loads(line))

    if not entries:
        return "# Reproducibility Summary\n\nNo operations logged yet."

    # Group by date
    by_date: dict[str, list[dict]] = defaultdict(list)
    for entry in entries:
        date_str = entry["timestamp"][:10]
        by_date[date_str].append(entry)

    lines = ["# Reproducibility Summary", ""]

    for date in sorted(by_date.keys(), reverse=True):
        lines.append(f"## {date}")
        lines.append("")
        lines.append("| Time | Skill | Operation | Data Files |")
        lines.append("|------|-------|-----------|------------|")

        for entry in by_date[date]:
            time_str = entry["timestamp"][11:19]
            skill = entry["skill"]
            operation = entry["operation"]
            data_files = ", ".join(
                d["path"].split("/")[-1] for d in entry.get("data_files", [])
            )
            if not data_files:
                data_files = "-"
            lines.append(f"| {time_str} | {skill} | {operation} | {data_files} |")

        lines.append("")

    summary = "\n".join(lines)

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(summary)

    return summary
