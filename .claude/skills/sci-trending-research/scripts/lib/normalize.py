"""Normalization of raw API data to canonical schema.

Adapted from https://github.com/Ronnie-Nutrition/last30days-skill
"""

from typing import Any, Dict, List, TypeVar, Union

from . import dates, schema

T = TypeVar("T", schema.RedditItem, schema.XItem, schema.WebSearchItem)


def filter_by_date_range(
    items: List[T], from_date: str, to_date: str, require_date: bool = False,
) -> List[T]:
    """Hard filter: Remove items outside the date range."""
    result = []
    for item in items:
        if item.date is None:
            if not require_date:
                result.append(item)
            continue
        if item.date < from_date:
            continue
        if item.date > to_date:
            continue
        result.append(item)
    return result


def normalize_reddit_items(
    items: List[Dict[str, Any]], from_date: str, to_date: str,
) -> List[schema.RedditItem]:
    """Normalize raw Reddit items to schema."""
    normalized = []
    for item in items:
        engagement = None
        eng_raw = item.get("engagement")
        if isinstance(eng_raw, dict):
            engagement = schema.Engagement(
                score=eng_raw.get("score"),
                num_comments=eng_raw.get("num_comments"),
                upvote_ratio=eng_raw.get("upvote_ratio"),
            )

        top_comments = []
        for c in item.get("top_comments", []):
            top_comments.append(schema.Comment(
                score=c.get("score", 0), date=c.get("date"),
                author=c.get("author", ""), excerpt=c.get("excerpt", ""),
                url=c.get("url", ""),
            ))

        date_str = item.get("date")
        date_confidence = dates.get_date_confidence(date_str, from_date, to_date)

        normalized.append(schema.RedditItem(
            id=item.get("id", ""), title=item.get("title", ""),
            url=item.get("url", ""), subreddit=item.get("subreddit", ""),
            date=date_str, date_confidence=date_confidence,
            engagement=engagement, top_comments=top_comments,
            comment_insights=item.get("comment_insights", []),
            relevance=item.get("relevance", 0.5),
            why_relevant=item.get("why_relevant", ""),
        ))
    return normalized


def normalize_x_items(
    items: List[Dict[str, Any]], from_date: str, to_date: str,
) -> List[schema.XItem]:
    """Normalize raw X items to schema."""
    normalized = []
    for item in items:
        engagement = None
        eng_raw = item.get("engagement")
        if isinstance(eng_raw, dict):
            engagement = schema.Engagement(
                likes=eng_raw.get("likes"), reposts=eng_raw.get("reposts"),
                replies=eng_raw.get("replies"), quotes=eng_raw.get("quotes"),
            )

        date_str = item.get("date")
        date_confidence = dates.get_date_confidence(date_str, from_date, to_date)

        normalized.append(schema.XItem(
            id=item.get("id", ""), text=item.get("text", ""),
            url=item.get("url", ""), author_handle=item.get("author_handle", ""),
            date=date_str, date_confidence=date_confidence,
            engagement=engagement, relevance=item.get("relevance", 0.5),
            why_relevant=item.get("why_relevant", ""),
        ))
    return normalized


def items_to_dicts(items: List) -> List[Dict[str, Any]]:
    """Convert schema items to dicts for JSON serialization."""
    return [item.to_dict() for item in items]
