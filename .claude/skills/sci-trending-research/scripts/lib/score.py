"""Popularity-aware scoring for last30days skill.

Adapted from https://github.com/Ronnie-Nutrition/last30days-skill
"""

import math
from typing import List, Optional, Union

from . import dates, schema

WEIGHT_RELEVANCE = 0.45
WEIGHT_RECENCY = 0.25
WEIGHT_ENGAGEMENT = 0.30

WEBSEARCH_WEIGHT_RELEVANCE = 0.55
WEBSEARCH_WEIGHT_RECENCY = 0.45
WEBSEARCH_SOURCE_PENALTY = 15
WEBSEARCH_VERIFIED_BONUS = 10
WEBSEARCH_NO_DATE_PENALTY = 20

DEFAULT_ENGAGEMENT = 35
UNKNOWN_ENGAGEMENT_PENALTY = 10


def log1p_safe(x: Optional[int]) -> float:
    if x is None or x < 0:
        return 0.0
    return math.log1p(x)


def compute_reddit_engagement_raw(engagement: Optional[schema.Engagement]) -> Optional[float]:
    if engagement is None:
        return None
    if engagement.score is None and engagement.num_comments is None:
        return None
    score = log1p_safe(engagement.score)
    comments = log1p_safe(engagement.num_comments)
    ratio = (engagement.upvote_ratio or 0.5) * 10
    return 0.55 * score + 0.40 * comments + 0.05 * ratio


def compute_x_engagement_raw(engagement: Optional[schema.Engagement]) -> Optional[float]:
    if engagement is None:
        return None
    if engagement.likes is None and engagement.reposts is None:
        return None
    likes = log1p_safe(engagement.likes)
    reposts = log1p_safe(engagement.reposts)
    replies = log1p_safe(engagement.replies)
    quotes = log1p_safe(engagement.quotes)
    return 0.55 * likes + 0.25 * reposts + 0.15 * replies + 0.05 * quotes


def normalize_to_100(values: List[float], default: float = 50) -> List[float]:
    valid = [v for v in values if v is not None]
    if not valid:
        return [default if v is None else 50 for v in values]
    min_val = min(valid)
    max_val = max(valid)
    range_val = max_val - min_val
    if range_val == 0:
        return [50 if v is None else 50 for v in values]
    result = []
    for v in values:
        if v is None:
            result.append(None)
        else:
            normalized = ((v - min_val) / range_val) * 100
            result.append(normalized)
    return result


def score_reddit_items(items: List[schema.RedditItem]) -> List[schema.RedditItem]:
    if not items:
        return items
    eng_raw = [compute_reddit_engagement_raw(item.engagement) for item in items]
    eng_normalized = normalize_to_100(eng_raw)
    for i, item in enumerate(items):
        rel_score = int(item.relevance * 100)
        rec_score = dates.recency_score(item.date)
        eng_score = int(eng_normalized[i]) if eng_normalized[i] is not None else DEFAULT_ENGAGEMENT
        item.subs = schema.SubScores(relevance=rel_score, recency=rec_score, engagement=eng_score)
        overall = WEIGHT_RELEVANCE * rel_score + WEIGHT_RECENCY * rec_score + WEIGHT_ENGAGEMENT * eng_score
        if eng_raw[i] is None:
            overall -= UNKNOWN_ENGAGEMENT_PENALTY
        if item.date_confidence == "low":
            overall -= 10
        elif item.date_confidence == "med":
            overall -= 5
        item.score = max(0, min(100, int(overall)))
    return items


def score_x_items(items: List[schema.XItem]) -> List[schema.XItem]:
    if not items:
        return items
    eng_raw = [compute_x_engagement_raw(item.engagement) for item in items]
    eng_normalized = normalize_to_100(eng_raw)
    for i, item in enumerate(items):
        rel_score = int(item.relevance * 100)
        rec_score = dates.recency_score(item.date)
        eng_score = int(eng_normalized[i]) if eng_normalized[i] is not None else DEFAULT_ENGAGEMENT
        item.subs = schema.SubScores(relevance=rel_score, recency=rec_score, engagement=eng_score)
        overall = WEIGHT_RELEVANCE * rel_score + WEIGHT_RECENCY * rec_score + WEIGHT_ENGAGEMENT * eng_score
        if eng_raw[i] is None:
            overall -= UNKNOWN_ENGAGEMENT_PENALTY
        if item.date_confidence == "low":
            overall -= 10
        elif item.date_confidence == "med":
            overall -= 5
        item.score = max(0, min(100, int(overall)))
    return items


def score_websearch_items(items: List[schema.WebSearchItem]) -> List[schema.WebSearchItem]:
    if not items:
        return items
    for item in items:
        rel_score = int(item.relevance * 100)
        rec_score = dates.recency_score(item.date)
        item.subs = schema.SubScores(relevance=rel_score, recency=rec_score, engagement=0)
        overall = WEBSEARCH_WEIGHT_RELEVANCE * rel_score + WEBSEARCH_WEIGHT_RECENCY * rec_score
        overall -= WEBSEARCH_SOURCE_PENALTY
        if item.date_confidence == "high":
            overall += WEBSEARCH_VERIFIED_BONUS
        elif item.date_confidence == "low":
            overall -= WEBSEARCH_NO_DATE_PENALTY
        item.score = max(0, min(100, int(overall)))
    return items


def sort_items(items: List[Union[schema.RedditItem, schema.XItem, schema.WebSearchItem]]) -> List:
    def sort_key(item):
        score = -item.score
        date = item.date or "0000-00-00"
        date_key = -int(date.replace("-", ""))
        if isinstance(item, schema.RedditItem):
            source_priority = 0
        elif isinstance(item, schema.XItem):
            source_priority = 1
        else:
            source_priority = 2
        text = getattr(item, "title", "") or getattr(item, "text", "")
        return (score, date_key, source_priority, text)
    return sorted(items, key=sort_key)
