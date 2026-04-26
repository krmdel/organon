"""Full-text PDF fetch for open-access papers.

Fetch priority for a given citation:
  1. arXiv PDF   — free, reliable, no API key required
  2. Unpaywall   — free OA resolver; requires UNPAYWALL_EMAIL env var
  3. PMC OA      — open-access full-text via NCBI FTP/efetch

Extracted text is cached at ~/.cache/scientific-os/fulltext/ for 30 days
so repeated verification runs don't re-download.

Public surface:
    fetch_full_text(doi=None, arxiv_id=None, pmid=None) -> str | None
        Main entry point.  Returns plain text or None if unavailable.

    fetch_open_access_pdf(doi=None, arxiv_id=None, pmid=None) -> Path | None
        Returns local path to the cached PDF (downloads if needed).

    extract_text_from_pdf(path: Path) -> str
        Extracts text from a PDF. Requires pdfminer.six (graceful degradation
        returns empty string when unavailable).

    quote_in_full_text(quote: str, full_text: str) -> bool
        Case/whitespace normalised substring check.

    UNPAYWALL_EMAIL is read from the env var of the same name.
    Set it once in .env — fulltext_fetch loads dotenv automatically.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

UNPAYWALL_BASE = "https://api.unpaywall.org/v2"
ARXIV_PDF_BASE = "https://arxiv.org/pdf"
PMC_EFETCH_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

FETCH_TIMEOUT_SECONDS = 30
PDF_CACHE_TTL_DAYS = 30
CACHE_MAX_SIZE_GB = 2.0
USER_AGENT = "Organon/1.0 (mailto:organon@example.com)"

_CACHE_DIR = Path.home() / ".cache" / "scientific-os" / "fulltext"


def _get_unpaywall_email() -> str:
    """Read UNPAYWALL_EMAIL from env or dotenv."""
    email = os.environ.get("UNPAYWALL_EMAIL", "").strip()
    if not email:
        # Try loading .env from repo root (same heuristic as other repro scripts)
        for candidate in [Path(".env"), Path(__file__).parent.parent / ".env"]:
            if candidate.exists():
                for line in candidate.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("UNPAYWALL_EMAIL=") and not line.startswith("#"):
                        email = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if email:
                            break
            if email:
                break
    return email


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _cache_key(identifier: str) -> str:
    return hashlib.sha1(identifier.encode()).hexdigest()


def _cache_path_pdf(key: str) -> Path:
    return _CACHE_DIR / f"{key}.pdf"


def _cache_path_txt(key: str) -> Path:
    return _CACHE_DIR / f"{key}.txt"


def _cache_path_meta(key: str) -> Path:
    return _CACHE_DIR / f"{key}.meta.json"


def _is_cache_fresh(key: str) -> bool:
    meta = _cache_path_meta(key)
    if not meta.exists():
        return False
    try:
        data = json.loads(meta.read_text())
        ts = data.get("fetched_at", 0)
        age_days = (time.time() - ts) / 86400
        return age_days < PDF_CACHE_TTL_DAYS
    except Exception:
        return False


def _write_cache_meta(key: str, identifier: str, source: str) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    meta = {
        "identifier": identifier,
        "source": source,
        "fetched_at": time.time(),
    }
    _cache_path_meta(key).write_text(json.dumps(meta, indent=2))


def _evict_cache_if_needed() -> None:
    """Simple LRU eviction: remove oldest files when cache exceeds max size."""
    if not _CACHE_DIR.exists():
        return
    files = sorted(_CACHE_DIR.iterdir(), key=lambda p: p.stat().st_mtime)
    total = sum(f.stat().st_size for f in files if f.is_file())
    limit = CACHE_MAX_SIZE_GB * 1024 ** 3
    while total > limit and files:
        oldest = files.pop(0)
        total -= oldest.stat().st_size
        oldest.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# PDF download helpers
# ---------------------------------------------------------------------------

def _download_pdf(url: str, dest: Path, timeout: float = FETCH_TIMEOUT_SECONDS) -> bool:
    """Download a PDF from url to dest.  Returns True on success."""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "")
            data = resp.read()
            # Reject obvious non-PDFs (e.g. HTML error pages redirected to 200)
            if b"%PDF" not in data[:8] and "pdf" not in content_type.lower():
                return False
            dest.write_bytes(data)
            return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Source-specific fetch functions
# ---------------------------------------------------------------------------

def _fetch_arxiv_pdf(arxiv_id: str) -> Optional[Path]:
    """Download arXiv PDF to cache.  Returns local path or None."""
    norm = arxiv_id.strip().lstrip("arXiv:").lstrip("arxiv:")
    # Normalise version suffix: use v1 explicitly if no version given
    cache_key = _cache_key(f"arxiv:{norm}")
    pdf_path = _cache_path_pdf(cache_key)

    if _is_cache_fresh(cache_key) and pdf_path.exists():
        return pdf_path

    url = f"{ARXIV_PDF_BASE}/{norm}.pdf"
    if _download_pdf(url, pdf_path):
        _write_cache_meta(cache_key, f"arxiv:{norm}", "arxiv")
        _evict_cache_if_needed()
        return pdf_path
    return None


def _query_unpaywall(doi: str, email: str) -> Optional[str]:
    """Query Unpaywall for an OA PDF URL. Returns URL or None."""
    if not email:
        return None
    url = f"{UNPAYWALL_BASE}/{doi}?email={email}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return None

    # Walk best_oa_location → oa_url
    best = data.get("best_oa_location") or {}
    oa_url = best.get("url_for_pdf") or best.get("url")
    if oa_url and oa_url.lower().endswith(".pdf"):
        return oa_url

    # Fallback: scan all OA locations for a PDF URL
    for loc in data.get("oa_locations", []):
        url_pdf = loc.get("url_for_pdf")
        if url_pdf and url_pdf.lower().endswith(".pdf"):
            return url_pdf

    return None


def _fetch_unpaywall_pdf(doi: str) -> Optional[Path]:
    """Fetch OA PDF via Unpaywall. Returns local path or None."""
    email = _get_unpaywall_email()
    if not email:
        return None

    cache_key = _cache_key(f"doi:{doi}")
    pdf_path = _cache_path_pdf(cache_key)
    if _is_cache_fresh(cache_key) and pdf_path.exists():
        return pdf_path

    oa_url = _query_unpaywall(doi, email)
    if not oa_url:
        return None

    if _download_pdf(oa_url, pdf_path):
        _write_cache_meta(cache_key, f"doi:{doi}", "unpaywall")
        _evict_cache_if_needed()
        return pdf_path
    return None


def _get_pmcid_for_pmid(pmid: str) -> Optional[str]:
    """Try to resolve PMID → PMCID via NCBI elink."""
    url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
        f"?dbfrom=pubmed&db=pmc&id={pmid}&retmode=json"
    )
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode())
        linksets = data.get("linksets", [])
        for ls in linksets:
            for ld in ls.get("linksetdbs", []):
                if ld.get("dbto") == "pmc":
                    ids = ld.get("links", [])
                    if ids:
                        return str(ids[0])
    except Exception:
        pass
    return None


def _fetch_pmc_pdf(pmid: str) -> Optional[Path]:
    """Fetch PMC open-access full text as PDF via FTP/efetch. Returns path or None."""
    pmcid = _get_pmcid_for_pmid(pmid)
    if not pmcid:
        return None

    cache_key = _cache_key(f"pmc:{pmcid}")
    pdf_path = _cache_path_pdf(cache_key)
    if _is_cache_fresh(cache_key) and pdf_path.exists():
        return pdf_path

    # PMC OA PDF via efetch (XML fallback when no PDF available)
    url = f"{PMC_EFETCH_BASE}?db=pmc&id={pmcid}&rettype=full&retmode=xml"
    # We won't get a PDF here — use the XML text instead; save as .txt
    txt_path = _cache_path_txt(cache_key)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_SECONDS) as resp:
            xml_text = resp.read().decode("utf-8", errors="replace")
        # Strip XML tags to get body text
        body = re.sub(r"<[^>]+>", " ", xml_text)
        body = re.sub(r"\s+", " ", body).strip()
        if len(body) > 500:  # minimal sanity check
            txt_path.write_text(body, encoding="utf-8")
            _write_cache_meta(cache_key, f"pmc:{pmcid}", "pmc")
            _evict_cache_if_needed()
            return txt_path  # returns a .txt, caller handles this
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# PDF text extraction
# ---------------------------------------------------------------------------

def extract_text_from_pdf(path: Path) -> str:
    """Extract plain text from a PDF using pdfminer.six.

    Falls back to empty string when pdfminer is unavailable so callers
    always get a str — never raises ImportError.

    Strips common PDF artefacts: ligatures (ﬁ→fi, ﬀ→ff), column-break
    hyphens, and excessive whitespace.
    """
    # If path is a .txt file (PMC XML was stored as text), just read it
    if path.suffix == ".txt":
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return ""

    try:
        from pdfminer.high_level import extract_text as pdfminer_extract  # type: ignore
    except ImportError:
        return ""

    try:
        raw = pdfminer_extract(str(path))
    except Exception:
        return ""

    if not raw:
        return ""

    # Normalise ligatures
    ligature_map = {
        "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl",
        "ﬃ": "ffi", "ﬄ": "ffl",
    }
    for lig, rep in ligature_map.items():
        raw = raw.replace(lig, rep)

    # Remove soft hyphens at line endings
    raw = re.sub(r"(\w)-\n(\w)", r"\1\2", raw)
    # Normalise whitespace
    raw = re.sub(r"[ \t]+", " ", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw.strip()


# ---------------------------------------------------------------------------
# Main public surface
# ---------------------------------------------------------------------------

def fetch_open_access_pdf(
    doi: Optional[str] = None,
    arxiv_id: Optional[str] = None,
    pmid: Optional[str] = None,
) -> Optional[Path]:
    """Attempt to obtain a local PDF/text path for an open-access paper.

    Fetch priority:
        1. arXiv PDF   (reliable, no key needed)
        2. Unpaywall   (needs UNPAYWALL_EMAIL env var)
        3. PMC OA XML  (needs PMID + PMCID linkage)

    Returns a Path to the local file, or None if no OA version is found.
    """
    if arxiv_id:
        result = _fetch_arxiv_pdf(arxiv_id)
        if result:
            return result

    if doi:
        result = _fetch_unpaywall_pdf(doi)
        if result:
            return result

    if pmid:
        result = _fetch_pmc_pdf(pmid)
        if result:
            return result

    return None


def fetch_full_text(
    doi: Optional[str] = None,
    arxiv_id: Optional[str] = None,
    pmid: Optional[str] = None,
) -> Optional[str]:
    """Fetch full text for an open-access paper.

    Returns plain text string or None when no OA version is available.
    The caller should treat None as "unknown" (fall back to abstract),
    not as evidence the paper doesn't exist.
    """
    # Check txt cache first (avoids re-running PDF extraction)
    for identifier, prefix in [
        (arxiv_id, "arxiv"),
        (doi, "doi"),
        (pmid, "pmid"),
    ]:
        if identifier:
            cache_key = _cache_key(f"{prefix}:{identifier}")
            txt_path = _cache_path_txt(cache_key)
            if _is_cache_fresh(cache_key) and txt_path.exists():
                try:
                    return txt_path.read_text(encoding="utf-8")
                except Exception:
                    pass

    pdf_path = fetch_open_access_pdf(doi=doi, arxiv_id=arxiv_id, pmid=pmid)
    if pdf_path is None:
        return None

    text = extract_text_from_pdf(pdf_path)
    if not text:
        return None

    # Cache the extracted text alongside the PDF
    cache_key = pdf_path.stem  # sha1 from filename
    txt_path = _cache_path_txt(cache_key)
    try:
        txt_path.write_text(text, encoding="utf-8")
    except Exception:
        pass

    return text


# ---------------------------------------------------------------------------
# Quote matching
# ---------------------------------------------------------------------------

_WHITESPACE_RE = re.compile(r"\s+")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9 ]")


def _normalize_for_ft_match(s: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    s = s.lower()
    s = _NON_ALNUM_RE.sub(" ", s)
    s = _WHITESPACE_RE.sub(" ", s).strip()
    return s


def quote_in_full_text(quote: str, full_text: str, min_chars: int = 20) -> bool:
    """Check whether quote appears in full_text (normalised match).

    Uses two passes:
      1. Exact normalised substring (fast).
      2. Head match: first 60% of the quote, in case line breaks or
         column artefacts split the passage.

    Returns False if the quote is too short to be meaningful (< min_chars).
    """
    if not quote or len(quote.strip()) < min_chars:
        return False
    norm_ft = _normalize_for_ft_match(full_text)
    norm_q = _normalize_for_ft_match(quote)
    if not norm_q:
        return False

    if norm_q in norm_ft:
        return True

    head_len = max(min_chars, int(len(norm_q) * 0.6))
    if norm_q[:head_len] in norm_ft:
        return True

    return False
