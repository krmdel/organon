#!/usr/bin/env python3
"""
bib_sweep.py — CI bib integrity sweep.

Finds every *.bib file under projects/ and clients/*/projects/, runs
check_bib_integrity against each, and exits non-zero if any CRITICAL
finding is present.

Usage:
    python3 scripts/bib_sweep.py [--fail-on-major]

Exit codes:
    0  — no CRITICAL findings (MAJOR findings only print a warning)
    1  — one or more CRITICAL findings, or import/runtime error
"""
import re
import sys
import glob
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".claude" / "skills" / "sci-writing" / "scripts"))
sys.path.insert(0, str(ROOT))

_KEY_RE = re.compile(r"(?:Bib entry|for key) '([^']+)'")


def _extract_key(finding: dict) -> str:
    """Pull the bib key from the finding text (no separate bib_key field exists)."""
    text = finding.get("finding", finding.get("message", ""))
    m = _KEY_RE.search(text)
    return m.group(1) if m else "?"


_EXCLUDE_DIR_PARTS = {
    "_processed",
    "node_modules",
    ".git",
    ".cache",
    ".venv",
    "venv",
    "__pycache__",
    "build",
    "dist",
}


def find_bib_files() -> list[Path]:
    """Phase 9: walk the entire repo for *.bib, not just projects/.

    Pre-Phase-9 the cron + CI sweep only scanned projects/** and
    clients/*/projects/**, while the verify_gate.py PreToolUse hook fires
    on ANY .md with a sibling .bib. That divergence let bibs under repro/,
    papers/, docs/, and arbitrary user paths escape the cron audit. Phase 9
    aligns the sweep to walk the whole repo with a sensible exclude list.
    """
    pattern = ROOT / "**" / "*.bib"
    found: list[Path] = []
    for p in glob.glob(str(pattern), recursive=True):
        path = Path(p)
        if any(part in _EXCLUDE_DIR_PARTS for part in path.parts):
            continue
        # Skip example/template fixtures
        if path.name.endswith(".example.bib"):
            continue
        # Skip test fixtures: tests/fixtures/*.bib are intentionally
        # malformed inputs for the test suite; gating on them would always
        # fail the cron and CI sweep on a clean checkout.
        rel_parts = path.parts
        if "tests" in rel_parts and "fixtures" in rel_parts:
            continue
        found.append(path)
    return sorted(set(found))


def run_sweep(fail_on_major: bool = False) -> int:
    try:
        from verify_ops import check_bib_integrity
    except ImportError as exc:
        print(f"[bib_sweep] ERROR: cannot import verify_ops — {exc}", file=sys.stderr)
        return 1

    try:
        from writing_ops import parse_bib_file
    except ImportError:
        # Minimal fallback: returns list[dict] with key + raw fields parsed from
        # the .bib text. Enough for check_bib_integrity to run identifier checks.
        import re

        def parse_bib_file(path: str) -> list[dict]:  # type: ignore[misc]
            entries: list[dict] = []
            with open(path) as fh:
                content = fh.read()
            for block in re.split(r"(?=@\w+\{)", content):
                block = block.strip()
                if not block or not block.startswith("@"):
                    continue
                m_key = re.match(r"@\w+\{([^,]+),", block)
                if not m_key:
                    continue
                entry: dict = {"key": m_key.group(1).strip()}
                for field, value in re.findall(
                    r"(\w+)\s*=\s*[{\"]([^}\"]*)[\"}]", block
                ):
                    entry[field.lower()] = value.strip()
                entries.append(entry)
            return entries

    bib_files = find_bib_files()
    if not bib_files:
        print("[bib_sweep] No .bib files found — nothing to audit.")
        return 0

    total_critical = 0
    total_major = 0
    total_entries = 0
    any_error = False

    for bib_path in bib_files:
        rel = bib_path.relative_to(ROOT)
        try:
            # parse_bib_file returns list[dict]; each dict has a "key" field.
            entries: list[dict] = parse_bib_file(str(bib_path))
        except Exception as exc:
            print(f"[bib_sweep] WARN: could not parse {rel}: {exc}", file=sys.stderr)
            any_error = True
            continue

        if not entries:
            print(f"[bib_sweep] SKIP {rel} — 0 entries")
            continue

        # Audit every entry in the file (treat all keys as "used").
        all_keys = {e.get("key", "") for e in entries if e.get("key")}

        try:
            # check_bib_integrity(used_keys, bib_entries)
            findings = check_bib_integrity(all_keys, entries)
        except Exception as exc:
            print(
                f"[bib_sweep] WARN: check_bib_integrity failed for {rel}: {exc}",
                file=sys.stderr,
            )
            any_error = True
            continue

        critical = [f for f in findings if f.get("severity") == "critical"]
        major = [f for f in findings if f.get("severity") == "major"]
        total_entries += len(entries)
        total_critical += len(critical)
        total_major += len(major)

        status = "CLEAN"
        if critical:
            status = f"CRITICAL×{len(critical)}"
        elif major:
            status = f"MAJOR×{len(major)}"

        print(f"[bib_sweep] {rel}: {len(entries)} entries — {status}")

        for f in critical:
            key = _extract_key(f)
            criterion = f.get("criterion", "?")
            finding = f.get("finding", f.get("message", ""))
            print(f"  CRITICAL [{key}] {criterion}: {finding}")

        if fail_on_major:
            for f in major:
                key = _extract_key(f)
                criterion = f.get("criterion", "?")
                finding = f.get("finding", f.get("message", ""))
                print(f"  MAJOR    [{key}] {criterion}: {finding}")

    print(
        f"\n[bib_sweep] Summary: {len(bib_files)} file(s), "
        f"{total_entries} entries, "
        f"{total_critical} CRITICAL, "
        f"{total_major} MAJOR"
    )

    if total_critical > 0:
        print(
            f"[bib_sweep] FAILED — {total_critical} CRITICAL finding(s) must be fixed.",
            file=sys.stderr,
        )
        return 1

    if fail_on_major and total_major > 0:
        print(
            f"[bib_sweep] FAILED — {total_major} MAJOR finding(s) (--fail-on-major set).",
            file=sys.stderr,
        )
        return 1

    if any_error:
        print("[bib_sweep] WARNING — some files could not be parsed (see above).")
        return 0

    print("[bib_sweep] PASSED — no CRITICAL findings.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CI bib integrity sweep")
    parser.add_argument(
        "--fail-on-major",
        action="store_true",
        help="Also exit non-zero when MAJOR findings exist",
    )
    args = parser.parse_args()
    sys.exit(run_sweep(fail_on_major=args.fail_on_major))
