"""Researcher compliance validator (Phase 3) + receipt forensics (Tier B).

Phase 3 validates that research.md produced by the sci-researcher agent
contains a '## Verification receipts' table documenting what was actually
retrieved from APIs for each evidence entry.

Tier B (receipt forensics) goes further:
  B1 — parse_receipts_table: extract structured rows from the table
  B2 — cross_reference_receipts: diff receipts against bib entries (CRITICAL on mismatch)
  B3 — verify_receipts_against_api: re-call live APIs to confirm receipts (env-gated)
  B5 — check_receipt_confidence: sidecar source_confidence must not exceed seed confidence

Called by paper_pipeline.py cmd_check_research.

Public API
----------
check_research_receipts(research_md_path: Path) -> list[dict]
parse_receipts_table(research_md_path: Path) -> list[dict]
cross_reference_receipts(receipts, bib_entries) -> list[dict]
verify_receipts_against_api(receipts) -> list[dict]
check_receipt_confidence(receipts, seed_quotes, sidecar_quotes) -> list[dict]
validate_research_compliance(research_md_path: Path) -> tuple[bool, list[dict]]

Finding dict schema (same as verify_ops):
    {criterion, severity, section, finding, suggestion}
"""

from __future__ import annotations

import difflib
import os
import re
import sys
import unicodedata
from pathlib import Path

_SECTION_PATTERN = re.compile(
    r"^##\s+Verification receipts\b",
    re.IGNORECASE | re.MULTILINE,
)
_TABLE_ROW_PATTERN = re.compile(r"^\|\s*\d+\s*\|", re.MULTILINE)
_SEPARATOR_PATTERN = re.compile(r"^\|[-| ]+\|", re.MULTILINE)

_CRITERION = "Researcher Integrity (Phase 3)"
_CRITERION_B = "Receipt Forensics (Tier B)"
_SECTION_LABEL = "Verification receipts"

# Similarity thresholds for receipt forensics
TITLE_CROSS_THRESHOLD = 0.85   # receipt vs bib title similarity floor
TITLE_API_THRESHOLD   = 0.90   # receipt vs live API title similarity floor
AUTHOR_THRESHOLD      = 0.80   # first-author surname similarity floor

# Confidence tier ordering for B5
_CONFIDENCE_RANK: dict[str, int] = {"abstract": 1, "partial": 2, "full-text": 3}

# Column header keyword matching: (keywords_in_header, field_name)
_HEADER_COLUMN_MAP: list[tuple[list[str], str]] = [
    (["#", "no", "num"], "entry_num"),
    (["api source", "source", "api"], "api_source"),
    (["returned title", "title", "returned"], "returned_title"),
    (["first author", "author"], "first_author"),
    (["doi", "eprint", "id", "identifier", "confirmed"], "identifier"),
]


def _make_finding(severity: str, finding: str, suggestion: str) -> dict:
    return {
        "criterion": _CRITERION,
        "severity": severity,
        "section": _SECTION_LABEL,
        "finding": finding,
        "suggestion": suggestion,
    }


def _make_b_finding(severity: str, finding: str, suggestion: str) -> dict:
    return {
        "criterion": _CRITERION_B,
        "severity": severity,
        "section": _SECTION_LABEL,
        "finding": finding,
        "suggestion": suggestion,
    }


# ---------------------------------------------------------------------------
# Text normalisation helpers (receipt forensics)
# ---------------------------------------------------------------------------


def _normalize_for_compare(s: str) -> str:
    """Lowercase, strip LaTeX braces, strip diacritics, collapse whitespace."""
    s = re.sub(r"\{[^{}]*\}", "", s)
    s = "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )
    s = re.sub(r"[^\w\s]", " ", s.lower())
    return " ".join(s.split())


def _normalize_surname(s: str) -> str:
    """Normalize a surname: strip particles, lowercase, strip diacritics."""
    _PARTICLES = {"van", "de", "der", "von", "den", "la", "le", "del", "di", "da"}
    s = _normalize_for_compare(s)
    parts = [p for p in s.split() if p not in _PARTICLES]
    return " ".join(parts)


def _first_bib_surname(author_field: str) -> str:
    """Extract the first author's surname from a BibTeX author string."""
    if not author_field:
        return ""
    first = author_field.split(" and ")[0].strip()
    if "," in first:
        return first.split(",")[0].strip()
    parts = first.split()
    return parts[-1] if parts else ""


def _title_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(
        None,
        _normalize_for_compare(a),
        _normalize_for_compare(b),
    ).ratio()


def _author_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(
        None,
        _normalize_surname(a),
        _normalize_surname(b),
    ).ratio()


def parse_receipts_table(research_md_path: Path) -> list[dict]:
    """B1: Parse the ## Verification receipts table into a list of row dicts.

    Returns list of dicts with keys:
        entry_num, api_source, returned_title, first_author, identifier

    Returns [] if the section or table is absent (no exception raised).
    """
    research_md_path = Path(research_md_path)
    if not research_md_path.exists():
        return []
    text = research_md_path.read_text(encoding="utf-8", errors="replace")

    section_match = _SECTION_PATTERN.search(text)
    if not section_match:
        return []
    section_text = text[section_match.start():]

    next_section = re.search(r"^##\s", section_text[1:], re.MULTILINE)
    if next_section:
        section_text = section_text[: next_section.start() + 1]

    table_lines = [
        line.strip()
        for line in section_text.splitlines()
        if line.strip().startswith("|")
    ]
    if not table_lines:
        return []

    header_line: list[str] | None = None
    data_lines: list[list[str]] = []
    separator_seen = False
    for line in table_lines:
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if not separator_seen:
            if all(re.match(r"^[-: ]+$", c) for c in cells if c):
                separator_seen = True
                continue
            if header_line is None:
                header_line = cells
        else:
            if cells:
                data_lines.append(cells)

    if not header_line:
        return []

    # Map header positions to field names using keyword matching
    col_map: dict[int, str] = {}
    for i, cell in enumerate(header_line):
        cell_lower = cell.lower()
        for keywords, field_name in _HEADER_COLUMN_MAP:
            if any(kw in cell_lower for kw in keywords):
                if field_name not in col_map.values():
                    col_map[i] = field_name
                    break

    rows: list[dict] = []
    for cells in data_lines:
        row: dict = {}
        for i, cell in enumerate(cells):
            if i in col_map:
                row[col_map[i]] = cell.strip()
        # Only include rows that have a numeric entry_num
        entry_num = row.get("entry_num", "")
        if entry_num and re.match(r"^\d+$", entry_num):
            for _, field_name in _HEADER_COLUMN_MAP:
                row.setdefault(field_name, "")
            rows.append(row)

    return rows


def cross_reference_receipts(
    receipts: list[dict],
    bib_entries: list[dict],
) -> list[dict]:
    """B2: Compare receipt rows against bib entries.

    For each receipt row, look up the bib entry by identifier (DOI or eprint).
    Diff title (fuzzy, threshold TITLE_CROSS_THRESHOLD) and first-author
    surname (fuzzy, threshold AUTHOR_THRESHOLD).

    Mismatch → CRITICAL. Identifier present in receipt but absent from bib → MAJOR.

    Returns list of finding dicts (empty = all match or no receipts/bib to compare).
    """
    if not receipts or not bib_entries:
        return []

    # Build lookup by normalised DOI and normalised eprint
    bib_by_doi: dict[str, dict] = {}
    bib_by_eprint: dict[str, dict] = {}
    for entry in bib_entries:
        doi = (entry.get("doi") or "").strip().lower()
        if doi:
            bib_by_doi[doi] = entry
        eprint = (entry.get("eprint") or "").strip().lower()
        if eprint:
            bib_by_eprint[eprint] = entry

    findings: list[dict] = []

    for row in receipts:
        identifier = (row.get("identifier") or "").strip()
        if not identifier:
            continue

        id_lower = identifier.lower()
        bib_entry = (
            bib_by_doi.get(id_lower)
            or bib_by_eprint.get(id_lower)
            or bib_by_eprint.get(re.sub(r"^arxiv:", "", id_lower))
        )

        if bib_entry is None:
            findings.append(_make_b_finding(
                severity="major",
                finding=(
                    f"Receipt row #{row.get('entry_num')} references identifier "
                    f"'{identifier}' but no matching entry was found in the .bib file. "
                    "The receipt may belong to a source that was removed from the bib, "
                    "or the identifier was mis-transcribed."
                ),
                suggestion=(
                    f"Check whether '{identifier}' was dropped from the .bib, "
                    "or correct the identifier in the receipt row."
                ),
            ))
            continue

        receipt_title = row.get("returned_title", "")
        receipt_author = row.get("first_author", "")
        bib_title = bib_entry.get("title", "")
        bib_first = _first_bib_surname(bib_entry.get("author", ""))

        if receipt_title and bib_title:
            tsim = _title_similarity(receipt_title, bib_title)
            if tsim < TITLE_CROSS_THRESHOLD:
                findings.append(_make_b_finding(
                    severity="critical",
                    finding=(
                        f"Receipt row #{row.get('entry_num')}: title mismatch "
                        f"(similarity {tsim:.2f} < threshold {TITLE_CROSS_THRESHOLD}). "
                        f"Receipt: '{receipt_title}'. "
                        f"Bib: '{bib_title}'. "
                        f"Identifier: {identifier}"
                    ),
                    suggestion=(
                        "Update the receipt or the bib entry so both refer to the same "
                        "paper. The receipt must reflect what the API actually returned."
                    ),
                ))

        if receipt_author and bib_first:
            asim = _author_similarity(receipt_author, bib_first)
            if asim < AUTHOR_THRESHOLD:
                findings.append(_make_b_finding(
                    severity="critical",
                    finding=(
                        f"Receipt row #{row.get('entry_num')}: first-author mismatch "
                        f"(similarity {asim:.2f} < threshold {AUTHOR_THRESHOLD}). "
                        f"Receipt: '{receipt_author}'. "
                        f"Bib first author: '{bib_first}'. "
                        f"Identifier: {identifier}"
                    ),
                    suggestion=(
                        "Fix the bib entry's author field or the receipt's first-author "
                        "cell so they agree on who the first author is."
                    ),
                ))

    return findings


def verify_receipts_against_api(receipts: list[dict]) -> list[dict]:
    """B3: Re-call verify_citation for each receipt row and check consistency.

    Enabled only when env SCI_OS_VERIFY_RECEIPTS=1 or CI=true (any non-empty value).
    For each receipt: if the live API returns a title or first-author that
    does not match what the receipt claims → CRITICAL.

    Network errors per row are swallowed (non-fatal); the row is skipped.
    Returns [] when the env guard is not set or no identifiers are present.
    """
    ci_active = os.environ.get("CI", "").lower() in ("1", "true", "yes")
    verify_flag = os.environ.get("SCI_OS_VERIFY_RECEIPTS", "") == "1"
    if not ci_active and not verify_flag:
        return []
    if not receipts:
        return []

    # Lazy import so offline tests that never set the env flag have no import cost
    try:
        _repro = str(Path(__file__).resolve().parents[4] / "repro")
        if _repro not in sys.path:
            sys.path.insert(0, _repro)
        from citation_verify import verify_citation  # type: ignore
    except ImportError:
        return []

    findings: list[dict] = []

    for row in receipts:
        identifier = (row.get("identifier") or "").strip()
        if not identifier:
            continue

        entry = {"doi": identifier} if identifier.startswith("10.") else {"eprint": identifier}

        try:
            live = verify_citation(entry)
        except Exception:
            continue

        if not live:
            continue

        receipt_title = row.get("returned_title", "")
        receipt_author = row.get("first_author", "")
        live_title = live.get("title", "")
        live_authors = live.get("authors") or []
        live_first = live_authors[0] if live_authors else ""

        if receipt_title and live_title:
            tsim = _title_similarity(receipt_title, live_title)
            if tsim < TITLE_API_THRESHOLD:
                findings.append(_make_b_finding(
                    severity="critical",
                    finding=(
                        f"Receipt row #{row.get('entry_num')}: receipt title does not "
                        f"match the live API response (similarity {tsim:.2f} < "
                        f"threshold {TITLE_API_THRESHOLD}). "
                        f"Receipt claims: '{receipt_title}'. "
                        f"API returns: '{live_title}'. "
                        f"Identifier: {identifier}"
                    ),
                    suggestion=(
                        "The receipt may have been written from memory rather than from "
                        "a live API call. Re-spawn the sci-researcher agent to regenerate "
                        "the receipt from actual API data."
                    ),
                ))

        if receipt_author and live_first:
            asim = _author_similarity(receipt_author, live_first)
            if asim < AUTHOR_THRESHOLD:
                findings.append(_make_b_finding(
                    severity="critical",
                    finding=(
                        f"Receipt row #{row.get('entry_num')}: receipt first-author "
                        f"does not match the live API (similarity {asim:.2f} < "
                        f"threshold {AUTHOR_THRESHOLD}). "
                        f"Receipt claims: '{receipt_author}'. "
                        f"API returns first author: '{live_first}'. "
                        f"Identifier: {identifier}"
                    ),
                    suggestion=(
                        "Re-spawn the sci-researcher agent to regenerate receipts "
                        "from live API data — the first-author field may be fabricated."
                    ),
                ))

    return findings


def check_receipt_confidence(
    receipts: list[dict],
    seed_quotes: dict,
    sidecar_quotes: dict,
) -> list[dict]:
    """B5: Flag when sidecar source_confidence claims a stronger tier than the seed.

    seed_quotes: cite-key → dict with "confidence" field (upstream quotes.json).
    sidecar_quotes: cite-key → dict with "source_confidence" field (citations.json).

    A sidecar that claims "full-text" while the seed is "abstract" is MAJOR:
    the writer cannot have seen more than the researcher retrieved.

    Keys absent from either dict are silently skipped.
    """
    findings: list[dict] = []

    for key, sidecar_entry in sidecar_quotes.items():
        if key not in seed_quotes:
            continue

        seed_conf = (seed_quotes[key].get("confidence") or "").lower().strip()
        sidecar_conf = (sidecar_entry.get("source_confidence") or "").lower().strip()

        seed_rank = _CONFIDENCE_RANK.get(seed_conf, 0)
        sidecar_rank = _CONFIDENCE_RANK.get(sidecar_conf, 0)

        if sidecar_rank > seed_rank > 0:
            findings.append(_make_b_finding(
                severity="major",
                finding=(
                    f"Cite-key '{key}': sidecar claims source_confidence='{sidecar_conf}' "
                    f"but the upstream seed only has confidence='{seed_conf}'. "
                    "The sidecar cannot claim higher evidence quality than the source it was "
                    "derived from."
                ),
                suggestion=(
                    f"Downgrade '{key}' source_confidence to '{seed_conf}' in the sidecar, "
                    "or re-run the sci-researcher agent with full-text access to legitimately "
                    "upgrade the seed confidence first."
                ),
            ))

    return findings


def check_research_receipts(research_md_path: Path) -> list[dict]:
    """Validate the Verification receipts table in research.md.

    Returns an empty list if the section is present and has ≥1 data row.
    Returns a list with one CRITICAL finding otherwise.

    Raises FileNotFoundError if research_md_path does not exist.
    """
    research_md_path = Path(research_md_path)
    if not research_md_path.exists():
        raise FileNotFoundError(f"research.md not found at {research_md_path}")

    text = research_md_path.read_text(encoding="utf-8", errors="replace")

    section_match = _SECTION_PATTERN.search(text)
    if not section_match:
        return [_make_finding(
            severity="critical",
            finding=(
                "research.md is missing the '## Verification receipts' section. "
                "This section is mandatory (Phase 3): it documents the exact title "
                "and first author returned from each API call so downstream gates "
                "can audit whether the bib was filled from memory or live data."
            ),
            suggestion=(
                "Add a '## Verification receipts' section at the end of research.md "
                "with a markdown table listing, for each evidence entry: entry #, "
                "API source used, verbatim title returned by the API, first author "
                "surname from the API, and the DOI/eprint ID that was confirmed. "
                "Example row: | 1 | paper-search | Actual Title From API | Smith | 10.xxx/yyy |"
            ),
        )]

    # Extract only the text from the section header onwards so we don't
    # accidentally match table rows from earlier sections.
    section_text = text[section_match.start():]

    # Stop at the next ## heading (if any) so we only inspect this section.
    next_section = re.search(r"^##\s", section_text[1:], re.MULTILINE)
    if next_section:
        section_text = section_text[: next_section.start() + 1]

    data_rows = _TABLE_ROW_PATTERN.findall(section_text)
    if not data_rows:
        return [_make_finding(
            severity="critical",
            finding=(
                "The '## Verification receipts' section exists but contains no data rows. "
                "Either the table header/separator was written but left empty, or only "
                "prose was placed under the heading. Every evidence entry in the table "
                "must have a corresponding receipt row."
            ),
            suggestion=(
                "Add one row per evidence entry to the Verification receipts table. "
                "Each row must start with the entry number (e.g. | 1 |) and include "
                "the API source, verbatim title, first author, and confirmed DOI/eprint."
            ),
        )]

    # B7 (Phase 9): if raw `| N |` data rows are present but the parser
    # extracts zero structured rows, the column headers don't match any
    # keyword in _HEADER_COLUMN_MAP. Without this check the downstream
    # cross_reference_receipts is silently a no-op — every receipt in the
    # table escapes the title/author cross-check against bib entries. Emit
    # a CRITICAL so the writer cannot drift the table format.
    parsed = parse_receipts_table(research_md_path)
    if len(parsed) == 0:
        return [_make_finding(
            severity="critical",
            finding=(
                f"The '## Verification receipts' section has {len(data_rows)} raw data "
                "row(s) but the parser extracted zero structured rows. The column "
                "headers do not match any expected keyword (entry/API/title/author/"
                "DOI/eprint), so cross_reference_receipts cannot diff them against the "
                "bib. This is a silent forensic bypass — receipts must be parseable."
            ),
            suggestion=(
                "Use header keywords the parser recognises. The first column must "
                "contain 'entry' or '#'; subsequent columns must contain 'api'/'source', "
                "'title', 'author', and 'doi'/'eprint'/'identifier'. See the example "
                "row format: | 1 | paper-search | Actual Title | Smith | 10.xxx/yyy |"
            ),
        )]

    return []


def validate_research_compliance(research_md_path: Path) -> tuple[bool, list[dict]]:
    """Return (ok, findings) for research.md.

    ok=True means zero compliance findings (receipts present and populated).
    Raises FileNotFoundError if path is missing.
    """
    findings = check_research_receipts(research_md_path)
    return (len(findings) == 0, findings)
