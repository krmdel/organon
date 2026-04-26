"""Citation verification via CrossRef REST API, arXiv Atom API, and NCBI efetch.

Checks DOIs against CrossRef, arXiv IDs against arXiv's public Atom API, and
PMIDs against the NCBI efetch API to retrieve metadata, detect retracted
papers, and surface author-list mismatches that pure title-similarity checks
miss.

Uses urllib.request (stdlib only) -- no requests library dependency.

Public surface:
    verify_doi(doi)            -> {title, authors, ...}     # CrossRef path
    verify_arxiv(arxiv_id)     -> {title, authors, ...}     # arXiv Atom path
    verify_pubmed(pmid)        -> {title, authors, ...}     # NCBI efetch path
    verify_citation(entry)     -> {title, authors, ..., source}
                                  # dispatcher: arXiv > PubMed > CrossRef
    extract_arxiv_id_from_doi  -> normalized arXiv id, or None
    normalize_pmid             -> canonical PMID string, or raises ValueError
"""

import json
import os
import re
import urllib.error
import urllib.request
import unicodedata
import xml.etree.ElementTree as ET

CROSSREF_BASE = "https://api.crossref.org/works"
ARXIV_API_BASE = "http://export.arxiv.org/api/query"
NCBI_EFETCH_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom"}
MAILTO = "organon@example.com"
USER_AGENT = "Organon/1.0 (mailto:organon@example.com)"

# Per-request timeout for CrossRef, arXiv, and NCBI API calls. verify_gate.py
# wraps the whole verify_ops run in a 120s outer timeout, but
# verify_doi() and verify_arxiv() are also called directly by
# review_ops and ad-hoc tools — a network stall with no timeout could
# hang those callers indefinitely. 15s matches the polite pool
# responsiveness in practice and leaves budget for the 90+ lookups a
# long manuscript can trigger.
CROSSREF_TIMEOUT_SECONDS = 15
ARXIV_TIMEOUT_SECONDS = 15
NCBI_TIMEOUT_SECONDS = 15

# NCBI PMID: 1-8 digit positive integer (current max is ~39M, well within 8 digits).
_PMID_RE = re.compile(r"^\d{1,8}$")


def verify_doi(doi: str, timeout: float = CROSSREF_TIMEOUT_SECONDS) -> dict:
    """Check a DOI against CrossRef (or arXiv for 10.48550/arXiv.* DOIs).

    10.48550/arXiv.XXXX.YYYYY DOIs are arXiv canonical DOIs that CrossRef
    cannot resolve to full metadata. They are re-routed to verify_arxiv()
    so callers that go through verify_doi directly (rather than the
    verify_citation() dispatcher) still get correct author + title data.

    Args:
        doi: The DOI to verify (e.g., "10.1038/s41586-024-00001-0").

    Returns:
        Dict with keys: doi, title, authors, published, journal,
        is_retracted, retraction_info, type, source.

    Raises:
        ValueError: If the DOI is not found (404 from CrossRef).
        ConnectionError: If the CrossRef API is unreachable.
    """
    arxiv_id = extract_arxiv_id_from_doi(doi)
    if arxiv_id:
        return verify_arxiv(arxiv_id, timeout=timeout)

    url = f"{CROSSREF_BASE}/{doi}?mailto={MAILTO}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise ValueError(
                "DOI not found in CrossRef. Check the DOI format and try again."
            )
        raise ConnectionError(
            f"CrossRef API returned HTTP {e.code}."
        )
    except urllib.error.URLError as e:
        # URLError wraps socket.timeout in Python 3.10+; surface it as a
        # ConnectionError with an actionable message so callers can
        # distinguish "network issue" from "bad DOI".
        import socket
        if isinstance(e.reason, socket.timeout):
            raise ConnectionError(
                f"CrossRef API timed out after {timeout:.0f}s. "
                f"Retry, or skip this DOI if it's persistently slow."
            )
        raise ConnectionError(
            "Could not reach CrossRef API. Check your network connection."
        )
    except TimeoutError:
        raise ConnectionError(
            f"CrossRef API timed out after {timeout:.0f}s. "
            f"Retry, or skip this DOI if it's persistently slow."
        )

    # Phase 9: harden against malformed 200 responses. CrossRef occasionally
    # returns a 200 with empty body, missing "message" key, or a stub object.
    # Pre-Phase-9 this raised KeyError, which escaped past the upstream
    # (ValueError, ConnectionError) handler in check_bib_integrity and
    # surfaced as an uncaught exception in the substack/export gate path.
    if not isinstance(data, dict) or "message" not in data:
        raise ValueError(
            f"CrossRef returned a malformed 200 response for DOI '{doi}' "
            "(no 'message' field). Treating as unverifiable."
        )
    work = data.get("message")
    if not isinstance(work, dict):
        raise ValueError(
            f"CrossRef returned an unexpected payload shape for DOI '{doi}'."
        )

    is_retracted = False
    retraction_info = None

    # Check update-to field for retraction notices
    if "update-to" in work:
        for update in work["update-to"]:
            if update.get("type") == "retraction":
                is_retracted = True
                retraction_info = update
                break

    return {
        "doi": doi,
        "title": (work.get("title") or [""])[0],
        "authors": [a.get("family", "") for a in work.get("author", [])],
        "abstract": work.get("abstract", "") or "",
        "published": work.get("published-print", work.get("published-online", {})),
        "journal": (work.get("container-title") or [""])[0],
        "is_retracted": is_retracted,
        "retraction_info": retraction_info,
        "type": work.get("type"),
        "source": "crossref",
    }


# ---------------------------------------------------------------------------
# arXiv Atom API
# ---------------------------------------------------------------------------


_ARXIV_ID_RE = re.compile(
    r"^(?:arxiv:)?(\d{4}\.\d{4,5})(v\d+)?$",
    re.IGNORECASE,
)
# Legacy arXiv ids: subject/NNNNNNN  (e.g. astro-ph/0608061, cond-mat/0102001).
# Subject is lowercase letters with optional hyphen.
_ARXIV_OLD_ID_RE = re.compile(
    r"^(?:arxiv:)?([a-z][a-z\-]+/\d{7})(v\d+)?$",
    re.IGNORECASE,
)


def normalize_arxiv_id(raw: str) -> str:
    """Strip prefix and trailing version suffix; return the canonical id."""
    if not raw:
        raise ValueError("arXiv id is empty")
    raw = raw.strip()
    m = _ARXIV_ID_RE.match(raw)
    if m:
        return m.group(1)
    m = _ARXIV_OLD_ID_RE.match(raw)
    if m:
        return m.group(1)
    raise ValueError(
        f"'{raw}' does not look like an arXiv id "
        "(expected NNNN.NNNNN or e.g. cond-mat.mes-hall/0102001)"
    )


def extract_arxiv_id_from_doi(doi: str) -> str | None:
    """Pull the arXiv id out of a 10.48550/arXiv.* DOI, if present."""
    if not doi:
        return None
    doi = doi.strip().lower()
    m = re.match(r"^10\.48550/arxiv\.(.+)$", doi)
    if m:
        try:
            return normalize_arxiv_id(m.group(1))
        except ValueError:
            return None
    return None


def _strip_diacritics(s: str) -> str:
    """Fold combining marks. 'Pólik' -> 'Polik'."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    )


def _arxiv_surname(full_name: str) -> str:
    """Best-effort surname extractor for arXiv author full names.

    arXiv returns names in 'Given Family' order. Handle particles
    ('de la', 'van der', 'von') by treating everything from the first
    lowercase particle onwards as the surname.
    """
    if not full_name:
        return ""
    name = full_name.strip()
    # Drop trailing affiliation in parentheses or after comma+space
    name = re.sub(r"\s*\(.*?\)\s*$", "", name)
    parts = name.split()
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    # Walk from left and find the first lowercase word — likely a particle.
    particles = {
        "de", "del", "della", "der", "di", "du", "la", "le", "lo", "van",
        "von", "y", "ten", "ter", "den", "dos", "das",
    }
    for i in range(1, len(parts) - 1):
        token = _strip_diacritics(parts[i]).lower()
        if token in particles:
            return " ".join(parts[i:])
    return parts[-1]


def verify_arxiv(arxiv_id: str, timeout: float = ARXIV_TIMEOUT_SECONDS) -> dict:
    """Fetch arXiv paper metadata via the public Atom API.

    Args:
        arxiv_id: An arXiv id (with or without 'arXiv:' prefix and
            optional version suffix). Both new (NNNN.NNNNN) and legacy
            (subject/NNNNNNN) formats are accepted.

    Returns:
        Dict with keys: arxiv_id, title, authors, full_authors,
        published, abstract, source. `authors` is the list of family
        names (best-effort extraction); `full_authors` is the raw list
        of "Given Family" strings as arXiv returned them.

    Raises:
        ValueError: If the id is malformed or arXiv returns no entry
            (paper does not exist).
        ConnectionError: If arXiv is unreachable or times out.
    """
    canonical = normalize_arxiv_id(arxiv_id)
    url = f"{ARXIV_API_BASE}?id_list={canonical}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
    except urllib.error.HTTPError as e:
        raise ConnectionError(f"arXiv API returned HTTP {e.code}.") from e
    except urllib.error.URLError as e:
        import socket

        if isinstance(e.reason, socket.timeout):
            raise ConnectionError(
                f"arXiv API timed out after {timeout:.0f}s."
            ) from e
        raise ConnectionError("Could not reach arXiv API.") from e
    except TimeoutError as e:
        raise ConnectionError(
            f"arXiv API timed out after {timeout:.0f}s."
        ) from e

    try:
        root = ET.fromstring(body)
    except ET.ParseError as e:
        raise ConnectionError(f"arXiv API returned malformed XML: {e}") from e

    entry = root.find("atom:entry", ARXIV_NS)
    if entry is None:
        raise ValueError(
            f"arXiv id '{canonical}' returned no entry — id may be wrong or withdrawn."
        )

    # arXiv occasionally returns a placeholder entry for unknown ids
    # whose title is literally "Error". Detect and refuse.
    title_el = entry.find("atom:title", ARXIV_NS)
    title_text = (title_el.text or "").strip() if title_el is not None else ""
    if title_text.lower() == "error":
        raise ValueError(f"arXiv id '{canonical}' resolves to an error entry.")
    # Collapse internal whitespace runs so "Multi  line\n   title" -> "Multi line title".
    title_text = re.sub(r"\s+", " ", title_text)

    summary_el = entry.find("atom:summary", ARXIV_NS)
    abstract_text = ""
    if summary_el is not None and summary_el.text:
        abstract_text = re.sub(r"\s+", " ", summary_el.text).strip()

    pub_el = entry.find("atom:published", ARXIV_NS)
    published = (pub_el.text or "") if pub_el is not None else ""

    full_authors: list[str] = []
    surnames: list[str] = []
    for author_el in entry.findall("atom:author", ARXIV_NS):
        name_el = author_el.find("atom:name", ARXIV_NS)
        if name_el is None or not name_el.text:
            continue
        full = re.sub(r"\s+", " ", name_el.text).strip()
        full_authors.append(full)
        surnames.append(_arxiv_surname(full))

    # Phase 9 — withdrawn-preprint detection. arXiv flags a withdrawal in the
    # comment field (e.g. "This paper has been withdrawn by the authors."),
    # the title prefix, or the summary body. Pre-Phase-9 we always returned
    # is_retracted=False, so a writer citing a withdrawn arXiv paper passed
    # the gate cleanly. We now mirror the CrossRef retraction signalling.
    is_retracted = False
    retraction_info = None
    comment_el = entry.find(
        "{http://arxiv.org/schemas/atom}comment"
    )
    comment_text = ""
    if comment_el is not None and comment_el.text:
        comment_text = comment_el.text.strip()
    withdrawn_re = re.compile(
        r"\b(?:withdraw(?:n|al)?|paper\s+is\s+withdrawn|been\s+withdrawn)\b",
        re.IGNORECASE,
    )
    sources_to_scan = (title_text, abstract_text, comment_text)
    for source in sources_to_scan:
        if source and withdrawn_re.search(source):
            is_retracted = True
            retraction_info = {
                "type": "withdrawn",
                "source": "arxiv",
                "comment": comment_text or None,
                "detail": (
                    "arXiv preprint flagged as withdrawn by author. "
                    "Verify against the canonical record before citing."
                ),
            }
            break

    return {
        "arxiv_id": canonical,
        "title": title_text,
        "authors": surnames,
        "full_authors": full_authors,
        "abstract": abstract_text,
        "published": published,
        "source": "arxiv",
        # Mirror the verify_doi shape so callers can treat the two as one type.
        "doi": "",
        "journal": "arXiv preprint",
        "is_retracted": is_retracted,
        "retraction_info": retraction_info,
        "type": "preprint",
    }


# ---------------------------------------------------------------------------
# NCBI PubMed efetch API
# ---------------------------------------------------------------------------


def normalize_pmid(raw: str) -> str:
    """Strip PMID: prefix and whitespace; validate as 1-8 digits.

    Accepts: "12345678", "PMID:12345678", "PMID: 12345678", " 12345678 ".
    Raises ValueError for empty or non-numeric input.
    """
    if not raw:
        raise ValueError("PMID is empty")
    raw = raw.strip()
    raw = re.sub(r"^pmid:?\s*", "", raw, flags=re.IGNORECASE).strip()
    if not _PMID_RE.match(raw):
        raise ValueError(
            f"'{raw}' is not a valid PMID (expected 1-8 digits, got '{raw}')"
        )
    return raw


def verify_pubmed(pmid: str, timeout: float = NCBI_TIMEOUT_SECONDS) -> dict:
    """Fetch PubMed paper metadata via NCBI efetch API (XML mode).

    Reads NCBI_API_KEY from the environment if present — with a key the
    NCBI polite pool allows 10 req/s vs 3 req/s without. The key is sourced
    at call time so the .env shim in scripts/with-env.sh is honoured even
    if the module was imported before the env was populated.

    Returns the same uniform shape as verify_doi / verify_arxiv so callers
    can treat all three backends identically:
        {pmid, title, authors, abstract, published, journal, doi,
         is_retracted, retraction_info, type, source}

    Raises:
        ValueError: If the PMID is malformed or NCBI returns no article.
        ConnectionError: If the NCBI efetch endpoint is unreachable.
    """
    canonical = normalize_pmid(pmid)

    api_key = os.environ.get("NCBI_API_KEY", "").strip()
    params = f"db=pubmed&id={canonical}&rettype=abstract&retmode=xml"
    if api_key:
        params += f"&api_key={api_key}"

    url = f"{NCBI_EFETCH_BASE}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 400:
            raise ValueError(
                f"NCBI rejected PMID '{canonical}' (HTTP 400). Check the PMID."
            )
        raise ConnectionError(f"NCBI efetch returned HTTP {e.code}.")
    except urllib.error.URLError as e:
        import socket
        if isinstance(e.reason, socket.timeout):
            raise ConnectionError(
                f"NCBI efetch timed out after {timeout:.0f}s."
            )
        raise ConnectionError("Could not reach NCBI efetch API. Check your network.")
    except TimeoutError:
        raise ConnectionError(f"NCBI efetch timed out after {timeout:.0f}s.")

    try:
        root = ET.fromstring(body)
    except ET.ParseError as e:
        raise ConnectionError(f"NCBI efetch returned malformed XML: {e}")

    article = root.find(".//PubmedArticle")
    if article is None:
        raise ValueError(
            f"PMID {canonical} returned no article from NCBI — check the PMID."
        )

    # Article title (strip trailing period that MEDLINE sometimes appends)
    title_el = article.find(".//ArticleTitle")
    title = (title_el.text or "").strip() if title_el is not None else ""
    title = re.sub(r"\s+", " ", title).rstrip(".")

    # Author surnames — LastName elements; fall back to CollectiveName
    surnames: list[str] = []
    for author_el in article.findall(".//AuthorList/Author"):
        last_el = author_el.find("LastName")
        if last_el is not None and last_el.text:
            surnames.append(last_el.text.strip())
        else:
            collective_el = author_el.find("CollectiveName")
            if collective_el is not None and collective_el.text:
                surnames.append(collective_el.text.strip())

    # Abstract — may be structured (multiple AbstractText with Label attrs)
    abstract_parts: list[str] = []
    for abs_el in article.findall(".//AbstractText"):
        text = abs_el.text or ""
        label = abs_el.get("Label", "")
        if label:
            abstract_parts.append(f"{label}: {text.strip()}")
        else:
            abstract_parts.append(text.strip())
    abstract = re.sub(r"\s+", " ", " ".join(abstract_parts)).strip()

    # Journal title
    journal_el = article.find(".//Journal/Title")
    journal = (journal_el.text or "").strip() if journal_el is not None else ""

    # Publication year
    year_el = article.find(".//PubDate/Year")
    month_el = article.find(".//PubDate/Month")
    year = (year_el.text or "").strip() if year_el is not None else ""
    month = (month_el.text or "").strip() if month_el is not None else ""
    published = f"{year} {month}".strip()

    # DOI from ArticleIdList (preferred) or ELocationID
    doi = ""
    for aid_el in article.findall(".//ArticleId"):
        if aid_el.get("IdType") == "doi":
            doi = (aid_el.text or "").strip()
            break
    if not doi:
        for loc_el in article.findall(".//ELocationID"):
            if loc_el.get("EIdType") == "doi":
                doi = (loc_el.text or "").strip()
                break

    # A9: Retraction detection — check PublicationType list and
    # CommentsCorrectionsList for RetractionIn / RetractionOf notices.
    is_retracted = False
    retraction_info = None
    for pt_el in article.findall(".//PublicationType"):
        if (pt_el.text or "").strip().lower() in (
            "retracted publication",
            "retraction of publication",
        ):
            is_retracted = True
            retraction_info = "PubMed PublicationType: Retracted Publication"
            break
    if not is_retracted:
        for cc_el in article.findall(".//CommentsCorrections"):
            ref_type = cc_el.get("RefType", "")
            if ref_type in ("RetractionIn", "RetractionOf"):
                is_retracted = True
                pmid_ref = ""
                pmid_el = cc_el.find("PMID")
                if pmid_el is not None:
                    pmid_ref = (pmid_el.text or "").strip()
                retraction_info = (
                    f"PubMed CommentsCorrectionsList RefType={ref_type}"
                    + (f" (PMID {pmid_ref})" if pmid_ref else "")
                )
                break

    return {
        "pmid": canonical,
        "title": title,
        "authors": surnames,
        "abstract": abstract,
        "published": published,
        "journal": journal,
        "doi": doi,
        "is_retracted": is_retracted,
        "retraction_info": retraction_info,
        "type": "journal-article",
        "source": "pubmed",
    }


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


def _titles_agree(t1: str, t2: str, threshold: float = 0.85) -> bool:
    """Loose title agreement check for dual-backend cross-validation."""
    from difflib import SequenceMatcher

    def _norm(t: str) -> str:
        return re.sub(r"\W+", " ", t.lower()).strip()

    return SequenceMatcher(None, _norm(t1), _norm(t2)).ratio() >= threshold


def verify_citation(entry: dict) -> dict:
    """Pick the right backend for a bib entry and return uniform metadata.

    Preference order:
      1. arXiv if the entry has `eprint` (or a 10.48550/arXiv.* DOI).
         arXiv preprints are commonly missing from CrossRef; calling
         arXiv directly is the only path that catches author/title
         mismatches on preprints.
      2. PubMed if the entry has a `pmid` field — PubMed returns abstracts
         that CrossRef often omits, which feeds the live-source quote check.
      3. CrossRef if the entry has a `doi` field.

    A8 — dual-id cross-check: when the entry carries BOTH an `eprint` AND
    a `doi` (that is not just the canonical arXiv DOI for the same eprint),
    both backends are queried and their titles are compared. A mismatch
    means the bib has internally inconsistent identifiers — e.g. a real
    arXiv id paired with a fabricated DOI pointing to a different paper.
    The primary (arXiv) result is returned but carries `dual_id_conflict=True`
    and `dual_id_detail` so callers (check_bib_integrity) can surface CRITICAL.

    Raises:
        ValueError: If the entry has no usable arXiv id, PMID, or DOI.
        Network errors propagate from the underlying backend.
    """
    eprint = (entry.get("eprint") or "").strip()
    doi = (entry.get("doi") or "").strip()
    pmid = (entry.get("pmid") or "").strip()

    # A8: dual-id consistency. Run both when eprint + doi are present and
    # the doi is NOT the canonical 10.48550/arXiv.* alias for this eprint.
    arxiv_from_doi = extract_arxiv_id_from_doi(doi)
    if eprint and doi and not arxiv_from_doi:
        primary = verify_arxiv(eprint)
        try:
            secondary = verify_doi(doi)
            primary_title = primary.get("title", "")
            secondary_title = secondary.get("title", "")
            if primary_title and secondary_title and not _titles_agree(
                primary_title, secondary_title
            ):
                primary["dual_id_conflict"] = True
                primary["dual_id_detail"] = (
                    f"eprint='{eprint}' resolves to '{primary_title}' "
                    f"but doi='{doi}' resolves to '{secondary_title}'. "
                    "These identifiers point to different papers — the bib "
                    "entry has inconsistent identifiers."
                )
            else:
                primary["dual_id_conflict"] = False
                primary["dual_id_detail"] = ""
        except (ValueError, ConnectionError):
            # DOI lookup failed — can't cross-check; flag as inconclusive
            primary["dual_id_conflict"] = None
            primary["dual_id_detail"] = (
                f"Could not fetch doi='{doi}' to cross-check against "
                f"eprint='{eprint}'. Manual verification recommended."
            )
        return primary

    if eprint:
        return verify_arxiv(eprint)

    if arxiv_from_doi:
        return verify_arxiv(arxiv_from_doi)

    if pmid:
        return verify_pubmed(pmid)

    if doi:
        return verify_doi(doi)

    raise ValueError(
        "Bib entry has neither a DOI, arXiv eprint, nor PMID — cannot verify."
    )


def batch_verify(dois: list[str]) -> list[dict]:
    """Verify multiple DOIs, continuing past individual failures.

    Args:
        dois: List of DOI strings to verify.

    Returns:
        List of result dicts. Failed DOIs include an 'error' key
        and is_retracted=None.
    """
    results = []
    for doi in dois:
        try:
            result = verify_doi(doi)
            results.append(result)
        except (ValueError, ConnectionError) as e:
            results.append({
                "doi": doi,
                "error": str(e),
                "is_retracted": None,
            })
    return results
