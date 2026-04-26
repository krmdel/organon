"""Programmatic verification engine for sci-writing and sci-communication.

Implements the Accuracy Verification Gate as automated checks. Some issues
are auto-fixed (citation marker syntax), others are flagged for human
review (hedging escalation, statistical reporting gaps), and CRITICAL
findings block the save.

Checker phases:
  A. Citation Mechanics     -- malformed markers, unmatched bib keys (auto-fix/flag)
  B. Completeness Metrics    -- citation density, figure refs, abbreviations (flag)
  C. Bib Integrity           -- CrossRef title match + retraction + 404 (CRITICAL/MAJOR)
  D. Hedging Consistency     -- source vs draft hedging comparison (flag)
  E. Statistical Reporting   -- p-values without stats, missing effect sizes (flag)
  F. Paperclip Anchor Format -- citations.gxl.ai URL pattern enforcement (CRITICAL)
  G. Quote-or-Cite Sidecar   -- every [@Key] must have a quoted passage (CRITICAL)

`run_verification` requires `bib_path` — this is a hard contract. Calling
without a bib file raises ValueError. Manuscripts with `[@Key]` markers
also require a citations sidecar JSON.

Output is compatible with review_ops.generate_review_report's findings format:
  {criterion, severity, section, finding, suggestion}

See references/verification-rules.md for thresholds and patterns.
"""

import json
import os
import re
import subprocess
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

# Project root for repro and writing_ops imports
PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from repro.repro_logger import log_operation
from repro.citation_verify import (
    verify_doi,
    verify_arxiv,
    verify_citation,
    extract_arxiv_id_from_doi,
    _strip_diacritics,
)
try:
    from repro.url_verify import verify_url as _verify_url
    _URL_VERIFY_AVAILABLE = True
except ImportError:
    _URL_VERIFY_AVAILABLE = False
try:
    from repro.fulltext_fetch import fetch_full_text as _fetch_full_text, quote_in_full_text as _quote_in_full_text
    _FULLTEXT_FETCH_AVAILABLE = True
except ImportError:
    _FULLTEXT_FETCH_AVAILABLE = False
from writing_ops import parse_bib_file, _parse_author_parts


# ============================================================
# Hard contract
# ============================================================


class VerificationError(ValueError):
    """Raised when the verification gate cannot run safely (missing bib,
    missing sidecar when required, etc.). The caller MUST NOT save the
    manuscript — this is a refusal, not a warning."""


# Title-match threshold: normalized ratio below this is treated as a
# possible fabrication. Raised from 0.75 → 0.90 in Tier 1, and from
# 0.90 → 0.95 in Tier 5 (anti-misattribution): the old 0.90 ratio let
# titles where the LLM had drifted a few words still pass while the
# author list had been confabulated entirely. 0.95 demands a near-exact
# title match, while the new author check (below) catches misattribution
# even when the title is correct.
TITLE_MATCH_THRESHOLD = 0.95

# Author validation thresholds (Tier 5).
#   FIRST_AUTHOR_MATCH_THRESHOLD: normalized similarity between the bib
#   first-author surname and the live first-author surname; below this
#   we treat the first author as mismatched.
#   COAUTHOR_JACCARD_MIN: minimum Jaccard overlap between bib author
#   surnames and live author surnames (set-based; copes with bib lists
#   truncated to a few authors).
#   AUTHOR_LIST_TRUNCATION_MARKER: bib entries that explicitly say
#   "and others" are treated as wildcard-tail (only first author is
#   compared) so legitimately-short bib lists do not trip the check.
FIRST_AUTHOR_MATCH_THRESHOLD = 0.85
COAUTHOR_JACCARD_MIN = 0.70
AUTHOR_LIST_TRUNCATION_MARKER = "others"

# Minimum quote length in the citations sidecar. Raised from 20 → 80
# in Tier 1: 20 chars fits inside a single clause and can't prove
# grounding; 80 chars forces a full sentence or two.
MIN_QUOTE_CHARS = 80

# Minimum token Jaccard overlap between a sidecar quote and the
# manuscript sentence containing its [@Key] marker (Tier C3).
# 0.30 is deliberately loose to avoid false positives on legitimate
# paraphrasing; start MAJOR and promote to CRITICAL after calibration.
_CLAIM_QUOTE_JACCARD_MIN = 0.30

# Paperclip citation anchor format. Doc id is the directory name under
# /papers/ (alphanumeric + underscore + dot). Line anchors can be a
# single L45, a range L45-L52, or a comma list L45,L120,L210.
PAPERCLIP_ANCHOR_RE = re.compile(
    r"^https://citations\.gxl\.ai/papers/[A-Za-z0-9_.]+#L\d+(?:-L\d+)?(?:,L\d+(?:-L\d+)?)*$"
)


# ============================================================
# Configuration
# ============================================================

# Citation density thresholds: minimum citations per paragraph by section
CITATION_DENSITY_MIN = {
    "introduction": 2,
    "intro": 2,
    "background": 2,
    "discussion": 1,
    "results": 0,  # results sections are typically self-contained
    "methods": 1,
    "abstract": 0,
    "conclusion": 1,
}

# Hedging escalation pairs: (source_phrase, draft_phrase) where draft
# overstates relative to source. Each is a flagged finding.
HEDGING_ESCALATIONS = [
    (r"\bsuggests?\b", r"\bproves?\b"),
    (r"\bsuggests?\b", r"\bdemonstrates?\b"),
    (r"\bmay\b", r"\bdoes\b"),
    (r"\bmight\b", r"\bdoes\b"),
    (r"\bcould\b", r"\bdoes\b"),
    (r"\bassociated with\b", r"\bcaused by\b"),
    (r"\bcorrelat(e|ed|es)\b", r"\bcaus(e|ed|es)\b"),
    (r"\bpreliminary\b", r"\bdefinitive\b"),
    (r"\bappears?\b", r"\bis\b"),
    (r"\bsuggests?\b", r"\bestablishes?\b"),
    (r"\bsupports?\b", r"\bproves?\b"),
    (r"\blikely\b", r"\bcertainly\b"),
    (r"\bpossibly\b", r"\bdefinitely\b"),
]

# Phase 8 — scope-mismatch escalation pairs. Identical structure to
# HEDGING_ESCALATIONS, but covers shifts in *who* / *how many* / *what
# system* the claim applies to. These are the dominant overclaim shape
# in biomedical and clinical writing — the source studies one population
# (mice, n=12, in vitro) and the draft generalizes to a wider one.
#
# Each pair fires when the source-phrase pattern matches a sidecar quote
# AND the draft-phrase pattern matches the manuscript sentence containing
# the [@Key] marker, AND the draft-phrase is NOT in the source.
SCOPE_ESCALATIONS = [
    # Animal model → human / clinical
    (r"\b(?:in\s+)?mice\b",                     r"\b(?:in\s+)?(?:patients|humans|people)\b"),
    (r"\b(?:in\s+)?rats\b",                     r"\b(?:in\s+)?(?:patients|humans|people)\b"),
    (r"\b(?:in\s+)?(?:rodents?|murine)\b",      r"\b(?:in\s+)?(?:patients|humans|people)\b"),
    (r"\bnon[- ]?human primates?\b",            r"\b(?:in\s+)?(?:patients|humans|people)\b"),
    (r"\banimal\s+model(?:s)?\b",               r"\bclinical\b"),
    (r"\bpreclinical\b",                        r"\bclinical(?:ly)?\b"),
    # In vitro → in vivo / clinical
    (r"\bin\s+vitro\b",                         r"\bin\s+vivo\b"),
    (r"\bin\s+vitro\b",                         r"\b(?:in\s+)?(?:patients|humans|people|clinical)\b"),
    (r"\bcell\s+line(?:s)?\b",                  r"\bin\s+vivo\b"),
    (r"\bex\s+vivo\b",                          r"\bin\s+vivo\b"),
    # Simulation / computational → empirical
    (r"\b(?:in\s+silico|simulation|computational(?:ly)?|modeled|simulated)\b",
                                                r"\b(?:empirical(?:ly)?|experimental(?:ly)?|observed|measured)\b"),
    # Small / pilot → general
    (r"\bpilot\s+stud(?:y|ies)\b",              r"\b(?:established|proven|demonstrated)\b"),
    (r"\bpreliminary\b",                        r"\b(?:established|proven|definitive)\b"),
    (r"\bcase\s+report(?:s)?\b",                r"\b(?:patients|population|generally|broadly)\b"),
    (r"\bcase\s+series\b",                      r"\b(?:patients|population|generally|broadly)\b"),
    (r"\bsingle[- ]center\b",                   r"\bgenerally\b"),
    # Single cohort / single trial → universal
    (r"\bin\s+(?:our|this)\s+cohort\b",         r"\b(?:in\s+)?(?:all|every|patients|generally|broadly)\b"),
    (r"\b(?:our|this)\s+stud(?:y|ies)\b",       r"\b(?:always|universally|in\s+general)\b"),
    # Specific subgroup → broader population
    (r"\bin\s+(?:adults?|elderly|children|pediatric)\b",
                                                r"\b(?:in\s+)?(?:all\s+ages|the\s+general\s+population|broadly)\b"),
    # Observational / cross-sectional → causal
    (r"\bobservational\b",                      r"\bcaus(?:e|ed|es|ing|ation|ative)\b"),
    (r"\bcross[- ]sectional\b",                 r"\bcaus(?:e|ed|es|ing|ation|ative)\b"),
    # Specific dose / regimen → "any"
    (r"\bat\s+(?:high|low|specific)\s+dose(?:s)?\b",
                                                r"\b(?:at\s+(?:any|all)\s+doses?|regardless\s+of\s+dose)\b"),
]

# Common scientific abbreviation pattern (2-6 uppercase letters, optionally
# with digits). Excludes well-known acronyms that don't need definition.
WELL_KNOWN_ABBREVS = {
    "DNA", "RNA", "PCR", "CT", "MRI", "USA", "UK", "EU", "WHO", "FDA",
    "NIH", "NSF", "PI", "MD", "PhD", "MSc", "BSc", "AI", "ML", "API",
    "HTTP", "URL", "PDF", "CSV", "JSON", "XML", "SQL", "UV", "IR",
}

# Statistical reporting patterns
P_VALUE_PATTERN = re.compile(r"p\s*[<>=≤≥]\s*0?\.\d+", re.IGNORECASE)
TEST_STAT_PATTERN = re.compile(
    r"\b(?:t|F|χ²|chi-?square|z|U|H|r|R²|d|η²)\s*\(\s*\d",
    re.IGNORECASE,
)
EFFECT_SIZE_PATTERN = re.compile(
    r"\b(?:Cohen'?s d|η²|eta\s*squared|R²|r²|odds ratio|OR|hazard ratio|HR|"
    r"risk ratio|RR|effect size|95%\s*CI)\b",
    re.IGNORECASE,
)

# Citation marker patterns.
#
# Phase 9: GOOD_MARKER previously matched ONLY `[@Key]` (no locator suffix).
# A pandoc-style draft using `[@Smith2020, p. 5]` or `[@Smith2020; @Jones2019]`
# silently fell into pure-expertise mode (extract_used_keys returned empty),
# which skipped the entire bib + sidecar + provenance contract. That was a
# fundamental fall-through. Now:
#   - GOOD_MARKER accepts the locator suffix.
#   - MULTI_MARKER accepts both ; (canonical pandoc) and , (sometimes seen).
#   - BROAD_MARKER_RE is the fail-safe detector: ANY `[@\w` substring counts
#     as a cite-like marker; if the strict extractor returns empty while
#     BROAD matches, the gate refuses (Phase 9 unparseable-marker check).
GOOD_MARKER = re.compile(
    r"\[@([A-Za-z][A-Za-z0-9_-]*[a-z]?)(?:\s*[,;:][^\]]*)?\]"
)
MULTI_MARKER = re.compile(
    r"\[@([A-Za-z][A-Za-z0-9_-]*"
    r"(?:\s*[,;]\s*@?[A-Za-z][A-Za-z0-9_-]*)*"
    r"(?:\s*[,;:][^\]]*)?)\]"
)
BROAD_MARKER_RE = re.compile(r"\[@[A-Za-z][A-Za-z0-9_-]*")
KEY_INSIDE_BRACKET_RE = re.compile(r"@([A-Za-z][A-Za-z0-9_-]*[a-z]?)")
MALFORMED_MARKER_PATTERNS = [
    (re.compile(r"@([A-Za-z][A-Za-z0-9_-]*)\]"), r"[@\1]"),  # missing [
    (re.compile(r"\[@\s+([A-Za-z][A-Za-z0-9_-]*)\]"), r"[@\1]"),  # space after @
    (re.compile(r"\[@([A-Za-z][A-Za-z0-9_-]*)\s+\]"), r"[@\1]"),  # space before ]
]


# ============================================================
# Phase A: Citation Mechanics (auto-fixable)
# ============================================================


def fix_citation_markers(text: str) -> tuple[str, list[dict]]:
    """Auto-fix common malformed citation markers.

    Returns (fixed_text, list_of_fixes_applied).
    """
    fixes = []
    fixed = text
    for pattern, replacement in MALFORMED_MARKER_PATTERNS:
        matches = pattern.findall(fixed)
        if matches:
            fixed = pattern.sub(replacement, fixed)
            for m in matches:
                fixes.append({
                    "type": "citation_marker",
                    "original": pattern.pattern,
                    "fixed_to": replacement,
                    "key": m if isinstance(m, str) else m[0] if m else "",
                })
    return fixed, fixes


def extract_used_keys(text: str) -> set[str]:
    """Return the set of citation keys referenced by [@Key] markers.

    Phase 9: replaced the brittle MULTI_MARKER + ;-split with a robust
    in-bracket extractor — find every [...] block that starts with @ and
    pull all @Key tokens from inside, regardless of locator suffix or
    separator (`;`, `,`).
    """
    used: set[str] = set()
    for block in re.finditer(r"\[@[^\]\n]+\]", text):
        for key in KEY_INSIDE_BRACKET_RE.findall(block.group(0)):
            used.add(key.lower())
    return used


def has_citation_markers(text: str) -> bool:
    """Phase 9: did the manuscript intend to cite anything?

    Returns True if any `[@\\w...` substring appears, even if
    `extract_used_keys` cannot parse it. Used by the unparseable-marker
    fail-closed check so a draft with mangled markers cannot fall into
    pure-expertise mode.
    """
    return bool(BROAD_MARKER_RE.search(text))


def normalize_for_match(s: str) -> str:
    """Unicode + punctuation-preserving normalization for title comparison.

    Tier 1 change: previously stripped every non-alphanumeric character,
    which collapsed 'The Role of A in B' and 'The Role of A in B and C'
    onto near-identical strings and let cite-laundering slip through. We
    now keep whitespace and common punctuation so that a missing subtitle
    or appended clause is visible to the ratio check.
    """
    if not s:
        return ""
    # NFKC folds ligatures, compatibility forms, and most width variants.
    s = unicodedata.normalize("NFKC", s)
    # Strip LaTeX commands FIRST (\textbf, \LaTeX, \&, etc) so they
    # don't merge with their following brace argument and grow into an
    # over-greedy match. Word-boundary anchored to keep "\&" trailing
    # punctuation intact.
    s = re.sub(r"\\[a-zA-Z]+\b", "", s)
    # Then strip BibTeX protected-case braces like {AI} -> AI. These
    # are typographic, not semantic, and would otherwise tank the
    # title-similarity score against the live record.
    s = re.sub(r"\{([^{}]*)\}", r"\1", s)
    # Fold typographic quotes/dashes to ASCII so "—" vs "-" doesn't affect
    # the comparison.
    fold = str.maketrans({
        "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
        "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"',
        "\u2013": "-", "\u2014": "-", "\u2212": "-", "\u00a0": " ",
    })
    s = s.translate(fold).lower()
    # Collapse whitespace but keep punctuation.
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _title_tokens(s: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", s.lower()) if t}


def title_similarity(a: str, b: str) -> float:
    """Ratio between two titles. 1.0 = identical.

    We combine a character-level SequenceMatcher ratio (catches
    whitespace/punctuation drift) with a token-set Jaccard ratio
    (catches appended/dropped words that character matching can
    overweight). The returned score is the minimum of the two so a
    failure on either dimension drags the score below the threshold —
    this is deliberately stricter than the old alphanumeric-only
    SequenceMatcher.
    """
    na = normalize_for_match(a)
    nb = normalize_for_match(b)
    if not na or not nb:
        return 0.0
    char_ratio = SequenceMatcher(None, na, nb).ratio()
    ta, tb = _title_tokens(na), _title_tokens(nb)
    if not ta or not tb:
        return char_ratio
    jaccard = len(ta & tb) / len(ta | tb)
    return min(char_ratio, jaccard)


def check_bib_key_match(text: str, bib_entries: list[dict]) -> list[dict]:
    """Verify every [@Key] in text has a matching .bib entry."""
    bib_keys = {e.get("key", "").lower() for e in bib_entries if e.get("key")}
    findings = []

    for key in sorted(extract_used_keys(text)):
        if key not in bib_keys:
            findings.append({
                "criterion": "Citation Mechanics",
                "severity": "major",
                "section": "Citations",
                "finding": f"Citation marker [@{key}] has no matching .bib entry.",
                "suggestion": (
                    f"Add an entry with key '{key}' to your .bib file, or "
                    f"check for typos in the marker."
                ),
            })

    return findings


# ============================================================
# Phase B: Completeness Metrics (flagged)
# ============================================================


def detect_section_type(heading: str) -> str:
    """Map a section heading to its type for citation density rules."""
    h = heading.lower().strip("# ").strip()
    for key in CITATION_DENSITY_MIN:
        if key in h:
            return key
    return "other"


def check_citation_density(text: str) -> list[dict]:
    """Count citations per paragraph by section, flag below threshold."""
    findings = []
    lines = text.split("\n")
    current_section = "other"
    current_paragraph = []
    paragraph_idx = 0

    def evaluate_paragraph(para: list[str], section: str, idx: int):
        if not para:
            return
        para_text = " ".join(para)
        if len(para_text.strip()) < 50:  # skip very short paragraphs
            return
        threshold = CITATION_DENSITY_MIN.get(section, 0)
        if threshold == 0:
            return
        cite_count = len(MULTI_MARKER.findall(para_text))
        if cite_count < threshold:
            findings.append({
                "criterion": "Completeness — Citation Density",
                "severity": "minor",
                "section": section.title(),
                "finding": (
                    f"Paragraph {idx} in {section} has {cite_count} citations "
                    f"(minimum {threshold} expected)."
                ),
                "suggestion": (
                    f"Add citations to support claims in this paragraph, or "
                    f"verify it's a transition/summary that doesn't need them."
                ),
            })

    for line in lines:
        if line.startswith("#"):
            evaluate_paragraph(current_paragraph, current_section, paragraph_idx)
            current_paragraph = []
            current_section = detect_section_type(line)
            paragraph_idx = 0
        elif line.strip() == "":
            evaluate_paragraph(current_paragraph, current_section, paragraph_idx)
            current_paragraph = []
            paragraph_idx += 1
        else:
            current_paragraph.append(line)

    evaluate_paragraph(current_paragraph, current_section, paragraph_idx)
    return findings


def check_figure_references(text: str) -> list[dict]:
    """Verify figure references are sequential and used."""
    findings = []
    fig_refs = re.findall(r"\bFigure\s+(\d+)\b", text, re.IGNORECASE)
    if not fig_refs:
        return findings

    nums = sorted(set(int(n) for n in fig_refs))
    expected = list(range(1, max(nums) + 1))
    missing = [n for n in expected if n not in nums]

    if missing:
        findings.append({
            "criterion": "Completeness — Figure References",
            "severity": "minor",
            "section": "Figures",
            "finding": (
                f"Figure references jump: found {nums}, missing "
                f"{missing}. Figures should be numbered sequentially."
            ),
            "suggestion": (
                "Renumber figure references so they're sequential, or add "
                "the missing figures."
            ),
        })

    return findings


def check_abbreviations(text: str) -> list[dict]:
    """Verify uppercase abbreviations have a definition on first use."""
    findings = []
    # Find candidate abbreviations: 2-6 uppercase letters, possibly with digits
    abbrev_pattern = re.compile(r"\b([A-Z]{2,6}\d*)\b")

    seen_abbrevs = set()
    for match in abbrev_pattern.finditer(text):
        abbrev = match.group(1)
        if abbrev in WELL_KNOWN_ABBREVS or abbrev in seen_abbrevs:
            continue
        seen_abbrevs.add(abbrev)

        # Check if it's defined within ±50 chars (definition pattern: "phrase (ABBR)")
        start = max(0, match.start() - 100)
        end = min(len(text), match.end() + 5)
        context = text[start:end]
        # Look for "( ABBR )" preceded by lowercase words
        def_pattern = re.compile(rf"\b[a-z][\w\s-]+\s*\(\s*{re.escape(abbrev)}\s*\)")
        if not def_pattern.search(context):
            findings.append({
                "criterion": "Completeness — Abbreviations",
                "severity": "minor",
                "section": "Style",
                "finding": (
                    f"Abbreviation '{abbrev}' used without definition on "
                    f"first occurrence."
                ),
                "suggestion": (
                    f"Define on first use: 'full phrase ({abbrev})'."
                ),
            })

    return findings


# ============================================================
# Phase C: DOI Verification (uses repro/citation_verify.py)
# ============================================================


# ============================================================
# Tier 3: preprint / gray-literature detection
# ============================================================


GRAY_LIT_TYPES = {"unpublished", "techreport", "misc"}
ARXIV_DOI_PREFIXES = ("10.48550/arxiv",)


def _is_arxiv_entry(entry: dict) -> bool:
    if (entry.get("archivePrefix") or "").strip().lower() == "arxiv":
        return True
    if (entry.get("eprint") or "").strip():
        return True
    doi = (entry.get("doi") or "").strip().lower()
    return any(doi.startswith(prefix) for prefix in ARXIV_DOI_PREFIXES)


def _approval_status(
    entry: dict,
    *,
    flag_field: str,
    reason_field: str,
    date_field: str,
) -> tuple[str, str]:
    """Phase 9: shared reason+date validator for the three opt-in escape
    hatches (`unverifiable`, `gray_lit`, `historical`). All three previously
    accepted a bare `{approved}` tag, allowing a retroactive rubber-stamp.
    Now each requires:
      * the `{flag_field}` field set to "approved"
      * a `{reason_field}` of >= _UNVERIFIABLE_REASON_MIN_CHARS chars,
        not in the generic-template blocklist
      * a `{date_field}` in ISO YYYY-MM-DD form

    Returns ("approved", ""), ("incomplete", "<diagnostic>"), or ("none", "").
    """
    raw = (entry.get(flag_field) or "").strip()
    if not raw:
        return ("none", "")
    if raw.lower() != "approved":
        return ("none", "")

    reason = (entry.get(reason_field) or "").strip()
    date = (entry.get(date_field) or "").strip()

    problems: list[str] = []
    if not reason:
        problems.append(
            f"missing `{reason_field} = {{...}}` (must explain the specific "
            f"reason this entry uses the {flag_field} approval, "
            f"≥{_UNVERIFIABLE_REASON_MIN_CHARS} chars)"
        )
    elif len(reason) < _UNVERIFIABLE_REASON_MIN_CHARS:
        problems.append(
            f"`{reason_field}` is too short ({len(reason)} < "
            f"{_UNVERIFIABLE_REASON_MIN_CHARS} chars) — describe the specific "
            "obstacle"
        )
    elif reason.lower() in _UNVERIFIABLE_REASON_BLOCKLIST:
        problems.append(
            f"`{reason_field}` is a generic template ('{reason}') — "
            "write a specific justification"
        )
    if not date:
        problems.append(
            f"missing `{date_field} = {{YYYY-MM-DD}}` (the date this approval "
            "was granted)"
        )
    elif not _UNVERIFIABLE_DATE_RE.match(date):
        problems.append(
            f"`{date_field}` is not ISO YYYY-MM-DD ('{date}')"
        )

    if problems:
        return ("incomplete", "; ".join(problems))
    return ("approved", "")


def _gray_lit_status(entry: dict) -> tuple[str, str]:
    return _approval_status(
        entry,
        flag_field="gray_lit",
        reason_field="gray_lit_reason",
        date_field="gray_lit_date",
    )


def _gray_lit_approved(entry: dict) -> bool:
    """Phase 9: bare `gray_lit = {approved}` is no longer enough — must also
    carry `gray_lit_reason` (specific) and `gray_lit_date` (ISO).
    """
    status, _ = _gray_lit_status(entry)
    return status == "approved"


def _is_gray_lit(entry: dict) -> bool:
    entry_type = (entry.get("entry_type") or "").strip().lower()
    if entry_type in GRAY_LIT_TYPES:
        return True
    return _is_arxiv_entry(entry)


_UNVERIFIABLE_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_UNVERIFIABLE_REASON_BLOCKLIST = {
    "approved",
    "ok",
    "n/a",
    "na",
    "tbd",
    "pure expertise",
    "tutorial with no primary sources",
    "tutorial with no primary sources, pure expertise",
    "no doi",
    "no-doi",
}
_UNVERIFIABLE_REASON_MIN_CHARS = 30


def _unverifiable_status(entry: dict) -> tuple[str, str]:
    """A1 opt-in: parse the `unverifiable` contract from a bib entry.

    The legacy ``unverifiable = {approved}`` form is no longer sufficient on its
    own — Phase 8 (2026-04-26) requires every approval to carry an explicit
    reason and an ISO date so the audit trail records *who decided what, when*.

    Returns one of:
      ("none",         "")                 — field absent or not approved
      ("approved",     "")                 — approved AND reason+date both present and valid
      ("incomplete",   "<diagnostic>")     — approved but missing/blocklisted reason or bad date
    """
    raw = (entry.get("unverifiable") or "").strip()
    if not raw:
        return ("none", "")
    if raw.lower() != "approved":
        return ("none", "")

    reason = (entry.get("unverifiable_reason") or "").strip()
    date = (entry.get("unverifiable_date") or "").strip()

    problems: list[str] = []
    if not reason:
        problems.append(
            "missing `unverifiable_reason = {...}` (must explain why this "
            "source cannot be programmatically verified, ≥30 chars)"
        )
    elif len(reason) < _UNVERIFIABLE_REASON_MIN_CHARS:
        problems.append(
            f"`unverifiable_reason` is too short ({len(reason)} < "
            f"{_UNVERIFIABLE_REASON_MIN_CHARS} chars) — describe the specific "
            "obstacle (paywall searched, OA not available; in-press; private "
            "communication on date X; etc.)"
        )
    elif reason.lower() in _UNVERIFIABLE_REASON_BLOCKLIST:
        problems.append(
            f"`unverifiable_reason` is a generic template ('{reason}') — "
            "write a specific justification"
        )
    if not date:
        problems.append(
            "missing `unverifiable_date = {YYYY-MM-DD}` (the date this "
            "approval was granted)"
        )
    elif not _UNVERIFIABLE_DATE_RE.match(date):
        problems.append(
            f"`unverifiable_date` is not ISO YYYY-MM-DD ('{date}')"
        )

    if problems:
        return ("incomplete", "; ".join(problems))
    return ("approved", "")


def _unverifiable_approved(entry: dict) -> bool:
    """Backward-compatible wrapper. Returns True only when the contract is
    fully satisfied (approved + reason ≥30 chars + ISO date)."""
    status, _ = _unverifiable_status(entry)
    return status == "approved"


def _historical_status(entry: dict) -> tuple[str, str]:
    return _approval_status(
        entry,
        flag_field="historical",
        reason_field="historical_reason",
        date_field="historical_date",
    )


def _historical_approved(entry: dict) -> bool:
    """A2 opt-in: bib entry carries `historical = {approved}` for references
    that pre-date the DOI/arXiv system (typically pre-1950) and thus have no
    machine-verifiable identifier by design.

    Phase 9: bare `historical = {approved}` no longer suffices — `historical_reason`
    (specific, ≥30 chars) and `historical_date` (ISO YYYY-MM-DD) are required.
    """
    status, _ = _historical_status(entry)
    return status == "approved"


def _is_pre_1950(entry: dict) -> bool:
    """Return True if the entry's year field is a 4-digit year before 1950."""
    year_str = (entry.get("year") or "").strip()
    m = re.search(r"\b(\d{4})\b", year_str)
    if m:
        try:
            return int(m.group(1)) < 1950
        except ValueError:
            pass
    return False


def _is_url_only_misc(entry: dict) -> bool:
    """Return True if this is a @misc / @online entry with only a URL identifier
    (no DOI, no eprint, no PMID) — the A3 URL-livecheck candidate."""
    entry_type = (entry.get("entry_type") or "").strip().lower()
    if entry_type not in ("misc", "online", "electronic", "www"):
        return False
    doi = (entry.get("doi") or "").strip()
    eprint = (entry.get("eprint") or "").strip()
    pmid = (entry.get("pmid") or "").strip()
    url = (entry.get("url") or "").strip()
    return bool(url) and not doi and not eprint and not pmid


# ---------------------------------------------------------------------------
# Tier 5: Author validation helpers
# ---------------------------------------------------------------------------


_LATEX_BRACE_RE = re.compile(r"\\[a-zA-Z]+|[\{\}\\\"'`~^]")


_LATEX_LETTER_SUB = re.compile(r"\\([ijlLoOaAeEuU])\b")

def _normalize_surname(name: str) -> str:
    """Lowercase, strip diacritics + LaTeX braces, fold whitespace."""
    if not name:
        return ""
    # LaTeX letter-producing commands (\i, \j, \l, \o ...) must be
    # replaced with their letter BEFORE stripping other commands,
    # otherwise \i in e.g. Dess{\`\i} (= Dessì) loses the 'i'.
    cleaned = _LATEX_LETTER_SUB.sub(r"\1", name)
    # Strip LaTeX accent/command prefixes and brace/quote noise.
    cleaned = _LATEX_BRACE_RE.sub("", cleaned)
    cleaned = _strip_diacritics(cleaned).lower().strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _bib_surnames(author_str: str) -> tuple[list[str], bool]:
    """Return (normalized surnames, has_truncation_marker).

    has_truncation_marker is True if the bib field used "and others",
    BibTeX's idiomatic "et al." token. In that case the caller should
    only enforce the first-author check — the trailing list is missing
    by design, not by hallucination.
    """
    if not author_str:
        return [], False

    # Detect "and others" / "et al." truncation markers BEFORE parsing,
    # then strip them so _parse_author_parts doesn't choke.
    has_truncation = False
    cleaned = author_str
    for pattern in (
        r"\s+and\s+others\b",
        r"\s+et\s+al\.?",
    ):
        if re.search(pattern, cleaned, re.IGNORECASE):
            has_truncation = True
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    parts = _parse_author_parts(cleaned)
    surnames = [_normalize_surname(last) for last, _first in parts if last.strip()]
    return surnames, has_truncation


def _author_check_finding(
    key: str,
    backend: str,
    bib_authors_display: str,
    live_authors: list[str],
    reason: str,
) -> dict:
    return {
        "criterion": "Bib Integrity (Tier 5)",
        "severity": "critical",
        "section": "Citations",
        "finding": (
            f"Author mismatch for key '{key}' ({backend} backend): "
            f"bib says '{bib_authors_display}' but the live record "
            f"lists {live_authors[:6]}{'...' if len(live_authors) > 6 else ''}. "
            f"{reason} This is a possible misattribution — the cited paper "
            "exists, but the bib author list does not match it."
        ),
        "suggestion": (
            "Fix the bib `author` field to match the live record exactly "
            "(family names + ordering), or replace the citation with the "
            "correct paper for the authors you meant to cite. If the bib "
            "uses an intentional 'and others' truncation, ensure the first "
            "author at least matches."
        ),
    }


def compare_authors(
    bib_authors_str: str,
    live_authors: list[str],
) -> tuple[bool, str]:
    """Compare bib author string to a live author list.

    Returns (passed, reason). reason is empty when passed.

    Logic:
      * Empty bib → fail (cannot verify).
      * Empty live → pass with note (e.g. corporate author returned
        no individuals from CrossRef; falls back to title match).
      * "and others" truncation → only check first surname.
      * Otherwise: first-author similarity + co-author Jaccard.
    """
    bib_surnames, has_truncation = _bib_surnames(bib_authors_str)
    live_surnames = [_normalize_surname(s) for s in live_authors if s]

    if not bib_surnames:
        return False, "Bib author field is empty or unparseable."
    if not live_surnames:
        # A7: live backend returned no individual authors (corporate author,
        # CrossRef quirk, or malformed record). Rather than a silent pass,
        # return a sentinel so check_bib_integrity can surface a MAJOR —
        # "we could not confirm authors" is not the same as "authors match".
        return True, "__EMPTY_LIVE__"

    bib_first = bib_surnames[0]
    live_first = live_surnames[0]
    first_ratio = SequenceMatcher(None, bib_first, live_first).ratio()
    first_match = first_ratio >= FIRST_AUTHOR_MATCH_THRESHOLD or bib_first == live_first

    if has_truncation:
        if not first_match:
            return False, (
                f"First author '{bib_first}' does not match live first "
                f"author '{live_first}' (similarity {first_ratio:.2f}; "
                f"bib used 'and others' so only the first author was checked)."
            )
        return True, ""

    bib_set = set(bib_surnames)
    live_set = set(live_surnames)
    intersection = bib_set & live_set
    union = bib_set | live_set
    jaccard = len(intersection) / len(union) if union else 0.0

    # Either a clean first-author match plus reasonable Jaccard, OR a
    # high Jaccard alone (covers the case where bib uses given-name-
    # last vs family-only and the first-author normalization disagrees).
    if first_match and jaccard >= COAUTHOR_JACCARD_MIN:
        return True, ""
    if jaccard >= 0.9:
        return True, ""

    # Build a reason string that names the missing/extra authors so the
    # writer-agent can fix the bib without reading the live list.
    extra_in_bib = sorted(bib_set - live_set)
    missing_from_bib = sorted(live_set - bib_set)
    parts = [
        f"first-author match={first_match} (similarity {first_ratio:.2f}; "
        f"threshold {FIRST_AUTHOR_MATCH_THRESHOLD}); "
        f"co-author Jaccard {jaccard:.2f} (threshold {COAUTHOR_JACCARD_MIN})."
    ]
    if extra_in_bib:
        parts.append(f"In bib but not in live record: {extra_in_bib}.")
    if missing_from_bib:
        parts.append(f"In live record but not in bib: {missing_from_bib[:4]}.")
    return False, " ".join(parts)


def check_bib_integrity(
    used_keys: set[str],
    bib_entries: list[dict],
) -> list[dict]:
    """For every USED bib entry: verify authenticity + provenance.

    Tier 5 behavior:
      * arXiv eprint entries are verified via the arXiv Atom API
        (was: short-circuited as gray-lit MAJOR before any check).
      * After title-similarity passes, the bib author list is compared
        against the live record (CrossRef OR arXiv) using a combined
        first-author + Jaccard test. Mismatches are CRITICAL — this is
        the path that catches confabulated co-authors (e.g., a real DOI
        cited with a fabricated author list).
      * The preprint warning still fires as MAJOR (preprints are not
        peer-reviewed), but it no longer skips the title/author check.
        `gray_lit = {approved}` suppresses the warning while still
        running the verification.
      * CrossRef / arXiv ConnectionError remains MAJOR (fail-closed).
      * Title mismatch, retraction, and author mismatch are CRITICAL.

    Only used_keys are checked — uncited bib entries are ignored.
    """
    findings: list[dict] = []
    if not used_keys:
        return findings

    by_key = {e.get("key", "").lower(): e for e in bib_entries if e.get("key")}

    for key in sorted(used_keys):
        entry = by_key.get(key)
        if not entry:
            continue  # already flagged by check_bib_key_match
        doi = (entry.get("doi") or "").strip()
        eprint = (entry.get("eprint") or "").strip()
        pmid = (entry.get("pmid") or "").strip()
        bib_title = (entry.get("title") or "").strip()
        bib_authors = (entry.get("author") or "").strip()

        # Preprint warning — still emitted, but does NOT skip verification.
        # Phase 9: split bare/incomplete `gray_lit = {approved}` from a clean
        # absence so the writer learns that bare-tag approvals are no longer
        # valid (they used to silently downgrade the warning).
        gl_status, gl_problem = _gray_lit_status(entry)
        if _is_gray_lit(entry) and gl_status != "approved":
            if gl_status == "incomplete":
                findings.append({
                    "criterion": "Bib Integrity (gray_lit incomplete)",
                    "severity": "critical",
                    "section": "Citations",
                    "finding": (
                        f"Bib entry '{key}' is a preprint and carries "
                        f"`gray_lit = {{approved}}` but the approval "
                        f"contract is incomplete: {gl_problem}. Phase 9 "
                        "requires both `gray_lit_reason` and "
                        "`gray_lit_date` alongside the flag — bare-tag "
                        "approvals are no longer accepted."
                    ),
                    "suggestion": (
                        "Add reason + date next to the bib entry, e.g.:\n"
                        "  gray_lit = {approved},\n"
                        "  gray_lit_reason = {arXiv preprint, peer-reviewed "
                        "version not yet published},\n"
                        "  gray_lit_date = {2026-04-26}"
                    ),
                })
            else:
                findings.append({
                    "criterion": "Bib Integrity",
                    "severity": "major",
                    "section": "Citations",
                    "finding": (
                        f"Bib entry '{key}' is a preprint or gray-literature "
                        f"reference (entry_type='{entry.get('entry_type')}', "
                        f"eprint='{eprint}'). Preprints are flagged by default "
                        "— they are not peer-reviewed and may be withdrawn or "
                        "superseded."
                    ),
                    "suggestion": (
                        "Either replace with the peer-reviewed version (once "
                        "published), or add the full Phase 9 contract: "
                        "`gray_lit = {approved}`, "
                        "`gray_lit_reason = {...}`, "
                        "`gray_lit_date = {YYYY-MM-DD}`. "
                        "Verification still runs regardless of this flag."
                    ),
                })

        # A1/A2/A3: entries with no machine-verifiable identifier.
        if not eprint and not doi and not pmid:
            # A3: URL-only @misc — run livecheck before deciding severity.
            if _is_url_only_misc(entry) and _URL_VERIFY_AVAILABLE:
                url = (entry.get("url") or "").strip()
                url_result = _verify_url(url, bib_title)
                if not url_result["is_accessible"]:
                    findings.append({
                        "criterion": "Bib Integrity (A3 — URL livecheck)",
                        "severity": "critical",
                        "section": "Citations",
                        "finding": (
                            f"URL-only bib entry '{key}' is inaccessible: "
                            f"{url_result['error']} (URL: {url})"
                        ),
                        "suggestion": (
                            "Update the URL or replace with an archival "
                            "copy (e.g. Wayback Machine URL with a date). "
                            "A broken URL is as bad as a missing citation."
                        ),
                    })
                elif url_result.get("error"):
                    # Accessible but title mismatch
                    findings.append({
                        "criterion": "Bib Integrity (A3 — URL livecheck)",
                        "severity": "critical",
                        "section": "Citations",
                        "finding": (
                            f"URL bib entry '{key}': {url_result['error']}"
                        ),
                        "suggestion": (
                            "Verify the URL points to the correct resource. "
                            "If the page title doesn't match the bib title, "
                            "either fix the bib title or update the URL."
                        ),
                    })
                else:
                    # URL is live and title matches — demote to MAJOR
                    findings.append({
                        "criterion": "Bib Integrity (A3 — URL livecheck)",
                        "severity": "major",
                        "section": "Citations",
                        "finding": (
                            f"Bib entry '{key}' is a URL-only reference "
                            f"(no DOI/arXiv/PMID). URL resolves (HTTP "
                            f"{url_result['status_code']}) and title "
                            f"matches (ratio "
                            f"{url_result['title_match_ratio']:.2f}), "
                            "but the resource may move or disappear."
                        ),
                        "suggestion": (
                            "Consider archiving the URL (archive.org) and "
                            "adding the archived URL as a fallback. If a "
                            "DOI exists, prefer it over a bare URL."
                        ),
                    })
                continue

            # A2: historical references (pre-1950) with explicit approval.
            # Phase 9: the approval requires reason + date — bare-tag is
            # surfaced as CRITICAL ("historical incomplete") to match the
            # gray_lit and unverifiable contracts.
            if _is_pre_1950(entry):
                hist_status, hist_problem = _historical_status(entry)
                if hist_status == "approved":
                    findings.append({
                        "criterion": "Bib Integrity (A2 — historical)",
                        "severity": "major",
                        "section": "Citations",
                        "finding": (
                            f"Bib entry '{key}' is a pre-1950 historical "
                            "reference with no DOI/arXiv/PMID. Marked "
                            "`historical = {approved}` with full reason+date "
                            "contract — severity downgraded to MAJOR."
                        ),
                        "suggestion": (
                            "Verify manually against a reputable digitized "
                            "source (JSTOR, HathiTrust, Internet Archive) "
                            "and add an `url` field pointing to it."
                        ),
                    })
                    continue
                if hist_status == "incomplete":
                    findings.append({
                        "criterion": "Bib Integrity (A2 — historical incomplete)",
                        "severity": "critical",
                        "section": "Citations",
                        "finding": (
                            f"Bib entry '{key}' carries `historical = "
                            f"{{approved}}` but the approval contract is "
                            f"incomplete: {hist_problem}. Phase 9 requires "
                            "both `historical_reason` and `historical_date` "
                            "alongside the flag."
                        ),
                        "suggestion": (
                            "Add reason + date next to the bib entry, e.g.:\n"
                            "  historical = {approved},\n"
                            "  historical_reason = {Pre-1950 reference; "
                            "verified against the digitized JSTOR copy},\n"
                            "  historical_date = {2026-04-26}"
                        ),
                    })
                    continue

            # A1 opt-in: explicit `unverifiable = {approved}` by the user.
            # Phase 8: the contract now requires reason + ISO date alongside
            # the approval flag. Bare `unverifiable = {approved}` is treated
            # as an incomplete approval and stays CRITICAL.
            uv_status, uv_problem = _unverifiable_status(entry)
            if uv_status == "approved":
                findings.append({
                    "criterion": "Bib Integrity (A1 — unverifiable approved)",
                    "severity": "major",
                    "section": "Citations",
                    "finding": (
                        f"Bib entry '{key}' has no verifiable identifier "
                        "and carries the full `unverifiable = {approved}` "
                        "contract (reason + date). Severity capped at MAJOR."
                    ),
                    "suggestion": (
                        "Reason and date are recorded — keep them current. "
                        "If the source later gains a DOI/arXiv id, swap the "
                        "approval for the real identifier."
                    ),
                })
                continue
            if uv_status == "incomplete":
                findings.append({
                    "criterion": "Bib Integrity (A1 — unverifiable incomplete)",
                    "severity": "critical",
                    "section": "Citations",
                    "finding": (
                        f"Bib entry '{key}' is marked `unverifiable = "
                        "{approved}` but the approval contract is "
                        f"incomplete: {uv_problem}. Bare-tag approvals are "
                        "no longer accepted (Phase 8) — every "
                        "unverifiable downgrade must be auditable."
                    ),
                    "suggestion": (
                        "Add both fields next to the bib entry, e.g.:\n"
                        "  unverifiable = {approved},\n"
                        "  unverifiable_reason = {Personal communication "
                        "with X, no preprint planned for 12 months},\n"
                        "  unverifiable_date = {2026-04-26}"
                    ),
                })
                continue

            # A1 default: CRITICAL — no identifier, no approval.
            findings.append({
                "criterion": "Bib Integrity (A1 — no identifier)",
                "severity": "critical",
                "section": "Citations",
                "finding": (
                    f"Bib entry '{key}' has no DOI, arXiv eprint, PMID, "
                    "or URL — cannot verify authenticity. "
                    "This is a fabrication risk."
                ),
                "suggestion": (
                    "Add a DOI, arXiv id, PMID, or URL to this bib entry. "
                    "If the source genuinely has no identifier (personal "
                    "communication, in-press), add "
                    "`unverifiable = {approved}` to acknowledge this "
                    "explicitly. For pre-1950 sources, add "
                    "`historical = {approved}`."
                ),
            })
            continue

        cache_key = (doi.lower(), eprint.lower(), pmid.lower())
        try:
            result = verify_citation(entry)
            _LIVE_METADATA_CACHE[cache_key] = result
        except ValueError as e:
            _LIVE_METADATA_CACHE[cache_key] = {}
            if eprint or extract_arxiv_id_from_doi(doi):
                backend = "arxiv"
            elif pmid:
                backend = "pubmed"
            else:
                backend = "crossref"
            findings.append({
                "criterion": "Bib Integrity",
                "severity": "major",
                "section": "Citations",
                "finding": (
                    f"{backend.upper()} lookup failed for key '{key}' "
                    f"(doi='{doi}', eprint='{eprint}'): {e}"
                ),
                "suggestion": (
                    "Check the DOI / arXiv id for typos. If it's a preprint "
                    "not yet indexed, replace the citation or note it "
                    "explicitly."
                ),
            })
            continue
        except ConnectionError as e:
            _LIVE_METADATA_CACHE[cache_key] = {}
            if eprint or extract_arxiv_id_from_doi(doi):
                backend = "arxiv"
            elif pmid:
                backend = "pubmed"
            else:
                backend = "crossref"
            findings.append({
                "criterion": "Bib Integrity (network fail-closed)",
                "severity": "critical",
                "section": "Citations",
                "finding": (
                    f"Could not reach {backend} for key '{key}' "
                    f"(doi='{doi}', eprint='{eprint}', pmid='{pmid}'): {e}. "
                    "Fail-closed (Phase 8): a network outage is treated as "
                    "an unverified citation, not as silent passage. The save "
                    "is blocked until the lookup succeeds or the entry is "
                    "explicitly removed."
                ),
                "suggestion": (
                    "Re-run verification once the network is available. "
                    "If the source is genuinely unverifiable (private, "
                    "in-press), add `unverifiable = {approved}` with both "
                    "`unverifiable_reason` and `unverifiable_date` fields "
                    "to acknowledge it explicitly."
                ),
            })
            continue

        backend = result.get("source", "crossref")

        # A8: dual-id conflict (both eprint and doi present, titles disagree).
        if result.get("dual_id_conflict") is True:
            findings.append({
                "criterion": "Bib Integrity (A8 — dual-id conflict)",
                "severity": "critical",
                "section": "Citations",
                "finding": (
                    f"Bib entry '{key}' has BOTH an arXiv eprint AND a DOI "
                    "that point to different papers. "
                    f"{result.get('dual_id_detail', '')}"
                ),
                "suggestion": (
                    "Remove the incorrect identifier. The DOI and eprint "
                    "must reference the same paper — having both point to "
                    "different papers is a misattribution."
                ),
            })
            continue
        if result.get("dual_id_conflict") is None and result.get("dual_id_detail"):
            # Inconclusive — DOI lookup failed during cross-check
            findings.append({
                "criterion": "Bib Integrity (A8 — dual-id inconclusive)",
                "severity": "major",
                "section": "Citations",
                "finding": (
                    f"Bib entry '{key}' has both an arXiv eprint and a DOI "
                    "but the DOI could not be fetched for cross-check. "
                    f"{result.get('dual_id_detail', '')}"
                ),
                "suggestion": (
                    "Manually verify that the arXiv eprint and the DOI "
                    "refer to the same paper."
                ),
            })

        if result.get("is_retracted"):
            findings.append({
                "criterion": "Bib Integrity",
                "severity": "critical",
                "section": "Citations",
                "finding": (
                    f"Key '{key}' is RETRACTED: "
                    f"{result.get('retraction_info')}"
                ),
                "suggestion": (
                    "Remove this citation immediately. Cite the retraction "
                    "notice if relevant to your discussion."
                ),
            })
            continue

        live_title = (result.get("title") or "").strip()
        live_authors = result.get("authors") or []
        ratio = title_similarity(bib_title, live_title)
        if ratio < TITLE_MATCH_THRESHOLD:
            findings.append({
                "criterion": "Bib Integrity",
                "severity": "critical",
                "section": "Citations",
                "finding": (
                    f"Title mismatch for key '{key}' ({backend} backend): "
                    f"bib says '{bib_title[:80]}' but the live record "
                    f"resolves to '{live_title[:80]}' (similarity "
                    f"{ratio:.2f}). This is a possible fabrication — "
                    "the cited identifier and the bib title do not "
                    "belong to the same paper."
                ),
                "suggestion": (
                    "Fix the .bib title to match the actual paper at that "
                    "identifier, or replace the citation with the correct "
                    "DOI / arXiv id for the work you meant to cite."
                ),
            })
            continue

        # Tier 5 author validation. Runs after title check so the user gets
        # the most-specific failure first.
        passed, reason = compare_authors(bib_authors, live_authors)
        if not passed:
            findings.append(
                _author_check_finding(
                    key=key,
                    backend=backend,
                    bib_authors_display=bib_authors,
                    live_authors=live_authors,
                    reason=reason,
                )
            )
            continue
        # A7: empty-live sentinel — authors could not be confirmed.
        if reason == "__EMPTY_LIVE__":
            findings.append({
                "criterion": "Bib Integrity (A7 — authors unconfirmed)",
                "severity": "major",
                "section": "Citations",
                "finding": (
                    f"Live record for key '{key}' ({backend} backend) "
                    "returned no individual authors — author check is "
                    "unenforceable for this entry. Title matched; this "
                    "is likely a corporate author or malformed CrossRef "
                    "record."
                ),
                "suggestion": (
                    "Manually verify the author list is correct. If the "
                    "paper has a PMID, adding it to the bib entry may "
                    "unlock a richer PubMed record with individual authors."
                ),
            })

    return findings


# ============================================================
# Phase A5: Inline attribution detection (pure-expertise mode)
# ============================================================

# Matches "Smith et al. 2023", "Smith et al. (2023)", "Smith (2023)", etc.
_INLINE_ATTRIBUTION_RE = re.compile(
    r"\b([A-Z][a-z]{1,30}(?:\s+and\s+[A-Z][a-z]{1,30})?)"
    r"(?:\s+et\s+al\.?)?"
    r"\s*\(?\d{4}\)?",
)
# Explicit opt-out annotation. Phase 8 restricts the match to the document
# header (first 20 lines or YAML/comment frontmatter) — a no-cite buried in
# the middle of the body shouldn't suppress checks for everything above and
# below it. The reason field is captured for content + length validation.
_NO_CITE_ANNOTATION_RE = re.compile(
    r"<!--\s*no-cite:\s*(.+?)\s*-->",
    re.IGNORECASE,
)
_NO_CITE_HEADER_LINES = 20
_NO_CITE_REASON_MIN_CHARS = 30
_NO_CITE_REASON_BLOCKLIST = {
    "approved",
    "ok",
    "n/a",
    "na",
    "tbd",
    "tutorial",
    "blog",
    "expertise",
    "pure expertise",
    "tutorial with no primary sources",
    "tutorial with no primary sources, pure expertise",
    "no citations",
    "no cite",
}

# Patterns hinting at unanchored factual claims inside a no-cite block.
# These don't auto-fail; they emit a NOTE so the writer sees what kind of
# content slipped through unchecked.
_UNANCHORED_FACTUAL_PATTERNS = [
    re.compile(r"\b\d{1,3}(?:\.\d+)?\s*%", re.IGNORECASE),                       # 37% / 12.5%
    re.compile(r"\baccording to (?:the\s+)?[A-Z]"),                                # "According to WHO"
    re.compile(r"\b(?:study|studies|research|trial|paper) (?:found|shows?|showed|demonstrate[ds]?|reports?|reported|reveals?|revealed)", re.IGNORECASE),
    re.compile(r"\bresearchers? (?:found|showed|reported|demonstrated|reveal(?:ed)?)", re.IGNORECASE),
    re.compile(r"\bN\s*=\s*\d+\b"),                                                # sample sizes
    re.compile(r"\bpublished in\s+\d{4}\b", re.IGNORECASE),
    re.compile(r"\b[A-Z][a-z]{2,30}\s+et\s+al\.?\b"),                              # author-year prose
    re.compile(r"\bp\s*[<>=≤≥]\s*0?\.\d+", re.IGNORECASE),                         # p < 0.05
]


def _find_no_cite_in_header(text: str) -> tuple[str | None, int | None, bool]:
    """Return (reason, match_line_index, is_in_header).

    Phase 8 contract: the no-cite annotation must live in the document
    header (first _NO_CITE_HEADER_LINES lines, OR within a YAML
    frontmatter / leading HTML comment block). Anywhere else, it does not
    suppress A5.

    Returns:
      (reason, line_idx, True)  — valid header annotation
      (reason, line_idx, False) — found a no-cite, but outside the header
      (None,   None,    False)  — no annotation at all
    """
    lines = text.splitlines()
    header_end = _NO_CITE_HEADER_LINES
    # Extend header window if we're still inside YAML frontmatter or a
    # leading HTML comment block.
    if lines and lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                header_end = max(header_end, i + 1)
                break
    elif lines and lines[0].strip().startswith("<!--"):
        for i, line in enumerate(lines):
            if "-->" in line:
                header_end = max(header_end, i + 1)
                break

    for idx, line in enumerate(lines):
        m = _NO_CITE_ANNOTATION_RE.search(line)
        if m:
            return (m.group(1).strip(), idx, idx < header_end)
    return (None, None, False)


def check_inline_attributions(text: str, used_keys: set) -> list[dict]:
    """A5 (Phase 8 hardened): detect inline author-year attributions when
    no [@Key] markers exist.

    Pure-expertise mode (zero [@Key] markers) used to be an off-switch:
    a single ``<!-- no-cite -->`` anywhere in the file disabled the check
    completely, with no scope or content discipline. Phase 8 changes that:

      1. The annotation only suppresses A5 when it lives in the document
         header (first 20 lines, or inside YAML/leading comment frontmatter).
      2. The reason text must be ≥30 chars and not match a generic
         template ("approved", "tutorial", "pure expertise", ...).
      3. Even when the annotation passes, a NOTE is emitted reporting the
         density of unanchored factual claims that survived suppression —
         the writer has informed visibility into what wasn't checked.
    """
    if used_keys:
        return []  # cited mode — bib integrity already covers these

    findings: list[dict] = []
    reason, _idx, in_header = _find_no_cite_in_header(text)

    if reason is not None and not in_header:
        findings.append({
            "criterion": "Inline Attribution (A5 — no-cite scope)",
            "severity": "major",
            "section": "Citations",
            "finding": (
                "Found a `<!-- no-cite: ... -->` annotation outside the "
                "document header (must appear within the first 20 lines or "
                "inside a YAML/HTML-comment frontmatter block). Out-of-scope "
                "annotations do not suppress citation checks (Phase 8)."
            ),
            "suggestion": (
                "Move the annotation to the very top of the file. If it was "
                "intentionally local, replace inline attributions in that "
                "section with [@Key] markers backed by a .bib entry."
            ),
        })
        # treat as if no annotation existed
        reason = None

    if reason is not None:
        # Validate the reason content (Phase 8).
        problems: list[str] = []
        if len(reason) < _NO_CITE_REASON_MIN_CHARS:
            problems.append(
                f"reason is too short ({len(reason)} < {_NO_CITE_REASON_MIN_CHARS} chars)"
            )
        elif reason.lower() in _NO_CITE_REASON_BLOCKLIST:
            problems.append(
                f"reason is a generic template ('{reason}')"
            )
        if problems:
            findings.append({
                "criterion": "Inline Attribution (A5 — no-cite reason)",
                "severity": "major",
                "section": "Citations",
                "finding": (
                    "The `<!-- no-cite: ... -->` annotation is present but "
                    f"the reason is insufficient: {'; '.join(problems)}. "
                    "Phase 8 requires a specific justification so the audit "
                    "trail records why a section ships without citation gate."
                ),
                "suggestion": (
                    "Replace the reason with a specific sentence describing "
                    "the content type and why no primary sources are cited "
                    "(e.g. 'Personal essay on lab onboarding; no published "
                    "claims, all examples are first-person observations')."
                ),
            })
        else:
            # Annotation valid → suppress A5 main finding but emit a NOTE
            # listing unanchored factual-claim density so the writer sees
            # what slipped through.
            stripped = re.sub(r"```[\s\S]*?```", " ", text)
            stripped = re.sub(r"`[^`]+`", " ", stripped)
            stripped = re.sub(r"\[.*?\]\(https?://[^\)]+\)", " ", stripped)
            density = sum(
                len(p.findall(stripped)) for p in _UNANCHORED_FACTUAL_PATTERNS
            )
            if density > 0:
                findings.append({
                    "criterion": "Inline Attribution (A5 — no-cite density)",
                    "severity": "info",
                    "section": "Citations",
                    "finding": (
                        f"`<!-- no-cite -->` is active and {density} unanchored "
                        "factual-claim pattern(s) survived suppression "
                        "(percentages, 'study found', 'researchers reported', "
                        "sample sizes, p-values, author-year prose). The gate "
                        "did NOT verify any of these — they ship as the writer's "
                        "own assertion."
                    ),
                    "suggestion": (
                        "Skim the flagged patterns and decide: keep them as "
                        "first-person observations, hedge them, or attach a "
                        "[@Key] citation. The NOTE is informational; the save "
                        "is not blocked."
                    ),
                })
            return findings  # valid annotation → skip the main A5 finding

    # No (valid) annotation: run the original A5 inline-attribution scan.
    stripped = re.sub(r"```[\s\S]*?```", "", text)
    stripped = re.sub(r"`[^`]+`", "", stripped)
    stripped = re.sub(r"\[.*?\]\(https?://[^\)]+\)", "", stripped)

    matches = list(_INLINE_ATTRIBUTION_RE.finditer(stripped))
    if not matches:
        return findings

    examples = [m.group(0) for m in matches[:3]]
    findings.append({
        "criterion": "Inline Attribution (A5)",
        "severity": "major",
        "section": "Citations",
        "finding": (
            f"Manuscript contains {len(matches)} inline author-year "
            "attribution(s) but no [@Key] citation markers — the gate "
            "cannot verify these references. "
            f"Examples: {examples}"
        ),
        "suggestion": (
            "Either (a) convert each attribution to a [@Key] marker backed "
            "by a .bib entry so the gate can verify it, or (b) add "
            "<!-- no-cite: <reason ≥30 chars> --> within the first 20 "
            "lines of the file to acknowledge that no citations are "
            "verifiable in this content. Generic reasons "
            "('approved', 'tutorial') are rejected."
        ),
    })
    return findings


# ============================================================
# Phase A6: Inline DOI/arXiv link verification
# ============================================================

_INLINE_DOI_URL_RE = re.compile(
    r"\[([^\]]*)\]\((https?://(?:doi\.org/|dx\.doi\.org/)(10\.[^\s\)\"]+))\)",
    re.IGNORECASE,
)
_INLINE_ARXIV_URL_RE = re.compile(
    r"\[([^\]]*)\]\((https?://arxiv\.org/abs/([\d]{4}\.\d{4,5}(?:v\d+)?))\)",
    re.IGNORECASE,
)

# Phase 9 — publisher-URL → DOI/PMID extractors. The pre-Phase-9 inline-link
# check only handled doi.org/dx.doi.org and arxiv.org/abs URLs; publisher
# domains carried unchecked phantom claims into Substack/export bodies.
# The patterns below extract a canonical identifier from each link and route
# it through the existing DOI/PMID dispatcher.
_INLINE_PUBLISHER_PATTERNS = (
    # Nature group: nature.com/articles/<doi-suffix>
    (
        re.compile(
            r"\[([^\]]*)\]\((https?://(?:www\.)?nature\.com/articles/"
            r"([A-Za-z0-9._\-]+)[^\s)]*)\)",
            re.IGNORECASE,
        ),
        "doi",
        # Most Nature article slugs map directly to 10.1038/<slug>
        lambda slug: f"10.1038/{slug}",
    ),
    # Cell Press: cell.com/cell/fulltext/S0092-8674(21)00...
    (
        re.compile(
            r"\[([^\]]*)\]\((https?://(?:www\.)?cell\.com/[^\s)]+/(?:fulltext|abstract)/"
            r"(S\d{4}-\d{4}\(\d{2}\)\d{5}-\d)[^\s)]*)\)",
            re.IGNORECASE,
        ),
        "doi",
        # Cell PII → DOI: 10.1016/j.<journal>.<id-without-parens>. Resolution
        # via PII is not deterministic without a journal lookup, so we hand
        # the PII to verify_doi as the suffix; if it fails we surface MAJOR.
        lambda pii: f"10.1016/{pii.replace('(', '.').replace(')', '.')}",
    ),
    # bioRxiv / medRxiv: biorxiv.org/content/10.1101/2024.01.02.123456
    (
        re.compile(
            r"\[([^\]]*)\]\((https?://(?:www\.)?(?:bio|med)rxiv\.org/content/"
            r"(10\.1101/[A-Za-z0-9._\-]+)(?:[?#][^\s)]*)?)\)",
            re.IGNORECASE,
        ),
        "doi",
        lambda doi: doi,
    ),
    # PMC OA: ncbi.nlm.nih.gov/pmc/articles/PMC1234567/
    (
        re.compile(
            r"\[([^\]]*)\]\((https?://(?:www\.)?ncbi\.nlm\.nih\.gov/pmc/articles/"
            r"(PMC\d+)[^\s)]*)\)",
            re.IGNORECASE,
        ),
        "pmcid",
        lambda pmcid: pmcid,
    ),
    # PubMed: pubmed.ncbi.nlm.nih.gov/12345678
    (
        re.compile(
            r"\[([^\]]*)\]\((https?://(?:www\.)?pubmed\.ncbi\.nlm\.nih\.gov/"
            r"(\d{6,9})[/]?[^\s)]*)\)",
            re.IGNORECASE,
        ),
        "pmid",
        lambda pmid: pmid,
    ),
)


_CITE_KEY_LINK_TEXT_RE = re.compile(
    r"^[^,\d]{1,80},\s*\d{4}[a-z]?$"
)


def _is_cite_key_link_text(link_text: str) -> bool:
    """True when the markdown link's display text is an `(Author, Year)`
    citation key rather than a paper title.

    Substack-style drafts use `[Wales and Ulker, 2006](https://doi.org/...)`
    where the link text is a short cite-key form, not the paper title. The
    A6 title-similarity check would always fail on these (cite-text vs full
    paper title is naturally low overlap), producing false-positive
    CRITICALs that block legitimate saves. The protective check that
    catches DOI digit-transposition errors (e.g. the historical
    Cohn-Triantafillou 3649 vs 3662 incident) is `check_bib_integrity`,
    which compares the *bib* title to the *live* title — that signal is
    preserved unchanged. The A6 link-text-vs-live-title check is therefore
    only meaningful when the link text is a *title-style* string. Cite-key
    formats are exempted here so the bib-integrity check carries the
    DOI-correctness load alone.
    """
    s = (link_text or "").strip().rstrip(".")
    if not s or len(s) > 80:
        return False
    word_count = len(s.split())
    if word_count > 8:
        return False
    return bool(_CITE_KEY_LINK_TEXT_RE.match(s))


def check_inline_links(text: str, bib_entries: list[dict]) -> list[dict]:
    """A6: Verify DOI and arXiv URLs embedded directly in markdown links.

    Substack drafts and blog posts often use [text](https://doi.org/...) links
    directly in the body rather than [@Key] markers. These are never checked
    by check_bib_integrity (which only audits .bib keys). This function
    extracts every such link and runs it through verify_citation.

    CRITICAL on title mismatch (wrong paper behind the link).
    MAJOR on network error (can't confirm).

    Phase 9 fix-up: when the link's display text is an `(Author, Year)`
    citation-key form rather than a title string, skip the title-similarity
    sub-check (it is structurally guaranteed to fail). DOI/arXiv resolution,
    retraction, and `check_bib_integrity` title vs live title still run.
    """
    try:
        from repro.citation_verify import verify_doi, verify_arxiv
    except ImportError:
        return []

    findings = []
    checked: set[str] = set()  # deduplicate

    # DOI links
    for m in _INLINE_DOI_URL_RE.finditer(text):
        link_text = m.group(1).strip()
        doi = m.group(3).strip().rstrip(")")
        if doi in checked:
            continue
        checked.add(doi)
        try:
            result = verify_doi(doi)
        except ValueError as e:
            findings.append({
                "criterion": "Inline Link (A6 — DOI)",
                "severity": "major",
                "section": "Citations",
                "finding": (
                    f"Inline DOI link '{doi}' could not be resolved: {e}"
                ),
                "suggestion": (
                    "Check the DOI for typos or use a [@Key] citation "
                    "backed by a .bib entry instead."
                ),
            })
            continue
        except ConnectionError as e:
            findings.append({
                "criterion": "Inline Link (A6 — DOI, network fail-closed)",
                "severity": "critical",
                "section": "Citations",
                "finding": (
                    f"Network error checking inline DOI '{doi}': {e}. "
                    "Fail-closed (Phase 8): an inline DOI link cannot be "
                    "verified, so the save is blocked rather than passing "
                    "an unchecked link to the published artifact."
                ),
                "suggestion": (
                    "Re-run verification once the network is reachable. "
                    "If the link must remain in the draft despite verification "
                    "being unavailable, replace it with a [@Key] marker backed "
                    "by a .bib entry carrying the full `unverifiable` contract."
                ),
            })
            continue

        live_title = (result.get("title") or "").strip()
        if link_text and live_title and not _is_cite_key_link_text(link_text):
            from difflib import SequenceMatcher

            def _n(t: str) -> str:
                return re.sub(r"\W+", " ", t.lower()).strip()
            ratio = SequenceMatcher(None, _n(link_text), _n(live_title)).ratio()
            if ratio < 0.60:
                findings.append({
                    "criterion": "Inline Link (A6 — DOI mismatch)",
                    "severity": "critical",
                    "section": "Citations",
                    "finding": (
                        f"Inline DOI link text '{link_text[:80]}' does not "
                        f"match the paper at doi:{doi} which is titled "
                        f"'{live_title[:80]}' (similarity {ratio:.2f}). "
                        "The link may point to the wrong paper."
                    ),
                    "suggestion": (
                        "Update the link text to match the actual paper "
                        "title, or correct the DOI."
                    ),
                })

        if result.get("is_retracted"):
            findings.append({
                "criterion": "Inline Link (A6 — retracted DOI)",
                "severity": "critical",
                "section": "Citations",
                "finding": (
                    f"Inline DOI '{doi}' points to a RETRACTED paper: "
                    f"{result.get('retraction_info')}"
                ),
                "suggestion": "Remove or replace this inline link.",
            })

    # arXiv links
    for m in _INLINE_ARXIV_URL_RE.finditer(text):
        arxiv_id = m.group(3).strip()
        if arxiv_id in checked:
            continue
        checked.add(arxiv_id)
        try:
            result = verify_arxiv(arxiv_id)
        except ConnectionError as e:
            findings.append({
                "criterion": "Inline Link (A6 — arXiv, network fail-closed)",
                "severity": "critical",
                "section": "Citations",
                "finding": (
                    f"Network error checking inline arXiv link "
                    f"'{arxiv_id}': {e}. Fail-closed (Phase 8): the link "
                    "cannot be verified, so the save is blocked."
                ),
                "suggestion": (
                    "Re-run verification once arXiv is reachable. "
                    "Network outages are not a silent pass."
                ),
            })
            continue
        except ValueError as e:
            findings.append({
                "criterion": "Inline Link (A6 — arXiv)",
                "severity": "major",
                "section": "Citations",
                "finding": (
                    f"Inline arXiv link '{arxiv_id}' could not be "
                    f"resolved: {e}"
                ),
                "suggestion": "Check the arXiv id for typos.",
            })
            continue

        if result.get("is_retracted"):
            findings.append({
                "criterion": "Inline Link (A6 — retracted arXiv)",
                "severity": "critical",
                "section": "Citations",
                "finding": (
                    f"Inline arXiv link '{arxiv_id}' is marked retracted: "
                    f"{result.get('retraction_info')}"
                ),
                "suggestion": "Remove or replace this inline link.",
            })

    # Phase 9 — publisher-URL inline links (Nature, Cell, bioRxiv, PMC, PubMed).
    try:
        from repro.citation_verify import verify_pubmed
    except ImportError:
        verify_pubmed = None  # type: ignore[assignment]

    for pattern, kind, mapper in _INLINE_PUBLISHER_PATTERNS:
        for m in pattern.finditer(text):
            link_text = m.group(1).strip()
            url = m.group(2).strip()
            slug = m.group(3).strip().rstrip("/")
            try:
                identifier = mapper(slug)
            except Exception:
                continue
            if identifier in checked:
                continue
            checked.add(identifier)
            try:
                if kind == "doi":
                    result = verify_doi(identifier)
                elif kind == "pmid":
                    if verify_pubmed is None:
                        raise ImportError("verify_pubmed unavailable")
                    result = verify_pubmed(identifier)
                elif kind == "pmcid":
                    # PMC ids resolve via the same NCBI infrastructure but
                    # need a PMC→PMID mapping that the existing dispatcher
                    # does not provide. Surface as MAJOR rather than CRITICAL —
                    # the link exists on a known publisher domain but we
                    # cannot mechanically verify the title without an extra
                    # NCBI elink call (deferred).
                    findings.append({
                        "criterion": "Inline Link (A6 — PMC URL, not verified)",
                        "severity": "major",
                        "section": "Citations",
                        "finding": (
                            f"Inline PMC link '{url}' detected but PMC→PMID "
                            "mapping is not yet wired into the dispatcher. "
                            "Link points to a known-OA paper but the title "
                            "cannot be cross-checked here."
                        ),
                        "suggestion": (
                            "Replace the PMC URL with the canonical DOI "
                            "(preferred) or run the audit pipeline manually."
                        ),
                    })
                    continue
                else:
                    continue
            except ConnectionError as e:
                findings.append({
                    "criterion": (
                        f"Inline Link (A6 — publisher URL, network "
                        f"fail-closed)"
                    ),
                    "severity": "critical",
                    "section": "Citations",
                    "finding": (
                        f"Network error checking inline publisher link "
                        f"'{url}' ({kind}={identifier}): {e}. Fail-closed."
                    ),
                    "suggestion": (
                        "Re-run verification once the network is reachable, "
                        "or replace with a [@Key] marker backed by a .bib "
                        "entry."
                    ),
                })
                continue
            except (ValueError, ImportError) as e:
                findings.append({
                    "criterion": "Inline Link (A6 — publisher URL)",
                    "severity": "major",
                    "section": "Citations",
                    "finding": (
                        f"Inline publisher link '{url}' could not be "
                        f"resolved (kind={kind}, identifier={identifier}): "
                        f"{e}"
                    ),
                    "suggestion": (
                        "Verify the publisher URL routes to a real paper. "
                        "Prefer [@Key] markers backed by .bib entries with "
                        "explicit DOIs."
                    ),
                })
                continue

            live_title = (result.get("title") or "").strip()
            if (
                link_text
                and live_title
                and not _is_cite_key_link_text(link_text)
            ):
                from difflib import SequenceMatcher

                def _n(t: str) -> str:
                    return re.sub(r"\W+", " ", t.lower()).strip()
                ratio = SequenceMatcher(
                    None, _n(link_text), _n(live_title)
                ).ratio()
                if ratio < 0.60:
                    findings.append({
                        "criterion": (
                            f"Inline Link (A6 — publisher URL mismatch)"
                        ),
                        "severity": "critical",
                        "section": "Citations",
                        "finding": (
                            f"Inline publisher link text "
                            f"'{link_text[:80]}' does not match the paper "
                            f"at {url} ({kind}={identifier}) which is "
                            f"titled '{live_title[:80]}' (similarity "
                            f"{ratio:.2f})."
                        ),
                        "suggestion": (
                            "Update the link text to match the actual paper "
                            "title, or correct the URL."
                        ),
                    })

            if result.get("is_retracted"):
                findings.append({
                    "criterion": (
                        f"Inline Link (A6 — publisher URL, retracted)"
                    ),
                    "severity": "critical",
                    "section": "Citations",
                    "finding": (
                        f"Inline publisher link '{url}' "
                        f"({kind}={identifier}) points to a RETRACTED paper: "
                        f"{result.get('retraction_info')}"
                    ),
                    "suggestion": "Remove or replace this inline link.",
                })

    return findings


# ============================================================
# Phase A10: Non-standard citation grammar detection
# ============================================================

_LATEX_CITE_RE = re.compile(r"\\cite(?:p|t|alt|alp)?\{([^}]{1,80})\}")
_PAREN_AUTHOR_YEAR_RE = re.compile(
    r"\(([A-Z][a-z]{1,25}(?:\s*(?:and|&)\s*[A-Z][a-z]{1,25})?(?:\s+et\s+al\.?)?),?\s+\d{4}[a-z]?\)"
)
_NUMERIC_REF_RE = re.compile(r"\[(\d{1,3}(?:,\s*\d{1,3})*)\](?!\()")  # [1] but not [1]( markdown


def check_non_standard_grammar(text: str) -> list[dict]:
    """A10: Detect citation markers the gate does NOT process.

    The gate only recognizes [@Key] markers. If a writer uses \\cite{},
    (Smith, 2023), or [1] style references, those are silently ignored —
    the gate cannot verify them. Surface them as MAJOR so the author can
    decide to convert to [@Key] or acknowledge them.

    Skips code blocks to avoid flagging example code.
    """
    # Strip fenced code blocks
    stripped = re.sub(r"```[\s\S]*?```", " ", text)
    stripped = re.sub(r"`[^`\n]+`", " ", stripped)

    findings = []

    latex_matches = _LATEX_CITE_RE.findall(stripped)
    if latex_matches:
        examples = latex_matches[:4]
        findings.append({
            "criterion": "Citation Grammar (A10 — LaTeX \\cite)",
            "severity": "major",
            "section": "Citations",
            "finding": (
                f"Found {len(latex_matches)} LaTeX \\cite{{}} marker(s) — "
                "the gate does NOT verify these. "
                f"Examples: {examples}"
            ),
            "suggestion": (
                "Convert \\cite{key} to [@key] so the gate can audit them, "
                "or remove them if this is not a LaTeX manuscript."
            ),
        })

    paren_matches = _PAREN_AUTHOR_YEAR_RE.findall(stripped)
    if paren_matches:
        examples = paren_matches[:4]
        findings.append({
            "criterion": "Citation Grammar (A10 — parenthetical author-year)",
            "severity": "major",
            "section": "Citations",
            "finding": (
                f"Found {len(paren_matches)} parenthetical (Author, YYYY) "
                "style reference(s) — the gate does NOT verify these. "
                f"Examples: {examples}"
            ),
            "suggestion": (
                "Convert (Author, YYYY) to [@Key] backed by a .bib entry, "
                "or add <!-- no-cite: reason --> to acknowledge deliberately "
                "unverified inline references."
            ),
        })

    numeric_matches = _NUMERIC_REF_RE.findall(stripped)
    if numeric_matches:
        findings.append({
            "criterion": "Citation Grammar (A10 — numeric [N] refs)",
            "severity": "major",
            "section": "Citations",
            "finding": (
                f"Found {len(numeric_matches)} numeric [N] style "
                "reference(s) — the gate does NOT verify these."
            ),
            "suggestion": (
                "Convert numeric references to [@Key] backed by a .bib "
                "entry so they can be verified."
            ),
        })

    return findings


# ============================================================
# Phase D: Hedging Consistency (flagged)
# ============================================================


def check_hedging(draft_text: str, source_text: str | None) -> list[dict]:
    """Detect hedging escalation when draft overstates relative to source.

    If source_text is None, only flag obvious overclaiming patterns in
    isolation (e.g., "proves causation").
    """
    findings = []

    # Always-flagged overclaiming patterns (no source comparison needed)
    overclaim_patterns = [
        (r"\bproves?\s+(that\s+)?\w+\s+caus", "Causal claims require explicit RCT or formal proof — consider hedging to 'suggests' or 'is consistent with'."),
        (r"\bdefinitively\s+show", "'Definitively' is rarely justified in research — consider 'demonstrates' or 'provides evidence for'."),
        (r"\balways\s+(?:results?|leads?|causes?)", "Universal claims ('always') are usually too strong — consider 'typically' or 'in this study'."),
        (r"\bnever\s+(?:fails?|results?)", "Universal negation ('never') is usually too strong — consider 'rarely' or 'in our sample'."),
    ]

    for pattern, suggestion in overclaim_patterns:
        for match in re.finditer(pattern, draft_text, re.IGNORECASE):
            findings.append({
                "criterion": "Hedging Consistency",
                "severity": "major",
                "section": "Claims",
                "finding": f"Possible overclaiming: '{match.group()}'",
                "suggestion": suggestion,
            })

    # Source comparison: if source is available, find escalations
    if source_text:
        for source_pat, draft_pat in HEDGING_ESCALATIONS:
            source_has = bool(re.search(source_pat, source_text, re.IGNORECASE))
            draft_has = bool(re.search(draft_pat, draft_text, re.IGNORECASE))
            if source_has and draft_has:
                # Check the source doesn't ALSO have the strong word
                if not re.search(draft_pat, source_text, re.IGNORECASE):
                    findings.append({
                        "criterion": "Hedging Consistency",
                        "severity": "major",
                        "section": "Claims",
                        "finding": (
                            f"Source uses {source_pat} but draft uses {draft_pat} — "
                            f"hedging may have been escalated."
                        ),
                        "suggestion": (
                            "Verify the strength of the claim is justified by "
                            "the source. Match the source's hedging level."
                        ),
                    })

    return findings


# ============================================================
# Phase E: Statistical Reporting (flagged)
# ============================================================


def check_statistics(text: str) -> list[dict]:
    """Detect p-values without test statistics and other reporting gaps."""
    findings = []

    # Find every p-value occurrence
    for match in P_VALUE_PATTERN.finditer(text):
        # Check if a test statistic appears within ±200 chars
        start = max(0, match.start() - 200)
        end = min(len(text), match.end() + 200)
        context = text[start:end]
        if not TEST_STAT_PATTERN.search(context):
            findings.append({
                "criterion": "Statistical Reporting",
                "severity": "major",
                "section": "Results",
                "finding": (
                    f"P-value '{match.group()}' appears without an "
                    f"accompanying test statistic (e.g., t(df), F(df1,df2), χ²(df))."
                ),
                "suggestion": (
                    "Report the test statistic, degrees of freedom, and "
                    "exact p-value together: 't(48) = 2.41, p = 0.020'."
                ),
            })

    # Look for "significant" without any p-value nearby
    for match in re.finditer(r"\bsignificant(?:ly)?\b", text, re.IGNORECASE):
        start = max(0, match.start() - 200)
        end = min(len(text), match.end() + 200)
        context = text[start:end]
        if not P_VALUE_PATTERN.search(context):
            findings.append({
                "criterion": "Statistical Reporting",
                "severity": "minor",
                "section": "Results",
                "finding": (
                    f"'{match.group()}' used without a nearby p-value or "
                    f"test result."
                ),
                "suggestion": (
                    "Either provide the supporting statistics or rephrase "
                    "to avoid implying statistical significance."
                ),
            })

    # Look for p-values without effect sizes nearby (best practice)
    p_count = len(P_VALUE_PATTERN.findall(text))
    es_count = len(EFFECT_SIZE_PATTERN.findall(text))
    if p_count >= 2 and es_count == 0:
        findings.append({
            "criterion": "Statistical Reporting",
            "severity": "minor",
            "section": "Results",
            "finding": (
                f"Found {p_count} p-values but no effect sizes "
                f"(Cohen's d, η², R², odds ratio, etc.)."
            ),
            "suggestion": (
                "Modern reporting standards expect effect sizes alongside "
                "p-values. Add Cohen's d for t-tests, η² for ANOVAs, etc."
            ),
        })

    return findings


# ============================================================
# Phase F + G: Paperclip Anchors & Quote-or-Cite Sidecar
# ============================================================


def sidecar_path_for(manuscript_path: str) -> Path:
    """Default sidecar location: <manuscript>.citations.json."""
    return Path(manuscript_path + ".citations.json")


def load_citations_sidecar(manuscript_path: str) -> dict | None:
    """Load the citations sidecar JSON, or None if it does not exist."""
    path = sidecar_path_for(manuscript_path)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise VerificationError(
            f"Citations sidecar '{path}' is not valid JSON: {e}. "
            "Fix or delete the file and re-draft with sidecar writes enabled."
        )


_QUOTE_FOLD = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"',
    "\u2013": "-", "\u2014": "-", "\u2212": "-",
    "\u00a0": " ", "\u202f": " ", "\u2009": " ",
})


def _normalize_for_quote_match(s: str) -> str:
    """Normalize a quote or source passage for verbatim substring check.

    Tier 1 change: the previous normalizer stripped *all* whitespace
    variation and lowercased everything, but that was too permissive —
    punctuation was preserved implicitly so smart quotes vs straight
    quotes bypassed the check. Now we:
      1. NFKC-normalize (folds ligatures, width variants, many dashes).
      2. Explicitly fold typographic quotes/dashes/NBSP to ASCII.
      3. Collapse whitespace runs to a single space.
      4. Lowercase.
    Punctuation is preserved deliberately so a quote that only matches
    after stripping punctuation no longer passes as verbatim.
    """
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = s.translate(_QUOTE_FOLD)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


# Back-compat alias used by legacy call sites within this module.
_normalize_whitespace = _normalize_for_quote_match


def check_quote_sidecar(
    manuscript_path: str,
    used_keys: set[str],
    source_text: str | None,
) -> list[dict]:
    """Every [@Key] must have an entry in the sidecar with a real quote.

    Sidecar schema:
        {
          "version": 1,
          "claims": [
            {
              "key": "Smith2023",
              "quote": "verbatim passage >= MIN_QUOTE_CHARS",
              "source_anchor": "10.1038/... or citations.gxl.ai/... URL",
              "source_type": "doi" | "paperclip" | "url",
              "source_confidence": "full-text" | "abstract"
            }
          ]
        }

    Tier 3: source_confidence is the provenance tier the upstream
    researcher recorded. Paperclip full-text passes cleanly; abstract
    is flagged MAJOR because abstracts are press-release prose, not
    verbatim paper text. Absent source_confidence defaults to the
    upstream tag — if that tag itself is 'abstract' the quote is
    flagged.

    Checks:
      - Sidecar exists when used_keys is non-empty (else CRITICAL).
      - Every used key has a claim entry (CRITICAL).
      - Quote is >= MIN_QUOTE_CHARS (MAJOR).
      - source_type == "paperclip" → source_anchor matches the
        citations.gxl.ai anchor pattern (CRITICAL).
      - source_confidence == "abstract" (MAJOR — weak provenance).
      - source_confidence == "title" (CRITICAL — title fallback is dead).
      - If source_text is provided, the quote must appear in it as a
        normalized substring (CRITICAL — fabricated quote).
    """
    findings: list[dict] = []
    if not used_keys:
        return findings

    sidecar = load_citations_sidecar(manuscript_path)
    if sidecar is None:
        findings.append({
            "criterion": "Quote-or-Cite Sidecar",
            "severity": "critical",
            "section": "Citations",
            "finding": (
                f"Manuscript has {len(used_keys)} [@Key] markers but no "
                f"sidecar at {sidecar_path_for(manuscript_path)}."
            ),
            "suggestion": (
                "Create the sidecar with a 'claims' entry for each "
                "citation: {key, quote, source_anchor, source_type}. "
                "Without it, quoted passages cannot be audited and the "
                "gate refuses to pass."
            ),
        })
        return findings

    claims_by_key: dict[str, dict] = {}
    for claim in sidecar.get("claims", []):
        key = (claim.get("key") or "").strip().lower()
        if key:
            claims_by_key[key] = claim

    normalized_source = _normalize_whitespace(source_text) if source_text else None

    for key in sorted(used_keys):
        claim = claims_by_key.get(key)
        if not claim:
            findings.append({
                "criterion": "Quote-or-Cite Sidecar",
                "severity": "critical",
                "section": "Citations",
                "finding": (
                    f"Citation '[@{key}]' has no sidecar claim entry."
                ),
                "suggestion": (
                    f"Add {{key: '{key}', quote: '...', source_anchor: "
                    "'...', source_type: '...'}} to the sidecar."
                ),
            })
            continue

        quote = (claim.get("quote") or "").strip()
        source_type = (claim.get("source_type") or "").strip().lower()
        source_anchor = (claim.get("source_anchor") or "").strip()
        source_confidence = (
            claim.get("source_confidence") or claim.get("confidence") or ""
        ).strip().lower()

        # Tier 3 provenance gate: abstract-sourced quotes are weak
        # evidence (abstracts are promotional prose, not verbatim
        # paper text) and must not silently pass. The 'title' tier is
        # gone from the upstream builder, but if a legacy sidecar ever
        # shows up with one we treat it as CRITICAL.
        if source_confidence == "abstract":
            findings.append({
                "criterion": "Quote-or-Cite Sidecar",
                "severity": "major",
                "section": "Citations",
                "finding": (
                    f"Sidecar quote for '[@{key}]' is abstract-sourced "
                    "(source_confidence='abstract'). Abstracts are "
                    "press-release prose, not verbatim paper text."
                ),
                "suggestion": (
                    "Replace with a passage pulled from Paperclip full-text "
                    "(`source_confidence='full-text'`) or the published PDF."
                ),
            })
        elif source_confidence == "title":
            findings.append({
                "criterion": "Quote-or-Cite Sidecar",
                "severity": "critical",
                "section": "Citations",
                "finding": (
                    f"Sidecar quote for '[@{key}]' uses the legacy 'title' "
                    "provenance tier, which was retired in Tier 3."
                ),
                "suggestion": (
                    "Rebuild the upstream quotes.json sidecar from a current "
                    "sci-literature-research run (the title fallback is dead) "
                    "and re-seed the draft."
                ),
            })

        if len(quote) < MIN_QUOTE_CHARS:
            findings.append({
                "criterion": "Quote-or-Cite Sidecar",
                "severity": "major",
                "section": "Citations",
                "finding": (
                    f"Sidecar quote for '[@{key}]' is {len(quote)} chars "
                    f"(minimum {MIN_QUOTE_CHARS})."
                ),
                "suggestion": (
                    "Paste a longer verbatim passage from the source "
                    "that actually supports the claim."
                ),
            })

        if not source_anchor:
            findings.append({
                "criterion": "Quote-or-Cite Sidecar",
                "severity": "major",
                "section": "Citations",
                "finding": f"Sidecar claim for '[@{key}]' has no source_anchor.",
                "suggestion": (
                    "Add the DOI, citations.gxl.ai URL, or resolvable "
                    "source URL so the quote can be traced."
                ),
            })

        if source_type == "paperclip":
            if not PAPERCLIP_ANCHOR_RE.match(source_anchor):
                findings.append({
                    "criterion": "Paperclip Anchor Format",
                    "severity": "critical",
                    "section": "Citations",
                    "finding": (
                        f"Paperclip claim '[@{key}]' has anchor "
                        f"'{source_anchor}' which does not match "
                        "'https://citations.gxl.ai/papers/<doc_id>#L<n>[-L<m>][,L<n>...]'."
                    ),
                    "suggestion": (
                        "Rebuild the anchor from the Paperclip result's "
                        "doc_id and content.lines L<n> markers per "
                        "tool-paperclip/SKILL.md § Citations."
                    ),
                })

        if normalized_source and quote:
            if _normalize_whitespace(quote) not in normalized_source:
                findings.append({
                    "criterion": "Quote-or-Cite Sidecar",
                    "severity": "critical",
                    "section": "Citations",
                    "finding": (
                        f"Quote for '[@{key}]' was NOT found in the "
                        "provided source material — possible fabrication."
                    ),
                    "suggestion": (
                        "Either (a) paste a real verbatim passage that "
                        "appears in the source, or (b) remove the "
                        "citation if the source does not support the "
                        "claim."
                    ),
                })

    return findings


# ============================================================
# Tier 4: Upstream quotes.json provenance gate
# ============================================================


def _collect_upstream_seeds(quotes_path: Path) -> dict[str, list[str]]:
    """Read a sci-literature-research quotes.json sidecar and return a
    map {key_lower: [normalized candidate texts]}.
    """
    try:
        data = json.loads(quotes_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VerificationError(
            f"Upstream quotes.json '{quotes_path}' is not valid JSON: {exc}. "
            "Re-run sci-literature-research cite mode."
        )
    if not isinstance(data, dict):
        raise VerificationError(
            f"Upstream quotes.json '{quotes_path}' must be a JSON object."
        )
    seeds: dict[str, list[str]] = {}
    for entry in data.get("quotes") or []:
        key = (entry.get("key") or "").strip().lower()
        if not key:
            continue
        bucket: list[str] = []
        for cand in entry.get("candidate_quotes") or []:
            text = (cand.get("text") or "").strip()
            if text:
                bucket.append(_normalize_for_quote_match(text))
        if bucket:
            seeds[key] = bucket
    return seeds


def check_upstream_quotes_provenance(
    manuscript_path: str,
    used_keys: set[str],
    quotes_path: Path | None,
) -> list[dict]:
    """Every sidecar quote must trace back to the upstream quotes.json.

    Tier 4: the draft's .citations.json sidecar is only trustworthy if
    every claim quote lifts a passage from the pre-generated upstream
    seed file (quotes.json from sci-literature-research). Without this
    trace, a writer can invent a quote, paste it in the sidecar, and
    the only line of defense is the source_text substring check — which
    is LLM-generated prose in communication mode.

    If quotes_path is None → gate is skipped (backward compat).
    If quotes_path exists and a claim quote doesn't substring-match any
    seed for that key → CRITICAL.
    If quotes_path exists but has no entry for a key that's being used →
    CRITICAL (the writer cited a paper the researcher never surfaced).
    """
    findings: list[dict] = []
    if not quotes_path or not used_keys:
        return findings
    if not quotes_path.exists():
        findings.append({
            "criterion": "Upstream Provenance",
            "severity": "critical",
            "section": "Citations",
            "finding": (
                f"Upstream quotes.json '{quotes_path}' is missing. Every "
                "claim must trace to a pre-fetched seed from "
                "sci-literature-research."
            ),
            "suggestion": (
                "Run sci-literature-research cite mode to generate the "
                "quotes.json sidecar, then re-verify."
            ),
        })
        return findings

    try:
        seeds = _collect_upstream_seeds(quotes_path)
    except VerificationError:
        raise  # bubble out — contract failure

    sidecar = load_citations_sidecar(manuscript_path)
    if not sidecar:
        # check_quote_sidecar already raised on this; nothing to trace.
        return findings
    claims_by_key: dict[str, dict] = {}
    for claim in sidecar.get("claims", []):
        ckey = (claim.get("key") or "").strip().lower()
        if ckey:
            claims_by_key[ckey] = claim

    for key in sorted(used_keys):
        claim = claims_by_key.get(key)
        if not claim:
            continue  # already flagged by check_quote_sidecar
        seed_pool = seeds.get(key)
        if not seed_pool:
            findings.append({
                "criterion": "Upstream Provenance",
                "severity": "critical",
                "section": "Citations",
                "finding": (
                    f"Citation '[@{key}]' has no entry in the upstream "
                    f"quotes.json '{quotes_path.name}'. The writer cited a "
                    "paper the researcher never surfaced — possible "
                    "fabrication or a missed researcher step."
                ),
                "suggestion": (
                    "Add this key to the upstream quotes.json via "
                    "sci-literature-research, or remove the citation."
                ),
            })
            continue

        quote_norm = _normalize_for_quote_match(claim.get("quote") or "")
        if not quote_norm:
            continue  # empty-quote case already flagged
        # One-way containment: the draft quote MUST appear as a contiguous
        # substring inside at least one upstream seed (after normalization).
        # The reverse direction (`seed in quote_norm`) used to be accepted
        # but let a writer wrap a short seed fragment in fabricated prose
        # — e.g. seed "CRISPR enables editing" + writer quote "CRISPR
        # enables editing of oncogenic driver mutations in lung cancer
        # patients" would pass because the seed is a substring of the
        # quote. Dropping that direction closes the fabricated-surround
        # hole while still allowing the writer to lift any sub-span of a
        # longer seed verbatim.
        if not any(quote_norm in seed for seed in seed_pool):
            findings.append({
                "criterion": "Upstream Provenance",
                "severity": "critical",
                "section": "Citations",
                "finding": (
                    f"Quote for '[@{key}]' does not appear verbatim "
                    "(after normalization) inside any candidate in the "
                    "upstream quotes.json. Writer quotes must be a "
                    "contiguous sub-span of an upstream seed — "
                    "paraphrasing or fabricating surrounding prose is "
                    "not allowed."
                ),
                "suggestion": (
                    "Copy a candidate quote verbatim from the upstream "
                    "quotes.json into the sidecar, or regenerate the "
                    "upstream seed with a better source."
                ),
            })

    return findings


# ============================================================
# Tier G: Cross-bib contamination
# ============================================================


def check_quote_attributable_to_one_source(
    quote_norm: str,
    all_seeds: dict[str, list[str]],
    own_key: str,
) -> bool:
    """Return True iff quote_norm appears ONLY in own_key's seed pool.

    Used by check_cross_bib_contamination (G1) and by format_citation (Tier F)
    to detect when a quote is simultaneously attributable to multiple papers.
    An empty quote is considered vacuously attributable.
    """
    if not quote_norm:
        return True
    for key, seeds in all_seeds.items():
        if key == own_key:
            continue
        if any(quote_norm in seed for seed in seeds):
            return False
    return True


def check_cross_bib_contamination(
    manuscript_path: str,
    used_keys: set[str],
    quotes_path: "Path | None",
) -> list[dict]:
    """Tier G1: cross-key contamination detection.

    If a draft sidecar quote for [@KeyA] is also a verbatim substring of an
    upstream seed for some other KeyB ≠ KeyA, the attribution is ambiguous:
    the same passage appeared in at least two papers' upstream seeds, so we
    cannot confirm which paper the writer actually meant to cite.

    The dangerous case: a writer pulls a real quote from Paper A but writes
    Paper B's DOI in source_anchor. Because the quote appears verbatim in
    both papers' seeds, the upstream-provenance check passes regardless.
    This check surfaces the collision so the human can arbitrate.

    Severity: MAJOR. The passage may legitimately recur across papers (a
    standard formula reproduced in reviews). Surfacing lets the human verify;
    promote to CRITICAL only after confirming negligible false-positive rate.

    Skipped when:
      - quotes_path is None or does not exist (gate already reported this)
      - the sidecar is missing (check_quote_sidecar already reported)
      - used_keys is empty
    """
    findings: list[dict] = []
    if not quotes_path or not used_keys:
        return findings
    quotes_path = Path(quotes_path)
    if not quotes_path.exists():
        return findings  # check_upstream_quotes_provenance already flagged

    try:
        seeds = _collect_upstream_seeds(quotes_path)
    except VerificationError:
        return findings

    sidecar = load_citations_sidecar(manuscript_path)
    if sidecar is None:
        return findings  # check_quote_sidecar already flagged

    claims_by_key: dict[str, dict] = {}
    for claim in sidecar.get("claims", []):
        ckey = (claim.get("key") or "").strip().lower()
        if ckey:
            claims_by_key[ckey] = claim

    for raw_key in sorted(used_keys):
        key = raw_key.strip().lower()
        claim = claims_by_key.get(key)
        if not claim:
            continue  # already flagged by check_quote_sidecar
        quote_norm = _normalize_for_quote_match(claim.get("quote") or "")
        if not quote_norm:
            continue
        # Only check contamination when the quote is anchored in own seed.
        # If it's not in its own seed the upstream-provenance check already
        # fires CRITICAL — don't pile on a MAJOR from here too.
        own_seeds = seeds.get(key, [])
        if not any(quote_norm in s for s in own_seeds):
            continue

        if not check_quote_attributable_to_one_source(quote_norm, seeds, key):
            matching_others = sorted(
                other_key
                for other_key, other_seeds in seeds.items()
                if other_key != key and any(quote_norm in s for s in other_seeds)
            )
            findings.append({
                "criterion": "Cross-Bib Contamination (Tier G)",
                "severity": "major",
                "section": "Citations",
                "finding": (
                    f"Quote for '[@{key}]' also appears verbatim in the upstream "
                    f"seed for {', '.join(f'[@{k}]' for k in matching_others)}. "
                    "Ambiguous attribution: the same passage appears in multiple "
                    "papers’ upstream seeds — the source_anchor may point "
                    "to the wrong paper."
                ),
                "suggestion": (
                    f"Verify which paper contains this exact passage and update "
                    f"the '[@{key}]' sidecar’s source_anchor accordingly. "
                    "If both papers genuinely reproduce the passage (e.g. a formula "
                    "in a review that copies the original), cite the primary source "
                    "and mention the review in prose."
                ),
            })

    return findings


# ============================================================
# Tier 5: Live-source quote validation
# ============================================================


# Per-run cache so check_bib_integrity and check_quotes_against_live_source
# don't double-call the network for the same DOI / arXiv id. Keyed by the
# (doi, eprint) tuple. Reset at the top of run_verification.
_LIVE_METADATA_CACHE: dict[tuple[str, str], dict] = {}

# Cache for paperclip anchor lookups: anchor URL → bool (True = quote found)
_PAPERCLIP_ANCHOR_CACHE: dict[str, bool] = {}

# Regex to extract doc_id and line spec from a citations.gxl.ai anchor.
_PAPERCLIP_URL_RE = re.compile(
    r"^https://citations\.gxl\.ai/papers/([A-Za-z0-9_.]+)#(L\d+(?:-L\d+)?(?:,L\d+(?:-L\d+)?)*)$"
)

# Filesystem root for mounted paperclip corpus (paperclip MCP mounts here).
_PAPERCLIP_FS_ROOT = Path("/papers")


def _paperclip_line_numbers(line_spec: str) -> list[int]:
    """Parse L45, L45-L52, L45,L120, L45-L52,L120 into a sorted list of ints."""
    numbers: list[int] = []
    for part in line_spec.split(","):
        part = part.strip()
        m = re.match(r"L(\d+)(?:-L(\d+))?$", part)
        if not m:
            continue
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else start
        numbers.extend(range(start, end + 1))
    return sorted(set(numbers))


def _verify_paperclip_anchor(anchor: str, expected_quote: str) -> bool | None:
    """Check whether expected_quote appears in the lines referenced by a
    citations.gxl.ai anchor.

    Returns:
        True  — quote found in the referenced lines.
        False — quote NOT found (possible fabrication).
        None  — paperclip is not available; caller should fall back to
                abstract-based validation and log a WARN.

    Strategy (in order):
      1. Read from the mounted paperclip filesystem at /papers/<doc_id>/content.lines
         if it exists.
      2. Call `paperclip cat /papers/<doc_id>/content.lines` via subprocess if
         the `paperclip` binary is on PATH.
      3. Return None (unavailable) — caller falls back to abstract check.
    """
    if anchor in _PAPERCLIP_ANCHOR_CACHE:
        return _PAPERCLIP_ANCHOR_CACHE[anchor]

    m = _PAPERCLIP_URL_RE.match(anchor)
    if not m:
        return None  # malformed anchor — format gate already flagged it

    doc_id, line_spec = m.group(1), m.group(2)
    line_numbers = _paperclip_line_numbers(line_spec)
    if not line_numbers:
        return None

    content_lines: list[str] | None = None

    # Strategy 1: mounted filesystem
    fs_path = _PAPERCLIP_FS_ROOT / doc_id / "content.lines"
    if fs_path.exists():
        try:
            raw = fs_path.read_text(encoding="utf-8", errors="replace")
            content_lines = raw.splitlines()
        except OSError:
            pass

    # Strategy 2: paperclip CLI subprocess
    if content_lines is None:
        try:
            result = subprocess.run(
                ["paperclip", "cat", f"/papers/{doc_id}/content.lines"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout:
                content_lines = result.stdout.splitlines()
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass

    if content_lines is None:
        return None  # paperclip unavailable

    # content.lines format: "L<n>\t<text>" — extract the requested lines
    line_map: dict[int, str] = {}
    for raw_line in content_lines:
        lm = re.match(r"L(\d+)\t(.*)", raw_line)
        if lm:
            line_map[int(lm.group(1))] = lm.group(2)

    excerpt = " ".join(line_map.get(n, "") for n in line_numbers)
    norm_excerpt = _normalize_for_quote_match(excerpt)
    norm_quote = _normalize_for_quote_match(expected_quote)

    found = bool(norm_quote) and norm_quote in norm_excerpt
    _PAPERCLIP_ANCHOR_CACHE[anchor] = found
    return found


def _live_metadata(entry: dict) -> dict | None:
    """Fetch and cache live metadata for a bib entry, or None on failure.

    Errors are intentionally swallowed here — check_bib_integrity is the
    right place to surface lookup failures as findings; this helper just
    needs to know whether we have a live abstract to validate quotes
    against.
    """
    doi = (entry.get("doi") or "").strip()
    eprint = (entry.get("eprint") or "").strip()
    pmid = (entry.get("pmid") or "").strip()
    cache_key = (doi.lower(), eprint.lower(), pmid.lower())
    if cache_key in _LIVE_METADATA_CACHE:
        return _LIVE_METADATA_CACHE[cache_key]
    try:
        result = verify_citation(entry)
    except (ValueError, ConnectionError):
        _LIVE_METADATA_CACHE[cache_key] = {}
        return None
    _LIVE_METADATA_CACHE[cache_key] = result
    return result


def _strip_html(s: str) -> str:
    """Naively strip <jats:*> and HTML tags from a CrossRef-style abstract."""
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"&[a-zA-Z]+;", " ", s)
    return s


def check_quotes_against_live_source(
    manuscript_path: str,
    used_keys: set[str],
    bib_entries: list[dict],
) -> list[dict]:
    """Re-fetch each cited paper's abstract and verify the sidecar quote
    actually appears in it. Catches the case where a real DOI / arXiv id
    is paired with a fabricated quote, even when the upstream quotes.json
    seed is also fabricated (because the seed comes from the same LLM
    pass).

    Severity:
      MAJOR — quote not found in live abstract. (Abstracts are not the
      full text, so this is "suspicious" rather than "definitely wrong".
      The MAJOR signal pushes the writer to verify against the full PDF
      and either swap the quote or escalate provenance.)
    """
    findings: list[dict] = []
    if not used_keys:
        return findings

    sidecar = load_citations_sidecar(manuscript_path)
    if sidecar is None:
        return findings  # check_quote_sidecar already raised

    by_key = {e.get("key", "").lower(): e for e in bib_entries if e.get("key")}
    claims_by_key: dict[str, dict] = {}
    for claim in sidecar.get("claims", []):
        ckey = (claim.get("key") or "").strip().lower()
        if ckey:
            claims_by_key[ckey] = claim

    for key in sorted(used_keys):
        claim = claims_by_key.get(key)
        if not claim:
            continue
        quote = (claim.get("quote") or "").strip()
        if not quote:
            continue
        entry = by_key.get(key)
        if not entry:
            continue

        # Paperclip anchor check: full-text line validation runs FIRST.
        # If the sidecar claim carries a citations.gxl.ai anchor, verify
        # the exact lines before falling back to abstract-level matching.
        source_anchor = (claim.get("source_anchor") or "").strip()
        source_type = (claim.get("source_type") or "").strip().lower()
        if source_type == "paperclip" and source_anchor:
            anchor_result = _verify_paperclip_anchor(source_anchor, quote)
            if anchor_result is True:
                continue  # quote confirmed in full text — nothing more to do
            if anchor_result is False:
                findings.append({
                    "criterion": "Live-Source Quote",
                    "severity": "major",
                    "section": "Citations",
                    "finding": (
                        f"Paperclip full-text check FAILED for '[@{key}]': "
                        f"the quoted passage was not found in the lines "
                        f"referenced by anchor '{source_anchor}'. Full-text "
                        "mismatch is stronger evidence of fabrication than "
                        "an abstract miss — the passage does not appear where "
                        "the sidecar claims it does."
                    ),
                    "suggestion": (
                        "Re-read the paper at that anchor, confirm the exact "
                        "passage, and update the quote field. If the passage "
                        "is in a different section, update the anchor too."
                    ),
                })
                continue
            # anchor_result is None → paperclip unavailable; fall through to
            # full-text then abstract validation.

        # ── Tier D: full-text fetch ────────────────────────────────────────
        # Try to obtain an OA full-text copy (arXiv PDF → Unpaywall → PMC).
        # CRITICAL when full text is available AND the quote is absent —
        # stronger evidence than an abstract miss.
        # MAJOR when full text is unavailable and the abstract also misses.
        ft_checked = False
        if _FULLTEXT_FETCH_AVAILABLE:
            doi_val = entry.get("doi", "").strip() or None
            arxiv_val = entry.get("eprint", "").strip() or None
            pmid_val = entry.get("pmid", "").strip() or None
            if doi_val or arxiv_val or pmid_val:
                try:
                    full_text = _fetch_full_text(
                        doi=doi_val, arxiv_id=arxiv_val, pmid=pmid_val
                    )
                    if full_text:
                        ft_checked = True
                        if _quote_in_full_text(quote, full_text):
                            continue  # confirmed in full text — pass
                        # Quote absent from full text → CRITICAL
                        ft_identifier = doi_val or arxiv_val or pmid_val or "<unknown>"
                        findings.append({
                            "criterion": "Full-Text Quote (Tier D)",
                            "severity": "critical",
                            "section": "Citations",
                            "finding": (
                                f"Sidecar quote for '[@{key}]' was NOT found in "
                                f"the fetched open-access full text for "
                                f"'{ft_identifier}'. Full-text mismatch is "
                                "authoritative: the paper does not contain this "
                                "passage, or the quoted text has been substantially "
                                "paraphrased beyond recognition."
                            ),
                            "suggestion": (
                                "Open the PDF and locate the actual passage. "
                                "Either update the sidecar quote to match the "
                                "verbatim text, or remove the citation if the "
                                "paper does not support the claim."
                            ),
                        })
                        continue
                except Exception:
                    pass  # network error → fall through to abstract check

        if ft_checked:
            # Full text was checked (and passed above) or produced a CRITICAL.
            # Either way, skip the weaker abstract check to avoid double-firing.
            continue

        # ── Abstract fallback (existing behavior) ─────────────────────────
        live = _live_metadata(entry)
        if not live:
            continue  # bib_integrity already reported the lookup failure

        abstract = _strip_html(live.get("abstract") or "")
        if not abstract:
            continue  # paper has no abstract on file — cannot validate

        norm_abstract = _normalize_for_quote_match(abstract)
        norm_quote = _normalize_for_quote_match(quote)
        if not norm_quote:
            continue

        if norm_quote in norm_abstract:
            continue

        # Soft fallback: try matching the first 60% of the quote, in case
        # the abstract truncates a longer passage. Still MAJOR.
        head_len = max(MIN_QUOTE_CHARS, int(len(norm_quote) * 0.6))
        head = norm_quote[:head_len]
        if head in norm_abstract:
            continue

        backend = live.get("source", "live")
        identifier = live.get("doi") or live.get("arxiv_id") or "<unknown>"
        findings.append({
            "criterion": "Live-Source Quote",
            "severity": "major",
            "section": "Citations",
            "finding": (
                f"Sidecar quote for '[@{key}]' was NOT found in the live "
                f"{backend} abstract for {identifier}. The cited paper exists, "
                "but the abstract does not contain the quoted passage. This "
                "may be a legitimate full-text quote that simply isn't in "
                "the abstract, or it may be fabricated. "
                "(No open-access full text was available to perform a "
                "stronger CRITICAL check — see Tier D in verification-rules.md.)"
            ),
            "suggestion": (
                "Open the actual paper PDF and confirm the passage appears "
                "verbatim. If yes, escalate the sidecar's source_confidence "
                "to 'full-text' and add a paperclip anchor or page number. "
                "If no, swap the quote for one that appears in the source. "
                "Set UNPAYWALL_EMAIL in .env to enable automatic full-text "
                "retrieval for this and future papers."
            ),
        })

    return findings


# ============================================================
# Tier C3: Claim-Quote Alignment
# ============================================================


def _sentences_containing_key(text: str, key: str) -> list[str]:
    """Return all sentences in text that cite [@key] (any casing of key).

    Splits by blank-line paragraph, then by sentence-terminal punctuation.
    Uses extract_used_keys so multi-key markers like [@KeyA; @KeyB] are
    handled correctly.
    """
    results: list[str] = []
    for para in re.split(r"\n{2,}", text):
        for sent in re.split(r"(?<=[.!?])\s+", para.strip()):
            if key in extract_used_keys(sent):
                results.append(sent.strip())
    return results


def _token_jaccard(a: str, b: str) -> float:
    """Token-set Jaccard between two strings (alphanumeric tokens only)."""
    ta = {t for t in re.split(r"[^a-z0-9]+", a.lower()) if t}
    tb = {t for t in re.split(r"[^a-z0-9]+", b.lower()) if t}
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def check_unsupported_claims(
    text: str,
    used_keys: set[str],
    quotes_path: "Path",
    manuscript_path: str,
) -> list[dict]:
    """Tier C3: verify the manuscript sentence containing [@Key] has
    meaningful token overlap with the sidecar quote for that key.

    Catches writers who cite Paper X to support a claim that Paper X
    does not actually make — e.g. quoting "X is true" to back a sentence
    that says "X is true and so is Y and also Z."

    A claim sentence and its sidecar quote must share at least
    _CLAIM_QUOTE_JACCARD_MIN (0.30) of their token set. Below that
    threshold the quote is not meaningfully relevant to what the sentence
    asserts.

    Severity: MAJOR. Start here; promote to CRITICAL once false-positive
    rate is measured against 50+ real manuscripts.

    Skipped when:
      - quotes_path is None or does not exist (gate already reported this)
      - the sidecar is missing (check_quote_sidecar already reported)
      - a key has no sidecar entry (check_quote_sidecar already reported)
    """
    findings: list[dict] = []
    if not used_keys or not quotes_path:
        return findings
    if not quotes_path.exists():
        return findings  # check_upstream_quotes_provenance already flagged

    try:
        seeds = _collect_upstream_seeds(quotes_path)
    except VerificationError:
        return findings

    sidecar = load_citations_sidecar(manuscript_path)
    if sidecar is None:
        return findings  # check_quote_sidecar already flagged

    claims_by_key: dict[str, dict] = {}
    for claim in sidecar.get("claims", []):
        ckey = (claim.get("key") or "").strip().lower()
        if ckey:
            claims_by_key[ckey] = claim

    for key in sorted(used_keys):
        claim = claims_by_key.get(key)
        if not claim:
            continue  # already flagged by check_quote_sidecar
        quote = (claim.get("quote") or "").strip()
        if not quote or len(quote) < MIN_QUOTE_CHARS:
            continue  # too short to be meaningful; skip silently

        sentences = _sentences_containing_key(text, key)
        if not sentences:
            continue  # marker not found (code fence or auto-fixed away)

        # Check every sentence that uses [@key]; report the worst-overlapping one.
        min_jaccard = 1.0
        worst_sent = ""
        for sent in sentences:
            j = _token_jaccard(quote, sent)
            if j < min_jaccard:
                min_jaccard = j
                worst_sent = sent

        if min_jaccard < _CLAIM_QUOTE_JACCARD_MIN:
            preview = (worst_sent[:120] + "…") if len(worst_sent) > 120 else worst_sent
            findings.append({
                "criterion": "Claim-Quote Alignment (C3)",
                "severity": "major",
                "section": "Citations",
                "finding": (
                    f"Sentence containing '[@{key}]' has low token overlap with "
                    f"the sidecar quote (Jaccard={min_jaccard:.2f}, threshold="
                    f"{_CLAIM_QUOTE_JACCARD_MIN}). The quoted passage may not "
                    f"support the specific claim being made. "
                    f"Sentence: «{preview}»"
                ),
                "suggestion": (
                    "Choose a sidecar quote that directly supports this sentence, "
                    "narrow the sentence so it only asserts what the quote actually "
                    "says, or remove the claim entirely. The 'prefer no citation' "
                    "rule applies: if no upstream candidate for "
                    f"'[@{key}]' supports this claim, drop or hedge it."
                ),
            })

    return findings


# ============================================================
# Phase 8: Scope-mismatch escalation
# ============================================================


def check_scope_escalation(
    text: str,
    used_keys: set[str],
    quotes_path: "Path",
    manuscript_path: str,
) -> list[dict]:
    """Phase 8: detect *scope* overstatement between sidecar quote and claim sentence.

    Hedging escalation pairs (HEDGING_ESCALATIONS) catch verb-strength shifts
    ("suggests" → "proves"). Scope escalations are a different and dominant
    biomedical/clinical overclaim shape: the source studies *one* population
    and the draft generalizes to a *broader* one.

    A sidecar quote that mentions "in mice" / "in vitro" / "preclinical" /
    "pilot" / "n=12" while the manuscript sentence containing the same
    [@Key] talks about "patients" / "in vivo" / "definitive" / "broadly"
    is a scope mismatch — flagged MAJOR.

    Skipped when:
      - quotes_path missing (already flagged elsewhere)
      - sidecar missing (already flagged)
      - sidecar quote already contains the broader-scope phrase too
        (the source itself made the generalization, not the writer)
    """
    findings: list[dict] = []
    if not used_keys or not quotes_path:
        return findings
    if not quotes_path.exists():
        return findings

    sidecar = load_citations_sidecar(manuscript_path)
    if sidecar is None:
        return findings

    claims_by_key: dict[str, dict] = {}
    for claim in sidecar.get("claims", []):
        ckey = (claim.get("key") or "").strip().lower()
        if ckey:
            claims_by_key[ckey] = claim

    for key in sorted(used_keys):
        claim = claims_by_key.get(key)
        if not claim:
            continue
        quote = (claim.get("quote") or "").strip()
        if not quote:
            continue

        sentences = _sentences_containing_key(text, key)
        if not sentences:
            continue
        joined_sentences = " ".join(sentences)

        for source_pat, draft_pat in SCOPE_ESCALATIONS:
            quote_has = bool(re.search(source_pat, quote, re.IGNORECASE))
            draft_has = bool(re.search(draft_pat, joined_sentences, re.IGNORECASE))
            if not (quote_has and draft_has):
                continue
            # Suppress when the quote ALSO contains the broader-scope phrase
            # (the source itself made the generalization).
            if re.search(draft_pat, quote, re.IGNORECASE):
                continue
            # Suppress when the manuscript sentence ALSO retains the
            # narrow-scope phrase — the writer kept the qualifier.
            if re.search(source_pat, joined_sentences, re.IGNORECASE):
                continue
            sample_sentence = sentences[0]
            preview = (
                (sample_sentence[:140] + "…")
                if len(sample_sentence) > 140
                else sample_sentence
            )
            findings.append({
                "criterion": "Scope Escalation (Phase 8)",
                "severity": "major",
                "section": "Claims",
                "finding": (
                    f"Sentence containing '[@{key}]' generalizes beyond the "
                    f"sidecar quote's scope. Quote pattern '{source_pat}' "
                    f"(narrow scope) → manuscript pattern '{draft_pat}' "
                    f"(broader scope), with the narrow qualifier dropped. "
                    f"Sentence: «{preview}»"
                ),
                "suggestion": (
                    "Either keep the narrower-scope qualifier in the sentence "
                    "(e.g. 'in mice' / 'in vitro' / 'in this pilot study'), "
                    "or replace the citation with one that supports the "
                    "broader claim. Common scope mismatches: animal model → "
                    "human, in vitro → in vivo, pilot → definitive, "
                    "observational → causal."
                ),
            })
            break  # one finding per key per sentence is enough

    return findings


# ============================================================
# Tier F4: Per-claim deep-link presence check
# ============================================================

# Patterns that indicate a deep link is present in the rendered bibliography.
# Either a paperclip anchor or a text-fragment URL counts.
_DEEP_LINK_RE = re.compile(
    r"https://citations\.gxl\.ai/papers/[^\s)>\"']+"   # paperclip anchor
    r"|"
    r"https?://[^\s)>\"']+#:~:text=[^\s)>\"']*",       # text-fragment URL
    re.IGNORECASE,
)


def check_per_claim_links_present(
    rendered_bibliography: str,
    used_keys: set[str],
    sidecar: dict | None,
) -> list[dict]:
    """Tier F4: verify the rendered bibliography has at least one per-claim
    deep link per cited key that has a sidecar quote.

    Strategy: count keys-with-quotes vs deep-link occurrences in the whole
    bibliography. The rendered bib doesn't contain literal bib keys, so
    per-entry attribution is not feasible without re-parsing — instead we
    surface a single MAJOR when the deep-link count falls short of the
    expected count.

    A deep link is either a citations.gxl.ai anchor or a #:~:text= fragment.
    """
    findings: list[dict] = []
    if not used_keys or not rendered_bibliography:
        return findings

    if not sidecar:
        return findings

    keys_with_quotes = sum(
        1 for claim in sidecar.get("claims", [])
        if (claim.get("key") or "").strip().lower() in {k.lower() for k in used_keys}
        and (claim.get("quote") or "").strip()
    )
    if keys_with_quotes == 0:
        return findings

    deep_link_count = len(_DEEP_LINK_RE.findall(rendered_bibliography))

    if deep_link_count < keys_with_quotes:
        missing = keys_with_quotes - deep_link_count
        findings.append({
            "criterion": "Per-Claim Deep Link (Tier F)",
            "severity": "major",
            "section": "References",
            "finding": (
                f"{missing} of {keys_with_quotes} cited entries with sidecar quotes "
                "lack a per-claim deep link in the rendered bibliography. Each entry "
                "should carry either a paperclip citations.gxl.ai anchor or a "
                "#:~:text= text-fragment URL so readers land on the exact passage."
            ),
            "suggestion": (
                "Use `format_bibliography_with_deep_links(entries, style, sidecar)` "
                "from writing_ops.py instead of `format_bibliography` to generate "
                "per-claim URLs automatically."
            ),
        })

    return findings


# ============================================================
# Top-level Orchestrator
# ============================================================


def run_verification(
    manuscript_path: str,
    bib_path: str | None = None,
    source_path: str | None = None,
    apply_fixes: bool = True,
    quotes_path: str | None = None,
) -> dict:
    """Run all verification phases on a manuscript.

    `bib_path` is REQUIRED when the manuscript contains `[@Key]` citation
    markers — that's the core guardrail against fabricated citations.
    Pure-expertise content (explainers, whitepapers, lay summaries with
    ZERO `[@Key]` markers) runs in **pure-expertise mode**: the bib
    requirement, sidecar check (Phase G), bib integrity (Phase C), and
    provenance trace (Phase H) are all skipped. Non-citation phases
    (B completeness, D hedging self-comparison, E statistical reporting)
    still run.

    Args:
        manuscript_path: Path to the .md manuscript to verify.
        bib_path: Path to .bib file. Required when the manuscript has
                  `[@Key]` markers. Optional for pure-expertise content.
        source_path: Optional path to source material (paper, data report)
                     for hedging comparison and quote substring check.
        apply_fixes: If True, write auto-fixes back to manuscript_path.
        quotes_path: Optional upstream quotes.json for provenance trace.

    Returns:
        Dict with keys:
            findings: list of finding dicts (compatible with review_ops format)
            auto_fixes: list of auto-fixes applied
            summary: counts by severity
            blocked: True if CRITICAL findings exist (caller MUST NOT save)
            pure_expertise: True when verification ran without citations

    Raises:
        VerificationError: when the manuscript has citation markers but
            bib_path is missing, the bib file doesn't exist, or the bib
            parses to zero entries.
    """
    # Reset the per-run live-metadata cache so a previous verification
    # run's stale arXiv/CrossRef hit cannot leak into this one.
    _LIVE_METADATA_CACHE.clear()
    _PAPERCLIP_ANCHOR_CACHE.clear()

    # Extract citation markers FIRST so we can decide pure-expertise vs
    # cited mode before imposing the bib contract.
    text = Path(manuscript_path).read_text(encoding="utf-8")
    original_text = text
    used_keys = extract_used_keys(text)

    # Phase 9 — unparseable-marker fail-closed.
    # Pre-Phase-9, a manuscript using non-canonical pandoc forms (e.g.
    # `[@Smith2020, p. 5]` with a malformed locator) could land in
    # extract_used_keys = empty AND BROAD_MARKER_RE matching, silently
    # falling into pure-expertise mode and skipping the entire bib +
    # sidecar + provenance contract. Phase 9 refuses: if the writer used
    # cite-like markers but the gate cannot parse them, we contract-fail
    # rather than entering pure-expertise mode.
    if not used_keys and has_citation_markers(text):
        raise VerificationError(
            f"Manuscript ({manuscript_path}) contains '[@...' cite-like "
            "markers but the gate could not extract any keys from them. "
            "This usually means a malformed citation grammar that the "
            "extractor's pandoc-aware regex still cannot parse. The gate "
            "refuses to fall back to pure-expertise mode here — that "
            "would silently ship unaudited claims. "
            "Use the canonical forms: `[@Key]`, `[@Key1; @Key2]`, "
            "`[@Key, p. 5]`. If you intended pure expertise, remove the "
            "marker syntax entirely."
        )

    pure_expertise = not used_keys

    if pure_expertise:
        # Pure-expertise mode: no citations to audit. Skip bib, sidecar,
        # provenance, and Phase C. Bib is optional; if provided we parse
        # it anyway in case the caller also wants Phase B completeness
        # signals that reference it (currently none do).
        bib_entries: dict = {}
        if bib_path:
            bib_file = Path(bib_path)
            if bib_file.exists():
                bib_entries = parse_bib_file(bib_path)
    else:
        # Cited mode: full contract applies.
        if not bib_path:
            raise VerificationError(
                f"Manuscript has {len(used_keys)} citation markers but no "
                "bib_path was provided. The gate refuses to run cited "
                "content without a .bib — every [@Key] must be auditable. "
                "Run sci-literature-research cite mode first, or remove "
                "the markers if this is pure-expertise content."
            )
        bib_file = Path(bib_path)
        if not bib_file.exists():
            raise VerificationError(
                f"Bib file '{bib_path}' does not exist. Create it first via "
                "sci-literature-research cite mode."
            )
        bib_entries = parse_bib_file(bib_path)
        if not bib_entries:
            raise VerificationError(
                f"Manuscript has {len(used_keys)} citation markers but bib file "
                f"'{bib_path}' parses to zero entries. The gate refuses to run "
                "against an empty bib — fix the bib before verifying."
            )

    source_text = (
        Path(source_path).read_text(encoding="utf-8") if source_path else None
    )

    auto_fixes: list[dict] = []
    findings: list[dict] = []

    # Phase A: citation mechanics (auto-fix + key match)
    text, marker_fixes = fix_citation_markers(text)
    auto_fixes.extend(marker_fixes)
    # Re-extract after auto-fix (markers may have moved)
    used_keys = extract_used_keys(text)
    if not pure_expertise:
        findings.extend(check_bib_key_match(text, bib_entries))

    # Phase B: completeness (runs in both modes — applies to any prose)
    findings.extend(check_citation_density(text))
    findings.extend(check_figure_references(text))
    findings.extend(check_abbreviations(text))

    # Phase C: bib integrity (CrossRef title + retraction on USED keys only)
    # Skipped in pure-expertise mode — nothing to audit.
    if not pure_expertise:
        findings.extend(check_bib_integrity(used_keys, bib_entries))

    # Phase D: hedging (runs in both modes — overclaiming can happen
    # without citations too; source comparison only when a source is given)
    findings.extend(check_hedging(text, source_text))

    # Phase E: statistical reporting (runs in both modes)
    findings.extend(check_statistics(text))

    # Phase F + G: paperclip anchors + quote-or-cite sidecar
    # Skipped in pure-expertise mode — no markers → no sidecar required.
    if not pure_expertise:
        findings.extend(check_quote_sidecar(manuscript_path, used_keys, source_text))

    # Phase H (Tier 4): upstream provenance trace
    # Skipped in pure-expertise mode.
    if not pure_expertise and quotes_path:
        findings.extend(
            check_upstream_quotes_provenance(
                manuscript_path, used_keys, Path(quotes_path)
            )
        )

    # Phase I (Tier 5): live-source quote substring check.
    # Catches fabricated quotes attributed to real papers, by re-fetching
    # the abstract from CrossRef / arXiv and confirming the sidecar quote
    # appears verbatim. MAJOR (abstracts are not full text).
    if not pure_expertise:
        findings.extend(
            check_quotes_against_live_source(
                manuscript_path, used_keys, bib_entries
            )
        )

    # Phase J (Tier A5): inline attribution detection (pure-expertise mode).
    # Fires when no [@Key] markers exist but the prose contains author-year
    # references that the gate cannot audit.
    findings.extend(check_inline_attributions(text, used_keys))

    # Phase K (Tier A6): verify DOI/arXiv URLs embedded as inline links.
    # Applies in both modes — blog posts and Substack drafts use inline links
    # rather than [@Key] markers.
    findings.extend(check_inline_links(text, bib_entries if not pure_expertise else []))

    # Phase L (Tier A10): non-standard citation grammar.
    # Surfaces \cite{}, (Author, YYYY), and [N] style references that the
    # gate silently ignores — pushes the author to convert or acknowledge.
    findings.extend(check_non_standard_grammar(text))

    # Phase M (Tier C3): claim-quote alignment.
    # Checks that the manuscript sentence containing [@Key] has meaningful
    # token overlap with the sidecar quote — catches writers who cite Paper X
    # to support a claim that Paper X does not actually make.
    # Skipped in pure-expertise mode (no sidecar) and when quotes_path is absent.
    if not pure_expertise and quotes_path:
        findings.extend(
            check_unsupported_claims(text, used_keys, Path(quotes_path), manuscript_path)
        )

    # Phase N (Tier G): cross-bib contamination.
    # If a draft sidecar quote for [@KeyA] also appears verbatim in the upstream
    # seed for some other [@KeyB], the attribution is ambiguous — surfaces MAJOR
    # so the human can verify which paper actually contains that passage.
    # Skipped in pure-expertise mode and when quotes_path is absent.
    if not pure_expertise and quotes_path:
        findings.extend(
            check_cross_bib_contamination(
                manuscript_path, used_keys, Path(quotes_path)
            )
        )

    # Phase 8: scope-mismatch escalation.
    # The hedging-escalation pairs catch verb-strength shifts; this catches
    # *scope* shifts — animal model → human, in vitro → in vivo, pilot →
    # definitive, observational → causal. Same skip conditions as
    # check_unsupported_claims (no sidecar / no quotes file → silent).
    if not pure_expertise and quotes_path:
        findings.extend(
            check_scope_escalation(
                text, used_keys, Path(quotes_path), manuscript_path
            )
        )

    # Apply auto-fixes
    if apply_fixes and text != original_text:
        Path(manuscript_path).write_text(text, encoding="utf-8")

    # Summary counts. `info` and `note` are non-blocking advisory channels
    # (Phase 8 added the no-cite density NOTE); track them in the summary
    # so downstream consumers (substack push, export-md) can surface them.
    counts = {"critical": 0, "major": 0, "minor": 0, "info": 0, "pass": 0}
    for f in findings:
        sev = f.get("severity", "minor").lower()
        if sev == "note":
            sev = "info"
        if sev in counts:
            counts[sev] += 1

    blocked = counts["critical"] > 0

    # Log via repro
    try:
        log_operation(
            skill="sci-writing",
            operation="verify",
            params={
                "manuscript": manuscript_path,
                "bib": bib_path,
                "source": source_path,
                "apply_fixes": apply_fixes,
            },
            data_files=[manuscript_path]
                       + ([bib_path] if bib_path else [])
                       + ([source_path] if source_path else []),
            output_files=[manuscript_path] if (apply_fixes and text != original_text) else [],
            notes=(
                f"{len(findings)} findings, {len(auto_fixes)} auto-fixes, "
                f"blocked={blocked}, pure_expertise={pure_expertise}"
            ),
        )
    except Exception:
        pass  # Repro logging is best-effort

    return {
        "findings": findings,
        "auto_fixes": auto_fixes,
        "summary": counts,
        "blocked": blocked,
        "pure_expertise": pure_expertise,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Run the accuracy verification gate on a manuscript. "
            "CRITICAL findings block the save — exit code 2."
        )
    )
    parser.add_argument("manuscript", help="Path to manuscript .md file")
    parser.add_argument(
        "--bib",
        default=None,
        help="Path to .bib file. Required for cited content (with [@Key] "
             "markers). Optional for pure-expertise content (no citations).",
    )
    parser.add_argument("--source", help="Path to source material for hedging + quote check")
    parser.add_argument(
        "--quotes",
        help="Path to upstream quotes.json sidecar. When provided, every "
             "draft sidecar claim must trace to a candidate in this file "
             "(Tier 4 upstream provenance gate).",
    )
    parser.add_argument("--no-fix", action="store_true", help="Don't apply auto-fixes")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    try:
        report = run_verification(
            args.manuscript,
            bib_path=args.bib,
            source_path=args.source,
            quotes_path=args.quotes,
            apply_fixes=not args.no_fix,
        )
    except VerificationError as e:
        print(f"[REFUSED] {e}", file=sys.stderr)
        sys.exit(3)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"=== Verification Report: {args.manuscript} ===")
        print(f"Findings: {report['summary']}")
        print(f"Auto-fixes applied: {len(report['auto_fixes'])}")
        print(f"Blocked (CRITICAL > 0): {report['blocked']}")
        for f in report["findings"]:
            print(f"\n[{f['severity'].upper()}] {f['criterion']} ({f['section']})")
            print(f"  {f['finding']}")
            print(f"  → {f['suggestion']}")

    # Exit codes: 0 = pass, 2 = blocked by CRITICAL, 3 = refused (contract failure)
    sys.exit(2 if report["blocked"] else 0)
