"""URL verification for @misc bib entries that have only a URL identifier.

Used by verify_ops.py check_bib_integrity (Tier A3) to confirm URL-only
citations resolve and the page title plausibly matches the bib title field.

Public surface:
    verify_url(url, bib_title) -> {url, status_code, page_title,
                                    title_match_ratio, is_accessible,
                                    error}
"""

from __future__ import annotations

import re
import urllib.error
import urllib.request
from difflib import SequenceMatcher

USER_AGENT = "Organon/1.0 (mailto:organon@example.com)"
URL_TIMEOUT_SECONDS = 10

# Minimum ratio for page-title vs bib-title to count as a match.
URL_TITLE_MATCH_THRESHOLD = 0.60


def _fetch_head_then_get(url: str, timeout: float = URL_TIMEOUT_SECONDS) -> tuple[int, str]:
    """Return (status_code, body_excerpt).

    First tries HEAD (fast, no body); if that fails with method-not-allowed
    or a non-2xx, falls through to GET with a small byte range.
    """
    req = urllib.request.Request(
        url,
        method="HEAD",
        headers={"User-Agent": USER_AGENT},
    )
    body = ""
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, ""
    except urllib.error.HTTPError as e:
        if e.code in (405, 501):
            pass  # HEAD not allowed, fall through to GET
        else:
            return e.code, ""
    except urllib.error.URLError:
        return 0, ""

    # GET — read just the first 8 KB to extract the <title>
    req_get = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Range": "bytes=0-8191"},
    )
    try:
        with urllib.request.urlopen(req_get, timeout=timeout) as resp:
            raw = resp.read(8192).decode("utf-8", errors="replace")
            return resp.status, raw
    except urllib.error.HTTPError as e:
        return e.code, ""
    except urllib.error.URLError:
        return 0, ""


def _extract_page_title(html_snippet: str) -> str:
    """Extract the <title> content from an HTML snippet."""
    m = re.search(r"<title[^>]*>([^<]{1,300})</title>", html_snippet, re.IGNORECASE)
    if m:
        title = m.group(1).strip()
        # Decode common HTML entities
        title = re.sub(r"&amp;", "&", title)
        title = re.sub(r"&lt;", "<", title)
        title = re.sub(r"&gt;", ">", title)
        title = re.sub(r"&quot;", '"', title)
        title = re.sub(r"&#?\w+;", " ", title)
        return re.sub(r"\s+", " ", title).strip()
    return ""


def _norm_title(t: str) -> str:
    return re.sub(r"\W+", " ", t.lower()).strip()


def verify_url(url: str, bib_title: str = "") -> dict:
    """Check that a URL is accessible and its page title matches the bib title.

    Returns a dict with:
        url             — the checked URL
        status_code     — HTTP status (0 = network error)
        page_title      — extracted <title> or empty string
        title_match_ratio — SequenceMatcher ratio (0.0–1.0); -1 if no bib_title
        is_accessible   — True when status_code is 2xx or 3xx
        error           — human-readable problem description, or empty
    """
    result: dict = {
        "url": url,
        "status_code": 0,
        "page_title": "",
        "title_match_ratio": -1.0,
        "is_accessible": False,
        "error": "",
    }

    if not url or not url.startswith(("http://", "https://")):
        result["error"] = f"Not a valid http/https URL: '{url}'"
        return result

    try:
        status, body = _fetch_head_then_get(url)
    except Exception as exc:
        result["error"] = f"Network error fetching '{url}': {exc}"
        return result

    result["status_code"] = status
    result["is_accessible"] = 200 <= status < 400

    if body:
        result["page_title"] = _extract_page_title(body)

    if bib_title and result["page_title"]:
        ratio = SequenceMatcher(
            None, _norm_title(bib_title), _norm_title(result["page_title"])
        ).ratio()
        result["title_match_ratio"] = round(ratio, 4)
    elif bib_title and not result["page_title"]:
        result["title_match_ratio"] = -1.0  # can't compare

    if not result["is_accessible"]:
        result["error"] = (
            f"URL returned HTTP {status} — resource may be deleted, moved, "
            "or behind a paywall."
        )
    elif bib_title and result["page_title"] and result["title_match_ratio"] >= 0:
        if result["title_match_ratio"] < URL_TITLE_MATCH_THRESHOLD:
            result["error"] = (
                f"Page title '{result['page_title']}' does not match bib title "
                f"'{bib_title}' (similarity {result['title_match_ratio']:.2f} < "
                f"{URL_TITLE_MATCH_THRESHOLD}). The URL may point to the wrong resource."
            )

    return result
