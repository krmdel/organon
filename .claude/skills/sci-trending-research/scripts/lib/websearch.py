"""WebSearch module for last30days skill.

Adapted from https://github.com/Ronnie-Nutrition/last30days-skill

NOTE: WebSearch uses Claude's built-in WebSearch tool, which runs INSIDE Claude Code.
Unlike Reddit/X which use external APIs, WebSearch results are obtained by Claude
directly and passed to this module for normalization and scoring.
"""

import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from . import schema


MONTH_MAP = {
    "jan": 1, "january": 1, "feb": 2, "february": 2,
    "mar": 3, "march": 3, "apr": 4, "april": 4,
    "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def extract_date_from_url(url: str) -> Optional[str]:
    match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)
    if match:
        year, month, day = match.groups()
        if 2020 <= int(year) <= 2030 and 1 <= int(month) <= 12 and 1 <= int(day) <= 31:
            return f"{year}-{month}-{day}"
    match = re.search(r'/(\d{4})-(\d{2})-(\d{2})[-/]', url)
    if match:
        year, month, day = match.groups()
        if 2020 <= int(year) <= 2030 and 1 <= int(month) <= 12 and 1 <= int(day) <= 31:
            return f"{year}-{month}-{day}"
    match = re.search(r'/(\d{4})(\d{2})(\d{2})/', url)
    if match:
        year, month, day = match.groups()
        if 2020 <= int(year) <= 2030 and 1 <= int(month) <= 12 and 1 <= int(day) <= 31:
            return f"{year}-{month}-{day}"
    return None


def extract_date_from_snippet(text: str) -> Optional[str]:
    if not text:
        return None
    text_lower = text.lower()

    match = re.search(
        r'\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|'
        r'jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)'
        r'\s+(\d{1,2})(?:st|nd|rd|th)?,?\s*(\d{4})\b',
        text_lower
    )
    if match:
        month_str, day, year = match.groups()
        month = MONTH_MAP.get(month_str[:3])
        if month and 2020 <= int(year) <= 2030 and 1 <= int(day) <= 31:
            return f"{year}-{month:02d}-{int(day):02d}"

    match = re.search(
        r'\b(\d{1,2})(?:st|nd|rd|th)?\s+'
        r'(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|'
        r'jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)'
        r'\s+(\d{4})\b',
        text_lower
    )
    if match:
        day, month_str, year = match.groups()
        month = MONTH_MAP.get(month_str[:3])
        if month and 2020 <= int(year) <= 2030 and 1 <= int(day) <= 31:
            return f"{year}-{month:02d}-{int(day):02d}"

    match = re.search(r'\b(\d{4})-(\d{2})-(\d{2})\b', text)
    if match:
        year, month, day = match.groups()
        if 2020 <= int(year) <= 2030 and 1 <= int(month) <= 12 and 1 <= int(day) <= 31:
            return f"{year}-{month}-{day}"

    today = datetime.now()
    if "yesterday" in text_lower:
        date = today - timedelta(days=1)
        return date.strftime("%Y-%m-%d")
    if "today" in text_lower:
        return today.strftime("%Y-%m-%d")
    match = re.search(r'\b(\d+)\s*days?\s*ago\b', text_lower)
    if match:
        days = int(match.group(1))
        if days <= 60:
            date = today - timedelta(days=days)
            return date.strftime("%Y-%m-%d")
    match = re.search(r'\b(\d+)\s*hours?\s*ago\b', text_lower)
    if match:
        return today.strftime("%Y-%m-%d")
    if "last week" in text_lower:
        date = today - timedelta(days=7)
        return date.strftime("%Y-%m-%d")
    if "this week" in text_lower:
        date = today - timedelta(days=3)
        return date.strftime("%Y-%m-%d")
    return None


def extract_date_signals(url: str, snippet: str, title: str) -> Tuple[Optional[str], str]:
    url_date = extract_date_from_url(url)
    if url_date:
        return url_date, "high"
    snippet_date = extract_date_from_snippet(snippet)
    if snippet_date:
        return snippet_date, "med"
    title_date = extract_date_from_snippet(title)
    if title_date:
        return title_date, "med"
    return None, "low"


EXCLUDED_DOMAINS = {
    "reddit.com", "www.reddit.com", "old.reddit.com",
    "twitter.com", "www.twitter.com", "x.com", "www.x.com",
    "mobile.twitter.com",
}


def extract_domain(url: str) -> str:
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def is_excluded_domain(url: str) -> bool:
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        return domain in EXCLUDED_DOMAINS
    except Exception:
        return False


def parse_websearch_results(
    results: List[Dict[str, Any]], topic: str,
    from_date: str = "", to_date: str = "",
) -> List[Dict[str, Any]]:
    items = []
    for i, result in enumerate(results):
        if not isinstance(result, dict):
            continue
        url = result.get("url", "")
        if not url:
            continue
        if is_excluded_domain(url):
            continue

        title = str(result.get("title", "")).strip()
        snippet = str(result.get("snippet", result.get("description", ""))).strip()
        if not title and not snippet:
            continue

        date = result.get("date")
        date_confidence = "low"
        if date and re.match(r'^\d{4}-\d{2}-\d{2}$', str(date)):
            date_confidence = "med"
        else:
            extracted_date, confidence = extract_date_signals(url, snippet, title)
            if extracted_date:
                date = extracted_date
                date_confidence = confidence

        if date and from_date and date < from_date:
            continue
        if date and to_date and date > to_date:
            continue

        relevance = result.get("relevance", 0.5)
        try:
            relevance = min(1.0, max(0.0, float(relevance)))
        except (TypeError, ValueError):
            relevance = 0.5

        item = {
            "id": f"W{i+1}",
            "title": title[:200],
            "url": url,
            "source_domain": extract_domain(url),
            "snippet": snippet[:500],
            "date": date,
            "date_confidence": date_confidence,
            "relevance": relevance,
            "why_relevant": str(result.get("why_relevant", "")).strip(),
        }
        items.append(item)
    return items


def normalize_websearch_items(
    items: List[Dict[str, Any]], from_date: str, to_date: str,
) -> List[schema.WebSearchItem]:
    result = []
    for item in items:
        web_item = schema.WebSearchItem(
            id=item["id"], title=item["title"], url=item["url"],
            source_domain=item["source_domain"], snippet=item["snippet"],
            date=item.get("date"), date_confidence=item.get("date_confidence", "low"),
            relevance=item.get("relevance", 0.5),
            why_relevant=item.get("why_relevant", ""),
        )
        result.append(web_item)
    return result


def dedupe_websearch(items: List[schema.WebSearchItem]) -> List[schema.WebSearchItem]:
    seen_urls = set()
    result = []
    for item in items:
        url_key = item.url.lower().rstrip("/")
        if url_key not in seen_urls:
            seen_urls.add(url_key)
            result.append(item)
    return result
